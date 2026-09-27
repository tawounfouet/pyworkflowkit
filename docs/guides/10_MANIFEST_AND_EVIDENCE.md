# 10 — Manifest and Evidence

## What you will learn

You will understand the `RunManifest` as a portable terminal summary and distinguish it
from the event log and current runtime state.

## Mental model

```text
WorkflowRun
    current/final state

RuntimeEvent[]
    ordered history

RunManifest
    portable final summary

Lineage
    causal relationships
```

These surfaces complement each other; none is a complete replacement for the others.

## Build a manifest

After a terminal run:

```python
manifest = runtime.manifest(definition, run.run_id)

print(manifest.run_id)
print(manifest.status)
```

The manifest is designed to summarize terminal execution evidence in a portable form.

## CLI manifest

With durable metadata:

```bash
pwk manifest workflow:demo <RUN_ID> --config pyworkflowkit.toml
```

Machine mode:

```bash
pwk manifest workflow:demo <RUN_ID> --config pyworkflowkit.toml --json
```

## Manifest vs events

Use events when you need the timeline:

```text
TASK_STARTED
TASK_RETRYING
TASK_SUCCEEDED
```

Use the manifest when you need the final portable result:

```text
run identity
terminal status
task outcomes
attempt summary
references/evidence
```

## Lineage

The public facade also exposes:

```python
lineage = runtime.lineage(definition, run.run_id)
```

Lineage answers which runtime facts, dependencies, artifacts, and external references are
causally related.

## Common mistakes

- generating a final manifest before the run is terminal;
- treating the manifest as a full event log;
- embedding secrets in evidence;
- assuming external references are the external system itself rather than pointers to it.

## Exercises

1. Build a manifest for a successful workflow.
2. Compare it with the event history.
3. Run the workflow again and compare run IDs.
4. Inspect lineage for a multi-task workflow.

## Related example

Canonical companion: [`examples/11_manifest.py`](../../examples/11_manifest.py).

## Related notebook

DX05 target: `10 - Run Manifest.ipynb`.

## Next chapter

Continue with [11 — MetadataStore](11_METADATA_STORE.md).
