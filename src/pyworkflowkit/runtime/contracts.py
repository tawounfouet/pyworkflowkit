"""Machine-readable LOT-06 V2 runtime MVP contract."""

V2_RUNTIME_MVP_CONTRACT_VERSION = "4"

V2_RUNTIME_MVP_SURFACE: tuple[str, ...] = (
    "TaskOutcome",
    "WorkflowResult",
    "WorkflowRuntime",
)

V2_RUNTIME_MVP_RUN_INPUTS: tuple[str, ...] = (
    "WorkflowDefinition",
    "ExecutionPlan",
)


def v2_runtime_mvp_contract_snapshot() -> dict[str, object]:
    return {
        "contract_version": V2_RUNTIME_MVP_CONTRACT_VERSION,
        "surface": list(V2_RUNTIME_MVP_SURFACE),
        "run_inputs": list(V2_RUNTIME_MVP_RUN_INPUTS),
        "retry_execution": True,
        "timeout_execution": True,
        "cancellation_commands": True,
        "external_run_evidence": "attempt_scoped",
        "unknown_outcome_blind_retry": False,
        "cancellation_external_run_evidence": True,
        "durable_outputs": True,
        "basic_events": "semantic_projection_from_state_transitions",
        "executor_routing": "registry",
        "multi_executor_routing": True,
        "thread_executor": True,
    }


__all__ = [
    "V2_RUNTIME_MVP_CONTRACT_VERSION",
    "V2_RUNTIME_MVP_RUN_INPUTS",
    "V2_RUNTIME_MVP_SURFACE",
    "v2_runtime_mvp_contract_snapshot",
]
