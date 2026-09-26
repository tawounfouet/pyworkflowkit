"""Tests for structured diagnostics and redaction."""

import logging

from pyworkflowkit.application.observability import (
    LogContext,
    log_runtime,
    redact_mapping,
    structured_fields,
)


def test_redaction_is_recursive_and_key_based() -> None:
    values = {
        "user": "alice",
        "password": "plain",
        "nested": {"api_token": "abc", "safe": 42},
    }

    redacted = redact_mapping(values)

    assert redacted == {
        "user": "alice",
        "password": "<redacted>",
        "nested": {"api_token": "<redacted>", "safe": 42},
    }


def test_log_runtime_emits_structured_correlation_fields(caplog) -> None:  # type: ignore[no-untyped-def]
    logger = logging.getLogger("pyworkflowkit.test.observability")

    with caplog.at_level(logging.INFO, logger=logger.name):
        log_runtime(
            logger,
            logging.INFO,
            "Task started",
            context=LogContext(
                run_id="run-1",
                workflow_id="workflow",
                task_run_id="task-run-1",
                task_id="fetch",
                attempt_number=1,
                executor_key="local",
            ),
            fields={"authorization": "Bearer secret", "delay_seconds": 2.0},
        )

    record = caplog.records[-1]
    fields = structured_fields(record)

    assert fields["run_id"] == "run-1"
    assert fields["task_id"] == "fetch"
    assert fields["authorization"] == "<redacted>"
    assert fields["delay_seconds"] == 2.0
