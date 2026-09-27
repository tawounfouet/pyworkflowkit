# 14 — Configuration

## What you will learn

You will configure PyWorkflowKit through defaults, environment variables, TOML, and explicit
overrides while understanding their precedence.

## Configuration precedence

```text
explicit overrides
        ↓
TOML file
        ↓
environment variables
        ↓
defaults
```

Higher entries win over lower entries.

## Defaults

```python
from pyworkflowkit import RuntimeSettings

settings = RuntimeSettings.load()
print(settings.runtime.workspace)
print(settings.metadata.backend)
```

The default metadata backend is `memory`.

## TOML

```toml
[runtime]
workspace = ".pyworkflow-demo"

[metadata]
backend = "sqlite"
sqlite_path = "runtime.sqlite3"
sqlite_wal = true
```

Load it:

```python
settings = RuntimeSettings.load(config_file="pyworkflowkit.toml")
```

## Environment variables

Nested keys use a double underscore:

```bash
export PYWORKFLOWKIT_RUNTIME__WORKSPACE=.pyworkflow-env
export PYWORKFLOWKIT_METADATA__BACKEND=sqlite
export PYWORKFLOWKIT_METADATA__SQLITE_PATH=env.sqlite3
```

## Explicit overrides

```python
settings = RuntimeSettings.load(
    config_file="pyworkflowkit.toml",
    overrides={
        "metadata": {
            "sqlite_wal": False,
        }
    },
)
```

That explicit value wins over the file and environment.

## Redacted diagnostics

Sensitive values such as the PostgreSQL DSN are represented as secrets.

```python
print(settings.redacted_dict())
```

Use the redacted view for diagnostics rather than dumping secret-bearing configuration.

## Common mistakes

- assuming the config file overrides explicit Python values;
- using a single underscore for nested environment settings;
- logging raw secret configuration;
- putting workload business configuration into runtime settings without a clear reason.

## Exercises

1. Set a workspace through the environment.
2. Override it from TOML.
3. Override it again explicitly and observe precedence.
4. Configure SQLite without changing Python workflow code.

## Related example

Canonical companion: [`examples/14_configuration.py`](../../examples/14_configuration.py).

## Related notebook

Canonical notebook: [`12 - Configuration.ipynb`](<../../notebooks/12 - Configuration.ipynb>).

## Next chapter

Continue with [15 — CLI Zero to Hero](15_CLI_ZERO_TO_HERO.md).
