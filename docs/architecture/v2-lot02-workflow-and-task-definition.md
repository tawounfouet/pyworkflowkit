# PyWorkflowKit V2 — LOT-02 WorkflowDefinition and TaskDefinition

Status: implementation baseline  
Target milestone: `2.0.0a1`  
Depends on: LOT-00, LOT-01

## Purpose

LOT-02 establishes the canonical V2 authoring model.

The semantic root is:

```text
WorkflowDefinition
    └── TaskDefinition*
            └── one workload boundary
```

No public WorkflowGraph is required.

## WorkflowDefinition

The V2 definition is immutable and runtime-independent.

Canonical properties:

```text
name
tasks
version
failure_policy
metadata
```

Canonical operations:

```python
workflow.validate()
workflow.fingerprint()
workflow.explain()
workflow.task("task_key")
```

Construction and inspection never execute workloads.

## TaskDefinition

A V2 task represents exactly one workload boundary.

Canonical properties:

```text
key
workload
dependencies
retry_policy
timeout_policy
trigger_rule
inputs
outputs
metadata
```

It deliberately contains no:

```text
WorkflowRunId
TaskRunId
TaskAttemptId
attempt number
provider run ID
mutable runtime status
```

## Task keys

Task keys are authoring identities within one WorkflowDefinition.

They are:

- non-empty;
- unique in the workflow;
- used by dependency declarations;
- independent from future TaskRunId and TaskAttemptId values.

Changing a task key is a semantic authoring change and changes the definition fingerprint.

## Workload boundary

A task accepts either:

```text
trusted Python callable / async callable
or
WorkloadDescriptor
```

Arbitrary local callables are valid for local authoring but explicitly classify as:

```text
WorkloadPortability.LOCAL_ONLY
```

Portable descriptors implement the `WorkloadDescriptor` contract.

LOT-02 provides `RegisteredWorkload` as the first schema-driven portable descriptor:

```python
RegisteredWorkload(
    registry_key="jobs.refresh_cache",
    parameters=(("region", "eu"),),
    executor_key="inline",
)
```

Sibling-specific workload descriptors remain owned by LOT-18 and LOT-19.

## Dependencies

Dependencies are explicit task keys.

The builder accepts either:

```python
depends_on = (upstream_task,)
```

or:

```python
depends_on = ("upstream_task",)
```

Both compile into:

```text
dependencies = ("upstream_task",)
```

Dependencies represent execution ordering.

They do not automatically assert data lineage.

## Topology validation

LOT-02 validates authoring topology without exposing graph internals.

It rejects:

```text
duplicate task keys
duplicate dependencies
self dependencies
unknown dependency keys
cycles
```

LOT-03 may replace the local validation algorithm with the canonical internal planning
graph, but that implementation detail does not change the authoring contract.

## Builder

Preferred ergonomic entrypoint:

```python
builder = WorkflowDefinition.builder(
    name="customer_360",
)

customers = builder.task(
    "ingest_customers",
    workload=customers_workload,
)

orders = builder.task(
    "ingest_orders",
    workload=orders_workload,
)

builder.task(
    "transform_customer_360",
    workload=transform_workload,
    depends_on=(customers, orders),
)

workflow = builder.build()
```

The builder is mutable for convenience.

Every `build()` call returns an immutable snapshot.

Mutating the builder later does not mutate a previously built WorkflowDefinition.

## Decorators

The qualified V2 decorators are authoring sugar only.

`@task` returns a canonical V2 TaskDefinition without executing the function.

`@workflow(...)` remains lazy and returns a WorkflowTemplate whose `build()` method
produces the canonical WorkflowDefinition.

No decorator creates a second execution model.

The frozen root-level 1.1 decorators remain untouched during migration.

## Input and output declarations

LOT-02 introduces minimal immutable declarations:

```text
InputDeclaration
    name
    required
    portable
    metadata

OutputDeclaration
    name
    portable
    metadata
```

These describe authoring contracts.

They do not themselves store runtime output values or data lineage.

## TimeoutPolicy skeleton

LOT-02 introduces the public V2 timeout declaration:

```python
TimeoutPolicy(
    execution_timeout=300.0,
)
```

It represents a local workload execution deadline.

It does not claim that reaching the deadline proves external termination.

LOT-08 owns the complete timeout/cancellation/reconciliation semantics.

## TriggerRule

The V2 authoring vocabulary is:

```text
ALL_SUCCESS
ALL_DONE
ANY_SUCCESS
ANY_FAILED
NONE_FAILED
ALWAYS
```

Trigger rules describe readiness against upstream TaskRun states.

They do not inspect provider internals.

## Authoring metadata

Metadata is restricted to recursively JSON-like runtime-independent values.

Mappings are frozen and sequences become tuples.

This prevents mutable application objects, sessions, provider clients or arbitrary code
from being hidden inside canonical authoring metadata.

## Deterministic fingerprint

`WorkflowDefinition.fingerprint()` produces:

```text
sha256:<hex>
```

The fingerprint includes semantic authoring state:

```text
workflow name/version
workflow policy
task keys
workload identity
dependencies
retry/timeout declarations
trigger rules
input/output declarations
metadata
```

The fingerprint excludes incidental task insertion order.

Equivalent dependency sets and metadata key ordering therefore produce the same
fingerprint.

Changing workload parameters, task keys, policies or declared metadata changes it.

The fingerprint function never executes workload code.

## Local callable fingerprinting

A named Python callable contributes:

```text
module:qualified_name
```

to the authoring fingerprint.

This does not make the callable durable.

```text
fingerprintable
    !=
portable
```

Callable objects that cannot expose a deterministic qualified reference must be wrapped
in an explicit registered/portable descriptor if durable semantics are required.

## Public qualified API

Canonical LOT-02 imports:

```python
from pyworkflowkit.authoring import (
    InputDeclaration,
    OutputDeclaration,
    RegisteredWorkload,
    TaskDefinition,
    WorkflowDefinition,
    WorkflowDefinitionBuilder,
    WorkloadDescriptor,
    WorkloadPortability,
    task,
    workflow,
)

from pyworkflowkit.policies import (
    TimeoutPolicy,
    TriggerRule,
)
```

The root `pyworkflowkit.TaskDefinition` and `pyworkflowkit.WorkflowDefinition` remain
the frozen 1.1 contracts during the migration window.

## LOT-02 invariants

```text
TaskDefinition
    = one workload boundary

WorkflowDefinition
    = canonical authoring root

builder
    = convenience only

decorators
    = syntax sugar only

dependencies
    = explicit ordering

WorkflowGraph
    = not public

authoring
    ≠ execution

fingerprint
    = deterministic semantic evidence

local callable
    ≠ durable portable workload
```

## Exit criteria

LOT-02 is complete when:

```text
[ ] WorkflowDefinition is immutable
[ ] TaskDefinition is immutable
[ ] TaskDefinition represents one workload boundary
[ ] task keys are unique
[ ] dependencies are explicit
[ ] unknown/self/duplicate dependencies fail
[ ] cycles fail validation
[ ] builder emits canonical definitions
[ ] decorators emit/build canonical definitions
[ ] constructors do not execute workload code
[ ] local callables are marked non-portable
[ ] portable RegisteredWorkload exists
[ ] input/output declarations are immutable
[ ] TimeoutPolicy skeleton exists
[ ] TriggerRule vocabulary exists
[ ] fingerprint is deterministic
[ ] explain performs no execution
[ ] no public WorkflowGraph/DependencyGraph is required
[ ] root 1.1 API freeze remains green
[ ] full CI and release qualification pass
```

## Next lot

```text
LOT-03 — Planning and ExecutionPlan
```

LOT-03 will internalize graph mechanics and compile WorkflowDefinition into a public,
deterministic ExecutionPlan without workload execution.
