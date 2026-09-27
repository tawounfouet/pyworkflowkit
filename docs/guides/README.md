# PyWorkflowKit — Zero-to-Hero Guides

This directory is the canonical progressive learning path for PyWorkflowKit 1.1.

The guides teach the public framework from first installation to advanced embedding and
integration. Beginner chapters use the stable `pyworkflowkit` package facade and the
canonical `pwk` command. Internal modules are introduced only when an advanced capability
cannot be expressed through the stable facade.

## Learning path

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
failure / retry
  ↓
events / manifest
  ↓
persistence
  ↓
configuration / CLI
  ↓
concurrency / executors
  ↓
plugins / integrations
  ↓
production patterns
```

## Chapters

| Chapter | Topic | Status |
|---|---|---|
| [00](00_ZERO_TO_HERO.md) | Zero-to-Hero orientation | Available |
| [01](01_INSTALLATION_AND_FIRST_WORKFLOW.md) | Installation and first workflow | Available |
| [02](02_TASKS_AND_HANDLERS.md) | Tasks and handlers | Available |
| [03](03_WORKFLOW_DEFINITIONS.md) | Workflow definitions | Available |
| [04](04_DEPENDENCIES_AND_DAG.md) | Dependencies and DAG | Available |
| [05](05_EXECUTION_PLANNING.md) | Execution planning | Available |
| [06](06_WORKFLOW_RUNTIME.md) | Workflow runtime | Available |
| [07](07_RUN_CONTEXT_AND_DATA_FLOW.md) | RunContext and data flow | Available |
| [08](08_FAILURES_AND_RETRIES.md) | Failures and retries | Available |
| [09](09_EVENTS_AND_OBSERVABILITY.md) | Events and observability | Available |
| [10](10_MANIFEST_AND_EVIDENCE.md) | Manifest and evidence | Available |
| 11 | MetadataStore | Planned in DX03 |
| 12 | SQLite persistence | Planned in DX03 |
| 13 | PostgreSQL persistence | Planned in DX03 |
| 14 | Configuration | Planned in DX03 |
| 15 | CLI Zero-to-Hero | Existing CLI guide will be promoted |
| 16–27 | Advanced runtime, integrations and production patterns | Planned in DX03 |
| 99 | Complete reference application | Planned in DX03 |

## Guide contract

Each major chapter aims to provide:

1. what you will learn;
2. a mental model;
3. a minimal example;
4. a step-by-step explanation;
5. object inspection;
6. a CLI equivalent where relevant;
7. common mistakes;
8. exercises;
9. a related executable example;
10. a related notebook;
11. the next chapter.

The executable examples and notebooks are separate roadmap lots. Until DX04 and DX05 land,
guide links may explicitly say that the companion artifact is planned rather than pretend it
already exists.

## Product boundary

PyWorkflowKit executes generic dependency graphs of workloads. It is not a scheduler,
control plane, Web UI, IAM system, or distributed worker platform.
