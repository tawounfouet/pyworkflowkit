"""LOT-02 timeout-policy and trigger-rule skeleton tests."""

from __future__ import annotations

import pytest

from pyworkflowkit.policies import TimeoutPolicy, TriggerRule


def test_timeout_policy_is_optional_and_positive_when_present() -> None:
    assert TimeoutPolicy().execution_timeout is None
    assert TimeoutPolicy(execution_timeout=2.5).execution_timeout == 2.5

    with pytest.raises(ValueError):
        TimeoutPolicy(execution_timeout=0)

    with pytest.raises(ValueError):
        TimeoutPolicy(execution_timeout=float("inf"))


def test_trigger_rule_vocabulary_is_frozen_for_authoring() -> None:
    assert {value.value for value in TriggerRule} == {
        "all_success",
        "all_done",
        "any_success",
        "any_failed",
        "none_failed",
        "always",
    }
