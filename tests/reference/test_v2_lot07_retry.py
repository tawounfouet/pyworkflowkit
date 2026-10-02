"""LOT-07 reference acceptance for V2 retry semantics."""

from __future__ import annotations

import pyworkflowkit
from pyworkflowkit.diagnostics import (
    FailureCategory,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.domain.values import RetryPolicy as LegacyRetryPolicy
from pyworkflowkit.executors import InlineExecutor
from pyworkflowkit.policies import (
    V2_RETRY_CONTRACT_VERSION,
    BackoffStrategy,
    RetryDecision,
    RetryEvaluation,
    RetryEvaluator,
    RetryJitter,
    RetryPolicy,
    v2_retry_contract_snapshot,
)
from pyworkflowkit.runtime import RetryWaiter, SystemRetryWaiter


def test_v2_retry_contract_snapshot_is_machine_readable() -> None:
    snapshot = v2_retry_contract_snapshot()

    assert snapshot["contract_version"] == V2_RETRY_CONTRACT_VERSION
    assert snapshot["decisions"] == [value.value for value in RetryDecision]
    assert snapshot["backoff_strategies"] == [value.value for value in BackoffStrategy]
    assert snapshot["jitter_strategies"] == [value.value for value in RetryJitter]
    assert "total_budget_seconds" in snapshot["policy_fields"]
    assert "reconciliation_required" in snapshot["policy_fields"]


def test_v2_retry_policy_is_distinct_from_frozen_v1_root_policy() -> None:
    assert RetryPolicy is not LegacyRetryPolicy
    assert pyworkflowkit.RetryPolicy is LegacyRetryPolicy


def test_retry_evaluation_is_structured_not_boolean_only() -> None:
    fields = set(RetryEvaluation.__dataclass_fields__)

    assert {
        "decision",
        "reason",
        "delay_seconds",
        "attempt_number",
        "max_attempts",
        "failure_category",
        "retryability",
        "uncertainty",
        "budget_remaining_seconds",
    } <= fields
    assert RetryEvaluator is not None


def test_inline_executor_declares_no_hidden_workload_retry() -> None:
    descriptor = InlineExecutor().descriptor

    assert descriptor.performs_implicit_workload_retry is False


def test_retry_wait_boundary_is_explicit() -> None:
    waiter = SystemRetryWaiter()

    assert isinstance(waiter, RetryWaiter)


def test_failure_taxonomy_used_by_retry_remains_structured() -> None:
    assert FailureCategory.TRANSIENT.value == "transient"
    assert Retryability.RETRYABLE.value == "retryable"
    assert OutcomeUncertainty.REQUIRES_RECONCILIATION.value == "requires_reconciliation"
