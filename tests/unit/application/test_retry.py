"""Tests for RetryEngine decisions and backoff calculations."""

import pytest

from pyworkflowkit.application.retry import RetryDecision, RetryEngine
from pyworkflowkit.domain.enums import BackoffStrategy
from pyworkflowkit.domain.ids import TaskId
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
