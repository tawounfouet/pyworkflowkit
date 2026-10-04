# PyWorkflowKit 1.1 — Developer Experience & Learning Roadmap

## 1. Purpose

PyWorkflowKit `1.0.0` establishes the stable embedded workflow runtime.

The `1.1.x` line is dedicated to improving how developers **discover, learn, explore, operate, and extend** the framework without changing its core product boundary.

The objective is to move from a technically stable runtime to a framework that is also:

- easy to install and identify from the terminal;
- pleasant to operate interactively;
- teachable from zero to advanced usage;
- explorable through executable Python examples and notebooks;
- demonstrably coherent across documentation, CLI, examples, notebooks, and tests.

This roadmap must not turn PyWorkflowKit into a workflow platform.

The product boundary remains:

```text
PyIngestKit
    HOW TO EXECUTE A RELIABLE INGESTION LIFECYCLE

PyWorkflowKit
    HOW TO EXECUTE A GENERIC DEPENDENCY GRAPH OF WORKLOADS

Ochestrix
    HOW TO OPERATE AND GOVERN THOSE EXECUTIONS
```

---

## 2. Starting point

Stable baseline:

```text
Version       1.0.0
Tag           v1.0.0
Commit        d47adfd6949bd4f2cf9ef2e015d321e48b57ea33
Status        qualified
Runtime       frozen for 1.0
```

The `1.1.x` line starts **after** the stable `1.0.0` runtime qualification.

No `1.1.x` work must be retrofitted into the `1.0.0` release commit.

---

## 3. Guiding principles

### 3.1 Preserve the stable runtime

The `1.1.x` effort is primarily Developer Experience and Learning.

Changes to runtime semantics must be avoided unless required to correct a defect in an already documented public contract.

### 3.2 Keep machine contracts stable

The human CLI may become richer, but machine-readable output must remain deterministic and contract-driven.

```text
Human CLI
    ↓
Rich rendering

Machine CLI
    ↓
--json
    ↓
stable machine contract
```

### 3.3 One concept, multiple learning surfaces

Every important public concept should be represented through complementary surfaces:

```text
Guide
  ↓ explains

Example .py
  ↓ proves executable usage

Notebook .ipynb
  ↓ supports interactive exploration

CLI
  ↓ operates the framework

Tests
  ↓ prove correctness
```

### 3.4 Avoid platform drift

The following remain out of scope:

- distributed scheduler;
- long-running workflow server;
- worker fleet management;
- Web UI;
- IAM;
- centralized control plane;
- agent framework;
- Airflow-like orchestration platform.

---

# 4. Release line

The proposed release sequence is:

```text
1.1.0a1  CLI identity and pwk alias
1.1.0a2  Rich human CLI
1.1.0a3  Zero-to-Hero documentation architecture
1.1.0b1  Canonical executable examples
1.1.0b2  Interactive notebooks
1.1.0rc1 Transverse Developer Experience qualification
1.1.0    Stable Developer Experience & Learning release
```

---

# 5. LOT-DX00 — Close the 1.0 release ceremony

## Objective

Finish the non-development release ceremony around the already qualified `v1.0.0`.

## Actions

- verify `v1.0.0` points to the stable merge commit;
- verify tag-based Release Qualification is green;
- create the GitHub Release `v1.0.0`;
- use `docs/releases/1.0.0.md` as the release-note basis;
- keep the software-license decision explicit before any public package publication;
- do not publish to PyPI implicitly;
- open the `1.1.x` development line only after the `1.0.0` runtime is frozen.

## Exit criteria

```text
v1.0.0 tag                         ✅
tag qualification                 ✅
GitHub Release                    ✅
1.0 runtime frozen                ✅
1.1 work isolated from 1.0        ✅
```

---

# 6. LOT-DX01 — Canonical CLI identity: `pwk`

Target: **1.1.0a1**

## Objective

Introduce `pwk` as the canonical short command for PyWorkflowKit.

## Naming contract

```text
PyPI package       pyworkflowkit
Python namespace   pyworkflowkit
Canonical CLI      pwk
Long CLI alias     pyworkflowkit
Compatibility CLI  pyworkflow
```

## Packaging change

Target:

```toml
[project.scripts]
pwk = "pyworkflowkit.cli:main"
pyworkflowkit = "pyworkflowkit.cli:main"
pyworkflow = "pyworkflowkit.cli:main"
```

## Required behavior

The following must be equivalent:

```bash
pwk version
pyworkflowkit version
pyworkflow version
```

The aliases must share:

- identical command set;
- identical exit codes;
- identical JSON payloads;
- identical validation behavior;
- identical version output.

## Documentation rule

All new beginner-facing documentation should use `pwk` as the default command.

The long aliases remain documented in a compatibility note.

## Tests

Add qualification covering:

- installation of all console entry points;
- version parity;
- command parity;
- JSON parity;
- exit-code parity.

## Exit criteria

```text
pwk installed                     ✅
legacy aliases preserved          ✅
CLI contract unchanged            ✅
tests green                       ✅
docs use pwk by default           ✅
```

---

# 7. LOT-DX02 — Rich human CLI

Target: **1.1.0a2**

## Objective

Improve terminal readability without modifying machine-readable contracts.

## Dependency

Add Rich as a direct runtime dependency if the code imports Rich directly.

## Architecture

Introduce an explicit presentation layer:

```text
src/pyworkflowkit/
├── cli.py
└── cli_rendering/
    ├── __init__.py
    ├── console.py
    ├── formatting.py
    ├── tables.py
    └── trees.py
```

The CLI should continue to build stable data payloads first.

Rendering becomes a separate concern:

```text
command
   ↓
domain/application result
   ↓
stable payload
   ├── --json → JSON renderer
   └── human  → Rich renderer
```

## Commands to enrich

Priority:

- `pwk plan`
- `pwk inspect`
- `pwk events`
- `pwk manifest`
- `pwk plugins`
- `pwk doctor`

Secondary:

- `pwk validate`
- `pwk run`
- `pwk version`

## Presentation primitives

Use Rich selectively:

- tables for task/run summaries;
- trees for dependency or execution-plan structure;
- panels for workflow/run summaries;
- status symbols for success/failure;
- readable exception presentation.

## Machine-contract invariant

`--json` must not depend on Rich.

No color codes, formatting markup, or human text may leak into JSON output.

## Exit criteria

```text
Rich human rendering             ✅
JSON behavior unchanged          ✅
exit codes unchanged             ✅
snapshot/contract tests green    ✅
terminal output readable         ✅
```

---

# 8. LOT-DX03 — Zero-to-Hero guide architecture

Target: **1.1.0a3**

## Objective

Turn `docs/guides/` into the canonical progressive learning path.

## Target structure

```text
docs/guides/
├── README.md
├── 00_ZERO_TO_HERO.md
├── 01_INSTALLATION_AND_FIRST_WORKFLOW.md
├── 02_TASKS_AND_HANDLERS.md
├── 03_WORKFLOW_DEFINITIONS.md
├── 04_DEPENDENCIES_AND_DAG.md
├── 05_EXECUTION_PLANNING.md
├── 06_WORKFLOW_RUNTIME.md
├── 07_RUN_CONTEXT_AND_DATA_FLOW.md
├── 08_FAILURES_AND_RETRIES.md
├── 09_EVENTS_AND_OBSERVABILITY.md
├── 10_MANIFEST_AND_EVIDENCE.md
├── 11_METADATA_STORE.md
├── 12_SQLITE_PERSISTENCE.md
├── 13_POSTGRESQL_PERSISTENCE.md
├── 14_CONFIGURATION.md
├── 15_CLI_ZERO_TO_HERO.md
├── 16_CONCURRENCY.md
├── 17_TIMEOUTS_AND_CANCELLATION.md
├── 18_EXECUTORS.md
├── 19_PLUGINS_AND_ECOSYSTEM.md
├── 20_EXTERNAL_WORKLOADS.md
├── 21_CUSTOM_EXECUTOR.md
├── 22_CUSTOM_METADATA_STORE.md
├── 23_CONTROL_PLANE.md
├── 24_PYINGESTKIT_INTEGRATION.md
├── 25_TESTING_WORKFLOWS.md
├── 26_DEBUGGING_AND_TROUBLESHOOTING.md
├── 27_PRODUCTION_PATTERNS.md
└── 99_COMPLETE_REFERENCE_APPLICATION.md
```

Existing guides should be reused, expanded, renamed, or linked rather than silently duplicated.

## Learning progression

The canonical progression is:

```text
install
  ↓
task
  ↓
workflow
  ↓
dependency
  ↓
DAG
  ↓
execution plan
  ↓
runtime
  ↓
run context
  ↓
failure
  ↓
retry
  ↓
events
  ↓
manifest
  ↓
persistence
  ↓
configuration
  ↓
CLI
  ↓
concurrency
  ↓
extensions
  ↓
integration
  ↓
production patterns
```

## Guide template

Every major guide should include:

1. What you will learn
2. Mental model
3. Minimal example
4. Step-by-step explanation
5. Object inspection
6. CLI equivalent where relevant
7. Common mistakes
8. Exercises
9. Related example
10. Related notebook
11. Next chapter

## Exit criteria

- every public concept has a pedagogical entry point;
- beginner guides avoid unnecessary internal imports;
- every guide links to the next logical guide;
- code snippets use the stable public API;
- CLI examples use `pwk`;
- guides do not imply platform features outside the product boundary.

---

# 9. LOT-DX04 — Canonical executable examples

Target: **1.1.0b1**

## Objective

Create a complete set of small, canonical, executable Python examples.

## Target structure

```text
examples/
├── 00_hello_world.py
├── 01_tasks_and_handlers.py
├── 02_workflow_definitions.py
├── 03_dependencies.py
├── 04_dag.py
├── 05_execution_plan.py
├── 06_runtime.py
├── 07_run_context.py
├── 08_failure.py
├── 09_retry.py
├── 10_events.py
├── 11_manifest.py
├── 12_sqlite.py
├── 13_postgresql.py
├── 14_configuration.py
├── 15_concurrency.py
├── 16_timeout.py
├── 17_cancellation.py
├── 18_external_workload.py
├── 19_plugin.py
├── 20_custom_executor.py
├── 21_control_plane.py
├── integrations/
│   └── pyingestkit/
└── complete/
    └── data_pipeline.py
```

## Example rules

Every canonical example should be:

- executable from a clean development environment;
- deterministic where practical;
- short enough to understand;
- based on public API imports;
- suitable for copy/paste;
- free from notebook-specific behavior;
- covered by CI where feasible.

## Exit criteria

- every Zero-to-Hero guide has a canonical executable companion where relevant;
- all supported examples execute successfully;
- no example depends on accidental local state;
- examples clearly distinguish optional integrations.

---

# 10. LOT-DX05 — Interactive notebooks

Target: **1.1.0b2**

## Objective

Provide an interactive experimentation path for users who learn by inspecting objects and executing steps incrementally.

## Target structure

```text
notebooks/
├── README.md
├── 00 - Environment and Setup.ipynb
├── 01 - Hello Workflow.ipynb
├── 02 - Tasks and Handlers.ipynb
├── 03 - Workflow Definitions.ipynb
├── 04 - Dependencies and DAG.ipynb
├── 05 - Execution Planning.ipynb
├── 06 - Workflow Runtime.ipynb
├── 07 - RunContext and Data Flow.ipynb
├── 08 - Failures and Retries.ipynb
├── 09 - Events and Evidence.ipynb
├── 10 - Run Manifest.ipynb
├── 11 - SQLite Persistence.ipynb
├── 12 - Configuration.ipynb
├── 13 - Concurrency.ipynb
├── 14 - Executors.ipynb
├── 15 - Plugins.ipynb
├── 16 - External Workloads.ipynb
├── 17 - PyIngestKit Integration.ipynb
└── 99 - Complete Workflow Lab.ipynb
```

## Notebook learning model

Notebooks must not simply duplicate `.py` files cell by cell.

They should follow:

```text
Concept
   ↓
Construction
   ↓
Inspection
   ↓
Modification
   ↓
Execution
   ↓
Observation
   ↓
Experiment
```

Typical notebook exploration should expose objects such as:

- `WorkflowDefinition`
- `TaskDefinition`
- `DependencyGraph`
- `ExecutionPlan`
- `WorkflowRun`
- `TaskRun`
- `TaskAttempt`
- `RuntimeEvent`
- `RunManifest`
- `ArtifactReference`
- `ExternalRunRef`

## Notebook boundaries

Notebooks are not the preferred surface for:

- console-script packaging;
- shell exit-code behavior;
- plugin package installation;
- long-running service lifecycle;
- PostgreSQL server provisioning;
- distribution publication.

Those topics remain better served by guides, scripts, packages, and CLI examples.

## Exit criteria

- notebooks open without structural errors;
- selected notebooks execute cleanly in CI;
- outputs are deterministic enough for repeatable learning;
- notebooks use stable public API imports;
- every notebook references its related guide and script.

---

# 11. LOT-DX06 — Cross-surface consistency

Target: **1.1.0rc1**

## Objective

Qualify the entire Developer Experience as one coherent product surface.

## Required consistency

For a concept such as retries:

```text
docs/guides/08_FAILURES_AND_RETRIES.md
                  ↓
examples/09_retry.py
                  ↓
notebooks/08 - Failures and Retries.ipynb
                  ↓
pwk run / inspect / events
                  ↓
tests
```

The terminology, public imports, semantics, and expected behavior should agree.

## Automated checks

Add or extend CI qualification for:

- `pwk` entry point availability;
- alias equivalence;
- JSON contract stability;
- Rich human-mode execution;
- canonical examples;
- notebook structural validation;
- selected notebook execution;
- broken documentation links;
- guide-to-example references;
- guide-to-notebook references;
- forbidden/internal imports in beginner examples;
- clean installation journey;
- complete Zero-to-Hero smoke journey.

## Developer Experience Contract

Prefer evolving the existing Developer Experience Contract rather than introducing an unrelated mechanism.

Candidate scope for a v2 contract:

```text
CLI identity
CLI machine behavior
guide topology
example topology
notebook topology
cross-reference integrity
first-use journey
advanced-use journey
```

## Exit criteria

```text
CLI qualification                   ✅
examples qualification              ✅
notebook qualification              ✅
docs link qualification             ✅
cross-surface consistency           ✅
clean install journey               ✅
Zero-to-Hero journey                ✅
```

---

# 12. Stable promotion — 1.1.0

## Promotion rule

`1.1.0` should only be promoted after `1.1.0rc1` is fully qualified.

Promotion should not introduce new runtime behavior.

## Final checks

- Python 3.11 / 3.12 / 3.13;
- wheel and sdist;
- core install;
- optional extras;
- CLI aliases;
- Rich human rendering;
- JSON contract;
- examples;
- notebooks;
- guides;
- reference application;
- upgrade from 1.0.0;
- security gates;
- packaging metadata.

---

# 13. Recommended implementation order

```text
STEP 0
Close GitHub Release v1.0.0
        ↓
STEP 1
Create 1.1 development branch
        ↓
STEP 2
LOT-DX01 — pwk
        ↓
STEP 3
LOT-DX02 — Rich CLI
        ↓
STEP 4
LOT-DX03 — Zero-to-Hero guides
        ↓
STEP 5
LOT-DX04 — executable examples
        ↓
STEP 6
LOT-DX05 — notebooks
        ↓
STEP 7
LOT-DX06 — transverse qualification
        ↓
1.1.0rc1
        ↓
qualification
        ↓
1.1.0 stable
```

---

# 14. Target repository experience

At the end of `1.1.0`, the repository should present a clear user journey:

```text
PyWorkflowKit
│
├── README.md
│      Discover
│
├── docs/
│   ├── guides/
│   │      Learn
│   ├── architecture/
│   │      Understand deeply
│   └── releases/
│          Track releases
│
├── examples/
│      Execute
│
├── notebooks/
│      Explore
│
├── integrations/
│      Extend & Qualify
│
├── src/pyworkflowkit/
│      Build / Embed
│
└── tests/
       Verify
```

CLI journey:

```text
pip install pyworkflowkit
        ↓
pwk version
        ↓
pwk validate
        ↓
pwk plan
        ↓
pwk run
        ↓
pwk inspect
        ↓
pwk events
        ↓
pwk manifest
        ↓
pwk plugins
        ↓
pwk doctor
```

Python learning journey:

```text
TaskDefinition
     ↓
WorkflowDefinition
     ↓
DependencyGraph
     ↓
ExecutionPlan
     ↓
WorkflowRuntime
     ↓
WorkflowRun
     ↓
RuntimeEvent
     ↓
RunManifest
     ↓
Persistence / Plugins / Integrations
```

---

# 15. Definition of Done for 1.1.0

PyWorkflowKit `1.1.0` is complete when:

- `pwk` is the canonical CLI command;
- `pyworkflowkit` and `pyworkflow` remain compatible aliases;
- human CLI output is readable and Rich-powered;
- `--json` remains deterministic and machine-oriented;
- the Zero-to-Hero path covers beginner to advanced usage;
- canonical `.py` examples cover the public framework surface;
- notebooks provide interactive exploration of the core model;
- guides, examples, notebooks, CLI, and tests use consistent terminology;
- CI verifies the complete DX journey;
- no platform responsibilities have leaked into PyWorkflowKit;
- upgrading from `1.0.0` to `1.1.0` remains predictable.

---

# 16. Summary roadmap

| Lot | Version | Goal | Status |
|---|---|---|---|
| DX00 | 1.0.0 closure | GitHub Release and freeze | Complete |
| DX01 | 1.1.0a1 | `pwk` canonical CLI | Complete |
| DX02 | 1.1.0a2 | Rich human CLI | Complete |
| DX03 | 1.1.0a3 | Zero-to-Hero guides | Complete |
| DX04 | 1.1.0b1 | Canonical Python examples | Complete |
| DX05 | 1.1.0b2 | Interactive notebooks | Complete |
| DX06 | 1.1.0rc1 | Transverse DX qualification | Complete |
| Stable | 1.1.0 | Developer Experience & Learning | Complete |

---

## 17. Stable closure

PyWorkflowKit `1.1.0` is the completed Developer Experience & Learning line.

```text
1.0.0   Stable Runtime
   ↓
1.1.0   Stable Developer Experience & Learning
```

Maintenance releases in the `1.1.x` line must preserve the qualified contracts.
New capability work belongs to a later roadmap and must not be retrofitted into the
`1.1.0` stable promotion.
