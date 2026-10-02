# PyWorkflowKit V2 — LOT-04 Runtime State Machines

Status: implementation baseline  
Target milestone: `2.0.0a1`  
Depends on: LOT-00 → LOT-03

## Purpose

LOT-04 introduces explicit runtime identity-bearing entities and fail-closed state
machines:

```text
WorkflowRun
    └── TaskRun
            └── TaskAttempt
```

The governing invariants are:

```text
TaskDefinition
    ≠
TaskRun
    ≠
TaskAttempt

retry
    → same TaskRunId
    → new TaskAttemptId

reconciliation
    → same existing TaskAttemptId
```

## Runtime entities

The canonical qualified runtime entities are:

```text
pyworkflowkit.runtime.WorkflowRun
pyworkflowkit.runtime.TaskRun
pyworkflowkit.runtime.TaskAttempt
```

They use the typed IDs introduced by LOT-01.

### WorkflowRun

A WorkflowRun carries:

```text
WorkflowRunId
workflow_name
workflow_version
definition_fingerprint
plan_fingerprint
CorrelationContext
status
created_at
started_at?
ended_at?
FailureEvidence?
```

### TaskRun

A TaskRun represents one logical execution of one task key:

```text
TaskRunId
WorkflowRunId
task_key
status
created_at
started_at?
ended_at?
skip_reason?
block_reason?
FailureEvidence?
```

Its identity is stable across retries.

### TaskAttempt

A TaskAttempt represents one concrete workload attempt:

```text
TaskAttemptId
TaskRunId
attempt_number
status
created_at
started_at?
ended_at?
FailureEvidence?
```

Each retry creates a different TaskAttemptId.

## Public state vocabulary

### WorkflowRunStatus

```text
PENDING
RUNNING
SUCCEEDED
FAILED
CANCELLATION_REQUESTED
CANCELLED
TIMED_OUT
UNKNOWN_OUTCOME
```

Terminal/absorbing:

```text
SUCCEEDED
FAILED
CANCELLED
TIMED_OUT
```

`UNKNOWN_OUTCOME` is deliberately non-terminal because provider truth may still be
reconciled.

### TaskRunStatus

```text
PENDING
READY
RUNNING
SUCCEEDED
FAILED
SKIPPED
CANCELLED
TIMED_OUT
BLOCKED
UNKNOWN_OUTCOME
```

Terminal/absorbing:

```text
SUCCEEDED
FAILED
SKIPPED
CANCELLED
TIMED_OUT
```

`BLOCKED` is non-terminal. This permits a task blocked by unresolved upstream truth to
become READY after reconciliation.

### TaskAttemptStatus

```text
PENDING
STARTING
RUNNING
SUCCEEDED
FAILED
TIMED_OUT
CANCELLATION_REQUESTED
CANCELLED
CANCELLATION_UNCONFIRMED
UNKNOWN_OUTCOME
REQUIRES_RECONCILIATION
```

Terminal/absorbing:

```text
SUCCEEDED
FAILED
TIMED_OUT
CANCELLED
```

The uncertainty states remain non-terminal.

## State transition authority

Public state is read-only through the normal `status` property.

Transitions are owned by:

```text
WorkflowRunStateMachine
TaskRunStateMachine
TaskAttemptStateMachine
```

Invalid transitions raise:

```text
InvalidStateTransitionError
```

Attempts to transition an absorbing terminal entity raise:

```text
TerminalStateError
```

## WorkflowRun transition model

Representative paths:

```text
PENDING
    ↓
RUNNING
    ├── SUCCEEDED
    ├── FAILED
    ├── TIMED_OUT
    ├── CANCELLATION_REQUESTED
    │       ├── CANCELLED
    │       └── UNKNOWN_OUTCOME
    └── UNKNOWN_OUTCOME
            ├── RUNNING
            ├── SUCCEEDED
            ├── FAILED
            └── CANCELLED
```

A cancellation request is therefore never equivalent to confirmed cancellation.

## TaskRun transition model

Representative paths:

```text
PENDING
    ├── READY
    ├── BLOCKED
    ├── SKIPPED
    └── CANCELLED

BLOCKED
    ├── READY
    ├── SKIPPED
    └── CANCELLED

READY
    ├── RUNNING
    ├── BLOCKED
    ├── SKIPPED
    └── CANCELLED

RUNNING
    ├── SUCCEEDED
    ├── FAILED
    ├── TIMED_OUT
    ├── CANCELLED
    └── UNKNOWN_OUTCOME
```

## Skip semantics

`SKIPPED` requires a typed SkipReason.

Initial V2 reasons:

```text
CONDITION_FALSE
DEPENDENCY_FAILED
FAIL_FAST_ABORT
BRANCH_NOT_SELECTED
TRIGGER_RULE_UNSATISFIED
UPSTREAM_SKIPPED
```

A non-SKIPPED TaskRun cannot carry a SkipReason.

## Blocked semantics

`BLOCKED` requires a typed BlockReason.

Initial V2 reasons:

```text
UPSTREAM_FAILED
UPSTREAM_UNKNOWN
MISSING_INPUT
POLICY
CANCELLATION
```

BLOCKED is not treated as terminal because later reconciliation/readiness evaluation may
unblock the task.

## TaskAttempt uncertainty

The attempt state machine preserves uncertainty explicitly:

```text
RUNNING
    ↓
CANCELLATION_REQUESTED
    ↓
CANCELLATION_UNCONFIRMED
    ↓
REQUIRES_RECONCILIATION
    ↓
provider truth
```

and:

```text
RUNNING
    ↓
UNKNOWN_OUTCOME
    ↓
REQUIRES_RECONCILIATION
    ↓
SUCCEEDED / FAILED / CANCELLED / RUNNING
```

No transition implicitly maps uncertainty to FAILED.

## Attempt numbering

Attempt numbering is one-based and contiguous:

```text
TaskRun TR-1
    ├── TaskAttempt TA-1  attempt_number=1
    ├── TaskAttempt TA-2  attempt_number=2
    └── ...
```

The internal sequencing contract rejects:

```text
duplicate TaskAttemptId
duplicate attempt_number
non-contiguous numbering
attempts from another TaskRun
new attempt after SUCCEEDED
new attempt after CANCELLED
new attempt while outcome is UNKNOWN
new attempt while reconciliation is required
```

A new attempt is currently permitted only after:

```text
FAILED
TIMED_OUT
```

LOT-07 will decide whether retry policy actually authorizes that next attempt.

## Retry versus reconciliation

LOT-04 establishes the identity distinction before retry policy exists:

```text
RETRY
    same TaskRunId
    NEW TaskAttemptId

RECONCILE
    same TaskRunId
    SAME TaskAttemptId
```

This prevents later recovery code from accidentally converting process restart into blind
re-execution.

## Runtime snapshot invariants

Entity constructors validate persisted/reconstructed snapshots.

Examples rejected:

```text
terminal WorkflowRun without ended_at
terminal TaskRun without ended_at
terminal TaskAttempt without ended_at
SKIPPED TaskRun without SkipReason
BLOCKED TaskRun without BlockReason
naive runtime timestamps
```

These checks become important when LOT-05 and LOT-10 load runtime state from metadata
stores.

## Import-cycle boundary

State enums are import-safe without importing runtime entities.

State-machine service exports use lazy loading from `pyworkflowkit.states` so:

```text
runtime.entities
    → states.enums
```

does not create a circular import through:

```text
states.machine
    → runtime.entities
```

## Compatibility posture

The V2 qualified namespaces are now:

```python
from pyworkflowkit.runtime import (
    WorkflowRun,
    TaskRun,
    TaskAttempt,
)

from pyworkflowkit.states import (
    WorkflowRunStatus,
    TaskRunStatus,
    TaskAttemptStatus,
    WorkflowRunStateMachine,
    TaskRunStateMachine,
    TaskAttemptStateMachine,
)
```

The 1.1 root API remains frozen and unchanged.

The legacy domain runtime entities continue to exist only for the existing 1.1
WorkflowRuntime until LOT-06 migrates execution onto the V2 model.

## LOT-04 invariants

```text
state assignment
    = validated

terminal state
    = absorbing

UNKNOWN_OUTCOME
    ≠ FAILED

CANCELLATION_REQUESTED
    ≠ CANCELLED

CANCELLATION_UNCONFIRMED
    = reconcilable uncertainty

BLOCKED
    = non-terminal TaskRun readiness state

retry
    = new TaskAttempt identity

reconciliation
    = preserve TaskAttempt identity
```

## Exit criteria

LOT-04 is complete when:

```text
[ ] WorkflowRun uses WorkflowRunId
[ ] TaskRun uses TaskRunId + WorkflowRunId
[ ] TaskAttempt uses TaskAttemptId + TaskRunId
[ ] V2 state enums match the public specification
[ ] invalid transitions fail explicitly
[ ] terminal states are absorbing
[ ] cancellation request differs from confirmation
[ ] UNKNOWN_OUTCOME remains representable
[ ] REQUIRES_RECONCILIATION remains representable
[ ] SKIPPED requires SkipReason
[ ] BLOCKED requires BlockReason
[ ] TaskRun identity survives retries
[ ] retry creates a new TaskAttempt identity
[ ] uncertain attempts cannot be blindly retried
[ ] attempt numbering is contiguous
[ ] runtime snapshot invariants are validated
[ ] property tests prove terminal-state absorption
[ ] root 1.1 API freeze remains green
[ ] full CI and release qualification pass
```

## Next lot

```text
LOT-05 — In-Memory MetadataStore
```

LOT-05 will make these V2 runtime entities persistable behind a V2 MetadataStore contract
without introducing database-specific semantics.
