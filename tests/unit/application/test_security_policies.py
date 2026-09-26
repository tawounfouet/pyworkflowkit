"""Tests for M36 security hardening policies."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pyworkflowkit.adapters.executors.subprocess import (
    SubprocessCommand,
    SubprocessExecutor,
    SubprocessSecurityPolicy,
)
from pyworkflowkit.application.observability_plugins import ObservabilityDispatcher
from pyworkflowkit.application.security import ObservabilitySecurityPolicy
from pyworkflowkit.domain.definitions import TaskDefinition
from pyworkflowkit.domain.enums import RuntimeEventType
from pyworkflowkit.domain.ids import (
    RuntimeEventId,
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowRunId,
)
from pyworkflowkit.domain.runtime import RuntimeEvent
from pyworkflowkit.errors import SubprocessSecurityError
from pyworkflowkit.ports.executor import RunContext

NOW = datetime(2026, 9, 26, 21, 0, tzinfo=UTC)


def _task(name: str = "secure") -> TaskDefinition:
    return TaskDefinition(
        task_id=TaskId(name),
        handler_ref=f"handlers:{name}",
        executor_key="subprocess",
    )


def _context(name: str = "secure") -> RunContext:
    return RunContext(
        workflow_run_id=WorkflowRunId("run-security"),
        task_run_id=TaskRunId(f"task-run-{name}"),
        attempt_id=TaskAttemptId(f"attempt-{name}"),
        task_id=TaskId(name),
        attempt_number=1,
        workflow_parameters={},
        dependency_outputs={},
    )


def _event(payload: dict[str, object]) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=RuntimeEventId("event-1"),
        event_type=RuntimeEventType.TASK_FAILED,
        run_id=WorkflowRunId("run-security"),
        occurred_at=NOW,
        event_sequence=1,
        task_run_id=TaskRunId("task-run-secure"),
        task_id=TaskId("secure"),
        attempt_number=1,
        payload=payload,
    )


@dataclass
class RecordingSink:
    name: str = "recording"
    events: list[RuntimeEvent] = field(default_factory=list)

    def emit(self, event: RuntimeEvent) -> None:
        self.events.append(event)


@dataclass
class SecretFailingSink:
    name: str = "broken"

    def emit(self, event: RuntimeEvent) -> None:
        del event
        raise RuntimeError("token=super-secret")


def test_subprocess_security_policy_disables_environment_inheritance_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYWORKFLOWKIT_SECRET_TOKEN", "should-not-cross")
    policy = SubprocessSecurityPolicy()
    command = SubprocessCommand(argv=(sys.executable, "-c", "pass"))

    assert policy.environment_for(command) == {}


def test_subprocess_security_policy_can_filter_inherited_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAFE_VALUE", "visible")
    monkeypatch.setenv("SECRET_TOKEN", "hidden")
    policy = SubprocessSecurityPolicy(
        inherit_environment=True,
        allowed_env_keys=frozenset({"SAFE_VALUE"}),
    )
    command = SubprocessCommand(argv=(sys.executable, "-c", "pass"))

    assert policy.environment_for(command) == {"SAFE_VALUE": "visible"}


def test_subprocess_security_policy_rejects_unapproved_executable() -> None:
    policy = SubprocessSecurityPolicy(
        allowed_executables=frozenset({"/approved/python"}),
    )
    command = SubprocessCommand(argv=(sys.executable, "-c", "pass"))

    with pytest.raises(ValueError, match="executable"):
        policy.validate(command)


def test_subprocess_security_policy_limits_working_directory(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    child = allowed / "child"
    child.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    policy = SubprocessSecurityPolicy(allowed_cwd_roots=(str(allowed),))

    policy.validate(SubprocessCommand(argv=(sys.executable,), cwd=str(child)))

    with pytest.raises(ValueError, match="cwd"):
        policy.validate(SubprocessCommand(argv=(sys.executable,), cwd=str(outside)))


def test_subprocess_security_policy_rejects_explicit_disallowed_environment_key() -> None:
    policy = SubprocessSecurityPolicy(
        allowed_env_keys=frozenset({"SAFE"}),
    )

    with pytest.raises(ValueError, match="environment"):
        policy.validate(
            SubprocessCommand(
                argv=(sys.executable,),
                env={"SAFE": "yes", "TOKEN": "secret"},
            )
        )


def test_subprocess_security_policy_bounds_stdin_and_captured_output() -> None:
    policy = SubprocessSecurityPolicy(
        max_stdin_bytes=3,
        max_stdout_bytes=3,
        max_stderr_bytes=3,
    )

    with pytest.raises(ValueError, match="stdin"):
        policy.validate(
            SubprocessCommand(
                argv=(sys.executable,),
                stdin="four",
            )
        )

    command = SubprocessCommand(argv=(sys.executable,))
    with pytest.raises(ValueError, match="stdout"):
        policy.validate_captured_output(command=command, stdout="four", stderr="")
    with pytest.raises(ValueError, match="stderr"):
        policy.validate_captured_output(command=command, stdout="", stderr="four")


def test_subprocess_executor_normalizes_policy_violation() -> None:
    policy = SubprocessSecurityPolicy(
        allowed_executables=frozenset({"/approved/python"}),
    )
    executor = SubprocessExecutor(max_workers=1, security_policy=policy)

    def command() -> SubprocessCommand:
        return SubprocessCommand(argv=(sys.executable, "-c", "print('blocked')"))

    try:
        with pytest.raises(SubprocessSecurityError) as exc_info:
            executor.execute(
                task=_task(),
                handler=command,
                context=_context(),
            )

        assert exc_info.value.error_category == "security_policy"
        assert "executable" in exc_info.value.violation
    finally:
        executor.shutdown()


def test_subprocess_executor_enforces_output_limit_in_async_completion() -> None:
    policy = SubprocessSecurityPolicy(max_stdout_bytes=2)
    executor = SubprocessExecutor(max_workers=1, security_policy=policy)

    def command() -> SubprocessCommand:
        return SubprocessCommand(argv=(sys.executable, "-c", "print('long-output')"))

    try:
        handle = executor.submit(
            task=_task("output"),
            handler=command,
            context=_context("output"),
        )
        completion = executor.completion_queue.get(timeout=3.0)

        assert completion.handle == handle
        assert isinstance(completion.error, SubprocessSecurityError)
        assert completion.error.error_category == "security_policy"
    finally:
        executor.shutdown()


def test_observability_security_redacts_nested_sensitive_payloads() -> None:
    sink = RecordingSink()
    dispatcher = ObservabilityDispatcher((sink,))
    original = _event(
        {
            "status": "failed",
            "api_token": "super-secret",
            "nested": {
                "password": "hunter2",
                "safe": "visible",
            },
        }
    )

    dispatcher.publish(original)

    projected = sink.events[0]
    assert projected.event_id == original.event_id
    assert projected.payload["status"] == "failed"
    assert projected.payload["api_token"] == "<redacted>"
    assert projected.payload["nested"] == {
        "password": "<redacted>",
        "safe": "visible",
    }
    assert original.payload["api_token"] == "super-secret"


def test_observability_sink_error_message_is_redacted_by_default() -> None:
    dispatcher = ObservabilityDispatcher((SecretFailingSink(),))

    dispatcher.publish(_event({"safe": "value"}))

    assert dispatcher.failures[0].error_message == "<redacted>"


def test_observability_policy_can_expose_bounded_sink_error_for_debugging() -> None:
    dispatcher = ObservabilityDispatcher(
        (SecretFailingSink(),),
        security_policy=ObservabilitySecurityPolicy(
            expose_sink_error_messages=True,
            max_sink_error_message_chars=10,
        ),
    )

    dispatcher.publish(_event({"safe": "value"}))

    assert dispatcher.failures[0].error_message == "token=supe"


@pytest.mark.parametrize("value", [True, 1.5, "10"])
def test_subprocess_security_policy_rejects_invalid_size_types(value: object) -> None:
    with pytest.raises(TypeError):
        SubprocessSecurityPolicy(max_stdin_bytes=value)  # type: ignore[arg-type]


def test_subprocess_security_policy_rejects_negative_size() -> None:
    with pytest.raises(ValueError):
        SubprocessSecurityPolicy(max_stdout_bytes=-1)


@pytest.mark.parametrize("value", [True, 1.5, "10"])
def test_observability_security_policy_rejects_invalid_message_limit(value: object) -> None:
    with pytest.raises(TypeError):
        ObservabilitySecurityPolicy(max_sink_error_message_chars=value)  # type: ignore[arg-type]


def test_observability_security_policy_rejects_non_positive_message_limit() -> None:
    with pytest.raises(ValueError):
        ObservabilitySecurityPolicy(max_sink_error_message_chars=0)


def test_observability_security_policy_can_explicitly_disable_payload_redaction() -> None:
    policy = ObservabilitySecurityPolicy(redact_event_payloads=False)
    event = _event({"token": "visible-by-explicit-policy"})

    assert policy.event_for_sink(event) is event


def test_explicit_subprocess_environment_remains_exact_when_allowed() -> None:
    policy = SubprocessSecurityPolicy(
        allowed_env_keys=frozenset({"ONLY"}),
    )
    command = SubprocessCommand(
        argv=(sys.executable,),
        env={"ONLY": "value"},
    )

    policy.validate(command)

    assert policy.environment_for(command) == {"ONLY": "value"}
    assert "PATH" not in policy.environment_for(command)
    assert os.environ is not policy.environment_for(command)
