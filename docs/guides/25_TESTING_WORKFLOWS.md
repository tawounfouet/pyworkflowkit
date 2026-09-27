# 25 — Testing Workflows

## What you will learn

You will test workflow behavior at the right level: handlers, definitions, graph planning,
runtime state, evidence, and interchangeable adapters.

## Test layers

```text
handler unit tests
      ↓
definition / DAG tests
      ↓
runtime integration tests
      ↓
adapter contract tests
      ↓
reference workflow acceptance
      ↓
installed-artifact qualification
```

A workflow framework should not be qualified only through isolated helper functions.

## Handler tests

Keep business handlers directly testable as ordinary Python callables where practical.

## Definition and planning tests

Verify:

- dependencies;
- invalid cycles;
- deterministic plan shape;
- workflow/task identity.

## Runtime tests

Verify observable outcomes:

```text
WorkflowRun state
TaskRun state
TaskAttempt count
RuntimeEvent sequence
RunManifest
```

## Contract tests

Interchangeable executors and metadata stores should satisfy shared behavioral contracts.
This is stronger than testing only one concrete adapter.

## Reference workflows

PyWorkflowKit maintains stable acceptance scenarios such as single-task success, linear
dependency execution, retry, persistence, concurrency, timeout, cancellation, and recovery.

Use those scenarios as behavioral specifications, not as duplicated business logic.

## CLI tests

Machine-facing tests should use `--json` and assert exit codes separately from human Rich
rendering.

## Related executable qualification

DX04 smoke coverage lives in [`tests/reference/test_v1_1_canonical_examples.py`](../../tests/reference/test_v1_1_canonical_examples.py) and executes every canonical companion as a clean process.

## Next chapter

Continue with [26 — Debugging and Troubleshooting](26_DEBUGGING_AND_TROUBLESHOOTING.md).
