# PyWorkflowKit V2 — LOT-03 Planning and ExecutionPlan

Status: implementation baseline  
Target milestone: `2.0.0a1`  
Depends on: LOT-00, LOT-01, LOT-02

## Purpose

LOT-03 introduces the canonical compilation boundary:

```text
WorkflowDefinition
        ↓
WorkflowPlanner.compile()
        ↓
ExecutionPlan
```

Compilation validates and normalizes execution semantics without creating runtime
identity or executing any workload.

## WorkflowPlanner

The canonical planner API is:

```python
from pyworkflowkit.planning import WorkflowPlanner

planner = WorkflowPlanner()
plan = planner.compile(workflow)
```

`compile()` is the stable planning verb.

It performs:

```text
structural validation
dependency validation
cycle validation
deterministic topological sorting
deterministic layer/group construction
policy carry-forward / normalization
executor requirement extraction
integration requirement extraction
structured diagnostic generation
plan fingerprint preparation
```

It does not:

```text
execute workloads
allocate WorkflowRunId
allocate TaskRunId
allocate TaskAttemptId
open databases
activate plugins
resolve credentials
import sibling frameworks
mutate provider state
```

## Internal graph

The dependency graph is implemented under:

```text
pyworkflowkit.planning._graph
```

It is deliberately internal.

The public API does not export:

```text
DependencyGraph
WorkflowGraph
GraphNode
GraphEdge
```

Users author topology through WorkflowDefinition and inspect compiled semantics through
ExecutionPlan.

## Deterministic topological order

Planning uses lexical tie-breaking for simultaneously ready tasks.

Example:

```text
customers ─┐
           ├── transform ── publish
orders ────┘
```

compiles deterministically to:

```text
topological_order =
(
    "customers",
    "orders",
    "transform",
    "publish",
)
```

with groups:

```text
(
    ("customers", "orders"),
    ("transform",),
    ("publish",),
)
```

Equivalent WorkflowDefinition semantics compile to the same topological order and plan
fingerprint regardless of incidental task declaration ordering.

## TaskPlanEntry

Each planned task exposes resolved execution semantics:

```text
task
position
group_index
executor_requirement
required_integrations
```

Convenience projections expose:

```text
key
dependencies
retry_policy
timeout_policy
trigger_rule
portable
```

The entry retains the canonical TaskDefinition because LOT-06 WorkflowRuntime must later
execute the opaque workload represented by that definition.

## ExecutorRequirement

LOT-03 introduces:

```text
ExecutorRequirement
    executor_key
    workload_kind
    portable
```

Current extraction rules are intentionally small and explicit.

A local callable produces:

```text
executor_key = inline
workload_kind = python_callable
portable = false
```

A RegisteredWorkload uses its declared executor key when provided and otherwise defaults
to inline.

No installed plugin or sibling package silently changes executor selection.

## Integration requirements

Portable workload descriptors may declare an explicit integration requirement.

LOT-03 also recognizes the semantic workload-kind prefixes:

```text
pyingestkit...
pytransformkit...
```

and records corresponding requirements without importing either framework.

Actual sibling adapter activation and runtime behavior remain owned by LOT-18 and LOT-19.

## ExecutionPlan

ExecutionPlan is the public compiled workflow representation.

Canonical properties:

```text
workflow_name
workflow_version
definition_fingerprint
failure_policy
tasks
topological_order
groups
required_capabilities
required_integrations
diagnostics
```

Canonical inspection:

```python
plan.task("transform")
plan.topological_order
plan.required_capabilities
plan.required_integrations
plan.diagnostics
plan.fingerprint()
plan.explain()
```

## Runtime-state exclusion

ExecutionPlan deliberately contains no:

```text
WorkflowRunId
TaskRunId
TaskAttemptId
attempt number
mutable execution status
runtime timestamps
provider run identity
```

The plan describes executable semantics, not one execution instance.

## Effective policies

TaskPlanEntry exposes the effective policy declarations carried from authoring:

```text
RetryPolicy
TimeoutPolicy
TriggerRule
```

Later lots may add richer normalization, but policy semantics are already explicit in the
compiled plan rather than being rediscovered implicitly by an executor.

## Required capabilities

Planner output includes deterministic capability labels such as:

```text
executor:inline
executor:thread
workload:python_callable
workload:registered
```

These are declarative requirements.

LOT-06 and later executor-registry work will decide whether configured runtime
capabilities satisfy them.

## Structured diagnostics

Planning emits structured Diagnostic values.

The initial baseline includes:

```text
PWK-PLAN-001
    topology validated

PWK-PLAN-PORTABILITY-001
    process-local/non-portable workload declaration
```

Diagnostics are inspection data and do not require log parsing.

## Plan fingerprint

`ExecutionPlan.fingerprint()` returns:

```text
sha256:<hex>
```

It covers deterministic compiled semantics including:

```text
workflow identity
definition fingerprint
workflow failure policy
ordered task plan entries
topological order
execution groups
executor requirements
integration requirements
structured planning diagnostics
```

It excludes runtime-generated identity and timestamps.

## Portability

`ExecutionPlan.portable` is true only when every planned task workload is portable.

A local callable can be planned and executed later by an inline local runtime, but it does
not become durable merely because a deterministic plan fingerprint exists.

```text
planned
    !=
portable
```

## Qualified public API

LOT-03 exposes:

```python
from pyworkflowkit.planning import (
    ExecutionPlan,
    ExecutorRequirement,
    TaskPlanEntry,
    WorkflowPlanner,
)
```

The package root remains frozen at the 1.1 surface during migration.

The final V2 root promotion is owned by the later API-freeze lot.

## LOT-03 invariants

```text
WorkflowDefinition
    = author intent

ExecutionPlan
    = validated deterministic execution semantics

compile()
    ≠ run()

planning
    ≠ runtime

ExecutionPlan
    contains no runtime IDs

DependencyGraph
    = internal

same semantic definition
    → same plan semantics
    → same plan fingerprint
```

## Exit criteria

LOT-03 is complete when:

```text
[ ] WorkflowPlanner.compile() exists
[ ] compile performs no workload execution
[ ] deterministic topological order is produced
[ ] deterministic execution groups are produced
[ ] semantic WorkflowDefinition ordering does not change plan fingerprint
[ ] executor requirements are explicit
[ ] integration requirements are explicit
[ ] effective policies are inspectable
[ ] planning diagnostics are structured
[ ] ExecutionPlan is immutable
[ ] ExecutionPlan contains no runtime identity/state
[ ] plan fingerprint is deterministic
[ ] plan explain is side-effect free
[ ] graph internals are not exported
[ ] root 1.1 API freeze remains green
[ ] full CI and release qualification pass
```

## Next lot

```text
LOT-04 — WorkflowRun / TaskRun / TaskAttempt State Machines
```

LOT-04 will introduce the V2 runtime entities and explicit state machines while keeping
planning immutable and runtime-independent.
