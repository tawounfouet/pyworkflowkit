# 26 — Debugging and Troubleshooting

## What you will learn

You will diagnose common local workflow failures using the CLI, runtime evidence, and the
public extension boundaries.

## Workflow import failures

CLI targets use:

```text
module:attribute
```

Correct:

```text
my_package.workflows:daily
```

Run the command from an environment where the module is importable.

## Run not found after a CLI command

The default metadata backend is memory. Separate CLI invocations do not share one process.

Use SQLite or PostgreSQL when later commands must inspect an earlier run.

## Handler signature errors

Supported synchronous task handlers are:

```text
() -> object
(RunContext) -> object
```

Avoid broad implicit argument injection.

## Retry not happening

Check:

```text
max_attempts > 1
error category is retryable
backoff policy is valid
```

Remember that `max_attempts` includes the first attempt.

## Runtime evidence

Use:

```bash
pwk inspect <RUN_ID> --config pyworkflowkit.toml
pwk events <RUN_ID> --config pyworkflowkit.toml
pwk manifest workflow:demo <RUN_ID> --config pyworkflowkit.toml
```

For automation, add `--json`.

## Plugin problems

Third-party packages should use `pyworkflowkit.ecosystem`. If a plugin only works through
internal imports, treat that as a compatibility problem.

Inspect installed plugin candidates with:

```bash
pwk plugins
pwk doctor
```

## Debugging order

```text
definition
  ↓
validate
  ↓
plan
  ↓
run
  ↓
inspect
  ↓
events
  ↓
manifest
```

This order narrows the failing layer before you reach for internal implementation details.

Use the [canonical example index](../../examples/README.md) to reproduce concepts in isolation before debugging a larger application.

## Next chapter

Continue with [27 — Production Patterns](27_PRODUCTION_PATTERNS.md).
