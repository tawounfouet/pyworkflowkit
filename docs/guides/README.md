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
| [11](11_METADATA_STORE.md) | MetadataStore | Available |
| [12](12_SQLITE_PERSISTENCE.md) | SQLite persistence | Available |
| [13](13_POSTGRESQL_PERSISTENCE.md) | PostgreSQL persistence | Available |
| [14](14_CONFIGURATION.md) | Configuration | Available |
| [15](15_CLI_ZERO_TO_HERO.md) | CLI Zero-to-Hero | Available |
| [16](16_CONCURRENCY.md) | Concurrency | Available |
| [17](17_TIMEOUTS_AND_CANCELLATION.md) | Timeouts and cancellation | Available |
| [18](18_EXECUTORS.md) | Executors | Available |
| [19](19_PLUGINS_AND_ECOSYSTEM.md) | Plugins and ecosystem | Available |
| [20](20_EXTERNAL_WORKLOADS.md) | External workloads | Available |
| [21](21_CUSTOM_EXECUTOR.md) | Custom executor | Available |
| [22](22_CUSTOM_METADATA_STORE.md) | Custom MetadataStore | Available |
| [23](23_CONTROL_PLANE.md) | Control plane | Available |
| [24](24_PYINGESTKIT_INTEGRATION.md) | PyIngestKit integration | Available |
| [25](25_TESTING_WORKFLOWS.md) | Testing workflows | Available |
| [26](26_DEBUGGING_AND_TROUBLESHOOTING.md) | Debugging and troubleshooting | Available |
| [27](27_PRODUCTION_PATTERNS.md) | Production patterns | Available |
| [99](99_COMPLETE_REFERENCE_APPLICATION.md) | Complete reference application | Available |

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

Executable companions live under [`examples/`](../../examples/README.md) and interactive exploration companions live under [`notebooks/`](../../notebooks/README.md).

## Product boundary

PyWorkflowKit executes generic dependency graphs of workloads. It is not a scheduler,
control plane, Web UI, IAM system, or distributed worker platform.
