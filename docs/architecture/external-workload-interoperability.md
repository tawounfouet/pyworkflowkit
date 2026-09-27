# External Workload Interoperability Contract

Status: M47 — 0.8.0a1

## Purpose

M47 defines the smallest generic boundary required to represent one execution owned by
another runtime as one atomic PyWorkflowKit task.

The foreign runtime keeps ownership of its internal lifecycle.

PyWorkflowKit owns only:

~~~text
task invocation boundary
retry ownership declaration
failure normalization
TaskResult normalization
ArtifactReference propagation
ExternalRunRef evidence
~~~

The core does not import foreign runtime packages.

## Contract version

~~~text
EXTERNAL_WORKLOAD_CONTRACT_VERSION = "1"
~~~

The public import path is:

~~~python
from pyworkflowkit.integrations import (
    EXTERNAL_WORKLOAD_CONTRACT_VERSION,
    ExternalRetryOwner,
    ExternalWorkload,
    ExternalWorkloadAdapter,
    ExternalWorkloadResult,
    external_workload_task,
)
~~~

M47 intentionally does not add these names to the package-root `pyworkflowkit.__all__`
surface frozen in 0.7.

## Execution model

~~~text
TaskDefinition
      │
      ▼
ExternalWorkloadAdapter
      │
      ▼
ExternalWorkload.run(context=RunContext)
      │
      ▼
ExternalWorkloadResult
      │
      ├── success
      │     ↓
      │  TaskResult
      │     ├── output
      │     ├── artifacts
      │     └── ExternalRunRef
      │
      └── failure
            ↓
      ExternalWorkloadError
            ↓
      TaskExecutionError
            ↓
      existing RetryEngine / runtime state machine
~~~

No new TaskRun, TaskAttempt, WorkflowRun or RuntimeEvent state is introduced.

## ExternalWorkload

A third-party wrapper implements:

~~~python
class ExternalWorkload(Protocol):
    def run(self, *, context: RunContext) -> ExternalWorkloadResult: ...
~~~

The protocol is deliberately small.

It does not expose:

~~~text
PyWorkflowKit MetadataStore
UnitOfWork
Runner internals
state machine mutation
executor internals
foreign runtime internals
~~~

## ExternalWorkloadResult

The normalized result contains:

~~~text
external_run_id
succeeded
output
uri
metadata
artifacts
error_type
error_message
error_category
~~~

A successful result cannot contain failure fields.

A failed result must contain `error_type`.

Metadata is frozen at the boundary.

## Portable evidence

A successful foreign execution becomes:

~~~text
TaskResult
    │
    ├── output
    ├── artifacts
    └── external_refs
          │
          ▼
      ExternalRunRef
      ├── provider
      ├── external_run_id
      ├── uri
      └── metadata
          ├── workload_ref
          └── retry_owner
~~~

The foreign execution is referenced rather than copied into the PyWorkflowKit runtime
domain.

~~~text
ExternalRunRef != WorkflowRun
~~~

M48 will further harden portability, serialization, provider naming and lineage rules.

## Retry ownership

Exactly one runtime owns retry decisions across the integration boundary.

M47 defines:

~~~text
ExternalRetryOwner.PYWORKFLOWKIT
ExternalRetryOwner.EXTERNAL
~~~

### External runtime owns retries

~~~python
retry_owner = ExternalRetryOwner.EXTERNAL
~~~

PyWorkflowKit must then use:

~~~text
RetryPolicy(max_attempts=1)
~~~

Any larger value raises `ExternalWorkloadRetryOwnershipError`.

This prevents accidental multiplication:

~~~text
PyWorkflowKit attempts = 3
external attempts      = 3

BAD effective executions = 9
~~~

### PyWorkflowKit owns retries

~~~python
retry_owner = ExternalRetryOwner.PYWORKFLOWKIT
~~~

The foreign wrapper must disable its own retry loop.

External failure categories are preserved through the Python executor boundary into the
existing `TaskExecutionError.error_category`, so normal `RetryPolicy` category filters
continue to work.

## Failure normalization

A foreign exception becomes `ExternalWorkloadError`.

A normalized failed `ExternalWorkloadResult` also becomes
`ExternalWorkloadError`.

When invoked through a PyWorkflowKit Python executor, that boundary error is translated
to the existing `TaskExecutionError` contract while retaining:

~~~text
error_type
error_message
error_category
~~~

This keeps retry and runtime failure semantics owned by existing PyWorkflowKit machinery.

## Timeout and cancellation boundary

M47 does not invent a second timeout or cancellation model.

The helper accepts ordinary task execution configuration:

~~~text
executor_key
timeout_seconds
timeout_mode
~~~

Those values continue to be validated against the selected PyWorkflowKit Executor
capabilities.

Cancellation remains coordinator/executor behavior.

M47 therefore does not claim that a foreign runtime can itself be remotely cancelled or
hard-terminated.

A future integration that exposes true remote cancellation must define a real action
contract before advertising that capability.

## Declarative helper

A generic external task can be declared with:

~~~python
external = external_workload_task(
    id="refresh_customers",
    provider="acme",
    workload_ref="customers.refresh",
    workload=workload,
)
~~~

The helper creates a normal `TaskHandle`.

It does not add:

~~~text
TaskType
ExternalTaskDefinition
foreign-runtime state
provider-specific TaskDefinition fields
~~~

## Plugin relationship

M47 is compatible with the existing `workload` Plugin API category, but it does not
automatically wire discovered workload plugins into workflows.

Plugin discovery remains:

~~~text
metadata-first
explicit
opt-in
non-loading until enabled
~~~

M52 will address broader external-package authoring and conformance ergonomics.

## PyIngestKit compatibility

The existing PyIngestKit adapter remains supported unchanged in M47.

Its current public types and behavior remain available:

~~~text
PyIngestKitJob
PyIngestKitRunResult
PyIngestKitRetryOwner
PyIngestKitTaskAdapter
pyingestkit_task
~~~

M47 generalizes the architectural pattern without forcing a breaking rewrite of the
existing adapter.

M50 may use the generic contract as the basis for independently packaged reference
integrations.

## Acceptance criteria

M47 is qualified when:

~~~text
generic third-party workload requires no foreign dependency in core
adapter construction has no execution side effect
success produces TaskResult + ExternalRunRef
foreign exceptions are normalized
failed external results are normalized
error_category reaches RetryEngine
retry ownership prevents nested retry multiplication
executor timeout semantics remain unchanged
package-root API remains unchanged
existing PyIngestKit acceptance remains green
~~~

## Non-goals

M47 does not add:

~~~text
remote cancellation protocol
remote timeout protocol
polling protocol
scheduler
background daemon
distributed worker
HTTP client dependency
cloud SDK dependency
OpenTelemetry dependency
business connector model
provider registry
foreign-runtime persistence schema
~~~

## Next

M48 — External References & Portable Integration Evidence — 0.8.0a2.
