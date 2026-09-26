"""Tests for RetryEngine decisions and backoff calculations."""

from datetime import UTC, datetime, timedelta

import pytest

from pyworkflowkit.application.retry import (
    RetryDecision,
    RetryEngine,
    pending_retry_attempt,
    retry_eligible_at,
)
from pyworkflowkit.domain.enums import BackoffStrategy
from pyworkflowkit.domain.enums import TaskAttemptStatus
from pyworkflowkit.domain.ids import TaskAttemptId, TaskId, TaskRunId
from pyworkflowkit.domain.runtime import TaskAttempt
from pyworkflowkit.domain.values import RetryPolicy
from pyworkflowkit.errors import InvalidHandlerError, TaskExecutionError


def failure(category: str = "TimeoutError") -> TaskExecutionError:
    return TaskExecutionError(
        task_id=TaskId("A"),
        handler_ref="handlers:A",
        error_type=category,
        error_message="boom",
        error_category=category,
    )


def test_retry_decision_rejects_inconsistent_values() -> None:
    with pytest.raises(ValueError, match="next_attempt_number"):
        RetryDecision(should_retry=True)

    with pytest.raises(ValueError, match="zero delay"):
        RetryDecision(should_retry=False, delay_seconds=1.0)


def test_default_policy_does_not_retry() -> None:
    decision = RetryEngine().decide(
        policy=RetryPolicy(),
        attempt_number=1,
        error=failure(),
    )

    assert decision == RetryDecision(should_retry=False)


def test_retry_engine_retries_task_execution_error_when_attempts_remain() -> None:
    decision = RetryEngine().decide(
        policy=RetryPolicy(max_attempts=3),
        attempt_number=1,
        error=failure(),
    )

    assert decision.should_retry is True
    assert decision.next_attempt_number == 2
    assert decision.delay_seconds == 0.0


def test_retry_engine_does_not_retry_non_execution_executor_errors() -> None:
    decision = RetryEngine().decide(
        policy=RetryPolicy(max_attempts=3),
        attempt_number=1,
        error=InvalidHandlerError(
            task_id=TaskId("A"),
            reason="bad signature",
        ),
    )

    assert decision.should_retry is False


def test_retry_category_allowlist_blocks_non_matching_failure() -> None:
    decision = RetryEngine().decide(
        policy=RetryPolicy(
            max_attempts=3,
            retryable_error_categories=frozenset({"TimeoutError"}),
        ),
        attempt_number=1,
        error=failure("ValueError"),
    )

    assert decision.should_retry is False


@pytest.mark.parametrize(
    ("strategy", "attempt_number", "expected"),
    [
        (BackoffStrategy.NONE, 1, 0.0),
        (BackoffStrategy.FIXED, 1, 2.0),
        (BackoffStrategy.FIXED, 2, 2.0),
        (BackoffStrategy.LINEAR, 1, 2.0),
        (BackoffStrategy.LINEAR, 2, 4.0),
        (BackoffStrategy.EXPONENTIAL, 1, 2.0),
        (BackoffStrategy.EXPONENTIAL, 2, 4.0),
        (BackoffStrategy.EXPONENTIAL, 3, 8.0),
    ],
)
def test_retry_backoff_strategies(
    strategy: BackoffStrategy,
    attempt_number: int,
    expected: float,
) -> None:
    decision = RetryEngine().decide(
        policy=RetryPolicy(
            max_attempts=5,
            backoff_strategy=strategy,
            delay_seconds=2.0,
        ),
        attempt_number=attempt_number,
        error=failure(),
    )

    assert decision.delay_seconds == expected


def test_retry_backoff_respects_max_delay() -> None:
    decision = RetryEngine().decide(
        policy=RetryPolicy(
            max_attempts=5,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            delay_seconds=3.0,
            max_delay_seconds=5.0,
        ),
        attempt_number=3,
        error=failure(),
    )

    assert decision.delay_seconds == 5.0



def test_retry_eligible_at_adds_decision_delay() -> None:
    failed_at = datetime(2026, 9, 27, 0, 30, tzinfo=UTC)
    decision = RetryDecision(
        should_retry=True,
        delay_seconds=2.5,
        next_attempt_number=2,
    )

    assert retry_eligible_at(
        failed_at=failed_at,
        decision=decision,
    ) == failed_at + timedelta(seconds=2.5)


def test_retry_eligible_at_rejects_non_retry_decision() -> None:
    with pytest.raises(ValueError, match="retry decision"):
        retry_eligible_at(
            failed_at=datetime(2026, 9, 27, 0, 30, tzinfo=UTC),
            decision=RetryDecision(should_retry=False),
        )


def test_retry_eligible_at_rejects_naive_failed_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        retry_eligible_at(
            failed_at=datetime(2026, 9, 27, 0, 30),
            decision=RetryDecision(
                should_retry=True,
                next_attempt_number=2,
            ),
        )


def test_pending_retry_attempt_returns_latest_scheduled_failure() -> None:
    now = datetime(2026, 9, 27, 0, 30, tzinfo=UTC)
    first = TaskAttempt(
        attempt_id=TaskAttemptId("attempt-1"),
        task_run_id=TaskRunId("task-run"),
        attempt_number=1,
        status=TaskAttemptStatus.FAILED,
        started_at=now,
        finished_at=now,
        error_type="RuntimeError",
        error_message="temporary",
        retry_eligible_at=now + timedelta(seconds=1),
    )

    assert pending_retry_attempt((first,)) is first


def test_pending_retry_attempt_requires_latest_attempt_to_be_scheduled_failure() -> None:
    now = datetime(2026, 9, 27, 0, 30, tzinfo=UTC)
    first = TaskAttempt(
        attempt_id=TaskAttemptId("attempt-1"),
        task_run_id=TaskRunId("task-run"),
        attempt_number=1,
        status=TaskAttemptStatus.FAILED,
        started_at=now,
        finished_at=now,
        error_type="RuntimeError",
        error_message="temporary",
        retry_eligible_at=now + timedelta(seconds=1),
    )
    second = TaskAttempt(
        attempt_id=TaskAttemptId("attempt-2"),
        task_run_id=TaskRunId("task-run"),
        attempt_number=2,
        status=TaskAttemptStatus.SUCCEEDED,
        started_at=now,
        finished_at=now,
    )

    assert pending_retry_attempt((first, second)) is None
    assert pending_retry_attempt(()) is None
