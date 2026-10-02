"""Typed retry-decision vocabulary for the V2 runtime."""

from enum import StrEnum


class RetryDecision(StrEnum):
    """Runtime disposition after evaluating structured failure evidence."""

    RETRY = "retry"
    DO_NOT_RETRY = "do_not_retry"
    RECONCILE = "reconcile"
    ABORT = "abort"
    CANCEL = "cancel"
    ESCALATE = "escalate"


__all__ = ["RetryDecision"]
