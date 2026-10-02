"""Canonical PyWorkflowKit V2 workload-retry policy and evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from random import SystemRandom
from typing import Protocol, runtime_checkable

from pyworkflowkit.diagnostics.failure import (
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.domain.enums import BackoffStrategy


class RetryDecision(StrEnum):
    """Runtime disposition after evaluating structured failure evidence."""

    RETRY = "retry"
    DO_NOT_RETRY = "do_not_retry"
    RECONCILE = "reconcile"
    ABORT = "abort"
    CANCEL = "cancel"
    ESCALATE = "escalate"


class RetryJitter(StrEnum):
    """Stable jitter strategies for workload-level retry delay."""

    NONE = "none"
    FULL = "full"


def _validate_non_negative_number(value: float, *, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a finite number")
    if not isfinite(value):
        raise ValueError(f"{field_name} must be finite")
    if value < 0:
        raise ValueError(f"{field_name} must be greater than or equal to 0")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Immutable V2 workload-level retry declaration.

    max_attempts includes the initial attempt.
    """

    max_attempts: int = 1
    backoff_strategy: BackoffStrategy = BackoffStrategy.NONE
    initial_delay_seconds: float = 0.0
    max_delay_seconds: float | None = None
    jitter: RetryJitter = RetryJitter.NONE
    retryable_failure_categories: frozenset[FailureCategory] = field(
        default_factory=frozenset
    )
    total_budget_seconds: float | None = None
    reconciliation_required: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.max_attempts, bool) or not isinstance(self.max_attempts, int):
            raise TypeError("max_attempts must be an integer")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be greater than or equal to 1")
        if not isinstance(self.backoff_strategy, BackoffStrategy):
            raise TypeError("backoff_strategy must be a BackoffStrategy")
        if not isinstance(self.jitter, RetryJitter):
            raise TypeError("jitter must be a RetryJitter")
        if not isinstance(self.reconciliation_required, bool):
            raise TypeError("reconciliation_required must be a bool")

        _validate_non_negative_number(
            self.initial_delay_seconds,
            field_name="initial_delay_seconds",
        )
        if self.max_delay_seconds is not None:
            _validate_non_negative_number(
                self.max_delay_seconds,
                field_name="max_delay_seconds",
            )
        if self.total_budget_seconds is not None:
            _validate_non_negative_number(
                self.total_budget_seconds,
                field_name="total_budget_seconds",
            )

        categories = frozenset(self.retryable_failure_categories)
        if not all(isinstance(item, FailureCategory) for item in categories):
            raise TypeError(
                "retryable_failure_categories must contain only FailureCategory values"
            )
        object.__setattr__(self, "retryable_failure_categories", categories)


@runtime_checkable
class RetryJitterSource(Protocol):
    """Entropy source used only when a retry policy requests jitter."""

    def full_jitter(self, upper_bound_seconds: float) -> float:
        """Return a delay in the inclusive range [0, upper_bound_seconds]."""


class SystemRetryJitterSource:
    """System-random jitter source for production runtime use."""

    def __init__(self) -> None:
        self._random = SystemRandom()

    def full_jitter(self, upper_bound_seconds: float) -> float:
        _validate_non_negative_number(
            upper_bound_seconds,
            field_name="upper_bound_seconds",
        )
        if upper_bound_seconds == 0:
            return 0.0
        return self._random.uniform(0.0, upper_bound_seconds)


@dataclass(frozen=True, slots=True)
class RetryEvaluation:
    """Structured evidence explaining one retry disposition."""

    decision: RetryDecision
    reason: str
    delay_seconds: float
    attempt_number: int
    max_attempts: int
    failure_category: FailureCategory
    retryability: Retryability
    uncertainty: OutcomeUncertainty
    budget_remaining_seconds: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.decision, RetryDecision):
            raise TypeError("decision must be a RetryDecision")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must not be empty")
        _validate_non_negative_number(self.delay_seconds, field_name="delay_seconds")
        if isinstance(self.attempt_number, bool) or not isinstance(self.attempt_number, int):
            raise TypeError("attempt_number must be an integer")
        if self.attempt_number < 1:
            raise ValueError("attempt_number must be greater than or equal to 1")
        if isinstance(self.max_attempts, bool) or not isinstance(self.max_attempts, int):
            raise TypeError("max_attempts must be an integer")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be greater than or equal to 1")
        if not isinstance(self.failure_category, FailureCategory):
            raise TypeError("failure_category must be a FailureCategory")
        if not isinstance(self.retryability, Retryability):
            raise TypeError("retryability must be a Retryability")
        if not isinstance(self.uncertainty, OutcomeUncertainty):
            raise TypeError("uncertainty must be an OutcomeUncertainty")
        if self.budget_remaining_seconds is not None:
            _validate_non_negative_number(
                self.budget_remaining_seconds,
                field_name="budget_remaining_seconds",
            )


class RetryEvaluator:
    """Pure evidence-driven retry decision service."""

    def __init__(self, *, jitter_source: RetryJitterSource | None = None) -> None:
        source = jitter_source or SystemRetryJitterSource()
        if not isinstance(source, RetryJitterSource):
            raise TypeError("jitter_source must satisfy RetryJitterSource")
        self._jitter_source = source

    def evaluate(
        self,
        *,
        policy: RetryPolicy,
        failure: FailureEvidence,
        attempt_number: int,
        elapsed_seconds: float,
    ) -> RetryEvaluation:
        if not isinstance(policy, RetryPolicy):
            raise TypeError("policy must be a V2 RetryPolicy")
        if not isinstance(failure, FailureEvidence):
            raise TypeError("failure must be FailureEvidence")
        if isinstance(attempt_number, bool) or not isinstance(attempt_number, int):
            raise TypeError("attempt_number must be an integer")
        if attempt_number < 1:
            raise ValueError("attempt_number must be greater than or equal to 1")
        _validate_non_negative_number(elapsed_seconds, field_name="elapsed_seconds")

        if (
            failure.uncertainty is not OutcomeUncertainty.KNOWN
            or failure.retryability is Retryability.RETRYABLE_AFTER_RECONCILIATION
            or failure.category is FailureCategory.UNKNOWN_OUTCOME
        ):
            decision = (
                RetryDecision.RECONCILE
                if policy.reconciliation_required
                else RetryDecision.ESCALATE
            )
            reason = (
                "uncertain_outcome_requires_reconciliation"
                if decision is RetryDecision.RECONCILE
                else "uncertain_outcome_escalated"
            )
            return self._evaluation(
                policy=policy,
                failure=failure,
                attempt_number=attempt_number,
                decision=decision,
                reason=reason,
                delay_seconds=0.0,
                elapsed_seconds=elapsed_seconds,
            )

        if attempt_number >= policy.max_attempts:
            return self._evaluation(
                policy=policy,
                failure=failure,
                attempt_number=attempt_number,
                decision=RetryDecision.DO_NOT_RETRY,
                reason="max_attempts_exhausted",
                delay_seconds=0.0,
                elapsed_seconds=elapsed_seconds,
            )

        if failure.retryability is Retryability.NON_RETRYABLE:
            return self._evaluation(
                policy=policy,
                failure=failure,
                attempt_number=attempt_number,
                decision=RetryDecision.DO_NOT_RETRY,
                reason="failure_marked_non_retryable",
                delay_seconds=0.0,
                elapsed_seconds=elapsed_seconds,
            )

        if failure.retryability is Retryability.UNKNOWN:
            return self._evaluation(
                policy=policy,
                failure=failure,
                attempt_number=attempt_number,
                decision=RetryDecision.DO_NOT_RETRY,
                reason="retryability_unknown",
                delay_seconds=0.0,
                elapsed_seconds=elapsed_seconds,
            )

        if (
            policy.retryable_failure_categories
            and failure.category not in policy.retryable_failure_categories
        ):
            return self._evaluation(
                policy=policy,
                failure=failure,
                attempt_number=attempt_number,
                decision=RetryDecision.DO_NOT_RETRY,
                reason="failure_category_not_retryable",
                delay_seconds=0.0,
                elapsed_seconds=elapsed_seconds,
            )

        delay_seconds = self._delay(
            policy=policy,
            failed_attempt_number=attempt_number,
        )
        if (
            policy.total_budget_seconds is not None
            and elapsed_seconds + delay_seconds > policy.total_budget_seconds
        ):
            return self._evaluation(
                policy=policy,
                failure=failure,
                attempt_number=attempt_number,
                decision=RetryDecision.DO_NOT_RETRY,
                reason="retry_budget_exhausted",
                delay_seconds=0.0,
                elapsed_seconds=elapsed_seconds,
            )

        return self._evaluation(
            policy=policy,
            failure=failure,
            attempt_number=attempt_number,
            decision=RetryDecision.RETRY,
            reason="structured_failure_retryable",
            delay_seconds=delay_seconds,
            elapsed_seconds=elapsed_seconds,
        )

    def _delay(
        self,
        *,
        policy: RetryPolicy,
        failed_attempt_number: int,
    ) -> float:
        strategy = policy.backoff_strategy
        initial = float(policy.initial_delay_seconds)

        if strategy is BackoffStrategy.NONE:
            delay = 0.0
        elif strategy is BackoffStrategy.FIXED:
            delay = initial
        elif strategy is BackoffStrategy.LINEAR:
            delay = initial * failed_attempt_number
        elif strategy is BackoffStrategy.EXPONENTIAL:
            delay = initial * (2 ** (failed_attempt_number - 1))
        else:  # pragma: no cover - enum exhaustiveness guard
            raise RuntimeError(f"unsupported BackoffStrategy {strategy!r}")

        if policy.max_delay_seconds is not None:
            delay = min(delay, float(policy.max_delay_seconds))

        if policy.jitter is RetryJitter.FULL:
            delay = self._jitter_source.full_jitter(delay)

        return delay

    @staticmethod
    def _evaluation(
        *,
        policy: RetryPolicy,
        failure: FailureEvidence,
        attempt_number: int,
        decision: RetryDecision,
        reason: str,
        delay_seconds: float,
        elapsed_seconds: float,
    ) -> RetryEvaluation:
        remaining: float | None = None
        if policy.total_budget_seconds is not None:
            remaining = max(0.0, policy.total_budget_seconds - elapsed_seconds)

        return RetryEvaluation(
            decision=decision,
            reason=reason,
            delay_seconds=delay_seconds,
            attempt_number=attempt_number,
            max_attempts=policy.max_attempts,
            failure_category=failure.category,
            retryability=failure.retryability,
            uncertainty=failure.uncertainty,
            budget_remaining_seconds=remaining,
        )


V2_RETRY_CONTRACT_VERSION = "1"


def v2_retry_contract_snapshot() -> dict[str, object]:
    return {
        "contract_version": V2_RETRY_CONTRACT_VERSION,
        "decisions": [value.value for value in RetryDecision],
        "backoff_strategies": [value.value for value in BackoffStrategy],
        "jitter_strategies": [value.value for value in RetryJitter],
        "policy_fields": [
            "max_attempts",
            "backoff_strategy",
            "initial_delay_seconds",
            "max_delay_seconds",
            "jitter",
            "retryable_failure_categories",
            "total_budget_seconds",
            "reconciliation_required",
        ],
    }


__all__ = [
    "RetryDecision",
    "RetryEvaluation",
    "RetryEvaluator",
    "RetryJitter",
    "RetryJitterSource",
    "RetryPolicy",
    "SystemRetryJitterSource",
    "V2_RETRY_CONTRACT_VERSION",
    "v2_retry_contract_snapshot",
]
