"""LOT-14 unit tests for the canonical V2 SubprocessExecutor."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta

from pyworkflowkit.diagnostics import FailureCategory, OutcomeUncertainty
from pyworkflowkit.executors import (
    CancellationStatus,
    SubprocessCommand,
    SubprocessExecutor,
    SubprocessResult,
    SubprocessSecurityPolicy,
    TaskCancellationRequest,
    TaskExecutionContext,
    TaskExecutionRequest,
)
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    TaskAttemptId,
    TaskRunId,
    WorkflowRunId,
)


def _context(attempt_id: str = "TA-subprocess") -> TaskExecutionContext:
    return TaskExecutionContext(
        workflow_run_id=WorkflowRunId.parse("W-subprocess"),
        task_run_id=TaskRunId.parse("TR-subprocess"),
        attempt_id=TaskAttemptId.parse(attempt_id),
        attempt_number=1,
        correlation=CorrelationContext(
            correlation_id=CorrelationId.parse("C-subprocess"),
        ),
    )


def _request(
    command: SubprocessCommand,
    *,
    attempt_id: str = "TA-subprocess",
    deadline_at: datetime | None = None,
) -> TaskExecutionRequest:
    return TaskExecutionRequest(
        task_key="subprocess-task",
        workload=command,
        executor_key="subprocess",
        context=_context(attempt_id),
        deadline_at=deadline_at,
    )


def test_subprocess_command_is_portable_workload_descriptor() -> None:
    command = SubprocessCommand(argv=(sys.executable, "-c", "print('ok')"))

    assert command.workload_kind == "subprocess"
    assert command.executor_key == "subprocess"
    assert command.portability.value == "portable"
    assert command.fingerprint_payload()["argv"] == [
        sys.executable,
        "-c",
        "print('ok')",
    ]


def test_subprocess_executor_captures_stdout_without_shell() -> None:
    marker = "; echo should-not-run"
    command = SubprocessCommand(
        argv=(
            sys.executable,
            "-c",
            "import sys; print(sys.argv[1])",
            marker,
        )
    )
    executor = SubprocessExecutor(max_workers=1)
    try:
        result = executor.execute(_request(command))
    finally:
        executor.shutdown()

    assert result.succeeded is True
    assert isinstance(result.output, SubprocessResult)
    assert result.output.stdout == marker + "\n"
    assert result.output.returncode == 0


def test_subprocess_nonzero_exit_is_structured_failure() -> None:
    command = SubprocessCommand(
        argv=(
            sys.executable,
            "-c",
            "import sys; print('bad', file=sys.stderr); raise SystemExit(7)",
        )
    )
    executor = SubprocessExecutor(max_workers=1)
    try:
        result = executor.execute(_request(command))
    finally:
        executor.shutdown()

    assert result.failure is not None
    assert result.failure.error_code == "PWK-SUBPROCESS-NONZERO-EXIT"
    assert result.failure.category is FailureCategory.EXTERNAL_PROVIDER
    assert ("returncode", "7") in result.failure.details


def test_subprocess_hard_timeout_is_known() -> None:
    command = SubprocessCommand(
        argv=(
            sys.executable,
            "-c",
            "import time; time.sleep(5)",
        )
    )
    executor = SubprocessExecutor(max_workers=1)
    try:
        result = executor.execute(
            _request(
                command,
                deadline_at=datetime.now(tz=UTC) + timedelta(milliseconds=40),
            )
        )
    finally:
        executor.shutdown(wait=False)

    assert result.failure is not None
    assert result.failure.category is FailureCategory.TIMEOUT
    assert result.failure.uncertainty is OutcomeUncertainty.KNOWN
    assert result.failure.error_code == "PWK-SUBPROCESS-HARD-TIMEOUT"


def test_subprocess_security_policy_fails_closed_before_spawn() -> None:
    command = SubprocessCommand(argv=(sys.executable, "-c", "print('no')"))
    policy = SubprocessSecurityPolicy(
        allowed_executables=frozenset({"/definitely/not/python"}),
    )
    executor = SubprocessExecutor(max_workers=1, security_policy=policy)
    try:
        result = executor.execute(_request(command))
    finally:
        executor.shutdown()

    assert result.failure is not None
    assert result.failure.error_code == "PWK-SUBPROCESS-SECURITY"
    assert result.failure.category is FailureCategory.VALIDATION


def test_subprocess_output_policy_is_enforced() -> None:
    command = SubprocessCommand(
        argv=(sys.executable, "-c", "print('abcdef')"),
    )
    executor = SubprocessExecutor(
        max_workers=1,
        security_policy=SubprocessSecurityPolicy(max_stdout_bytes=2),
    )
    try:
        result = executor.execute(_request(command))
    finally:
        executor.shutdown()

    assert result.failure is not None
    assert result.failure.error_code == "PWK-SUBPROCESS-OUTPUT-POLICY"


def test_subprocess_cancel_without_active_handle_is_unconfirmed() -> None:
    executor = SubprocessExecutor(max_workers=1)
    try:
        cancellation = executor.cancel(
            TaskCancellationRequest(
                workflow_run_id=WorkflowRunId.parse("W-subprocess"),
                task_run_id=TaskRunId.parse("TR-subprocess"),
                attempt_id=TaskAttemptId.parse("TA-missing"),
                task_key="missing",
                requested_at=datetime.now(tz=UTC),
            )
        )
    finally:
        executor.shutdown()

    assert cancellation.status is CancellationStatus.UNCONFIRMED
