# Troubleshooting

## The CLI cannot import my workflow

CLI targets must use `module:attribute` syntax.

Correct:

```text
my_package.workflows:daily
```

Incorrect:

```text
my_package/workflows.py
```

Run the command from an environment where the module is importable.

## `inspect` cannot find the run created by `run`

The default metadata backend is in-memory. Two CLI invocations are separate Python
processes and therefore do not share that state.

Use SQLite or PostgreSQL for cross-process inspection. See
[Persistence and Evidence](persistence-and-evidence.md).

## My task receives the wrong number of arguments

Supported task handlers are:

```text
() -> object
(RunContext) -> object
```

RQ-03 enforces this statically. A two-argument task handler is not part of the executable
contract.

## My retry never happens

Check all three parts of the retry policy:

```text
max_attempts > 1
error category is retryable
backoff policy is valid
```

`max_attempts` includes the initial attempt.

## My plugin works only with internal imports

Use `pyworkflowkit.ecosystem` as the authoring facade. RQ-03 re-exports the support
types required by the public extension Protocols.

If a Protocol cannot be implemented through the frozen facade, treat that as a
compatibility defect rather than silently depending on an internal module path.

## Which command should automation use?

Prefer `--json` output. The CLI machine contract v1 freezes machine-facing keys and exit
codes separately from human-readable formatting.

## Where should I start?

Use this order:

```text
getting-started.md
    ↓
cli-workflow.md
    ↓
failures-and-retries.md
    ↓
persistence-and-evidence.md
    ↓
plugin-authoring.md
```
