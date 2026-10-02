# PyWorkflowKit V2 — Migration Ledger

This ledger is the implementation control surface for the 1.1 → 2.0 migration.

## Status vocabulary

```text
PLANNED
IN_PROGRESS
IMPLEMENTED
QUALIFIED
MERGED
DEFERRED
REMOVED
```

## Component ledger

| V1 path / concept | V2 action | Canonical V2 owner | LOT | V2 status |
|---|---|---|---:|---|
| `pyworkflowkit.__init__` | ADAPT later | root facade | 00/22 | IN_PROGRESS |
| `domain.definitions` | MOVE + ADAPT | authoring | 02 | IMPLEMENTED |
| `declarative` | SPLIT | authoring | 02 | IMPLEMENTED |
| `domain.graph` | MOVE + INTERNALIZE | planning | 03 | IMPLEMENTED |
| `application.planning` | MOVE + ADAPT | planning | 03 | IMPLEMENTED |
| `domain.runtime` | SPLIT | runtime | 04/06 | IN_PROGRESS |
| `domain.enums` | SPLIT | states/policies | 04/07/08 | IN_PROGRESS |
| `domain.values` | SPLIT | policies/runtime/lineage | 01/07/12 | IN_PROGRESS |
| `application.runtime` | MOVE + ADAPT | runtime | 06 | PLANNED |
| `application.runner` | INTERNALIZE | runtime internals | 06 | PLANNED |
| `application.state_machine` | MOVE | states | 04 | IMPLEMENTED |
| `application.retry` | SPLIT | policies/runtime internals | 07 | PLANNED |
| `ports.executor` | REWRITE | executors | 06 | PLANNED |
| `adapters.executors.local` | RENAME + ADAPT | executors.inline | 06 | PLANNED |
| other executor adapters | MOVE + ADAPT | executors | 13/14 | PLANNED |
| `ports.metadata_store` | MOVE + ADAPT | persistence | 05 | IMPLEMENTED |
| metadata adapters | MOVE + MIGRATE | persistence | 05/10/17 | IN_PROGRESS |
| SQLAlchemy models/mapping | MOVE + INTERNALIZE | persistence._sqlalchemy | 10/17 | PLANNED |
| Alembic 0001–0003 | KEEP IMMUTABLE | persistence migrations | 10/17 | QUALIFIED BASELINE |
| `contracts.serialization` | MOVE + REBUILD | serialization | 15 | PLANNED |
| lineage modules | MOVE | lineage | 12 | PLANNED |
| `application.inspection` | MOVE | diagnostics | 11/12 | PLANNED |
| `plugins` | KEEP + ADAPT | plugins | 16 | PLANNED |
| `control_plane` | KEEP PROVISIONAL | control_plane | later | DEFERRED |
| `ecosystem` | DEPRECATE AS CANONICAL | compatibility | 21 | PLANNED |
| PyIngestKit integration | EXPAND | integrations.pyingestkit | 18 | PLANNED |
| PyTransformKit integration | NEW | integrations.pytransformkit | 19 | PLANNED |
| `compatibility.py` | MOVE/SHIM | _compat | 21 | PLANNED |

## Rewrite hotspots

Only rewrite aggressively where semantics conflict with V2:

```text
Executor Protocol
TaskDefinition workload boundary
WorkflowRuntime.run() result contract
RunContext
TaskResult
Timeout public contract
durable wire contracts
ExternalRunRef attempt ownership
```

## High-value reuse

Do not rewrite casually:

```text
run/task/attempt identity model
DAG validation and deterministic ordering
MetadataStore + UnitOfWork architecture
SQLite/PostgreSQL experience
advanced executor mechanics
events/manifests/lineage foundations
retry/recovery/reconciliation behavior
plugin discovery infrastructure
CLI/DX qualification assets
```


## LOT-01 delivered contracts

| Contract | Canonical V2 path | Status |
|---|---|---|
| `WorkflowRunId` | `pyworkflowkit.runtime` | IMPLEMENTED |
| `TaskRunId` | `pyworkflowkit.runtime` | IMPLEMENTED |
| `TaskAttemptId` | `pyworkflowkit.runtime` | IMPLEMENTED |
| `CorrelationId` | `pyworkflowkit.runtime` | IMPLEMENTED |
| `CorrelationContext` | `pyworkflowkit.runtime` | IMPLEMENTED |
| `WorkflowExecutionReference` | `pyworkflowkit.runtime` | IMPLEMENTED |
| V2 `ExternalRunRef` | `pyworkflowkit.runtime` | IMPLEMENTED |
| `FailureCategory` | `pyworkflowkit.diagnostics` | IMPLEMENTED |
| `Retryability` | `pyworkflowkit.diagnostics` | IMPLEMENTED |
| `OutcomeUncertainty` | `pyworkflowkit.diagnostics` | IMPLEMENTED |
| `FailureEvidence` | `pyworkflowkit.diagnostics` | IMPLEMENTED |
| `DiagnosticSeverity` | `pyworkflowkit.diagnostics` | IMPLEMENTED |
| `Diagnostic` | `pyworkflowkit.diagnostics` | IMPLEMENTED |
| `RetryDecision` skeleton | `pyworkflowkit.policies` | IMPLEMENTED |
| boundary wire descriptors | `pyworkflowkit.serialization` | IMPLEMENTED |

These contracts are qualified V2 values but are not yet all wired into the durable
1.1 runtime implementation. LOT-04, LOT-06, LOT-07, LOT-09 and LOT-15 progressively
replace the remaining legacy runtime/persistence/wire usage.


## LOT-02 delivered contracts

| Contract | Canonical V2 path | Status |
|---|---|---|
| `WorkflowDefinition` | `pyworkflowkit.authoring` | IMPLEMENTED |
| `TaskDefinition` | `pyworkflowkit.authoring` | IMPLEMENTED |
| `WorkflowDefinitionBuilder` | `pyworkflowkit.authoring` | IMPLEMENTED |
| `RegisteredWorkload` | `pyworkflowkit.authoring` | IMPLEMENTED |
| `WorkloadDescriptor` | `pyworkflowkit.authoring` | IMPLEMENTED |
| `WorkloadPortability` | `pyworkflowkit.authoring` | IMPLEMENTED |
| `InputDeclaration` | `pyworkflowkit.authoring` | IMPLEMENTED |
| `OutputDeclaration` | `pyworkflowkit.authoring` | IMPLEMENTED |
| V2 `task` decorator | `pyworkflowkit.authoring` | IMPLEMENTED |
| V2 `workflow` decorator | `pyworkflowkit.authoring` | IMPLEMENTED |
| `TimeoutPolicy` skeleton | `pyworkflowkit.policies` | IMPLEMENTED |
| `TriggerRule` | `pyworkflowkit.policies` | IMPLEMENTED |
| definition fingerprint | `WorkflowDefinition.fingerprint()` | IMPLEMENTED |
| definition inspection | `WorkflowDefinition.explain()` | IMPLEMENTED |

The frozen 1.1 root continues to expose the legacy definition/declarative classes.
Canonical V2 code must use the qualified `pyworkflowkit.authoring` surface until the
root migration/freeze is completed.


## LOT-03 delivered contracts

| Contract | Canonical V2 path | Status |
|---|---|---|
| `WorkflowPlanner` | `pyworkflowkit.planning` | IMPLEMENTED |
| `ExecutionPlan` | `pyworkflowkit.planning` | IMPLEMENTED |
| `TaskPlanEntry` | `pyworkflowkit.planning` | IMPLEMENTED |
| `ExecutorRequirement` | `pyworkflowkit.planning` | IMPLEMENTED |
| deterministic topological ordering | planning internals | IMPLEMENTED |
| deterministic execution groups | planning internals | IMPLEMENTED |
| policy normalization | `TaskPlanEntry` | IMPLEMENTED |
| executor requirement extraction | `ExecutorRequirement` | IMPLEMENTED |
| integration requirement extraction | `ExecutionPlan.required_integrations` | IMPLEMENTED |
| structured planning diagnostics | `ExecutionPlan.diagnostics` | IMPLEMENTED |
| plan fingerprint | `ExecutionPlan.fingerprint()` | IMPLEMENTED |
| plan inspection | `ExecutionPlan.explain()` | IMPLEMENTED |
| internal dependency graph | `pyworkflowkit.planning._graph` | IMPLEMENTED |

The qualified V2 planning namespace now replaces the LOT-00 compatibility re-export.
The frozen 1.1 package root remains unchanged. Runtime integration with V2 ExecutionPlan
is owned by LOT-06.


## LOT-04 delivered contracts

| Contract | Canonical V2 path | Status |
|---|---|---|
| `WorkflowRun` | `pyworkflowkit.runtime` | IMPLEMENTED |
| `TaskRun` | `pyworkflowkit.runtime` | IMPLEMENTED |
| `TaskAttempt` | `pyworkflowkit.runtime` | IMPLEMENTED |
| `WorkflowRunStatus` | `pyworkflowkit.states` | IMPLEMENTED |
| `TaskRunStatus` | `pyworkflowkit.states` | IMPLEMENTED |
| `TaskAttemptStatus` | `pyworkflowkit.states` | IMPLEMENTED |
| `SkipReason` | `pyworkflowkit.states` | IMPLEMENTED |
| `BlockReason` | `pyworkflowkit.states` | IMPLEMENTED |
| `WorkflowRunStateMachine` | `pyworkflowkit.states` | IMPLEMENTED |
| `TaskRunStateMachine` | `pyworkflowkit.states` | IMPLEMENTED |
| `TaskAttemptStateMachine` | `pyworkflowkit.states` | IMPLEMENTED |
| terminal-state protection | state machines | IMPLEMENTED |
| UNKNOWN_OUTCOME semantics | state machines | IMPLEMENTED |
| cancellation-requested/unconfirmed states | state machines | IMPLEMENTED |
| attempt sequencing | `runtime._attempts` | IMPLEMENTED |
| retry identity invariant | `runtime._attempts` | IMPLEMENTED |

The qualified V2 runtime namespace now owns the V2 run entities. The legacy 1.1
WorkflowRuntime and RuntimeEvent remain transitional until LOT-06 and LOT-12.


## LOT-05 delivered contracts

| Contract | Canonical V2 path | Status |
|---|---|---|
| `MetadataStore` Protocol | `pyworkflowkit.persistence` | IMPLEMENTED |
| `InMemoryMetadataStore` | `pyworkflowkit.persistence` | IMPLEMENTED |
| store contract/schema metadata | `MetadataStore.metadata()` | IMPLEMENTED |
| WorkflowRun persistence | MetadataStore | IMPLEMENTED |
| TaskRun persistence | MetadataStore | IMPLEMENTED |
| TaskAttempt append/history | MetadataStore | IMPLEMENTED |
| compare-and-set status updates | MetadataStore | IMPLEMENTED |
| append-only state transition history | MetadataStore | IMPLEMENTED |
| ExternalRunRef per TaskAttempt | MetadataStore | IMPLEMENTED |
| unfinished WorkflowRun query | MetadataStore | IMPLEMENTED |
| provisional manifest reference hook | MetadataStore | IMPLEMENTED |
| reusable MetadataStore conformance suite | tests/contract | IMPLEMENTED |

The V2 store rejects blind last-write-wins updates. State-machine services remain the
domain authority for legal transitions; MetadataStore protects persisted identity,
expected-status concurrency and append-only execution history.

The in-memory implementation is process-local and non-durable. It supports concurrent
threads using one store instance, but does not claim process safety, crash recovery or
multi-operation atomic batches. SQLite and PostgreSQL remain LOT-10/LOT-17.
