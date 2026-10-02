"""Machine-readable LOT-06 V2 runtime MVP contract."""

V2_RUNTIME_MVP_CONTRACT_VERSION = "2"

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
        "durable_outputs": False,
        "basic_events": "metadata_state_transitions",
    }


__all__ = [
    "V2_RUNTIME_MVP_CONTRACT_VERSION",
    "V2_RUNTIME_MVP_RUN_INPUTS",
    "V2_RUNTIME_MVP_SURFACE",
    "v2_runtime_mvp_contract_snapshot",
]
