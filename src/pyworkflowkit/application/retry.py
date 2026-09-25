"""Retry decisions and deterministic backoff calculations."""

from dataclasses import dataclass

from pyworkflowkit.domain.enums import BackoffStrategy
from pyworkflowkit.domain.values import RetryPolicy
from pyworkflowkit.errors import ExecutorError, TaskExecutionError


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """Decision returned after one failed task attempt."""

    should_retry: bool
    delay_seconds: float = 0.0
    next_attempt_number: int | None = None

    def __post_init__(self) -> None:
        if self.should_retry:
            if self.next_attempt_number is None or self.next_attempt_number < 2:
                raise ValueError(
                    "retry decision requires next_attempt_number greater than or equal to 2"
                )
            if self.delay_seconds < 0:
                raise ValueError("retry delay_seconds must be non-negative")
        else:
            if self.next_attempt_number is not None:
                raise ValueError("non-retry decision cannot define next_attempt_number")
            if self.delay_seconds != 0:
                raise ValueError("non-retry decision must have zero delay_seconds")


class RetryEngine:
    """Evaluate RetryPolicy without mutating runtime state."""

    def decide(
        self,
        *,
        policy: RetryPolicy,
        attempt_number: int,
        error: ExecutorError,
    ) -> RetryDecision:
        if attempt_number >= policy.max_attempts:
            return RetryDecision(should_retry=False)

        if not isinstance(error, TaskExecutionError):
            return RetryDecision(should_retry=False)

        if (
            policy.retryable_error_categories
            and error.error_category not in policy.retryable_error_categories
        ):
            return RetryDecision(should_retry=False)

        return RetryDecision(
            should_retry=True,
            delay_seconds=self._backoff_delay(
                policy=policy,
                failed_attempt_number=attempt_number,
            ),
            next_attempt_number=attempt_number + 1,
        )

    @staticmethod
    def _backoff_delay(
        *,
        policy: RetryPolicy,
        failed_attempt_number: int,
    ) -> float:
        if policy.backoff_strategy is BackoffStrategy.NONE:
            delay = 0.0
        elif policy.backoff_strategy is BackoffStrategy.FIXED:
            delay = policy.delay_seconds
        elif policy.backoff_strategy is BackoffStrategy.LINEAR:
            delay = policy.delay_seconds * failed_attempt_number
        elif policy.backoff_strategy is BackoffStrategy.EXPONENTIAL:
            delay = policy.delay_seconds * (2 ** (failed_attempt_number - 1))
        else:
            raise TypeError(f"Unsupported backoff strategy: {policy.backoff_strategy!r}")

        if policy.max_delay_seconds is not None:
            delay = min(delay, policy.max_delay_seconds)
        return float(delay)


__all__ = ["RetryDecision", "RetryEngine"]
