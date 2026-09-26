"""M36 reference acceptance for security hardening boundaries."""

from __future__ import annotations

import os
import sys

from pyworkflowkit.adapters.executors.subprocess import (
    SubprocessCommand,
    SubprocessExecutor,
    SubprocessSecurityPolicy,
)
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.adapters.runtime import SystemClock, SystemSleeper, UuidRuntimeIdFactory
from pyworkflowkit.application.concurrent_runner import ConcurrentRunner
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import WorkflowRunStatus
from pyworkflowkit.domain.ids import TaskId, WorkflowId


def _workflow() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id=WorkflowId("reference.security"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("external"),
                handler_ref="handlers:external",
                executor_key="subprocess",
            ),
        ),
    )


def _runner(
    *,
    executor: SubprocessExecutor,
    handlers: HandlerRegistry,
) -> ConcurrentRunner:
    return ConcurrentRunner(
        metadata_store=MemoryMetadataStore(),
        handler_registry=handlers,
        executor=executor,
        clock=SystemClock(),
        id_factory=UuidRuntimeIdFactory(),
        sleeper=SystemSleeper(),
        global_limit=1,
    )


def test_default_subprocess_policy_does_not_inherit_parent_secret(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PYWORKFLOWKIT_REFERENCE_SECRET_TOKEN", "do-not-leak")
    handlers = HandlerRegistry()

    def command() -> SubprocessCommand:
        return SubprocessCommand(
            argv=(
                sys.executable,
                "-c",
                (
                    "import os, sys; "
                    "sys.exit(0 if 'PYWORKFLOWKIT_REFERENCE_SECRET_TOKEN' "
                    "not in os.environ else 9)"
                ),
            )
        )

    handlers.register("handlers:external", command)
    executor = SubprocessExecutor(max_workers=1)

    try:
        run = _runner(executor=executor, handlers=handlers).run(_workflow())

        assert run.status is WorkflowRunStatus.SUCCEEDED
    finally:
        executor.shutdown(wait=False)


def test_subprocess_allowlist_violation_fails_workflow_before_command_runs() -> None:
    handlers = HandlerRegistry()

    def command() -> SubprocessCommand:
        return SubprocessCommand(
            argv=(sys.executable, "-c", "raise SystemExit(99)"),
        )

    handlers.register("handlers:external", command)
    executor = SubprocessExecutor(
        max_workers=1,
        security_policy=SubprocessSecurityPolicy(
            allowed_executables=frozenset({"/explicitly/allowed/executable"}),
        ),
    )

    try:
        run = _runner(executor=executor, handlers=handlers).run(_workflow())

        assert run.status is WorkflowRunStatus.FAILED
        assert executor.active_handles() == ()
    finally:
        executor.shutdown(wait=False)


def test_explicit_environment_can_be_reduced_to_allowlisted_keys(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAFE_VALUE", "visible")
    monkeypatch.setenv("SECRET_TOKEN", "hidden")
    policy = SubprocessSecurityPolicy(
        inherit_environment=True,
        allowed_env_keys=frozenset({"SAFE_VALUE"}),
    )
    command = SubprocessCommand(argv=(sys.executable, "-c", "pass"))

    assert policy.environment_for(command) == {"SAFE_VALUE": "visible"}
    assert "SECRET_TOKEN" not in policy.environment_for(command)
    assert os.environ["SECRET_TOKEN"] == "hidden"
