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
| `domain.runtime` | SPLIT | runtime | 04/06 | IMPLEMENTED |
| `domain.enums` | SPLIT | states/policies | 04/07/08 | IMPLEMENTED |
| `domain.values` | SPLIT | policies/runtime/lineage | 01/07/09/12 | IN_PROGRESS |
| `application.runtime` | MOVE + ADAPT | runtime | 06 | IMPLEMENTED |
| `application.runner` | INTERNALIZE | runtime internals | 06 | IMPLEMENTED |
| `application.state_machine` | MOVE | states | 04 | IMPLEMENTED |
| `application.retry` | SPLIT | policies/runtime internals | 07 | IMPLEMENTED |
| `ports.executor` | REWRITE | executors | 06 | IMPLEMENTED |
| `adapters.executors.local` | RENAME + ADAPT | executors.inline | 06 | IMPLEMENTED |
| other executor adapters | MOVE + ADAPT | executors | 13/14 | PLANNED |
| `ports.metadata_store` | MOVE + ADAPT | persistence | 05 | IMPLEMENTED |
| metadata adapters | MOVE + MIGRATE | persistence | 05/10/17 | IN_PROGRESS |
| SQLAlchemy models/mapping | MOVE + INTERNALIZE | persistence._sqlalchemy | 10/17 | IN_PROGRESS |
| Alembic 0001–0003 | KEEP IMMUTABLE | persistence migrations | 10/17 | QUALIFIED BASELINE |
| Alembic 0004 V2 runtime metadata | ADD | persistence migrations | 10 | IMPLEMENTED |
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


## LOT-06 delivered contracts

| Contract | Canonical V2 path | Status |
|---|---|---|
| `Executor` Protocol | `pyworkflowkit.executors` | IMPLEMENTED |
| `ExecutorDescriptor` | `pyworkflowkit.executors` | IMPLEMENTED |
| `TaskExecutionContext` | `pyworkflowkit.executors` | IMPLEMENTED |
| `TaskExecutionRequest` | `pyworkflowkit.executors` | IMPLEMENTED |
| `TaskExecutionResult` | `pyworkflowkit.executors` | IMPLEMENTED |
| `InlineExecutor` | `pyworkflowkit.executors` | IMPLEMENTED |
| `WorkflowRuntime` V2 | `pyworkflowkit.runtime` | IMPLEMENTED |
| `TaskOutcome` | `pyworkflowkit.runtime` | IMPLEMENTED |
| `WorkflowResult` | `pyworkflowkit.runtime` | IMPLEMENTED |
| WorkflowDefinition input | WorkflowRuntime.run | IMPLEMENTED |
| ExecutionPlan input | WorkflowRuntime.run | IMPLEMENTED |
| readiness evaluation | runtime internals | IMPLEMENTED |
| fail-fast propagation | runtime internals | IMPLEMENTED |
| trigger-rule skip | runtime internals | IMPLEMENTED |
| one-attempt execution | runtime internals | IMPLEMENTED |
| basic event evidence | MetadataStore state history | IMPLEMENTED |

The canonical V2 runtime does not call the legacy 1.1 Runner. The old application/runtime,
Runner and LocalExecutor remain intact only for the frozen 1.1 public root and migration
evidence.

LOT-06 intentionally fails closed when a task requests retry execution or timeout execution:
retry behavior starts in LOT-07 and timeout/cancellation semantics in LOT-08.

Task outputs are caller-visible process-local values in the MVP result but are not yet
declared durable. Portable/durable output policy is owned by LOT-12.


## LOT-07 delivered contracts

| Contract | Canonical V2 path | Status |
|---|---|---|
| V2 RetryPolicy | pyworkflowkit.policies | IMPLEMENTED |
| RetryDecision vocabulary | pyworkflowkit.policies | IMPLEMENTED |
| RetryEvaluation | pyworkflowkit.policies | IMPLEMENTED |
| RetryEvaluator | pyworkflowkit.policies | IMPLEMENTED |
| RetryJitter | pyworkflowkit.policies | IMPLEMENTED |
| retry budget | RetryPolicy.total_budget_seconds | IMPLEMENTED |
| reconciliation requirement | RetryPolicy.reconciliation_required | IMPLEMENTED |
| fixed/linear/exponential backoff | RetryEvaluator | IMPLEMENTED |
| full jitter | RetryEvaluator | IMPLEMENTED |
| injectable RetryWaiter | pyworkflowkit.runtime | IMPLEMENTED |
| same-TaskRun/new-TaskAttempt retry | WorkflowRuntime | IMPLEMENTED |
| retry diagnostics | WorkflowResult.diagnostics | IMPLEMENTED |
| retry amplification guard | ExecutorDescriptor / WorkflowRuntime | IMPLEMENTED |
| uncertainty-first decision | WorkflowRuntime | IMPLEMENTED |

The V2 RetryPolicy is intentionally distinct from the frozen 1.1 root RetryPolicy.
The stable 1.1 package root continues to expose pyworkflowkit.domain.values.RetryPolicy,
while V2 authoring and planning use pyworkflowkit.policies.RetryPolicy.

Retry evaluates structured FailureEvidence. Raw message matching is not used as the
primary retry contract.

UNKNOWN_OUTCOME and RETRYABLE_AFTER_RECONCILIATION never schedule a blind fresh attempt.
They produce RECONCILE when automatic reconciliation is required, otherwise ESCALATE,
while the WorkflowRun remains UNKNOWN_OUTCOME.

A retry preserves TaskRunId and allocates a fresh TaskAttemptId. The TaskRun stays RUNNING
until the task succeeds or retry is exhausted/non-retryable.


## LOT-08 delivered contracts

| Contract | Canonical V2 path | Status |
|---|---|---|
| TimeoutPolicy executable deadline | pyworkflowkit.policies | IMPLEMENTED |
| TaskExecutionRequest.deadline_at | pyworkflowkit.executors | IMPLEMENTED |
| CancellationCapability | pyworkflowkit.executors | IMPLEMENTED |
| CancellationStatus | pyworkflowkit.executors | IMPLEMENTED |
| TaskCancellationRequest | pyworkflowkit.executors | IMPLEMENTED |
| TaskCancellationResult | pyworkflowkit.executors | IMPLEMENTED |
| CancellableExecutor capability Protocol | pyworkflowkit.executors | IMPLEMENTED |
| WorkflowRuntime.cancel | pyworkflowkit.runtime | IMPLEMENTED |
| WorkflowRuntime.cancel_task | pyworkflowkit.runtime | IMPLEMENTED |
| CancellationResult | pyworkflowkit.runtime | IMPLEMENTED |
| confirmed timeout state mapping | runtime/state machines | IMPLEMENTED |
| uncertain timeout reconciliation mapping | runtime/state machines | IMPLEMENTED |
| cancellation request/confirmation distinction | runtime/state machines | IMPLEMENTED |
| unsupported cancellation result | runtime/executor capability | IMPLEMENTED |
| already-terminal idempotence | runtime cancellation API | IMPLEMENTED |

InlineExecutor explicitly declares that it does not enforce execution deadlines and does
not support active cancellation. WorkflowRuntime therefore rejects TimeoutPolicy for
InlineExecutor instead of pretending that synchronous same-thread execution can be
interrupted safely.

Executors that support deadlines receive an absolute timezone-aware deadline through
TaskExecutionRequest.deadline_at. A known stopped timeout maps to TIMED_OUT; an uncertain
timeout remains UNKNOWN_OUTCOME / REQUIRES_RECONCILIATION.

Cancellation commands return structured status rather than bool. REQUESTED, CONFIRMED,
UNSUPPORTED, UNCONFIRMED and ALREADY_TERMINAL are semantically distinct.



## LOT-09 delivered contracts

| Contract | Canonical V2 path | Status |
|---|---|---|
| attempt-scoped ExternalRunRef evidence | pyworkflowkit.persistence | IMPLEMENTED |
| TaskExecutionResult.external_runs | pyworkflowkit.executors | IMPLEMENTED |
| TaskCancellationResult.external_runs | pyworkflowkit.executors | IMPLEMENTED |
| FailureEvidence.external_run persistence | WorkflowRuntime | IMPLEMENTED |
| executor-result external evidence persistence | WorkflowRuntime | IMPLEMENTED |
| cancellation-result external evidence persistence | WorkflowRuntime | IMPLEMENTED |
| per-attempt external identity across retries | MetadataStore / WorkflowRuntime | IMPLEMENTED |
| UNKNOWN_OUTCOME no-blind-retry invariant | RetryEvaluator / WorkflowRuntime | IMPLEMENTED |
| duplicate reference suppression per attempt | WorkflowRuntime | IMPLEMENTED |

External execution identifiers are evidence, not authority. PyWorkflowKit does not copy
the provider state machine. It preserves provider + kind + external_run_id on the exact
TaskAttempt that created the foreign execution.

An uncertain external outcome therefore keeps the current attempt as the reconciliation
target. The runtime persists available ExternalRunRef evidence before returning
UNKNOWN_OUTCOME / REQUIRES_RECONCILIATION and does not create a fresh TaskAttempt until
later reconciliation establishes that retry is safe.

LOT-09 remains process-local because the canonical V2 store is still
InMemoryMetadataStore. Durable restart-safe evidence is owned by LOT-10.



## LOT-10 delivered contracts

| Contract | Canonical V2 path | Status |
|---|---|---|
| SQLiteMetadataStore | pyworkflowkit.persistence | IMPLEMENTED |
| SQLiteSettings | pyworkflowkit.persistence | IMPLEMENTED |
| internal V2 SQLAlchemy Base | pyworkflowkit.persistence._sqlalchemy | IMPLEMENTED |
| V2 relational runtime rows | pyworkflowkit.persistence._sqlalchemy | IMPLEMENTED |
| V2 domain ↔ relational mapping | pyworkflowkit.persistence._sqlalchemy | IMPLEMENTED |
| Alembic 0004_v2_runtime_metadata | pyworkflowkit.migrations | IMPLEMENTED |
| WorkflowRun durable persistence | SQLiteMetadataStore | IMPLEMENTED |
| TaskRun durable persistence | SQLiteMetadataStore | IMPLEMENTED |
| TaskAttempt durable persistence | SQLiteMetadataStore | IMPLEMENTED |
| attempt-scoped ExternalRunRef durability | SQLiteMetadataStore | IMPLEMENTED |
| FailureEvidence durable JSON mapping | SQLiteMetadataStore | IMPLEMENTED |
| CorrelationContext durable JSON mapping | SQLiteMetadataStore | IMPLEMENTED |
| append-only state transition durability | SQLiteMetadataStore | IMPLEMENTED |
| ManifestReference durability | SQLiteMetadataStore | IMPLEMENTED |
| compare-and-set status writes | SQLiteMetadataStore | IMPLEMENTED |
| restart/reopen acceptance | tests/contract | IMPLEMENTED |
| reusable MetadataStore conformance suite | tests/contract | IMPLEMENTED |

LOT-10 extends the existing migration lineage without mutating the published 0001–0003
sources. The new V2 relational tables are deliberately separate from the legacy 1.1
tables, allowing both persistence models to coexist during the 1.1 → 2.0 migration.

SQLite now provides durable evidence for UNKNOWN_OUTCOME and
REQUIRES_RECONCILIATION. LOT-11 can therefore perform recovery and external
reconciliation from evidence loaded after process restart.



## LOT-11 delivered contracts

| Contract | Canonical V2 path | Status |
|---|---|---|
| RecoveryDisposition | pyworkflowkit.diagnostics | IMPLEMENTED |
| TaskRecoveryAssessment | pyworkflowkit.diagnostics | IMPLEMENTED |
| RecoveryAssessment | pyworkflowkit.diagnostics | IMPLEMENTED |
| RecoveryInspector | pyworkflowkit.diagnostics | IMPLEMENTED |
| ExternalRunStatus | pyworkflowkit.runtime | IMPLEMENTED |
| ExternalRunVerifier | pyworkflowkit.runtime | IMPLEMENTED |
| ExternalRunVerifierRegistry | pyworkflowkit.runtime | IMPLEMENTED |
| ExternalRunObservation | pyworkflowkit.runtime | IMPLEMENTED |
| ReconciliationDisposition | pyworkflowkit.runtime | IMPLEMENTED |
| TaskReconciliation | pyworkflowkit.runtime | IMPLEMENTED |
| ReconciliationReport | pyworkflowkit.runtime | IMPLEMENTED |
| ReconciliationService | pyworkflowkit.runtime | IMPLEMENTED |
| WorkflowRuntime.recovery_assessment | pyworkflowkit.runtime | IMPLEMENTED |
| WorkflowRuntime.recovery_candidates | pyworkflowkit.runtime | IMPLEMENTED |
| WorkflowRuntime.register_external_run_verifier | pyworkflowkit.runtime | IMPLEMENTED |
| WorkflowRuntime.reconcile_run | pyworkflowkit.runtime | IMPLEMENTED |
| same-attempt provider reconciliation | runtime/state machines | IMPLEMENTED |
| terminal-attempt local repair | runtime/state machines | IMPLEMENTED |
| secret-safe verifier failures | runtime reconciliation | IMPLEMENTED |
| SQLite restart reconciliation | tests/integration | IMPLEMENTED |
| no-blind-retry acceptance | tests/unit + integration | IMPLEMENTED |

LOT-11 does not introduce a new persistence schema revision. It consumes the durable
runtime evidence introduced by LOT-10.

Provider truth is queried only through explicitly registered verifiers. Missing,
conflicting, NOT_FOUND, UNKNOWN, or verifier-failure evidence remains manual rather than
being converted into an invented task outcome.

A conclusive provider status is applied to the exact TaskAttempt that owns the
ExternalRunRef. LOT-11 never creates Attempt N+1.

When reconciliation resolves the ambiguous task but downstream work remains, an
UNKNOWN_OUTCOME WorkflowRun returns to RUNNING. Automatic workflow resume remains outside
LOT-11. LOT-12 owns the richer V2 event, manifest, lineage, inspection, and durable-output
evidence model.
