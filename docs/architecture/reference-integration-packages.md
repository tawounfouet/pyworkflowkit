# Reference Integration Packages

Status: M50 — 0.8.0a4

## Purpose

M50 moves the 0.8 interoperability contracts outside the main wheel.

M47-M49 established:

~~~text
M47  ExternalWorkload
M48  portable references
M49  telemetry projection
~~~

M50 now asks a harder question:

> Can an independently packaged Python distribution use those contracts through real
> entry points, be installed and removed, and leave PyWorkflowKit core operational?

The answer is qualified through four reference wheels.

## Package topology

~~~text
pyworkflowkit wheel
      ↑
      │ dependency
      │
      ├── pyworkflowkit-reference-workload
      ├── pyworkflowkit-reference-event-sink
      ├── pyworkflowkit-reference-metadata
      └── pyworkflowkit-reference-pyingestkit
~~~

The dependency direction is one-way.

There is no import from `src/pyworkflowkit` to `reference-integrations`.

## Reference workload package

Distribution:

~~~text
pyworkflowkit-reference-workload
~~~

Entry point:

~~~text
group = pyworkflowkit.workloads
name  = reference-workload
~~~

It exposes a `RegisteredPlugin` whose factory creates an M47-compatible
`ReferenceExternalWorkload`.

Execution produces:

~~~text
ExternalWorkloadResult
    ↓
TaskResult
    ↓
ExternalRunRef
provider = reference-workload
~~~

This proves the generic workload contract can live outside the core wheel.

## Reference event-sink package

Distribution:

~~~text
pyworkflowkit-reference-event-sink
~~~

Entry point:

~~~text
group = pyworkflowkit.events
name  = reference-event-sink
~~~

The plugin creates a `RuntimeEventSink` implementation.

The acceptance scenario verifies:

~~~text
runtime transition
    ↓
durable RuntimeEvent
    ↓
ObservabilityDispatcher
    ↓
installed third-party sink
~~~

and compares the sink event IDs with the durable event stream.

## Reference metadata package

Distribution:

~~~text
pyworkflowkit-reference-metadata
~~~

Entry point:

~~~text
group = pyworkflowkit.metadata
name  = reference-metadata
~~~

The reference package subclasses the built-in in-memory adapter solely to exercise the
independently packaged MetadataStore plugin boundary.

The scenario validates the structural MetadataStore contract, creates a UnitOfWork,
persists a WorkflowRun and reads it back.

M50 does not claim this package is a new production persistence backend.

## PyIngestKit reference package

Distribution:

~~~text
pyworkflowkit-reference-pyingestkit
~~~

Entry point:

~~~text
group = pyworkflowkit.workloads
name  = pyingestkit-reference
~~~

The adapter itself remains outside PyWorkflowKit core.

Its architecture is:

~~~text
PyWorkflowKit TaskRun
       ↓
ExternalWorkloadAdapter
       ↓
PyIngestKitWorkload
       ↓
PyIngestKit Runner
       ↓
PyIngestKit Job
       ↓
PyIngestKit Pipeline / Step lifecycle
       ↓
PyIngestKit RunResult
       ↓
ExternalWorkloadResult
       ↓
ExternalRunRef
provider = pyingestkit
~~~

PyWorkflowKit never imports PyIngestKit.

The reference adapter only does so when the external package is installed and used.

## Real PyIngestKit qualification

The M50 CI installs PyIngestKit from its real GitHub repository, pinned to:

~~~text
a19264845e10769fb8fd8cd42c83193ae011f702
~~~

The pinned package reports:

~~~text
pyingestkit 1.0.1
~~~

The scenario uses public PyIngestKit contracts:

~~~text
Job
Pipeline
Step
Runner
RunResult
LocalArtifactStore
~~~

A real PyIngestKit job executes successfully.

PyWorkflowKit sees only:

~~~text
external_run_id
status
job identity/version
duration
warnings count
portable URI
~~~

It does not copy:

~~~text
PyIngestKit StepResult lifecycle
PyIngestKit event vocabulary
PyIngestKit metadata schema
PyIngestKit artifact-store internals
PyIngestKit validation model
~~~

## Retry ownership

The M50 PyIngestKit package is built on the generic M47 `ExternalWorkload` contract.

It therefore inherits the generic retry-ownership rules rather than introducing a new
retry model.

PyWorkflowKit and PyIngestKit must still have one explicit retry authority at the nested
runtime boundary.

## Entry-point behavior

Every reference package uses the frozen M44 entry-point groups:

~~~text
pyworkflowkit.workloads
pyworkflowkit.events
pyworkflowkit.metadata
~~~

Discovery remains metadata-first.

Installation does not mean enablement.

~~~text
pip install integration
      ↓
entry point discoverable
      ↓
NO execution yet
      ↓
explicit enable_selected(...)
      ↓
plugin code loaded/registered
~~~

M50 does not add automatic plugin enablement.

## Install/remove qualification

The qualification harness creates a fresh virtual environment and performs:

~~~text
build core wheel
      ↓
install core wheel
      ↓
core workflow succeeds
      ↓
for each integration wheel
    build
    install
    discover
    explicitly enable
    execute reference scenario
    uninstall
    verify entry point absent
    core workflow succeeds again
~~~

For PyIngestKit:

~~~text
install pinned PyIngestKit
install adapter wheel
execute real ingestion job through adapter
uninstall adapter
verify adapter entry point absent
core workflow succeeds
uninstall PyIngestKit
core workflow succeeds
~~~

This proves removability and reverse-dependency isolation.

## CI integration

M50 adds a dedicated CI job:

~~~text
Reference integration packages
~~~

The same qualification is also added to Release Qualification and is required by the
aggregate release gate.

This means a future compatibility break in:

~~~text
Plugin API
entry-point discovery
ExternalWorkload
ExternalRunRef
RuntimeEventSink
MetadataStore
packaging metadata
~~~

is detected using actual independently built wheels.

## Security boundary

Installed plugins remain trusted Python code.

M50 does not claim:

~~~text
plugin sandboxing
process isolation
permission isolation
dynamic package installation by PyWorkflowKit
safe execution of untrusted wheels
~~~

The framework does not install integrations itself.

The qualification harness performs explicit package installation only in CI.

## Compatibility boundary

Reference packages depend on:

~~~text
pyworkflowkit >= 0.8.0a4, < 0.9
~~~

The PyIngestKit adapter declares an optional compatibility extra:

~~~text
pyingestkit >= 1.0.1, < 2
~~~

CI uses the pinned upstream commit for deterministic cross-project qualification.

## Core installation invariant

After every integration uninstall, a core-only workflow is executed.

Therefore M50 makes the following invariant executable:

> Removing an optional integration must not make ordinary PyWorkflowKit workflows stop
> working.

## No persistence migration

M50 adds no runtime state and no persistence schema.

Migration head remains:

~~~text
0003_retry_eligible_at
~~~

## Findings feeding M52

M50 deliberately exposes some ecosystem-author friction rather than hiding it.

Examples include:

~~~text
constructing RegisteredPlugin
choosing the correct entry-point group
explicit PluginDiscovery enablement
finding dedicated import paths
testing structural plugin compatibility
building isolated package wheels
~~~

M52 will use these findings to define the ecosystem SDK/conformance authoring experience.

## Acceptance criteria

M50 is complete when:

~~~text
four reference integration wheels build independently
real entry-point metadata is discoverable
plugin enablement remains explicit
generic workload package executes
event-sink package receives committed events
metadata package satisfies MetadataStore and persists a run
real PyIngestKit 1.0.1 job executes behind one PyWorkflowKit task
portable ExternalRunRef evidence is produced
each integration can be uninstalled
uninstalled entry point disappears
core workflow succeeds after every uninstall
CI qualifies the integration wheels
Release Qualification requires the integration-wheel gate
no reverse core dependency is introduced
no new PluginType is introduced
no migration is introduced
~~~

## Next

M51 — Control-Plane Provider Contract — 0.8.0a5.
