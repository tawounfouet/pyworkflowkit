# Observability Interoperability Contract

Status: M49 — 0.8.0a3

## Purpose

M49 defines a vendor-neutral telemetry projection layer on top of the durable
`RuntimeEvent` stream.

The core rule remains:

~~~text
RuntimeEvent
    =
durable runtime evidence

Telemetry
    =
secondary external projection
~~~

Telemetry must never become a second source of truth for workflow state.

## Contract version

~~~text
OBSERVABILITY_INTEROPERABILITY_CONTRACT_VERSION = "1"
~~~

The dedicated public import path is:

~~~python
from pyworkflowkit.integrations import (
    OBSERVABILITY_INTEROPERABILITY_CONTRACT_VERSION,
    OpenTelemetryBackend,
    RuntimeTelemetryProjector,
    RuntimeTelemetrySink,
    TelemetryBackend,
    TelemetryCorrelation,
    TelemetryEvent,
    TelemetryMetric,
    TelemetryMetricKind,
    TelemetryProjection,
)
~~~

The stable package-root API from 0.7 remains unchanged.

## Existing runtime boundary

M49 builds on the contract introduced in M35:

~~~text
runtime state transition
        ↓
MetadataStore commit
        ↓
RuntimeEvent durable
        ↓
ObservabilityDispatcher
        ↓
RuntimeEventSink
~~~

This ordering is not changed.

A telemetry backend therefore receives only already-committed runtime facts.

## Projection model

M49 adds:

~~~text
RuntimeEvent
      ↓
RuntimeTelemetryProjector
      ↓
TelemetryProjection
      ├── TelemetryEvent
      └── TelemetryMetric[]
      ↓
RuntimeTelemetrySink
      ↓
TelemetryBackend
~~~

`RuntimeTelemetrySink` implements the stable `RuntimeEventSink` protocol.

No runner or state-machine specialization is required.

## Correlation

Each telemetry event carries `TelemetryCorrelation` built from PyWorkflowKit identities:

~~~text
event_id
run_id
task_run_id
task_id
attempt_number
event_sequence
~~~

These identities remain PyWorkflowKit identities.

They must not be replaced by backend-specific identifiers.

In particular:

~~~text
WorkflowRunId  != TraceId
TaskRunId      != SpanId
RuntimeEventId != SpanId
~~~

A tracing backend may attach its own trace/span context in addition to the stable
PyWorkflowKit correlation attributes.

## External reference correlation

`RuntimeEvent` intentionally does not embed `ExternalRunRef`.

External-runtime correlation therefore remains indirect and explicit:

~~~text
TelemetryEvent
    │
    └── task_run_id
            │
            ▼
Manifest / Lineage
            │
            ▼
ExternalRunRef
~~~

This avoids duplicating foreign reference data into every runtime event.

## Telemetry event naming

Each RuntimeEvent is projected to:

~~~text
pyworkflowkit.runtime.<event_type.lower()>
~~~

Examples:

~~~text
pyworkflowkit.runtime.workflow_started
pyworkflowkit.runtime.task_started
pyworkflowkit.runtime.task_retrying
pyworkflowkit.runtime.task_succeeded
pyworkflowkit.runtime.workflow_succeeded
~~~

The original RuntimeEventType remains available as a telemetry attribute.

M49 does not modify the durable RuntimeEvent vocabulary.

## Generic metrics

M49 deliberately exposes only metrics owned by the generic workflow runtime.

Stable generic names introduced in v1:

~~~text
pyworkflowkit.runtime.events
pyworkflowkit.workflow.started
pyworkflowkit.workflow.completed
pyworkflowkit.workflow.duration
pyworkflowkit.task.started
pyworkflowkit.task.retries
pyworkflowkit.task.completed
pyworkflowkit.task.duration
~~~

Durations use seconds.

Counters use unit `1`.

## Metric cardinality rule

Runtime identifiers are intentionally excluded from metric labels.

Bad:

~~~text
run_id
task_run_id
event_id
external_run_id
~~~

These are high-cardinality identities and belong in event/span correlation, not metric
dimensions.

Allowed generic metric attributes are bounded values such as:

~~~text
event_type
outcome
~~~

This prevents a telemetry adapter from accidentally generating unbounded time-series
cardinality.

## Business metrics remain external

PyWorkflowKit does not generate metrics such as:

~~~text
rows_ingested
customers_processed
revenue
model_accuracy
records_rejected
~~~

Those belong to the workload or integration that owns the business semantics.

## Duration semantics

The projector records the first observed start timestamp for a workflow or task and
emits a duration when the corresponding terminal event is observed.

For a task with retries, task duration covers the logical TaskRun from its first
observed start until terminal completion.

~~~text
TASK_STARTED attempt 1
        ↓
TASK_RETRYING
        ↓
retry work
        ↓
TASK_SUCCEEDED
        │
        ▼
task.duration
~~~

The telemetry projector is intentionally ephemeral.

If a process restarts and receives only a terminal event without the corresponding
start event, it emits the terminal counter but does not fabricate a duration.

Durable history remains available through RuntimeEvent persistence.

## Redaction

M49 preserves the existing observability security boundary.

~~~text
durable RuntimeEvent
        ↓
ObservabilitySecurityPolicy
        ↓
redacted RuntimeEvent
        ↓
RuntimeTelemetryProjector
~~~

The projector additionally applies recursive key-based redaction defensively to its
event payload.

Telemetry backends therefore receive a safe projection by default.

This is not encryption and not a substitute for avoiding secrets in runtime metadata.

## Failure isolation

A telemetry backend is executed through the existing `ObservabilityDispatcher`.

If it fails:

~~~text
TelemetryBackend failure
        ↓
ObservabilityDispatchFailure
        ↓
diagnostic only
~~~

The workflow outcome is unchanged.

A healthy sibling sink continues receiving committed events.

## OpenTelemetry adapter

M49 includes a reference `OpenTelemetryBackend`.

PyWorkflowKit does not import or depend on OpenTelemetry.

Instead, applications inject tracer and meter objects that satisfy the small API subset
used by the adapter.

Example:

~~~python
from opentelemetry import metrics, trace

from pyworkflowkit.integrations import (
    OpenTelemetryBackend,
    RuntimeTelemetrySink,
)

backend = OpenTelemetryBackend(
    tracer=trace.get_tracer("pyworkflowkit"),
    meter=metrics.get_meter("pyworkflowkit"),
)

runtime.register_event_sink(RuntimeTelemetrySink(backend))
~~~

The OpenTelemetry package remains an application-level optional dependency.

## OpenTelemetry event mapping

Each telemetry event is represented by a short-lived OpenTelemetry span/event projection
containing:

~~~text
PyWorkflowKit correlation attributes
RuntimeEventType
redacted payload JSON
~~~

PyWorkflowKit does not claim that these short-lived projection spans are the canonical
workflow/task lifecycle.

An application-specific tracing strategy may choose longer-lived spans, but it must not
replace the durable runtime state model.

## OpenTelemetry metric mapping

~~~text
TelemetryMetricKind.COUNTER
    → meter.create_counter(...).add(...)

TelemetryMetricKind.HISTOGRAM
    → meter.create_histogram(...).record(...)
~~~

Instruments are cached per metric name/unit by the adapter.

## Plugin relationship

The existing plugin type:

~~~text
PluginType.EVENT
~~~

already represents `RuntimeEventSink` implementations.

A `RuntimeTelemetrySink` can therefore be distributed through the existing event-plugin
mechanism without adding a new PluginType.

M49 intentionally avoids introducing:

~~~text
PluginType.TELEMETRY
PluginType.OPENTELEMETRY
~~~

because telemetry is an event-sink specialization, not a new core extension category.

## Relationship with M47/M48

The 0.8 interoperability chain is now:

~~~text
External Runtime
      ↓
M47 ExternalWorkload
      ↓
M48 portable references
      ↓
PyWorkflowKit durable RuntimeEvent / Manifest / Lineage
      ↓
M49 telemetry projection
      ↓
external observability backend
~~~

Foreign runtime references remain in manifest/lineage evidence.

Telemetry correlates to them through PyWorkflowKit task/run identities.

## Acceptance criteria

M49 is complete when:

~~~text
RuntimeEvent remains the durable source of truth
telemetry receives only committed events
PyWorkflowKit IDs are preserved as correlation attributes
trace/span identifiers do not replace domain identities
metric labels avoid high-cardinality runtime IDs
generic workflow/task counters are produced
generic workflow/task durations are produced when starts are observed
retry metrics are generic and deterministic
payload redaction is preserved
telemetry backend failure cannot alter workflow outcome
OpenTelemetry interoperability is demonstrated without a required dependency
RuntimeEvent vocabulary remains unchanged
package-root API remains unchanged
~~~

## Non-goals

M49 does not add:

~~~text
mandatory OpenTelemetry dependency
telemetry collector
metrics server
Prometheus endpoint
trace storage
log aggregation service
business metrics
distributed tracing context propagation between arbitrary workloads
new RuntimeEvent types
new database tables
new Alembic migration
~~~

## Next

M50 — Reference Integration Packages — 0.8.0a4.
