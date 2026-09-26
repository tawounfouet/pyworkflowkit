# M35 — Observability Plugins

M35 turns the existing event-plugin foundation into a concrete runtime-observability
extension boundary.

## Source model

The architecture distinguishes:

```text
EVENT
    structured business/runtime fact

LOG
    diagnostic narrative

METRIC
    aggregated measurement
```

The complete observability model remains layered:

```text
STATE
EVENTS
LOGS
METRICS
MANIFEST
LINEAGE
```

M35 does not collapse those layers into one abstraction.

## Principle

RuntimeEvent remains durable execution evidence.

Observability plugins consume committed events as secondary projections.

```text
Runtime state transition
        ↓
MetadataStore UnitOfWork
        ↓
RuntimeEvent staged
        ↓
COMMIT
        ↓
ObservabilityDispatcher
        ↓
RuntimeEventSink
        ↓
external projection
```

This order is mandatory.

A sink never receives an event that failed to commit.

## RuntimeEventSink port

The new port is intentionally small:

```python
class RuntimeEventSink(Protocol):
    @property
    def name(self) -> str: ...

    def emit(self, event: RuntimeEvent) -> None: ...
```

The sink receives the existing immutable RuntimeEvent domain value.

It does not own persistence, state transitions, retries, scheduling, or workflow
progression.

## Why event-driven

RuntimeEvent already provides:

```text
run_id
task_run_id
task_id
attempt_number
event_sequence
event_type
occurred_at
payload
```

Those fields are sufficient for external plugins to derive:

```text
structured logs
counters
timers
retry metrics
failure metrics
traces/spans
dashboards
audit feeds
vendor-specific telemetry
```

PyWorkflowKit therefore does not need vendor APIs in the core.

## Deterministic fan-out

ObservabilityDispatcher registers sinks by stable name.

For one event:

```text
sink alpha
sink beta
sink zeta
```

are called in deterministic lexical name order.

This makes tests and diagnostics reproducible.

## Failure isolation

Observability is not runtime state authority.

If one sink raises:

```text
RuntimeEvent already committed
        ↓
sink raises exception
        ↓
ObservabilityDispatchFailure recorded
        ↓
warning logged
        ↓
remaining sinks still receive event
        ↓
workflow continues
```

A telemetry outage must not turn a successful workflow into a failed workflow.

## Failure diagnostics

Each isolated failure records:

```text
sink_name
event_id
event_type
error_type
error_message
```

WorkflowRuntime exposes the accumulated diagnostics through:

```python
runtime.observability_failures
```

This collection is process-local diagnostic state, not durable runtime evidence.

## Sequential runner

Every persistence helper that commits a RuntimeEvent publishes it only after the
UnitOfWork commit succeeds.

Single-event transition:

```text
save state
add event
commit
publish event
```

Atomic multi-event terminal failure:

```text
save failed state
add TASK_FAILED
add TASK_SKIPPED*
add WORKFLOW_FAILED
commit once
publish events in event_sequence order
```

## Concurrent runner

ConcurrentRunner inherits the same event persistence/publish helpers from Runner.

Its own running-sibling failure helper follows the same post-commit rule.

Worker threads/processes/coroutines do not invoke observability sinks directly.

The coordinator remains the single authority for state and event publication.

## WorkflowRuntime facade

Users can register a sink explicitly:

```python
runtime.register_event_sink(MySink())
```

No sink is enabled automatically.

This preserves embedded-runtime predictability.

## Plugin foundation

M22/M23 already defined:

```text
PluginType.EVENT
pyworkflowkit.events
```

M35 now gives that category a concrete type:

```text
PluginRegistry[RuntimeEventSink]
```

An entry-point provider can therefore return a RegisteredPlugin whose factory builds a
RuntimeEventSink.

Discovery remains opt-in.

## Logs

Existing stdlib structured runtime logging remains unchanged.

RuntimeEvent and diagnostic log remain different concepts:

```text
TASK_STARTED
    = durable runtime fact

"Task execution started"
    = diagnostic narrative
```

A RuntimeEventSink may project events into another logging backend, but the domain event
is not replaced by that log.

## Metrics

M35 does not add a metric domain model to the runtime core.

A sink may derive aggregates such as:

```text
workflow_started_total
workflow_failed_total
task_retry_total
task_failed_total
```

or durations by correlating committed events.

Vendor-specific metric instruments stay outside the core.

## Tracing

Tracing is also a projection.

A plugin may map run/task/attempt correlation identifiers to spans, but M35 does not make
OpenTelemetry or any tracing SDK a runtime dependency.

## Redaction and security

Existing structured log redaction remains unchanged.

M35 does not introduce a new event-payload redaction policy. Stronger observability
redaction, allowlists, secret policy, and telemetry hardening remain part of M36 Security
Hardening.

## Public API boundary

M35 adds advanced imports:

```python
from pyworkflowkit.ports.observability import RuntimeEventSink

from pyworkflowkit.application.observability_plugins import (
    ObservabilityDispatchFailure,
    ObservabilityDispatcher,
)
```

The package-root API remains intentionally small.

## Acceptance gates

M35 is qualified by:

- RuntimeEventSink runtime-checkable protocol;
- deterministic sink ordering;
- duplicate/blank sink-name rejection;
- isolated sink failure;
- continued fan-out after one sink fails;
- typed PluginType.EVENT registry;
- sequential Runner post-commit publication;
- ConcurrentRunner post-commit publication;
- durable event sequence equivalence;
- WorkflowRuntime sink registration;
- unchanged workflow outcome during telemetry failure;
- Python 3.11 / 3.12 / 3.13 CI;
- Ruff;
- strict mypy;
- branch coverage;
- reference acceptance;
- wheel/version smoke;
- PostgreSQL regression contract.

## Boundary

M35 does not implement:

- mandatory telemetry backends;
- OpenTelemetry dependency;
- Prometheus dependency;
- Datadog dependency;
- remote telemetry delivery guarantees;
- durable observability failure storage;
- asynchronous telemetry queues;
- payload redaction policy;
- executable/security hardening — M36;
- recovery/resume — 0.6.
