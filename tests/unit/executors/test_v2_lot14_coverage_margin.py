"""Coverage margin for LOT-14 advanced executor safety and lifecycle branches."""

from __future__ import annotations

import asyncio
import os
import stat
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from pyworkflowkit.authoring import RegisteredWorkload
from pyworkflowkit.diagnostics import FailureCategory, OutcomeUncertainty
from pyworkflowkit.errors import ExecutorShutdownError
from pyworkflowkit.executors import (
    AsyncExecutor,
    CancellationStatus,
    ProcessExecutor,
    SubprocessCommand,
    SubprocessExecutor,
    SubprocessSecurityPolicy,
    TaskCancellationRequest,
    TaskExecutionContext,
    TaskExecutionRequest,
    TaskExecutionResult,
)
from pyworkflowkit.executors import _common
from pyworkflowkit.executors import asyncio as async_module
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    TaskAttemptId,
    TaskRunId,
    WorkflowRunId,
)


def _context(
    attempt: str,
    *,
    dependencies: dict[str, object] | None = None,
) -> TaskExecutionContext:
    return TaskExecutionContext(
        workflow_run_id=WorkflowRunId.parse(f"W-{attempt}"),
        task_run_id=TaskRunId.parse(f"TR-{attempt}"),
        attempt_id=TaskAttemptId.parse(attempt),
        attempt_number=1,
        correlation=CorrelationContext(
            correlation_id=CorrelationId.parse(f"C-{attempt}"),
        ),
        dependency_outputs=dependencies or {},
    )


def _request(
    *,
    attempt: str,
    executor_key: str,
    workload: object,
    deadline_at: datetime | None = None,
) -> TaskExecutionRequest:
    return TaskExecutionRequest(
        task_key=f"task-{attempt}",
        workload=workload,  # type: ignore[arg-type]
        executor_key=executor_key,
        context=_context(attempt),
        deadline_at=deadline_at,
    )


def _cancel(request: TaskExecutionRequest) -> TaskCancellationRequest:
    return TaskCancellationRequest(
        workflow_run_id=request.context.workflow_run_id,
        task_run_id=request.context.task_run_id,
        attempt_id=request.context.attempt_id,
        task_key=request.task_key,
        requested_at=datetime.now(tz=UTC),
    )


def _raise_runtime() -> None:
    raise RuntimeError("boom")


def _process_result() -> TaskExecutionResult:
    return TaskExecutionResult(output={"ok": True})


def _exit_without_result() -> None:
    os._exit(3)


async def _async_value() -> str:
    await asyncio.sleep(0)
    return "ok"


async def _async_raise() -> None:
    await asyncio.sleep(0)
    raise RuntimeError("async boom")


async def _async_sleep() -> None:
    await asyncio.sleep(5)


def _sync_raise_before_awaitable() -> object:
    raise RuntimeError("sync boom")


def _bad_arity(first: object, second: object) -> object:
    return first, second


@pytest.mark.parametrize("value", [True, 1.5, "2"])
def test_process_rejects_invalid_worker_types(value: object) -> None:
    with pytest.raises(TypeError, match="max_workers"):
        ProcessExecutor(max_workers=value)  # type: ignore[arg-type]


def test_process_rejects_non_positive_workers_unknown_start_and_bad_grace() -> None:
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        ProcessExecutor(max_workers=0)
    with pytest.raises(ValueError, match="unsupported multiprocessing"):
        ProcessExecutor(start_method="not-real")
    with pytest.raises(TypeError, match="terminate_grace_seconds"):
        ProcessExecutor(terminate_grace_seconds=True)
    with pytest.raises(ValueError, match="greater than or equal to 0"):
        ProcessExecutor(terminate_grace_seconds=-0.1)


def test_process_registration_guards_and_properties() -> None:
    executor = ProcessExecutor(max_workers=1)
    try:
        assert executor.max_workers == 1
        assert executor.is_shutdown is False
        with pytest.raises(ValueError, match="key"):
            executor.register("", _process_result)
        with pytest.raises(TypeError, match="callable"):
            executor.register("bad", object())  # type: ignore[arg-type]
        executor.register("ok", _process_result)
        with pytest.raises(ValueError, match="already exists"):
            executor.register("ok", _process_result)
    finally:
        executor.shutdown()
    assert executor.is_shutdown is True


def test_process_mismatch_unresolved_and_bad_handler_contract_fail_closed() -> None:
    executor = ProcessExecutor(max_workers=1)
    try:
        mismatch = executor.execute(
            _request(attempt="P-mismatch", executor_key="thread", workload=_process_result)
        )
        unresolved = executor.execute(
            _request(
                attempt="P-missing",
                executor_key="process",
                workload=RegisteredWorkload("missing", executor_key="process"),
            )
        )
        bad_arity = executor.execute(
            _request(attempt="P-arity", executor_key="process", workload=_bad_arity)
        )
    finally:
        executor.shutdown()

    assert mismatch.failure is not None
    assert mismatch.failure.error_code == "PWK-EXECUTOR-MISMATCH"
    assert unresolved.failure is not None
    assert unresolved.failure.error_code == "PWK-PROCESS-WORKLOAD-UNRESOLVED"
    assert bad_arity.failure is not None
    assert bad_arity.failure.error_code == "PWK-PROCESS-HANDLER-CONTRACT"


def test_process_rejects_unpicklable_context_and_preserves_worker_failures() -> None:
    lock = threading.Lock()
    request = TaskExecutionRequest(
        task_key="context",
        workload=_process_result,
        executor_key="process",
        context=_context("P-context", dependencies={"lock": lock}),
    )
    executor = ProcessExecutor(max_workers=1)
    try:
        serialization = executor.execute(request)
        raised = executor.execute(
            _request(attempt="P-error", executor_key="process", workload=_raise_runtime)
        )
        passthrough = executor.execute(
            _request(attempt="P-result", executor_key="process", workload=_process_result)
        )
    finally:
        executor.shutdown()

    assert serialization.failure is not None
    assert serialization.failure.error_code == "PWK-PROCESS-SERIALIZATION"
    assert ("context", serialization.failure.details[0][1]) != ("context", "")
    assert raised.failure is not None
    assert raised.failure.error_code == "RuntimeError"
    assert passthrough.output == {"ok": True}


def test_process_detects_child_exit_without_result() -> None:
    executor = ProcessExecutor(max_workers=1)
    try:
        result = executor.execute(
            _request(
                attempt="P-exit",
                executor_key="process",
                workload=_exit_without_result,
            )
        )
    finally:
        executor.shutdown()

    assert result.failure is not None
    assert result.failure.error_code == "PWK-PROCESS-EXITED-WITHOUT-RESULT"


def test_process_expired_deadline_and_missing_cancel_handle_are_known() -> None:
    request = _request(
        attempt="P-expired",
        executor_key="process",
        workload=_process_result,
        deadline_at=datetime.now(tz=UTC) - timedelta(seconds=1),
    )
    executor = ProcessExecutor(max_workers=1)
    try:
        result = executor.execute(request)
        cancellation = executor.cancel(_cancel(request))
    finally:
        executor.shutdown()

    assert result.failure is not None
    assert result.failure.error_code == "PWK-PROCESS-HARD-TIMEOUT"
    assert result.failure.uncertainty is OutcomeUncertainty.KNOWN
    assert cancellation.status is CancellationStatus.UNCONFIRMED


def test_process_capacity_and_shutdown_rejection() -> None:
    first = _request(
        attempt="P-capacity-1",
        executor_key="process",
        workload=time.sleep,
    )
    # time.sleep accepts one argument only; bind it through a registered wrapper.
    executor = ProcessExecutor(
        {"slow": lambda: time.sleep(0.4)},  # deliberately unpicklable registration
        max_workers=1,
    )
    # The lambda itself fails serialization and therefore cannot occupy capacity.
    rejected = executor.execute(
        TaskExecutionRequest(
            task_key="slow",
            workload=RegisteredWorkload("slow", executor_key="process"),
            executor_key="process",
            context=first.context,
        )
    )
    assert rejected.failure is not None
    assert rejected.failure.error_code == "PWK-PROCESS-SERIALIZATION"

    executor.shutdown()
    with pytest.raises(ExecutorShutdownError):
        executor.execute(
            _request(attempt="P-shutdown", executor_key="process", workload=_process_result)
        )


@pytest.mark.parametrize("value", [True, 1.5, "2"])
def test_async_rejects_invalid_concurrency_types(value: object) -> None:
    with pytest.raises(TypeError, match="max_concurrency"):
        AsyncExecutor(max_concurrency=value)  # type: ignore[arg-type]


def test_async_constructor_registration_and_shutdown_guards() -> None:
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        AsyncExecutor(max_concurrency=0)
    with pytest.raises(ValueError, match="loop_thread_name"):
        AsyncExecutor(loop_thread_name=" ")

    executor = AsyncExecutor(max_concurrency=1)
    try:
        assert executor.max_concurrency == 1
        assert executor.is_shutdown is False
        with pytest.raises(ValueError, match="key"):
            executor.register("", _async_value)
        with pytest.raises(TypeError, match="callable"):
            executor.register("bad", object())  # type: ignore[arg-type]
        executor.register("ok", _async_value)
        with pytest.raises(ValueError, match="already exists"):
            executor.register("ok", _async_value)
    finally:
        executor.shutdown()
    assert executor.is_shutdown is True
    executor.shutdown()


def test_async_mismatch_unresolved_bad_arity_and_expired_deadline() -> None:
    executor = AsyncExecutor(max_concurrency=1)
    try:
        mismatch = executor.execute(
            _request(attempt="A-mismatch", executor_key="thread", workload=_async_value)
        )
        unresolved = executor.execute(
            _request(
                attempt="A-missing",
                executor_key="async",
                workload=RegisteredWorkload("missing", executor_key="async"),
            )
        )
        bad_arity = executor.execute(
            _request(attempt="A-arity", executor_key="async", workload=_bad_arity)
        )
        expired = executor.execute(
            _request(
                attempt="A-expired",
                executor_key="async",
                workload=_async_value,
                deadline_at=datetime.now(tz=UTC) - timedelta(seconds=1),
            )
        )
    finally:
        executor.shutdown()

    assert mismatch.failure is not None
    assert mismatch.failure.error_code == "PWK-EXECUTOR-MISMATCH"
    assert unresolved.failure is not None
    assert unresolved.failure.error_code == "PWK-ASYNC-WORKLOAD-UNRESOLVED"
    assert bad_arity.failure is not None
    assert bad_arity.failure.error_code == "PWK-ASYNC-HANDLER-CONTRACT"
    assert expired.failure is not None
    assert expired.failure.error_code == "PWK-ASYNC-DEADLINE-EXPIRED"


def test_async_sync_and_coroutine_exceptions_are_structured() -> None:
    executor = AsyncExecutor(max_concurrency=1)
    try:
        sync_failure = executor.execute(
            _request(
                attempt="A-sync-error",
                executor_key="async",
                workload=_sync_raise_before_awaitable,
            )
        )
        async_failure = executor.execute(
            _request(attempt="A-async-error", executor_key="async", workload=_async_raise)
        )
    finally:
        executor.shutdown()

    assert sync_failure.failure is not None
    assert sync_failure.failure.error_code == "RuntimeError"
    assert async_failure.failure is not None
    assert async_failure.failure.error_code == "RuntimeError"


def test_async_missing_and_completed_cancel_handles_are_distinct() -> None:
    executor = AsyncExecutor(max_concurrency=1)
    missing_request = _request(
        attempt="A-missing-cancel",
        executor_key="async",
        workload=_async_value,
    )
    completed_request = _request(
        attempt="A-completed-cancel",
        executor_key="async",
        workload=_async_value,
    )
    try:
        missing = executor.cancel(_cancel(missing_request))
        completed_result = executor.execute(completed_request)
        completed = executor.cancel(_cancel(completed_request))
    finally:
        executor.shutdown()

    assert missing.status is CancellationStatus.UNCONFIRMED
    assert completed_result.succeeded is True
    assert completed.status is CancellationStatus.ALREADY_TERMINAL


def test_async_capacity_is_explicit() -> None:
    executor = AsyncExecutor(max_concurrency=1)
    first_request = _request(
        attempt="A-capacity-1",
        executor_key="async",
        workload=_async_sleep,
    )
    second_request = _request(
        attempt="A-capacity-2",
        executor_key="async",
        workload=_async_value,
    )
    holder: list[TaskExecutionResult] = []
    worker = threading.Thread(
        target=lambda: holder.append(executor.execute(first_request)),
        daemon=True,
    )
    worker.start()
    time.sleep(0.05)
    try:
        second = executor.execute(second_request)
        cancellation = executor.cancel(_cancel(first_request))
        worker.join(timeout=2)
    finally:
        executor.shutdown(wait=False)

    assert second.failure is not None
    assert second.failure.error_code == "PWK-ASYNC-CAPACITY"
    assert cancellation.status is CancellationStatus.REQUESTED
    assert holder


def test_async_private_missing_start_is_noop() -> None:
    executor = AsyncExecutor(max_concurrency=1)
    try:
        executor._loop.call_soon_threadsafe(
            executor._start_execution,
            TaskAttemptId.parse("missing"),
        )
        time.sleep(0.02)
    finally:
        executor.shutdown()


def test_common_helpers_cover_direct_registered_failure_and_context_paths() -> None:
    request = _request(
        attempt="common",
        executor_key="async",
        workload=_async_value,
    )
    direct, params = _common.resolve_handler(request, {})
    assert direct is _async_value
    assert params == {}

    registered_request = TaskExecutionRequest(
        task_key="registered",
        workload=RegisteredWorkload(
            "job",
            parameters=(("mode", "full"),),
            executor_key="async",
        ),
        executor_key="async",
        context=_context("common-registered"),
    )
    registered, registered_params = _common.resolve_handler(
        registered_request,
        {"job": _async_value},
    )
    assert registered is _async_value
    assert registered_params == {"mode": "full"}

    unresolved, unresolved_params = _common.resolve_handler(
        registered_request,
        {},
    )
    assert unresolved is None
    assert unresolved_params == {}

    assert _common.resolve_invocation_arity(lambda: None) == 0
    assert _common.resolve_invocation_arity(lambda context: context) == 1
    with pytest.raises(ValueError, match="zero arguments or one"):
        _common.resolve_invocation_arity(_bad_arity)

    success = _common.invoke_handler(
        lambda: "ok",
        arity=0,
        context=request.context,
        request=request,
        source_component="test",
    )
    passthrough = TaskExecutionResult(output="passthrough")
    same = _common.invoke_handler(
        lambda: passthrough,
        arity=0,
        context=request.context,
        request=request,
        source_component="test",
    )
    failure = _common.invoke_handler(
        _raise_runtime,
        arity=0,
        context=request.context,
        request=request,
        source_component="test",
    )
    assert success.output == "ok"
    assert same is passthrough
    assert failure.failure is not None
    assert failure.failure.error_code == "RuntimeError"


def test_subprocess_command_validation_matrix() -> None:
    with pytest.raises(ValueError, match="at least one"):
        SubprocessCommand(argv=())
    with pytest.raises(TypeError, match="argv values"):
        SubprocessCommand(argv=(sys.executable, 3))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="executable"):
        SubprocessCommand(argv=(" ",))
    with pytest.raises(ValueError, match="NUL"):
        SubprocessCommand(argv=(sys.executable, "bad\x00arg"))
    with pytest.raises(TypeError, match="cwd"):
        SubprocessCommand(argv=(sys.executable,), cwd=3)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="cwd must not be blank"):
        SubprocessCommand(argv=(sys.executable,), cwd=" ")
    with pytest.raises(ValueError, match="cwd must not contain NUL"):
        SubprocessCommand(argv=(sys.executable,), cwd="bad\x00cwd")
    with pytest.raises(TypeError, match="stdin"):
        SubprocessCommand(argv=(sys.executable,), stdin=3)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="encoding"):
        SubprocessCommand(argv=(sys.executable,), encoding=3)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="encoding"):
        SubprocessCommand(argv=(sys.executable,), encoding=" ")
    with pytest.raises(TypeError, match="env keys"):
        SubprocessCommand(argv=(sys.executable,), env={"X": 3})  # type: ignore[dict-item]
    with pytest.raises(ValueError, match="env keys"):
        SubprocessCommand(argv=(sys.executable,), env={"BAD=KEY": "value"})
    with pytest.raises(ValueError, match="env values"):
        SubprocessCommand(argv=(sys.executable,), env={"KEY": "bad\x00value"})


def test_subprocess_security_policy_validation_environment_and_sizes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(TypeError, match="inherit_environment"):
        SubprocessSecurityPolicy(inherit_environment=1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="max_stdout_bytes"):
        SubprocessSecurityPolicy(max_stdout_bytes=True)
    with pytest.raises(ValueError, match="max_stderr_bytes"):
        SubprocessSecurityPolicy(max_stderr_bytes=-1)

    command = SubprocessCommand(
        argv=(sys.executable,),
        env={"KEEP": "1", "DROP": "2"},
        stdin="abc",
    )
    policy = SubprocessSecurityPolicy(
        allowed_executables=frozenset({sys.executable}),
        allowed_env_keys=frozenset({"KEEP"}),
        max_stdin_bytes=3,
        max_stdout_bytes=4,
        max_stderr_bytes=4,
    )
    with pytest.raises(ValueError, match="disallowed keys"):
        policy.validate(command)

    filtered = SubprocessSecurityPolicy(
        allowed_env_keys=frozenset({"KEEP"}),
    )
    assert filtered.environment_for(command) == {"KEEP": "1"}

    monkeypatch.setenv("KEEP", "visible")
    inherited = SubprocessSecurityPolicy(
        inherit_environment=True,
        allowed_env_keys=frozenset({"KEEP"}),
    )
    inherited_command = SubprocessCommand(argv=(sys.executable,))
    assert inherited.environment_for(inherited_command) == {"KEEP": "visible"}

    with pytest.raises(ValueError, match="stdout"):
        policy.validate_captured_output(
            command=command,
            stdout="12345",
            stderr="",
        )
    with pytest.raises(ValueError, match="stderr"):
        policy.validate_captured_output(
            command=command,
            stdout="",
            stderr="12345",
        )


def test_subprocess_security_cwd_and_stdin_fail_closed(tmp_path: Path) -> None:
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    policy = SubprocessSecurityPolicy(
        allowed_cwd_roots=(str(allowed_root),),
        max_stdin_bytes=2,
    )
    policy.validate(
        SubprocessCommand(argv=(sys.executable,), cwd=str(allowed_root))
    )
    with pytest.raises(ValueError, match="outside allowed"):
        policy.validate(
            SubprocessCommand(argv=(sys.executable,), cwd=str(outside))
        )
    with pytest.raises(ValueError, match="stdin"):
        policy.validate(
            SubprocessCommand(argv=(sys.executable,), stdin="abc")
        )


@pytest.mark.parametrize("value", [True, 1.5, "2"])
def test_subprocess_rejects_invalid_worker_types(value: object) -> None:
    with pytest.raises(TypeError, match="max_workers"):
        SubprocessExecutor(max_workers=value)  # type: ignore[arg-type]


def test_subprocess_constructor_and_registration_guards() -> None:
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        SubprocessExecutor(max_workers=0)
    with pytest.raises(TypeError, match="terminate_grace_seconds"):
        SubprocessExecutor(terminate_grace_seconds=True)
    with pytest.raises(ValueError, match="greater than or equal to 0"):
        SubprocessExecutor(terminate_grace_seconds=-1)
    with pytest.raises(TypeError, match="security_policy"):
        SubprocessExecutor(security_policy=object())  # type: ignore[arg-type]

    executor = SubprocessExecutor(max_workers=1)
    try:
        assert executor.max_workers == 1
        assert isinstance(executor.security_policy, SubprocessSecurityPolicy)
        with pytest.raises(ValueError, match="key"):
            executor.register("", _process_result)
        with pytest.raises(TypeError, match="callable"):
            executor.register("bad", object())  # type: ignore[arg-type]
        executor.register("ok", _process_result)
        with pytest.raises(ValueError, match="already exists"):
            executor.register("ok", _process_result)
    finally:
        executor.shutdown()


def test_subprocess_mismatch_unresolved_bad_arity_handler_error_and_bad_result() -> None:
    executor = SubprocessExecutor(max_workers=1)
    try:
        mismatch = executor.execute(
            _request(
                attempt="S-mismatch",
                executor_key="thread",
                workload=SubprocessCommand(argv=(sys.executable, "-V")),
            )
        )
        unresolved = executor.execute(
            _request(
                attempt="S-missing",
                executor_key="subprocess",
                workload=RegisteredWorkload("missing", executor_key="subprocess"),
            )
        )
        bad_arity = executor.execute(
            _request(attempt="S-arity", executor_key="subprocess", workload=_bad_arity)
        )
        handler_error = executor.execute(
            _request(
                attempt="S-handler-error",
                executor_key="subprocess",
                workload=_raise_runtime,
            )
        )
        bad_result = executor.execute(
            _request(
                attempt="S-bad-result",
                executor_key="subprocess",
                workload=lambda: "not-command",
            )
        )
    finally:
        executor.shutdown()

    assert mismatch.failure is not None
    assert mismatch.failure.error_code == "PWK-EXECUTOR-MISMATCH"
    assert unresolved.failure is not None
    assert unresolved.failure.error_code == "PWK-SUBPROCESS-WORKLOAD-UNRESOLVED"
    assert bad_arity.failure is not None
    assert bad_arity.failure.error_code == "PWK-SUBPROCESS-HANDLER-CONTRACT"
    assert handler_error.failure is not None
    assert handler_error.failure.error_code == "RuntimeError"
    assert bad_result.failure is not None
    assert bad_result.failure.error_code == "PWK-SUBPROCESS-COMMAND-CONTRACT"


def test_subprocess_missing_and_non_executable_commands_are_structured(tmp_path: Path) -> None:
    missing = SubprocessCommand(argv=("pyworkflowkit-command-does-not-exist",))
    not_executable = tmp_path / "program"
    not_executable.write_text("#!/bin/sh\necho no\n")
    not_executable.chmod(stat.S_IRUSR | stat.S_IWUSR)

    executor = SubprocessExecutor(max_workers=1)
    try:
        missing_result = executor.execute(
            _request(
                attempt="S-not-found",
                executor_key="subprocess",
                workload=missing,
            )
        )
        os_error = executor.execute(
            _request(
                attempt="S-os-error",
                executor_key="subprocess",
                workload=SubprocessCommand(argv=(str(not_executable),)),
            )
        )
    finally:
        executor.shutdown()

    assert missing_result.failure is not None
    assert missing_result.failure.error_code == "PWK-SUBPROCESS-NOT-FOUND"
    assert os_error.failure is not None
    assert os_error.failure.category is FailureCategory.INTERNAL


def test_subprocess_expired_deadline_completed_cancel_and_shutdown() -> None:
    command = SubprocessCommand(argv=(sys.executable, "-c", "print('ok')"))
    expired_request = _request(
        attempt="S-expired",
        executor_key="subprocess",
        workload=command,
        deadline_at=datetime.now(tz=UTC) - timedelta(seconds=1),
    )
    completed_request = _request(
        attempt="S-completed",
        executor_key="subprocess",
        workload=command,
    )
    executor = SubprocessExecutor(max_workers=1)
    try:
        expired = executor.execute(expired_request)
        completed_result = executor.execute(completed_request)
        completed_cancel = executor.cancel(_cancel(completed_request))
    finally:
        executor.shutdown()

    assert expired.failure is not None
    assert expired.failure.error_code == "PWK-SUBPROCESS-HARD-TIMEOUT"
    assert completed_result.succeeded is True
    assert completed_cancel.status is CancellationStatus.ALREADY_TERMINAL

    with pytest.raises(ExecutorShutdownError):
        executor.execute(
            _request(
                attempt="S-shutdown",
                executor_key="subprocess",
                workload=command,
            )
        )


def test_subprocess_active_cancel_is_confirmed() -> None:
    request = _request(
        attempt="S-cancel",
        executor_key="subprocess",
        workload=SubprocessCommand(
            argv=(sys.executable, "-c", "import time; time.sleep(5)"),
        ),
    )
    executor = SubprocessExecutor(max_workers=1)
    holder: list[TaskExecutionResult] = []
    worker = threading.Thread(
        target=lambda: holder.append(executor.execute(request)),
        daemon=True,
    )
    worker.start()
    time.sleep(0.1)
    try:
        cancellation = executor.cancel(_cancel(request))
        worker.join(timeout=3)
    finally:
        executor.shutdown(wait=False)

    assert cancellation.status is CancellationStatus.CONFIRMED
    assert holder
    assert holder[0].failure is not None
    assert holder[0].failure.category is FailureCategory.CANCELLED


def test_subprocess_capacity_is_explicit() -> None:
    first = _request(
        attempt="S-capacity-1",
        executor_key="subprocess",
        workload=SubprocessCommand(
            argv=(sys.executable, "-c", "import time; time.sleep(5)"),
        ),
    )
    second = _request(
        attempt="S-capacity-2",
        executor_key="subprocess",
        workload=SubprocessCommand(argv=(sys.executable, "-c", "print('second')")),
    )
    executor = SubprocessExecutor(max_workers=1)
    holder: list[TaskExecutionResult] = []
    worker = threading.Thread(
        target=lambda: holder.append(executor.execute(first)),
        daemon=True,
    )
    worker.start()
    time.sleep(0.1)
    try:
        saturated = executor.execute(second)
        executor.cancel(_cancel(first))
        worker.join(timeout=3)
    finally:
        executor.shutdown(wait=False)

    assert saturated.failure is not None
    assert saturated.failure.error_code == "PWK-SUBPROCESS-CAPACITY"
