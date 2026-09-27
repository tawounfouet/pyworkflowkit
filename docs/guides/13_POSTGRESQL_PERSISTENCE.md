# 13 — PostgreSQL Persistence

## What you will learn

You will enable the optional PostgreSQL metadata backend and keep the database DSN outside
ordinary source code.

## Install the optional backend

```bash
python -m pip install "pyworkflowkit[postgres]"
```

The PostgreSQL adapter exposes the same workflow metadata semantics as the local backends.

## Configure with environment variables

PyWorkflowKit uses the prefix `PYWORKFLOWKIT_` and `__` for nested settings.

Example:

```bash
export PYWORKFLOWKIT_METADATA__BACKEND=postgres
export PYWORKFLOWKIT_METADATA__POSTGRES_DSN='postgresql+psycopg://user:password@localhost/pwk'
```

Then:

```python
from pyworkflowkit import RuntimeSettings, WorkflowRuntime

settings = RuntimeSettings.load()
runtime = WorkflowRuntime(settings)
```

## Explicit configuration

```python
from pyworkflowkit import RuntimeSettings

settings = RuntimeSettings.load(
    overrides={
        "metadata": {
            "backend": "postgres",
            "postgres_dsn": "postgresql+psycopg://user:password@localhost/pwk",
            "postgres_pool_size": 5,
            "postgres_max_overflow": 10,
            "postgres_application_name": "my-service",
        }
    }
)
```

For real deployments, prefer a secret-injection mechanism rather than committing credentials
to source control.

## Why PostgreSQL

Use PostgreSQL when the metadata store needs characteristics such as multiple writers,
stronger concurrent access, server-managed durability, and operational database tooling.

PyWorkflowKit still remains an embedded runtime; choosing PostgreSQL does not turn it into
a scheduler or control plane.

## Common mistakes

- forgetting the `postgres` optional dependency;
- committing the DSN to the repository;
- assuming PostgreSQL changes workflow semantics;
- using one shared database without an operational ownership model.

## Exercises

1. Install the PostgreSQL extra.
2. Provide the DSN only through the environment.
3. Print `settings.redacted_dict()` and verify the secret is hidden.
4. Run the same workflow against SQLite and PostgreSQL and compare public behavior.

## Related example

Canonical companion: [`examples/13_postgresql.py`](../../examples/13_postgresql.py).

The script validates PostgreSQL configuration without requiring a live server.

## Next chapter

Continue with [14 — Configuration](14_CONFIGURATION.md).
