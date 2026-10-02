"""Typed task readiness trigger rules."""

from enum import StrEnum


class TriggerRule(StrEnum):
    ALL_SUCCESS = "all_success"
    ALL_DONE = "all_done"
    ANY_SUCCESS = "any_success"
    ANY_FAILED = "any_failed"
    NONE_FAILED = "none_failed"
    ALWAYS = "always"


__all__ = ["TriggerRule"]
