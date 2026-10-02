# PyWorkflowKit V2 — LOT-06 InlineExecutor and WorkflowRuntime MVP

Status: implementation baseline  
Target milestone: `2.0.0a1` candidate  
Depends on: LOT-00 → LOT-05

## Purpose

LOT-06 closes the first executable V2 vertical slice.

The complete path is now:

```text
WorkflowDefinition
        │
        ▼
WorkflowPlanner
        │
        ▼
ExecutionPlan
        │
        ▼
WorkflowRuntime
        │
        ├── WorkflowRunStateMachine
        ├── TaskRunStateMachine
        ├── TaskAttemptStateMachine
        ├── MetadataStore
        └── Executor
                │
                ▼
          InlineExecutor
                │
                ▼
           trusted workload
                │
                ▼
          WorkflowResult
```

No legacy 1.1 Runner participates in this V2 path.

## Executor contract

The canonical V2 executor boundary is:

```python
class Executor(Protocol):
    @property
    def descriptor(self) -> ExecutorDescriptor: ...

    def execute(
        self,
        request: TaskExecutionRequest,
    ) -> TaskExecutionResult: ...
```

The LOT-06 contract version is:

```text
V2_EXECUTOR_CONTRACT_VERSION = "1"
```

Cancellation and reconciliation are deliberately absent from this MVP contract.
They become capability-dependent runtime semantics in later lots.

## ExecutorDescriptor

The descriptor exposes:

```text
executor_id
display_name
executor_version
capabilities
execution_modes
portability_constraints
supported_workload_kinds
```

For InlineExecutor:

```text
executor_id             = inline
execution mode          = current_process
capabilities            = synchronous, trusted_python
workload kinds          = python_callable, registered
portability constraint  = process_local_execution
```

## LocalExecutor versus InlineExecutor

PyWorkflowKit 1.1 exposes LocalExecutor.

V2 does not mutate that contract in place.

Instead:

```text
V1
adapters.executors.local.LocalExecutor
        │
        └── legacy Executor(task, handler, context)

V2
executors.InlineExecutor
        │
        └── Executor.execute(TaskExecutionRequest)
```

This avoids pretending that the old protocol and the new protocol are API-compatible.

## TaskExecutionRequest

One request represents exactly one TaskAttempt:

```text
TaskExecutionRequest
├── task_key
├── workload
├── executor_key
└── TaskExecutionContext
        ├── WorkflowRunId
        ├── TaskRunId
        ├── TaskAttemptId
        ├── attempt_number
        ├── CorrelationContext
        ├── dependency_outputs
        └── workload_parameters
```

Dependency outputs and registered-workload parameters are exposed as read-only mappings.

## Inline callable convention

A trusted local callable may accept:

```python
def workload():
    ...
```

or:

```python
def workload(context: TaskExecutionContext): ...
```

Varargs and unsupported signatures are rejected as execution-contract failures.

## RegisteredWorkload

Portable authoring references resolve only through explicit InlineExecutor bindings:

```python
executor = InlineExecutor(
    {
        "jobs.customer": customer_job,
    }
)
```

No module import, package installation or global registry silently activates a workload.

Missing bindings produce structured FailureEvidence.

## TaskExecutionResult

Executor invocation is normalized into:

```text
TaskExecutionResult
├── output
├── failure?
├── diagnostics*
└── succeeded
```

Ordinary workload exceptions do not escape the InlineExecutor as arbitrary runtime
exceptions.

They become structured FailureEvidence with execution identity attached.

## WorkflowRuntime construction

The V2 runtime is dependency-injected:

```python
runtime = WorkflowRuntime(
    executor=InlineExecutor(),
    metadata=InMemoryMetadataStore(),
)
```

Optional injected services include:

```text
WorkflowPlanner
Clock
RuntimeIdentityFactory
```

There is no hidden global executor, metadata store or ID generator.

## Accepted run inputs

```python
runtime.run(workflow_definition)
```

and:

```python
runtime.run(execution_plan)
```

are both canonical.

When given a WorkflowDefinition, WorkflowRuntime compiles it internally.

When given an ExecutionPlan, it executes that exact plan.

## Execution lifecycle

The MVP lifecycle is explicit:

```text
preflight
    ↓
allocate WorkflowRunId
    ↓
persist WorkflowRun(PENDING)
    ↓
create all TaskRun(PENDING)
    ↓
WorkflowRun → RUNNING
    ↓
for each planned task
    ↓
evaluate dependency readiness / trigger
    ↓
TaskRun → READY
    ↓
TaskRun → RUNNING
    ↓
create TaskAttempt(PENDING)
    ↓
TaskAttempt → STARTING
    ↓
TaskAttempt → RUNNING
    ↓
Executor.execute(request)
    ↓
persist success/failure state
    ↓
repeat
    ↓
WorkflowRun terminal
    ↓
WorkflowResult
```

Persisted state is authoritative.

## Readiness and trigger rules

The runtime evaluates the V2 TriggerRule set after all declared dependencies reach
terminal state:

```text
ALL_SUCCESS
ALL_DONE
ANY_SUCCESS
ANY_FAILED
NONE_FAILED
ALWAYS
```

A terminal dependency set that does not satisfy the trigger causes:

```text
TaskRun → SKIPPED
SkipReason.TRIGGER_RULE_UNSATISFIED
```

No TaskAttempt is created for that skipped task.

## Fail-fast

The only currently supported FailurePolicy remains:

```text
FAIL_FAST
```

After one task fails:

```text
failed TaskAttempt → FAILED
failed TaskRun     → FAILED

remaining descendant tasks
    → SKIPPED / DEPENDENCY_FAILED

remaining independent tasks
    → SKIPPED / FAIL_FAST_ABORT

WorkflowRun
    → FAILED
```

This preserves the reason why each undispatched task did not run.

## Retry posture

LOT-06 creates exactly one TaskAttempt for an executed TaskRun.

A declaration such as:

```python
RetryPolicy(max_attempts=2)
```

is rejected during runtime preflight.

The runtime does not silently ignore requested retry semantics.

Actual retry execution begins in:

```text
LOT-07
```

## Timeout posture

A non-empty TimeoutPolicy is also rejected during LOT-06 preflight.

Inline execution does not pretend to implement deadlines it cannot yet enforce safely.

Timeout/cancellation semantics begin in:

```text
LOT-08
```

## WorkflowResult

WorkflowRuntime returns an immutable caller-facing projection:

```text
WorkflowResult
├── WorkflowRunId
├── WorkflowRunStatus
├── TaskOutcome*
├── Diagnostic*
├── CorrelationContext
├── FailureEvidence?
└── ManifestReference?
```

Task lookup is explicit:

```python
result.task("transform")
```

## TaskOutcome

Each TaskOutcome contains:

```text
task_key
TaskRunId
TaskRunStatus
TaskAttemptId*
output
FailureEvidence?
Diagnostic*
```

It is not a mutation surface for TaskRun.

## Output posture

LOT-06 permits process-local output values for dependency hand-off and caller-facing MVP
results.

It does not yet claim that arbitrary Python outputs are durable.

Therefore:

```text
dependency output in current run   ✅
WorkflowResult local output        ✅
durable arbitrary object           ❌
recovery-safe output contract      ❌
```

Portable/durable output policy belongs to LOT-12.

## Basic event evidence

LOT-06 does not introduce a competing public RuntimeEvent taxonomy.

Instead, the append-only StateTransitionRecord history delivered by LOT-05 is the
authoritative basic event evidence for the MVP.

For example:

```text
WorkflowRun: PENDING → RUNNING → SUCCEEDED
TaskRun:     PENDING → READY → RUNNING → SUCCEEDED
TaskAttempt: PENDING → STARTING → RUNNING → SUCCEEDED
```

The richer event/manifest/lineage model remains LOT-12.

## Correlation

WorkflowRuntime binds a CorrelationContext to the allocated WorkflowRunId.

Each TaskExecutionContext then extends that correlation with:

```text
task_run_id
task_attempt_id
```

Native runtime identities remain distinct from correlation identity.

## Determinism

Determinism comes from:

```text
ExecutionPlan topological order
explicit injected executor
explicit injected metadata store
typed runtime identities
state-machine transitions
deterministic MetadataStore queries
explicit Clock / RuntimeIdentityFactory injection
```

Tests can therefore replace wall-clock and UUID generation without changing production
semantics.

## Import safety

`pyworkflowkit.runtime` lazy-loads the orchestration/result layer.

This prevents dependency cycles such as:

```text
executors
    → runtime.context

persistence
    → runtime.entities
```

from eagerly importing WorkflowRuntime and recursively re-entering executors/persistence.

## Compatibility posture

The frozen 1.1 root remains unchanged:

```python
import pyworkflowkit

pyworkflowkit.WorkflowRuntime
# legacy 1.1 facade
```

The V2 facade is currently qualified:

```python
from pyworkflowkit.runtime import WorkflowRuntime
```

The final package-root migration is intentionally deferred until the V2 public API freeze.

## LOT-06 invariants

```text
WorkflowDefinition
    does not execute

ExecutionPlan
    contains no runtime identity

WorkflowRuntime
    owns lifecycle orchestration

Executor
    owns exactly one workload invocation

MetadataStore
    owns persisted runtime facts

retry requested before LOT-07
    = fail closed

timeout requested before LOT-08
    = fail closed

task failure
    = FailureEvidence

WorkflowResult
    ≠ WorkflowRun

V2 runtime
    ≠ legacy Runner
```

## Exit criteria

LOT-06 is complete when:

```text
[ ] Executor Protocol exists
[ ] ExecutorDescriptor exists
[ ] TaskExecutionRequest/Result exist
[ ] InlineExecutor satisfies Executor
[ ] explicit RegisteredWorkload binding works
[ ] WorkflowRuntime accepts WorkflowDefinition
[ ] WorkflowRuntime accepts ExecutionPlan
[ ] local DAG executes end to end
[ ] dependency outputs reach downstream workload context
[ ] WorkflowRun/TaskRun/TaskAttempt state is persisted
[ ] trigger-rule skip is explicit
[ ] fail-fast skip propagation is explicit
[ ] one attempt is created per executed task
[ ] retry > 1 fails closed until LOT-07
[ ] timeout fails closed until LOT-08
[ ] WorkflowResult is immutable
[ ] basic state-event evidence is queryable
[ ] deterministic clock/ID injection works
[ ] V2 runtime does not use legacy Runner
[ ] frozen 1.1 root remains unchanged
[ ] full CI passes
[ ] release qualification passes
```

## Milestone

With LOT-00 through LOT-06 implemented and qualified, the architecture reaches the
functional scope of the `2.0.0a1` milestone.

Package-version promotion is a separate release action; LOT-06 does not falsify a
published `2.0.0a1` version before its qualification gates pass.

## Next lot

```text
LOT-07 — RetryPolicy and Attempt Retry
```

LOT-07 will replace the current fail-closed `max_attempts > 1` preflight with executable
retry decisions while preserving:

```text
same TaskRunId
new TaskAttemptId
structured FailureEvidence
explicit backoff
no retry of uncertain external outcomes
```
