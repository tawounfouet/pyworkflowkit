# 09 — Events and Observability

## What you will learn

You will distinguish runtime state from runtime history and inspect the ordered events
emitted by a workflow run.

## Mental model

```text
state
    What is true now?

events
    What happened, and in what order?
```

Typical event flow for a successful single task:

```text
WORKFLOW_STARTED
TASK_READY
TASK_STARTED
TASK_SUCCEEDED
WORKFLOW_SUCCEEDED
```

## Inspect events

```python
events = runtime.events(run.run_id)

for event in events:
    print(event.sequence, event.event_type.value)
```

Runtime events are durable evidence when a durable metadata backend is used.

## CLI inspection

```bash
pwk events <RUN_ID> --config pyworkflowkit.toml
```

Machine mode:

```bash
pwk events <RUN_ID> --config pyworkflowkit.toml --json
```

## Observability sinks

Advanced applications can register a committed-event sink:

```python
runtime.register_event_sink(my_sink)
```

The ordering contract is important:

```text
state transition
      ↓
metadata transaction
      ↓
event persisted
      ↓
commit
      ↓
external observability sink
```

External sinks are projections. Durable runtime evidence remains the source of truth.

## Failure isolation

A sink failure must not rewrite a successfully committed workflow transition. Isolated
observability failures can be inspected through:

```python
runtime.observability_failures
```

## Common mistakes

- using logs as the only execution history;
- mutating historical event meaning;
- letting a metrics/log sink decide workflow state;
- parsing Rich human output instead of `--json`.

## Exercises

1. Print every event type for a two-task workflow.
2. Add a retry and identify `TASK_RETRYING`.
3. Compare events between two independent runs.
4. Inspect events using both Python and `pwk`.

## Related example

Canonical companion: [`examples/10_events.py`](../../examples/10_events.py).

## Related notebook

Canonical notebook: [`09 - Events and Evidence.ipynb`](<../../notebooks/09 - Events and Evidence.ipynb>).

## Next chapter

Continue with [10 — Manifest and Evidence](10_MANIFEST_AND_EVIDENCE.md).
