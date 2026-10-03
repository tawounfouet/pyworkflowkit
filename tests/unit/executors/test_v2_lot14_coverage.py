"""Coverage-focused behavioral proofs for LOT-14 advanced executors."""

from __future__ import annotations

import asyncio
import os
import sys
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest

from pyworkflowkit.authoring import RegisteredWorkload
from pyworkflowkit.diagnostics import FailureCategory
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
from pyworkflowkit.executors import process as process_module
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    TaskAttemptId,
    TaskRunId,
    WorkflowRunId,
)


def _context(
    *,
    attempt_id: str = "TA-coverage",
    dependency_outputs: dict[str, object] | None = None,
) -> TaskExecutionContext:
    return TaskExecutionContext(
        workflow_run_id=WorkflowRunId.parse("W-coverage"),
        task_run_id=TaskRunId.parse("TR-coverage"),
        attempt_id=TaskAttemptId.parse(attempt_id),
        attempt_number=1,
        correlation=CorrelationContext(
            correlation_id=CorrelationId.parse("C-coverage"),
        ),
        dependency_outputs=dependency_outputs or {},
    )


def _request(
    workload: object,
    executor_key: str,
    *,
    attempt_id: str = "TA-coverage",
    deadline_at: datetime | None = None,
    dependency_outputs: dict[str, object] | None = None,
) -> TaskExecutionRequest:
    return TaskExecutionRequest(
        task_key="coverage",
        workload=workload,  # type: ignore[arg-type]
        executor_key=executor_key,
        context=_context(
            attempt_id=attempt_id,
            dependency_outputs=dependency_outputs,
        ),
        deadline_at=deadline_at,
    )


def _value() -> str:
    return "ok"


def _context_value(context: TaskExecutionContext) -> str:
    return str(context.dependency_outputs["value"])


def _worker_boom() -> None:
    raise RuntimeError("worker-boom")


def _worker_lock() -> object:
    return threading.Lock()


def _two_args(first: object, second: object) -> None:
    del first, second


async def _async_value() -> str:
    await asyncio.sleep(0)
    return "async-ok"


async def _async_context(context: TaskExecutionContext) -> str:
    await asyncio.sleep(0)
    return str(context.dependency_outputs["value"])


async def _async_boom() -> None:
    await asyncio.sleep(0)
    raise RuntimeError("async-boom")


async def _async_result() -> TaskExecutionResult:
    await asyncio.sleep(0)
    return TaskExecutionResult(output="structured")


async def _async_slow() -> str:
    await asyncio.sleep(1)
    return "late"


def _command_factory(context: TaskExecutionContext) -> SubprocessCommand:
    return SubprocessCommand(
        argv=(
            sys.executable,
            "-c",
            "import sys; print(sys.argv[1])",
            str(context.dependency_outputs["value"]),
        )
    )


def _command_boom() -> SubprocessCommand:
    raise RuntimeError("command-boom")


def _not_a_command() -> str:
    return "wrong"


class _CapturingConnection:
    def __init__(self) -> None:
        self.messages: list[object] = []
        self.closed = False

    def send(self, value: object) -> None:
        self.messages.append(value)

    def close(self) -> None:
        self.closed = True


def _wait_for(predicate: object, *, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if callable(predicate) and predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition was not reached before timeout")


def test_common_helpers_cover_registered_callable_result_and_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registered = RegisteredWorkload(
        "jobs.coverage",
        parameters=(("mode", "full"),),
        executor_key="process",
    )
    request = _request(registered, "process")
    handler, parameters = _common.resolve_handler(
        request,
        {"jobs.coverage": _value},
    )
    assert handler is _value
    assert parameters == {"mode": "full"}

    callable_request = _request(_value, "process")
    callable_handler, callable_parameters = _common.resolve_handler(callable_request, {})
    assert callable_handler is _value
    assert callable_parameters == {}

    assert _common.resolve_invocation_arity(_value) == 0
    assert _common.resolve_invocation_arity(_context_value) == 1
    with pytest.raises(ValueError, match="zero arguments"):
        _common.resolve_invocation_arity(_two_args)

    monkeypatch.setattr(
        _common,
        "signature",
        lambda _handler: (_ for _ in ()).throw(ValueError("no signature")),
    )
    with pytest.raises(ValueError, match="cannot be inspected"):
        _common.resolve_invocation_arity(_value)


def test_common_invoke_handler_normalizes_outputs_results_and_exceptions() -> None:
    request = _request(_value, "process")
    context = request.context

    raw = _common.invoke_handler(
        _value,
        arity=0,
        context=context,
        request=request,
        source_component="coverage",
    )
    assert raw.output == "ok"

    structured = TaskExecutionResult(output="structured")
    same = _common.invoke_handler(
        lambda: structured,
        arity=0,
        context=context,
        request=request,
        source_component="coverage",
    )
    assert same is structured

    failed = _common.invoke_handler(
        _worker_boom,
        arity=0,
        context=context,
        request=request,
        source_component="coverage",
    )
    assert failed.failure is not None
    assert failed.failure.error_code == "RuntimeError"

    bound = _common.bound_context(request, {"mode": "full"})
    assert bound.workload_parameters == {"mode": "full"}


@pytest.mark.parametrize(
    ("kwargs", "error_type"),
    [
        ({"max_workers": True}, TypeError),
        ({"max_workers": 0}, ValueError),
        ({"start_method": "not-a-start-method"}, ValueError),
        ({"terminate_grace_seconds": True}, TypeError),
        ({"terminate_grace_seconds": -0.1}, ValueError),
    ],
)
def test_process_constructor_guards(kwargs: dict[str, object], error_type: type[Exception]) -> None:
    with pytest.raises(error_type):
        ProcessExecutor(**kwargs)  # type: ignore[arg-type]


def test_process_registration_and_preflight_guards() -> None:
    executor = ProcessExecutor(max_workers=1)
    try:
        with pytest.raises(ValueError, match="must not be empty"):
            executor.register("", _value)
        with pytest.raises(TypeError, match="callable"):
            executor.register("bad", object())  # type: ignore[arg-type]

        executor.register("job", _value)
        with pytest.raises(ValueError, match="already exists"):
            executor.register("job", _value)

        wrong = executor.execute(_request(_value, "inline"))
        assert wrong.failure is not None
        assert wrong.failure.category is FailureCategory.CAPABILITY

        unresolved = executor.execute(
            _request(
                RegisteredWorkload("missing", executor_key="process"),
                "process",
            )
        )
        assert unresolved.failure is not None
        assert unresolved.failure.error_code == "PWK-PROCESS-WORKLOAD-UNRESOLVED"

        invalid = executor.execute(_request(_two_args, "process"))
        assert invalid.failure is not None
        assert invalid.failure.error_code == "PWK-PROCESS-HANDLER-CONTRACT"

        unpicklable_context = executor.execute(
            _request(
                _value,
                "process",
                dependency_outputs={"lock": threading.Lock()},
            )
        )
        assert unpicklable_context.failure is not None
        assert unpicklable_context.failure.error_code == "PWK-PROCESS-SERIALIZATION"

        expired = executor.execute(
            _request(
                _value,
                "process",
                deadline_at=datetime.now(tz=UTC) - timedelta(seconds=1),
            )
        )
        assert expired.failure is not None
        assert expired.failure.error_code == "PWK-PROCESS-HARD-TIMEOUT"
    finally:
        executor.shutdown()


def test_process_worker_transport_paths_are_qualified_in_parent_process() -> None:
    request = _request(_value, "process")
    snapshot = process_module._snapshot(request, request.context)

    success = _CapturingConnection()
    process_module._worker_main(
        success,  # type: ignore[arg-type]
        _value,
        0,
        snapshot,
    )
    assert success.closed is True
    assert len(success.messages) == 1
    success_result = success.messages[0]
    assert isinstance(success_result, TaskExecutionResult)
    assert success_result.output == "ok"

    failed = _CapturingConnection()
    process_module._worker_main(
        failed,  # type: ignore[arg-type]
        _worker_boom,
        0,
        snapshot,
    )
    failure_result = failed.messages[0]
    assert isinstance(failure_result, TaskExecutionResult)
    assert failure_result.failure is not None
    assert failure_result.failure.error_code == "RuntimeError"

    nonportable = _CapturingConnection()
    process_module._worker_main(
        nonportable,  # type: ignore[arg-type]
        _worker_lock,
        0,
        snapshot,
    )
    nonportable_result = nonportable.messages[0]
    assert isinstance(nonportable_result, TaskExecutionResult)
    assert nonportable_result.failure is not None
    assert nonportable_result.failure.error_code == "PWK-PROCESS-RESULT-NONPORTABLE"


def test_process_shutdown_and_missing_cancel_guards() -> None:
    executor = ProcessExecutor(max_workers=1)
    missing = executor.cancel(
        TaskCancellationRequest(
            workflow_run_id=WorkflowRunId.parse("W-coverage"),
            task_run_id=TaskRunId.parse("TR-coverage"),
            attempt_id=TaskAttemptId.parse("TA-missing"),
            task_key="missing",
            requested_at=datetime.now(tz=UTC),
        )
    )
    assert missing.status is CancellationStatus.UNCONFIRMED

    executor.shutdown()
    assert executor.is_shutdown is True
    with pytest.raises(ExecutorShutdownError):
        executor.execute(_request(_value, "process"))


@pytest.mark.parametrize(
    ("kwargs", "error_type"),
    [
        ({"max_concurrency": True}, TypeError),
        ({"max_concurrency": 0}, ValueError),
        ({"loop_thread_name": "   "}, ValueError),
    ],
)
def test_async_constructor_guards(kwargs: dict[str, object], error_type: type[Exception]) -> None:
    with pytest.raises(error_type):
        AsyncExecutor(**kwargs)  # type: ignore[arg-type]


def test_async_registration_preflight_and_failure_paths() -> None:
    executor = AsyncExecutor(max_concurrency=2)
    try:
        with pytest.raises(ValueError, match="must not be empty"):
            executor.register("", _async_value)
        with pytest.raises(TypeError, match="callable"):
            executor.register("bad", object())  # type: ignore[arg-type]

        executor.register("job", _async_value)
        with pytest.raises(ValueError, match="already exists"):
            executor.register("job", _async_value)

        wrong = executor.execute(_request(_async_value, "inline"))
        assert wrong.failure is not None
        assert wrong.failure.category is FailureCategory.CAPABILITY

        unresolved = executor.execute(
            _request(
                RegisteredWorkload("missing", executor_key="async"),
                "async",
            )
        )
        assert unresolved.failure is not None
        assert unresolved.failure.error_code == "PWK-ASYNC-WORKLOAD-UNRESOLVED"

        invalid = executor.execute(_request(_two_args, "async"))
        assert invalid.failure is not None
        assert invalid.failure.error_code == "PWK-ASYNC-HANDLER-CONTRACT"

        raised = executor.execute(_request(_async_boom, "async"))
        assert raised.failure is not None
        assert raised.failure.error_code == "RuntimeError"

        context_result = executor.execute(
            _request(
                _async_context,
                "async",
                dependency_outputs={"value": "ctx"},
            )
        )
        assert context_result.output == "ctx"

        structured = executor.execute(_request(_async_result, "async"))
        assert structured.output == "structured"

        expired = executor.execute(
            _request(
                _async_value,
                "async",
                deadline_at=datetime.now(tz=UTC) - timedelta(seconds=1),
            )
        )
        assert expired.failure is not None
        assert expired.failure.error_code == "PWK-ASYNC-DEADLINE-EXPIRED"
    finally:
        executor.shutdown()


def test_async_capacity_completed_cancel_and_shutdown_lifecycle() -> None:
    executor = AsyncExecutor(max_concurrency=1)
    first_request = _request(
        _async_slow,
        "async",
        attempt_id="TA-async-capacity",
    )
    holder: list[TaskExecutionResult] = []
    worker = threading.Thread(
        target=lambda: holder.append(executor.execute(first_request)),
        daemon=True,
    )
    worker.start()

    _wait_for(lambda: bool(executor._active))
    saturated = executor.execute(
        _request(
            _async_value,
            "async",
            attempt_id="TA-async-second",
        )
    )
    assert saturated.failure is not None
    assert saturated.failure.error_code == "PWK-ASYNC-CAPACITY"

    cancellation = executor.cancel(
        TaskCancellationRequest(
            workflow_run_id=first_request.context.workflow_run_id,
            task_run_id=first_request.context.task_run_id,
            attempt_id=first_request.context.attempt_id,
            task_key=first_request.task_key,
            requested_at=datetime.now(tz=UTC),
        )
    )
    assert cancellation.status is CancellationStatus.REQUESTED
    worker.join(timeout=2)
    assert not worker.is_alive()

    completed = executor.cancel(
        TaskCancellationRequest(
            workflow_run_id=first_request.context.workflow_run_id,
            task_run_id=first_request.context.task_run_id,
            attempt_id=first_request.context.attempt_id,
            task_key=first_request.task_key,
            requested_at=datetime.now(tz=UTC),
        )
    )
    assert completed.status is CancellationStatus.ALREADY_TERMINAL

    missing = executor.cancel(
        TaskCancellationRequest(
            workflow_run_id=WorkflowRunId.parse("W-coverage"),
            task_run_id=TaskRunId.parse("TR-coverage"),
            attempt_id=TaskAttemptId.parse("TA-async-missing"),
            task_key="missing",
            requested_at=datetime.now(tz=UTC),
        )
    )
    assert missing.status is CancellationStatus.UNCONFIRMED

    executor.shutdown()
    executor.shutdown()
    assert executor.is_shutdown is True
    with pytest.raises(ExecutorShutdownError):
        executor.execute(
            _request(
                _async_value,
                "async",
                attempt_id="TA-after-shutdown",
            )
        )


@pytest.mark.parametrize(
    "factory",
    [
        lambda: SubprocessCommand(argv=()),
        lambda: SubprocessCommand(argv=(3,)),  # type: ignore[arg-type]
        lambda: SubprocessCommand(argv=(" ",)),
        lambda: SubprocessCommand(argv=("bad\x00argv",)),
        lambda: SubprocessCommand(argv=(sys.executable,), cwd=3),  # type: ignore[arg-type]
        lambda: SubprocessCommand(argv=(sys.executable,), cwd=" "),
        lambda: SubprocessCommand(argv=(sys.executable,), cwd="bad\x00cwd"),
        lambda: SubprocessCommand(argv=(sys.executable,), stdin=3),  # type: ignore[arg-type]
        lambda: SubprocessCommand(argv=(sys.executable,), encoding=3),  # type: ignore[arg-type]
        lambda: SubprocessCommand(argv=(sys.executable,), encoding=" "),
        lambda: SubprocessCommand(
            argv=(sys.executable,),
            env={"KEY": 3},  # type: ignore[dict-item]
        ),
        lambda: SubprocessCommand(argv=(sys.executable,), env={"": "value"}),
        lambda: SubprocessCommand(argv=(sys.executable,), env={"BAD=KEY": "value"}),
        lambda: SubprocessCommand(argv=(sys.executable,), env={"KEY": "bad\x00value"}),
    ],
)
def test_subprocess_command_guards(factory: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        assert callable(factory)
        factory()


@pytest.mark.parametrize(
    ("kwargs", "error_type"),
    [
        ({"max_stdin_bytes": True}, TypeError),
        ({"max_stdout_bytes": -1}, ValueError),
        ({"inherit_environment": 1}, TypeError),
    ],
)
def test_subprocess_security_policy_constructor_guards(
    kwargs: dict[str, object],
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type):
        SubprocessSecurityPolicy(**kwargs)  # type: ignore[arg-type]


def test_subprocess_security_policy_environment_cwd_and_size_guards(
    tmp_path: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pathlib import Path

    root = Path(str(tmp_path))
    allowed = SubprocessSecurityPolicy(
        allowed_cwd_roots=(str(root),),
        allowed_env_keys=frozenset({"VISIBLE"}),
        inherit_environment=True,
        max_stdin_bytes=4,
        max_stdout_bytes=4,
        max_stderr_bytes=4,
    )
    monkeypatch.setenv("VISIBLE", "yes")
    monkeypatch.setenv("HIDDEN", "no")

    command = SubprocessCommand(
        argv=(sys.executable,),
        cwd=str(root),
        stdin="1234",
    )
    allowed.validate(command)
    assert allowed.environment_for(command) == {"VISIBLE": "yes"}
    allowed.validate_captured_output(command=command, stdout="1234", stderr="")

    explicit = SubprocessCommand(
        argv=(sys.executable,),
        env={"VISIBLE": "explicit"},
    )
    assert allowed.environment_for(explicit) == {"VISIBLE": "explicit"}

    with pytest.raises(ValueError, match="outside allowed"):
        allowed.validate(
            SubprocessCommand(
                argv=(sys.executable,),
                cwd=str(root.parent),
            )
        )
    with pytest.raises(ValueError, match="disallowed keys"):
        allowed.validate(
            SubprocessCommand(
                argv=(sys.executable,),
                env={"HIDDEN": "no"},
            )
        )
    with pytest.raises(ValueError, match="stdin"):
        allowed.validate(
            SubprocessCommand(
                argv=(sys.executable,),
                stdin="12345",
            )
        )
    with pytest.raises(ValueError, match="stdout"):
        allowed.validate_captured_output(
            command=command,
            stdout="12345",
            stderr="",
        )


@pytest.mark.parametrize(
    ("kwargs", "error_type"),
    [
        ({"max_workers": True}, TypeError),
        ({"max_workers": 0}, ValueError),
        ({"terminate_grace_seconds": True}, TypeError),
        ({"terminate_grace_seconds": -0.1}, ValueError),
        ({"security_policy": object()}, TypeError),
    ],
)
def test_subprocess_executor_constructor_guards(
    kwargs: dict[str, object],
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type):
        SubprocessExecutor(**kwargs)  # type: ignore[arg-type]


def test_subprocess_registration_resolution_and_spawn_failure_paths() -> None:
    executor = SubprocessExecutor(max_workers=1)
    try:
        with pytest.raises(ValueError, match="must not be empty"):
            executor.register("", _command_factory)
        with pytest.raises(TypeError, match="callable"):
            executor.register("bad", object())  # type: ignore[arg-type]

        executor.register("command", _command_factory)
        with pytest.raises(ValueError, match="already exists"):
            executor.register("command", _command_factory)

        wrong = executor.execute(
            _request(
                SubprocessCommand(argv=(sys.executable, "-c", "print('x')")),
                "inline",
            )
        )
        assert wrong.failure is not None
        assert wrong.failure.category is FailureCategory.CAPABILITY

        unresolved = executor.execute(
            _request(
                RegisteredWorkload("missing", executor_key="subprocess"),
                "subprocess",
            )
        )
        assert unresolved.failure is not None
        assert unresolved.failure.error_code == "PWK-SUBPROCESS-WORKLOAD-UNRESOLVED"

        invalid = executor.execute(_request(_two_args, "subprocess"))
        assert invalid.failure is not None
        assert invalid.failure.error_code == "PWK-SUBPROCESS-HANDLER-CONTRACT"

        raised = executor.execute(_request(_command_boom, "subprocess"))
        assert raised.failure is not None
        assert raised.failure.error_code == "RuntimeError"

        wrong_result = executor.execute(_request(_not_a_command, "subprocess"))
        assert wrong_result.failure is not None
        assert wrong_result.failure.error_code == "PWK-SUBPROCESS-COMMAND-CONTRACT"

        registered = executor.execute(
            _request(
                RegisteredWorkload("command", executor_key="subprocess"),
                "subprocess",
                dependency_outputs={"value": "factory-ok"},
            )
        )
        assert registered.succeeded is True
        assert registered.output.stdout == "factory-ok\n"  # type: ignore[union-attr]

        expired = executor.execute(
            _request(
                SubprocessCommand(argv=(sys.executable, "-c", "print('late')")),
                "subprocess",
                deadline_at=datetime.now(tz=UTC) - timedelta(seconds=1),
            )
        )
        assert expired.failure is not None
        assert expired.failure.error_code == "PWK-SUBPROCESS-HARD-TIMEOUT"

        missing = executor.execute(
            _request(
                SubprocessCommand(argv=("pyworkflowkit-command-does-not-exist",)),
                "subprocess",
            )
        )
        assert missing.failure is not None
        assert missing.failure.error_code == "PWK-SUBPROCESS-NOT-FOUND"
    finally:
        executor.shutdown()


def test_subprocess_capacity_active_cancel_completed_cancel_and_shutdown() -> None:
    executor = SubprocessExecutor(max_workers=1)
    first_request = _request(
        SubprocessCommand(
            argv=(sys.executable, "-c", "import time; time.sleep(5)"),
        ),
        "subprocess",
        attempt_id="TA-subprocess-capacity",
    )
    holder: list[TaskExecutionResult] = []
    worker = threading.Thread(
        target=lambda: holder.append(executor.execute(first_request)),
        daemon=True,
    )
    worker.start()
    _wait_for(lambda: bool(executor._active))

    saturated = executor.execute(
        _request(
            SubprocessCommand(argv=(sys.executable, "-c", "print('second')")),
            "subprocess",
            attempt_id="TA-subprocess-second",
        )
    )
    assert saturated.failure is not None
    assert saturated.failure.error_code == "PWK-SUBPROCESS-CAPACITY"

    cancellation = executor.cancel(
        TaskCancellationRequest(
            workflow_run_id=first_request.context.workflow_run_id,
            task_run_id=first_request.context.task_run_id,
            attempt_id=first_request.context.attempt_id,
            task_key=first_request.task_key,
            requested_at=datetime.now(tz=UTC),
        )
    )
    assert cancellation.status is CancellationStatus.CONFIRMED
    worker.join(timeout=3)
    assert not worker.is_alive()
    assert holder
    assert holder[0].failure is not None
    assert holder[0].failure.category is FailureCategory.CANCELLED

    completed = executor.cancel(
        TaskCancellationRequest(
            workflow_run_id=first_request.context.workflow_run_id,
            task_run_id=first_request.context.task_run_id,
            attempt_id=first_request.context.attempt_id,
            task_key=first_request.task_key,
            requested_at=datetime.now(tz=UTC),
        )
    )
    assert completed.status is CancellationStatus.ALREADY_TERMINAL

    executor.shutdown()
    with pytest.raises(ExecutorShutdownError):
        executor.execute(
            _request(
                SubprocessCommand(argv=(sys.executable, "-c", "print('late')")),
                "subprocess",
                attempt_id="TA-subprocess-after-shutdown",
            )
        )
