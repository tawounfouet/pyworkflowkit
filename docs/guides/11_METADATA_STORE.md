# 11 — MetadataStore

## What you will learn

You will understand why workflow state must be stored behind a persistence contract and how
the default in-memory backend differs from durable backends.

## Mental model

```text
WorkflowRuntime
      ↓
MetadataStore contract
      ├── memory
      ├── SQLite
      └── PostgreSQL
```

The runtime decides *what* state means. The metadata backend decides *how* that state is
stored.

## What is persisted

The metadata layer records runtime evidence such as:

```text
WorkflowRun
TaskRun
TaskAttempt
RuntimeEvent
ArtifactReference
ExternalRunRef
```

This is execution metadata, not arbitrary application data.

## Default memory backend

```python
from pyworkflowkit import WorkflowRuntime

runtime = WorkflowRuntime()
```

The default backend is memory. It is ideal for tests, examples, and one-process
experimentation.

Its important limitation is lifecycle:

```text
process exits
    ↓
in-memory runtime state disappears
```

## Why a port matters

Application code should not need different workflow semantics for memory, SQLite, or
PostgreSQL.

```text
same definition
same runtime semantics
different persistence adapter
```

That separation is what lets local experiments grow into durable execution without making
the domain depend on a database engine.

## Transaction boundary

Runtime state and its corresponding event should be committed atomically where the backend
supports it.

Conceptually:

```text
state transition
      +
runtime event
      ↓
one transaction
```

This avoids states such as “task succeeded but the success event is missing”.

## Common mistakes

- treating MetadataStore as a business repository;
- writing SQL directly from task handlers;
- relying on memory persistence across CLI processes;
- making runtime semantics backend-specific.

## Exercises

1. Run a workflow with the default memory backend.
2. Create a second `WorkflowRuntime` and try to load the first run.
3. Predict what changes after switching to SQLite.
4. List the runtime objects that belong in metadata versus application data.

## Related example

Canonical persistence companion: [`examples/12_sqlite.py`](../../examples/12_sqlite.py).

## Related notebook

Canonical notebook: [`11 - SQLite Persistence.ipynb`](<../../notebooks/11 - SQLite Persistence.ipynb>).

## Next chapter

Continue with [12 — SQLite Persistence](12_SQLITE_PERSISTENCE.md).
