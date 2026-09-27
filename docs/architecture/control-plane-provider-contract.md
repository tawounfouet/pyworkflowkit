# Control-Plane Provider Contract

Status: M51 — 0.8.0a5

## Purpose

M51 defines the public boundary between PyWorkflowKit and an external control plane such
as Ochestrix.

The dependency direction is:

~~~text
Control Plane
    ↓
ControlPlaneProvider
    ↓
WorkflowRuntime
~~~

PyWorkflowKit does not import control-plane framework code, ORM models, IAM, scheduling,
web-framework types or registry implementations.

## Contract version

~~~text
CONTROL_PLANE_PROVIDER_CONTRACT_VERSION = "1"
~~~

The dedicated public import path is:

~~~python
from pyworkflowkit.control_plane import (
    CONTROL_PLANE_PROVIDER_CONTRACT_VERSION,
    ControlPlaneProvider,
    WorkflowRuntimeProvider,
)
~~~

The stable package-root API remains unchanged.

## Contract philosophy

The provider is an application facade.

It does not create a second workflow engine.

~~~text
portable control-plane request
          ↓
WorkflowRuntimeProvider
          ↓
existing validation / runtime / evidence services
          ↓
portable control-plane response
~~~

Runtime state transitions remain owned by the existing PyWorkflowKit runtime.

## Portable workflow input

A control plane supplies a workflow as either:

~~~text
WorkflowDefinitionSchema
~~~

or the equivalent JSON-compatible mapping.

The provider converts that boundary schema into the existing domain
`WorkflowDefinition` internally.

This keeps executable Python callables outside the control-plane contract.

The host application is still responsible for:

~~~text
handler registration
executor configuration
MetadataStore configuration
event-sink registration
external-run verifier registration
~~~

A control plane does not send function objects across the provider boundary.

## Operations

Control-plane contract v1 freezes these operation identifiers:

~~~text
validate_workflow
inspect_workflow
execute_workflow
inspect_run
list_runtime_events
retrieve_manifest
retrieve_lineage
request_cancellation
assess_recovery
reconcile_run
resume_run
inspect_capabilities
~~~

Capability support is declared explicitly per provider.

## Capability negotiation

`WorkflowRuntimeProvider.inspect_capabilities()` returns:

~~~text
contract_version
provider_name
runtime_version
operations
scheduling_owned_by_control_plane
background_execution
~~~

For the built-in WorkflowRuntime provider:

~~~text
scheduling_owned_by_control_plane = true
background_execution              = false
request_cancellation              = false
~~~

All other M51 operations are available.

## Why cancellation is declared but unsupported

The current `WorkflowRuntime` facade executes synchronously and has no external
run-cancellation command.

M51 does not fabricate one.

Instead:

~~~text
capabilities.operations["request_cancellation"] = false
~~~

and calling it raises:

~~~text
ControlPlaneCapabilityError
~~~

This preserves truthful capability negotiation.

A future provider backed by a runtime with an explicit cancellation command may advertise
that capability as true without changing the operation identifier.

## Validation

`validate_workflow()` performs:

~~~text
boundary schema validation
      ↓
WorkflowDefinition construction
      ↓
dependency graph construction
      ↓
DAG validation
      ↓
deterministic execution planning
~~~

Validation failures are returned as portable diagnostics instead of exposing graph or
validator implementation objects.

## Static inspection

`inspect_workflow()` returns:

~~~text
canonical WorkflowDefinitionSchema
deterministic task order
topological execution groups
~~~

It does not expose:

~~~text
DependencyGraph object
ExecutionPlanner instance
handler registry
executor registry
~~~

## Execution

`execute_workflow()` is synchronous because `WorkflowRuntime.run()` is synchronous.

The provider normalizes control-plane parameters through the strict portable JSON
contract before execution.

The response is a `ControlPlaneRunSchema` containing only:

~~~text
run_id
workflow_id
workflow_version
status
created_at
started_at
finished_at
~~~

Raw workflow parameters are deliberately omitted.

## Run inspection

`inspect_run()` returns the same parameter-free run summary.

This prevents the control-plane read boundary from accidentally exposing sensitive
runtime parameters.

Sensitive parameter values remain available in the canonical manifest only through its
existing redaction semantics.

## Runtime events

`list_runtime_events()` returns `RuntimeEventSchema` values.

Before leaving the provider boundary, event payloads receive defensive recursive
sensitive-key redaction.

This means the provider does not expose raw durable event payload objects directly.

## Manifest

`retrieve_manifest()` delegates to the existing `RunManifest` builder and serializer.

The response remains governed by:

~~~text
MANIFEST_SCHEMA_VERSION = "1"
~~~

M51 does not create a competing control-plane manifest format.

Existing manifest redaction for:

~~~text
sensitive workflow parameters
artifact metadata
external-reference metadata
~~~

therefore remains authoritative.

## Lineage

`retrieve_lineage()` projects the existing deterministic execution lineage into explicit
portable schemas:

~~~text
ExecutionLineageSchema
├── TaskExecutionLineageSchema[]
└── LineageDependencySchema[]
~~~

No MetadataStore or persistence row objects cross the boundary.

## Recovery

`assess_recovery()` projects the existing `RecoveryAssessment` into a portable schema.

The provider does not add its own stale-run or resume rules.

The following remain runtime-owned:

~~~text
RecoveryLiveness
ResumeEligibility
retry waiting semantics
idempotency metadata
reconciliation requirements
~~~

## Reconciliation

`reconcile_run()` delegates to the existing read-only ReconciliationService and returns
portable:

~~~text
task reconciliation
external run observations
normalized status
disposition
reasons
~~~

The provider never exposes verifier instances.

## Resume

`resume_run()` delegates to the existing same-WorkflowRun resume semantics.

M51 does not create a second resume model.

## Scheduling ownership

Scheduling remains explicitly outside PyWorkflowKit.

~~~text
Ochestrix / external control plane
    ├── cron / calendars
    ├── governance
    ├── user permissions
    ├── run policy
    └── trigger decisions
              ↓
      ControlPlaneProvider
              ↓
      PyWorkflowKit execution
~~~

The provider contains no polling loop, scheduler daemon or background queue.

## Ochestrix boundary

The intended Ochestrix dependency direction is:

~~~text
Ochestrix
    ↓
pyworkflowkit.control_plane
    ↓
WorkflowRuntimeProvider
    ↓
WorkflowRuntime
~~~

Ochestrix may persist its own provider configuration or business registry.

Those objects are not imported by PyWorkflowKit.

Rejected:

~~~text
PyWorkflowKit imports Django
PyWorkflowKit imports Ochestrix ORM models
provider returns SQLAlchemy Session
provider returns ORM rows
provider exposes RuntimeComponents
provider exposes MetadataStore instance
provider exposes Executor instance
provider exposes HandlerRegistry
~~~

## Security

M51 adds three boundary protections:

1. workflow execution parameters must be strict portable JSON;
2. run summaries never return raw parameters;
3. runtime-event payloads are defensively redacted before control-plane delivery.

Manifest security continues to use the existing manifest redaction policy.

## Artifact-level conformance

`scripts/qualify_control_plane_provider.py` builds or accepts a PyWorkflowKit wheel,
creates a fresh virtual environment, installs the wheel, and executes a standalone
control-plane program.

The program imports only:

~~~python
from pyworkflowkit import WorkflowRuntime
from pyworkflowkit.control_plane import ...
~~~

It verifies:

~~~text
contract version
protocol conformance
capability negotiation
validation
static inspection
execution
run inspection
event retrieval
manifest retrieval
lineage retrieval
recovery assessment
unsupported cancellation
JSON serialization of every response
~~~

Running the test from a temporary directory prevents accidental reliance on the source
checkout.

## Release qualification

M51 adds a dedicated release gate:

~~~text
Control-plane provider
~~~

It runs against the actual wheel produced by Release Qualification.

The aggregate release gate therefore fails if the distributed artifact cannot support
the public provider contract.

## Persistence

M51 adds no database state and no migration.

Migration head remains:

~~~text
0003_retry_eligible_at
~~~

## Acceptance criteria

M51 is complete when:

~~~text
dedicated public control-plane import path exists
provider contract version is explicit
operation names are frozen
workflow definitions cross as schemas/mappings
handlers never cross the provider boundary
validation is portable
static planning inspection is portable
execution returns parameter-free run summaries
events are redacted
manifest schema v1 is reused
lineage is portable
recovery assessment is portable
reconciliation is portable
resume delegates to existing semantics
unsupported cancellation is explicitly advertised
scheduling remains external
no ORM/session/repository/executor internals cross the boundary
wheel-level conformance passes
Release Qualification requires provider conformance
package-root API remains unchanged
no migration is introduced
~~~

## Next

M52 — Ecosystem SDK & Conformance Matrix — 0.8.0b1.
