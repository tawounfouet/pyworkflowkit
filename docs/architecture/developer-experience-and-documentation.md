# PyWorkflowKit Developer Experience & Documentation

Status: RQ-04 — 0.9.0b1

## Objective

RQ-04 proves that a developer can discover and use PyWorkflowKit without first learning
its internal architecture.

The milestone does not add runtime capability. It turns the first-use documentation into
executable release evidence.

## Developer Experience Contract

The machine-readable contract lives in:

```text
pyworkflowkit.contracts.developer_experience
```

with:

```python
DX_CONTRACT_VERSION = "1"
DX_TARGET_RELEASE = "1.0.0"
```

The contract records:

```text
required getting-started guides
executable first-use examples
allowed public authoring facades
required CLI first-run commands
```

The contract module itself remains internal release metadata under the existing
`pyworkflowkit.contracts.*` internal-module classification.

## Supported first-use path

RQ-04 qualifies this journey:

```text
install
  ↓
version
  ↓
define @task
  ↓
define @workflow
  ↓
run through WorkflowRuntime
  ↓
inspect events + manifest
  ↓
configure SQLite
  ↓
run through CLI
  ↓
inspect persisted run
  ↓
author first ecosystem plugin
```

## Public authoring boundary

The documented first-use path starts from only:

```text
pyworkflowkit
pyworkflowkit.ecosystem
```

The RQ-04 acceptance test parses every executable example and rejects PyWorkflowKit imports
from other module paths.

This does not forbid advanced internal examples elsewhere in the repository. It guarantees
that the recommended 1.0 onboarding path does not require internal architecture knowledge.

## Executable examples

RQ-04 qualifies:

```text
examples/00_hello_world.py
examples/01_failure_and_retry.py
examples/02_sqlite_persistence.py
examples/03_ecosystem_plugin.py
examples/getting_started_workflow.py
```

The former `00_hello_world.py` implementation used internal adapters, stores, runner,
clock, IDs, and manifest builders. RQ-04 replaces it with the stable public facade so the
first repository example now matches the documented product promise.

## Guides

The 1.0 first-use guide set is:

```text
docs/guides/getting-started.md
docs/guides/cli-workflow.md
docs/guides/failures-and-retries.md
docs/guides/persistence-and-evidence.md
docs/guides/plugin-authoring.md
docs/guides/troubleshooting.md
```

The guides deliberately separate:

```text
normal first-use path
    from
advanced architecture documentation
```

## CLI journey

The first-run CLI contract exercises:

```text
version
validate
plan
run
inspect
events
manifest
```

The qualification creates a temporary SQLite configuration, executes a decorated workflow,
captures its `run_id`, and verifies that later CLI processes can inspect the same durable
run.

Both console names are exercised:

```text
pyworkflow
pyworkflowkit
```

## Failures and retries

The retry example uses only the root facade and proves:

```text
RetryPolicy
BackoffStrategy
RuntimeError retry category
TASK_RETRYING evidence
successful recovery on attempt 2
```

## Persistence and evidence

The SQLite example proves:

```text
RuntimeSettings.load(...)
WorkflowRuntime(settings)
run in process A
reopen runtime against same SQLite database
get_run(...)
events(...)
manifest(...)
```

No MetadataStore implementation import is required by the documented path.

## Plugin authoring

The plugin example starts only from:

```text
pyworkflowkit.ecosystem
```

and demonstrates a typed `ExternalWorkload` registration through
`plugin_registration()`.

## Qualification strategy

Regular CI runs:

```text
RQ-04 contract tests
all public first-use examples
complete API/CLI user journey
```

Release Qualification repeats the same journey after installing the built wheel. Because
the repository uses a `src/` layout, running the examples from the repository root after
a non-editable wheel install still resolves `pyworkflowkit` from the installed artifact.

The Release Qualification gate therefore proves:

```text
documentation examples
    ↓
real wheel
    ↓
real console scripts
    ↓
real SQLite persistence
    ↓
real runtime evidence
```

## Exit criteria

```text
package version = 0.9.0b1
Developer Experience Contract v1 targets 1.0.0
README contains an explicit Start here path
all required guides exist
all first-use examples import only documented public facades
hello-world public example succeeds
retry example observes TASK_RETRYING and succeeds
SQLite example reopens persisted evidence
plugin example constructs a typed workload plugin
CLI version/validate/plan/run/inspect/events/manifest journey succeeds
pyworkflowkit console alias matches pyworkflow
source CI is green
built-wheel Release Qualification gate is green
```

## Next

RQ-05 — Packaging & Distribution.
