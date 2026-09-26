"""Tests for M34 SubprocessExecutor."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

from pyworkflowkit.adapters.executors.subprocess import (
    SubprocessCommand,
    SubprocessExecutor,
    SubprocessResult,
)
from pyworkflowkit.application.completion import CompletionQueue, ExecutionHandle
from pyworkflowkit.domain.definitions import TaskDefinition
from pyworkflowkit.domain.ids import (
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowRunId,
)
from pyworkflowkit.errors import (
    DuplicateExecutionSubmissionError,
    ExecutionHandleNotFoundError,
    ExecutorShutdownError,
    ExecutorWorkerError,
    InvalidHandlerError,
    SubprocessExecutionError,
    TaskExecutionError,
)
from pyworkflowkit.ports.executor import (
    CancellationCapability,
    RunContext,
    TimeoutCapability,
)


def _task(name: str) -> TaskDefinition:
    return TaskDefinition(
        task_id=TaskId(name),
        handler_ref=f"handlers:{name}",
        executor_key="subprocess",
    )


def _context(name: str) -> RunContext:
    return RunContext(
        workflow_run_id=WorkflowRunId("run"),
        task_run_id=TaskRunId(f"task-run-{name}"),
        attempt_id=TaskAttemptId(f"attempt-{name}"),
        task_id=TaskId(name),
        attempt_number=1,
        workflow_parameters={"name": "demo"},
        dependency_outputs={TaskId("upstream"): {"rows": 3}},
    )


def _print_ok() -> SubprocessCommand:
    return SubprocessCommand(
        argv=(sys.executable, "-c", "print('ok')"),
    )


def _sleep_long() -> SubprocessCommand:
    return SubprocessCommand(
        argv=(sys.executable, "-c", "import time; time.sleep(10)"),
    )


def test_subprocess_command_validates_shell_free_argv_contract() -> None:
    with pytest.raises(ValueError, match="at least one"):
        SubprocessCommand(argv=())

    with pytest.raises(ValueError, match="executable"):
        SubprocessCommand(argv=(" ",))

    with pytest.raises(ValueError, match="NUL"):
        SubprocessCommand(argv=(sys.executable, "bad\x00arg"))

    with pytest.raises(ValueError, match="cwd"):
        SubprocessCommand(argv=(sys.executable,), cwd=" ")

    with pytest.raises(ValueError, match="encoding"):
        SubprocessCommand(argv=(sys.executable,), encoding=" ")


def test_subprocess_command_defensively_freezes_environment() -> None:
    env = {"DEMO": "one"}
    command = SubprocessCommand(argv=(sys.executable,), env=env)
    env["DEMO"] = "two"

    assert command.env is not None
    assert command.env["DEMO"] == "one"

    with pytest.raises(TypeError):
        command.env["DEMO"] = "three"  # type: ignore[index]


def test_subprocess_executor_declares_hard_process_capabilities() -> None:
    executor = SubprocessExecutor(max_workers=3)
    try:
        capabilities = executor.capabilities

        assert capabilities.supports_parallelism is True
        assert capabilities.max_concurrency == 3
        assert capabilities.timeout is TimeoutCapability.HARD
        assert capabilities.cancellation is CancellationCapability.HARD
        assert capabilities.supports_async is False
    finally:
        executor.shutdown()


def test_subprocess_executor_preserves_explicit_completion_queue() -> None:
    completion_queue = CompletionQueue()
    executor = SubprocessExecutor(max_workers=1, completion_queue=completion_queue)
    try:
        assert executor.completion_queue is completion_queue
    finally:
        executor.shutdown()


def test_execute_captures_stdout_stderr_and_returncode() -> None:
    def command() -> SubprocessCommand:
        return SubprocessCommand(
            argv=(
                sys.executable,
                "-c",
                "import sys; print('out'); print('err', file=sys.stderr)",
            )
        )

    executor = SubprocessExecutor(max_workers=1)
    try:
        result = executor.execute(
            task=_task("capture"),
            handler=command,
            context=_context("capture"),
        )

        assert isinstance(result.output, SubprocessResult)
        assert result.output.returncode == 0
        assert result.output.stdout == "out\n"
        assert result.output.stderr == "err\n"
        assert result.metadata["returncode"] == 0
    finally:
        executor.shutdown()


def test_command_factory_receives_run_context() -> None:
    def command(context: RunContext) -> SubprocessCommand:
        return SubprocessCommand(
            argv=(
                sys.executable,
                "-c",
                "import sys; print(sys.argv[1])",
                str(context.workflow_parameters["name"]),
            )
        )

    executor = SubprocessExecutor(max_workers=1)
    try:
        result = executor.execute(
            task=_task("context"),
            handler=command,
            context=_context("context"),
        )

        assert isinstance(result.output, SubprocessResult)
        assert result.output.stdout == "demo\n"
    finally:
        executor.shutdown()


def test_subprocess_uses_argv_without_shell_interpretation() -> None:
    literal = "hello; echo injected && $(whoami)"

    def command() -> SubprocessCommand:
        return SubprocessCommand(
            argv=(
                sys.executable,
                "-c",
                "import sys; print(sys.argv[1])",
                literal,
            )
        )

    executor = SubprocessExecutor(max_workers=1)
    try:
        result = executor.execute(
            task=_task("shell-free"),
            handler=command,
            context=_context("shell-free"),
        )

        assert isinstance(result.output, SubprocessResult)
        assert result.output.stdout == f"{literal}\n"
    finally:
        executor.shutdown()


def test_subprocess_supports_stdin_cwd_and_explicit_environment(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["PYWORKFLOWKIT_TEST_VALUE"] = "visible"

    def command() -> SubprocessCommand:
        return SubprocessCommand(
            argv=(
                sys.executable,
                "-c",
                (
                    "import os, pathlib, sys; "
                    "print(pathlib.Path.cwd().name); "
                    "print(os.environ['PYWORKFLOWKIT_TEST_VALUE']); "
                    "print(sys.stdin.read())"
                ),
            ),
            cwd=str(tmp_path),
            env=env,
            stdin="payload",
        )

    executor = SubprocessExecutor(max_workers=1)
    try:
        result = executor.execute(
            task=_task("io"),
            handler=command,
            context=_context("io"),
        )

        assert isinstance(result.output, SubprocessResult)
        assert result.output.stdout.splitlines() == [
            tmp_path.name,
            "visible",
            "payload",
        ]
    finally:
        executor.shutdown()


def test_nonzero_exit_is_normalized_with_captured_evidence() -> None:
    def command() -> SubprocessCommand:
        return SubprocessCommand(
            argv=(
                sys.executable,
                "-c",
                "import sys; print('bad', file=sys.stderr); raise SystemExit(7)",
            )
        )

    executor = SubprocessExecutor(max_workers=1)
    try:
        with pytest.raises(SubprocessExecutionError) as exc_info:
            executor.execute(
                task=_task("exit"),
                handler=command,
                context=_context("exit"),
            )

        assert exc_info.value.returncode == 7
        assert exc_info.value.stderr == "bad\n"
        assert exc_info.value.error_category == "subprocess_exit"
    finally:
        executor.shutdown()


def test_missing_executable_is_normalized_as_spawn_failure() -> None:
    def command() -> SubprocessCommand:
        return SubprocessCommand(argv=("pyworkflowkit-command-that-does-not-exist",))

    executor = SubprocessExecutor(max_workers=1)
    try:
        with pytest.raises(TaskExecutionError) as exc_info:
            executor.execute(
                task=_task("missing"),
                handler=command,
                context=_context("missing"),
            )

        assert exc_info.value.error_category == "subprocess_spawn"
    finally:
        executor.shutdown()


def test_handler_must_return_subprocess_command() -> None:
    executor = SubprocessExecutor(max_workers=1)
    try:
        with pytest.raises(InvalidHandlerError, match="SubprocessCommand"):
            executor.execute(
                task=_task("invalid"),
                handler=lambda: "not-a-command",
                context=_context("invalid"),
            )
    finally:
        executor.shutdown()


def test_submit_publishes_captured_process_result() -> None:
    executor = SubprocessExecutor(max_workers=1)
    try:
        handle = executor.submit(
            task=_task("submit"),
            handler=_print_ok,
            context=_context("submit"),
        )
        completion = executor.completion_queue.get(timeout=3.0)

        assert completion.handle == handle
        assert completion.succeeded is True
        assert completion.result is not None
        assert isinstance(completion.result.output, SubprocessResult)
        assert completion.result.output.stdout == "ok\n"
        assert executor.wait(handle, timeout=1.0) is True
        assert executor.active_handles() == ()
    finally:
        executor.shutdown()


def test_submit_transfers_command_resolution_error_as_completion() -> None:
    def broken() -> SubprocessCommand:
        raise RuntimeError("factory failed")

    executor = SubprocessExecutor(max_workers=1)
    try:
        handle = executor.submit(
            task=_task("factory"),
            handler=broken,
            context=_context("factory"),
        )
        completion = executor.completion_queue.get(timeout=2.0)

        assert completion.handle == handle
        assert completion.succeeded is False
        assert isinstance(completion.error, TaskExecutionError)
        assert completion.error.error_category == "subprocess_command"
    finally:
        executor.shutdown()


def test_terminate_hard_stops_active_subprocess() -> None:
    executor = SubprocessExecutor(max_workers=1)
    try:
        handle = executor.submit(
            task=_task("slow"),
            handler=_sleep_long,
            context=_context("slow"),
        )
        assert executor.active_handles()

        started = time.monotonic()
        assert executor.terminate(handle) is True
        completion = executor.completion_queue.get(timeout=3.0)

        assert completion.handle == handle
        assert completion.succeeded is False
        assert executor.wait(handle, timeout=1.0) is True
        assert time.monotonic() - started < 3.0
    finally:
        executor.shutdown(wait=False)


def test_capacity_rejects_submission_beyond_declared_limit() -> None:
    executor = SubprocessExecutor(max_workers=1)
    first = executor.submit(
        task=_task("first"),
        handler=_sleep_long,
        context=_context("first"),
    )
    try:
        with pytest.raises(ExecutorWorkerError, match="SubprocessCapacityExceeded"):
            executor.submit(
                task=_task("second"),
                handler=_print_ok,
                context=_context("second"),
            )
    finally:
        executor.terminate(first)
        executor.completion_queue.get(timeout=3.0)
        executor.shutdown()


def test_duplicate_attempt_submission_is_rejected() -> None:
    executor = SubprocessExecutor(max_workers=2)
    task = _task("once")
    context = _context("once")
    first = executor.submit(task=task, handler=_sleep_long, context=context)
    try:
        with pytest.raises(DuplicateExecutionSubmissionError):
            executor.submit(task=task, handler=_sleep_long, context=context)
    finally:
        executor.terminate(first)
        executor.completion_queue.get(timeout=3.0)
        executor.shutdown()


def test_wait_and_terminate_reject_unknown_handle() -> None:
    executor = SubprocessExecutor(max_workers=1)
    unknown = ExecutionHandle(
        handle_id="subprocess:missing",
        attempt_id=TaskAttemptId("missing"),
        executor_key="subprocess",
    )
    try:
        with pytest.raises(ExecutionHandleNotFoundError):
            executor.wait(unknown)
        with pytest.raises(ExecutionHandleNotFoundError):
            executor.terminate(unknown)
    finally:
        executor.shutdown()


def test_wait_rejects_negative_timeout() -> None:
    executor = SubprocessExecutor(max_workers=1)
    handle = executor.submit(
        task=_task("wait"),
        handler=_print_ok,
        context=_context("wait"),
    )
    try:
        with pytest.raises(ValueError, match="timeout"):
            executor.wait(handle, timeout=-1)
        executor.completion_queue.get(timeout=3.0)
    finally:
        executor.shutdown()


def test_shutdown_rejects_new_submissions() -> None:
    executor = SubprocessExecutor(max_workers=1)
    executor.shutdown()

    with pytest.raises(ExecutorShutdownError):
        executor.submit(
            task=_task("late"),
            handler=_print_ok,
            context=_context("late"),
        )


@pytest.mark.parametrize("max_workers", [True, 1.5, "2"])
def test_subprocess_executor_rejects_non_integer_worker_counts(max_workers: object) -> None:
    with pytest.raises(TypeError):
        SubprocessExecutor(max_workers=max_workers)  # type: ignore[arg-type]


def test_subprocess_executor_rejects_non_positive_worker_count() -> None:
    with pytest.raises(ValueError):
        SubprocessExecutor(max_workers=0)


@pytest.mark.parametrize("terminate_grace_seconds", [True, "0.2"])
def test_subprocess_executor_rejects_non_numeric_termination_grace(
    terminate_grace_seconds: object,
) -> None:
    with pytest.raises(TypeError):
        SubprocessExecutor(
            terminate_grace_seconds=terminate_grace_seconds,  # type: ignore[arg-type]
        )


def test_subprocess_executor_rejects_negative_termination_grace() -> None:
    with pytest.raises(ValueError):
        SubprocessExecutor(terminate_grace_seconds=-0.1)


def test_subprocess_command_rejects_invalid_runtime_types_and_environment() -> None:
    with pytest.raises(TypeError, match="argv"):
        SubprocessCommand(argv=(sys.executable, 3))  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="cwd"):
        SubprocessCommand(argv=(sys.executable,), cwd=3)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="cwd"):
        SubprocessCommand(argv=(sys.executable,), cwd="bad\x00cwd")

    with pytest.raises(TypeError, match="stdin"):
        SubprocessCommand(argv=(sys.executable,), stdin=3)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="encoding"):
        SubprocessCommand(argv=(sys.executable,), encoding=3)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="env"):
        SubprocessCommand(
            argv=(sys.executable,),
            env={"KEY": 3},  # type: ignore[dict-item]
        )

    with pytest.raises(ValueError, match="env keys"):
        SubprocessCommand(argv=(sys.executable,), env={"BAD=KEY": "value"})

    with pytest.raises(ValueError, match="env values"):
        SubprocessCommand(argv=(sys.executable,), env={"KEY": "bad\x00value"})


def test_subprocess_executor_rejects_task_for_another_executor() -> None:
    executor = SubprocessExecutor(max_workers=1)
    task = TaskDefinition(
        task_id=TaskId("wrong"),
        handler_ref="handlers:wrong",
        executor_key="thread",
    )
    try:
        with pytest.raises(InvalidHandlerError, match="executor key is 'subprocess'"):
            executor.execute(
                task=task,
                handler=_print_ok,
                context=_context("wrong"),
            )
    finally:
        executor.shutdown()


def test_submit_missing_executable_publishes_spawn_failure() -> None:
    def command() -> SubprocessCommand:
        return SubprocessCommand(argv=("pyworkflowkit-command-that-does-not-exist",))

    executor = SubprocessExecutor(max_workers=1)
    try:
        handle = executor.submit(
            task=_task("missing-submit"),
            handler=command,
            context=_context("missing-submit"),
        )
        completion = executor.completion_queue.get(timeout=2.0)

        assert completion.handle == handle
        assert isinstance(completion.error, TaskExecutionError)
        assert completion.error.error_category == "subprocess_spawn"
        assert executor.wait(handle) is True
        assert executor.terminate(handle) is False
    finally:
        executor.shutdown()


def test_submit_unexpected_setup_failure_becomes_worker_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = SubprocessExecutor(max_workers=1)

    def fail_spawn(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise KeyboardInterrupt("unexpected setup failure")

    monkeypatch.setattr(executor, "_spawn", fail_spawn)
    try:
        handle = executor.submit(
            task=_task("worker-setup"),
            handler=_print_ok,
            context=_context("worker-setup"),
        )
        completion = executor.completion_queue.get(timeout=2.0)

        assert completion.handle == handle
        assert isinstance(completion.error, ExecutorWorkerError)
        assert completion.error.error_type == "KeyboardInterrupt"
    finally:
        executor.shutdown()


def test_wait_can_report_still_running_before_hard_termination() -> None:
    executor = SubprocessExecutor(max_workers=1)
    handle = executor.submit(
        task=_task("wait-running"),
        handler=_sleep_long,
        context=_context("wait-running"),
    )
    try:
        assert executor.wait(handle, timeout=0.01) is False
        assert executor.terminate(handle) is True
        executor.completion_queue.get(timeout=3.0)
        assert executor.wait(handle) is True
    finally:
        executor.shutdown(wait=False)


def test_subprocess_executor_shutdown_state_and_context_manager() -> None:
    executor = SubprocessExecutor(max_workers=1)
    assert executor.is_shutdown is False
    executor.shutdown()
    assert executor.is_shutdown is True

    with SubprocessExecutor(max_workers=1) as managed:
        result = managed.execute(
            task=_task("managed"),
            handler=_print_ok,
            context=_context("managed"),
        )
        assert isinstance(result.output, SubprocessResult)

    assert managed.is_shutdown is True
