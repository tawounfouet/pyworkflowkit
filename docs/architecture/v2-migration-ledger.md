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
| `domain.definitions` | MOVE + ADAPT | authoring | 02 | PLANNED |
| `declarative` | SPLIT | authoring | 02 | PLANNED |
| `domain.graph` | MOVE + INTERNALIZE | planning | 03 | PLANNED |
| `application.planning` | MOVE + ADAPT | planning | 03 | PLANNED |
| `domain.runtime` | SPLIT | runtime | 04/06 | PLANNED |
| `domain.enums` | SPLIT | states/policies | 04/07/08 | PLANNED |
| `domain.values` | SPLIT | policies/runtime/lineage | 01/07/12 | IN_PROGRESS |
| `application.runtime` | MOVE + ADAPT | runtime | 06 | PLANNED |
| `application.runner` | INTERNALIZE | runtime internals | 06 | PLANNED |
| `application.state_machine` | MOVE | states | 04 | PLANNED |
| `application.retry` | SPLIT | policies/runtime internals | 07 | PLANNED |
| `ports.executor` | REWRITE | executors | 06 | PLANNED |
| `adapters.executors.local` | RENAME + ADAPT | executors.inline | 06 | PLANNED |
| other executor adapters | MOVE + ADAPT | executors | 13/14 | PLANNED |
| `ports.metadata_store` | MOVE + ADAPT | persistence | 05 | PLANNED |
| metadata adapters | MOVE + MIGRATE | persistence | 05/10/17 | PLANNED |
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
