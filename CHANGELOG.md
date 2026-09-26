# Changelog

All notable changes to PyWorkflowKit will be documented in this file.

The project follows Semantic Versioning for released package lines and PEP 440 for Python pre-releases.

## Unreleased

### Added

- Explicit executor timeout capability levels: none, soft, and hard.
- Explicit executor cancellation capability levels: none, cooperative, and hard.
- Executor max_concurrency declaration with conservative invariants.
- Backward-compatible hard-timeout and hard-cancellation capability views.
- M25 acceptance coverage freezing LocalExecutor as single-slot, non-parallel, no-timeout, no-cancellation.

- Thread-safe CapacityManager with bounded global and per-executor execution slots.
- CapacityLease identity bound to TaskAttemptId for active-attempt accounting.
- Effective executor limits capped by intrinsic ExecutorCapabilities.max_concurrency.
- Immutable capacity snapshots exposing active and available global/executor slots.
- Explicit capacity configuration, invariant, and release errors.
- M26 acceptance coverage for saturation, release, active-attempt tracking, and concurrent acquisition safety.

- Immutable ExecutionHandle identities for submitted TaskAttempt executions.
- AttemptCompletion terminal outcomes carrying exactly one TaskResult or ExecutorError.
- Thread-safe FIFO CompletionQueue for worker-to-coordinator completion transfer.
- Blocking, non-blocking, and drain completion-consumption APIs.
- M27 acceptance coverage proving completion transfer without worker-owned state transitions.

- ThreadExecutor backed by concurrent.futures.ThreadPoolExecutor.
- Parallel trusted-Python workload execution with instance-bound max_concurrency.
- ExecutionHandle submission and CompletionQueue terminal-result transfer.
- Soft wait semantics that never interrupt an already running thread workload.
- Explicit executor shutdown lifecycle and duplicate-attempt submission protection.
- Shared in-process Python handler invocation mechanics across LocalExecutor and ThreadExecutor.
- M28 acceptance coverage for parallelism, soft timeout behavior, completion errors, and shutdown.

- ConcurrentRunner coordinator with serialized runtime-state authority.
- Bounded dispatch of multiple READY TaskRuns through CapacityManager and ThreadExecutor.
- Coordinator-owned fan-out/fan-in progression and completion processing.
- Duplicate-ready protection through serialized PENDING → READY → RUNNING transitions.
- FAIL_FAST concurrent semantics that stop new dispatch while allowing already-RUNNING siblings to finish.
- Concurrent retry coordination using the existing RetryEngine and Sleeper contracts.
- M29 mandatory coverage for fan-out, fan-in, capacity, duplicate-ready race, and fail-fast siblings.


### Changed

### Deprecated

### Removed

### Fixed

### Security

## 0.3.0 - 2026-09-26

### Added

- Strict Pydantic v2 serialization contracts for definitions and runtime evidence.
- Explicit Domain ↔ Schema mappers without Pydantic dependencies in domain objects.
- Neutral persistence Row DTOs for runtime entities, artifacts, and external references.
- Explicit Domain ↔ Row persistence mappings with UTC normalization.
- Canonical schema JSON codec with extra-field rejection and no implicit string fallback.
- SerializationError with structured path/type/reason context.
- SQLAlchemy 2.x dialect-neutral Declarative Base with deterministic naming conventions.
- Portable UTC datetime and JSON/JSONB persistence types.
- SQLAlchemy runtime/evidence rows for workflow runs, task runs, attempts, events, artifacts, and external run references.
- Explicit neutral-record ↔ ORM-row mappings.
- SqlAlchemyMetadataStore and SqlAlchemyUnitOfWork implementing the existing persistence ports.
- SQLAlchemy contract checks using a transient relational database without introducing the durable SQLite product adapter.
- Durable `SQLiteMetadataStore` backed by a local database file.
- SQLite connection policy with foreign keys enabled, configurable busy timeout, and optional WAL mode.
- Automatic parent-directory and schema bootstrap for local persistence.
- Restart acceptance coverage proving persisted runs, tasks, attempts, and events survive store recreation.
- Optional PostgreSQL persistence adapter with psycopg driver extra and READ COMMITTED transaction policy.
- PostgreSQL-native runtime UUID, TIMESTAMPTZ and JSONB mappings.
- PostgreSQL partial unique index preventing multiple RUNNING attempts for one TaskRun.
- PostgreSQL row-lock support and live PostgreSQL 15 contract qualification in CI.
- Alembic schema-evolution foundation with an explicit baseline runtime-metadata revision.
- Programmatic `upgrade_database()` and revision inspection for durable metadata engines.
- SQLite and PostgreSQL stores now bootstrap durable schemas through Alembic rather than `create_all()`.
- Fresh-upgrade and idempotent-upgrade migration qualification for SQLite and PostgreSQL.
- Wheel smoke coverage ensuring migration revision resources are shipped with the installed package.
- Strictly monotonic durable runtime-event ordering while allowing non-gapless sequences.
- Deterministic execution-lineage projection across task dependencies, attempts, artifacts, and external runs.
- Atomic local JSON export for canonical RunManifest evidence.
- V0.2 evidence-hardening acceptance coverage across SQLite restart, manifest serialization, lineage, and event ordering.
- Validated RuntimeSettings with nested environment-variable support.
- TOML configuration loading with explicit > file > environment > defaults precedence.
- SecretStr-backed PostgreSQL configuration with redacted diagnostic export.
- RuntimeFactory composition root for Memory, SQLite, PostgreSQL, and LocalExecutor.
- WorkflowRuntime public application facade for handler registration, execution, run lookup, events, manifests, and lineage.
- Intentional package-root API exposing workflow definitions, runtime settings, retry/result values, identifiers, and the public error root.
- Public API acceptance coverage proving end-to-end execution using only package-root imports.
- Lazy `@task` declaration producing explicit TaskHandle metadata without handler execution.
- Lazy `@workflow` declaration producing WorkflowBuilder values and immutable WorkflowDefinition materialization.
- Explicit decorator-level dependency declarations and handler references.
- Declarative acceptance coverage proving decoration/building never executes task workloads.
- Local Typer CLI with validate, plan, run, inspect, events, manifest, and version commands.
- Stable human and JSON CLI output modes with explicit validation/run failure exit codes.
- Dual console entrypoints `pyworkflow` and `pyworkflowkit` to cover the naming used across the architecture and acceptance corpus.
- CLI acceptance coverage across validation, deterministic planning, durable SQLite execution inspection, events, and manifest output.
- Structured LogContext correlation fields with recursive key-based secret redaction.
- Runner, LocalExecutor, and RetryEngine lifecycle diagnostics using stdlib logging.
- RuntimeInspector snapshots with ready/blocked task analysis and deadlock diagnostics.
- WorkflowRuntime.inspect_runtime() facade for structured persisted-run diagnostics.
- Observability acceptance coverage proving retry correlation without leaking sensitive workflow parameters.
- PluginType and immutable PluginDescriptor contracts with explicit plugin API version 1.
- Generic typed PluginRegistry and lazy RegisteredPlugin factories for manual registration.
- PluginCatalog with separate executor, metadata, workload, and event registries.
- Public PluginError hierarchy for duplicate, missing, and type-mismatched registrations.
- M22 acceptance coverage proving manual registration is explicit and performs no automatic discovery.
- Entry-point discovery across pyworkflowkit.executors, metadata, workloads, and events groups.
- Discovery metadata collection without importing plugin code.
- Explicit opt-in enablement with lazy provider loading.
- Plugin API compatibility checks against the runtime plugin contract version.
- Discovery reports distinguishing discovered, loaded, incompatible, and failed plugins.
- Failure isolation so non-enabled or broken plugins do not implicitly break the runtime.
- CLI `plugins` command for non-loading entry-point inventory.
- CLI `doctor --enable type:name` compatibility diagnostics for explicit plugin activation.
- PyIngestKit anti-corruption adapter treating one ingestion job as one atomic workflow task.
- Normalized PyIngestKitRunResult to TaskResult translation with ExternalRunRef evidence.
- PyIngestKit integration error translation into public PyWorkflowKit integration errors.
- Explicit retry ownership preventing nested PyWorkflowKit × PyIngestKit retry multiplication.
- PyIngestKit adapter guide documenting the no-core-dependency boundary and retry contract.

### Changed

- SQLAlchemy 2.x is now a runtime dependency for the relational persistence foundation.

### Deprecated

### Removed

### Fixed

### Security

## 0.1.0a1 - 2026-09-25

### Added

- Initial repository bootstrap.
- Standards-based Python packaging with a src layout.
- Pytest, Ruff, mypy, coverage, and package-build quality gates.
- GitHub Actions CI baseline.
- Typed domain identifiers for workflow, task, run, attempt, event, artifact, and external-run identities.
- Core lifecycle, failure, retry, skip, and event enums.
- Immutable domain value objects: RetryPolicy, ArtifactReference, ExternalRunRef, WorkflowParameter, and TaskResult.
- Immutable TaskDefinition and WorkflowDefinition models with local definition invariants.
- WorkflowRun, TaskRun, TaskAttempt, and immutable RuntimeEvent domain entities.
- RunStateMachine as the single runtime state-transition authority.
- GraphNode, GraphEdge, and deterministic DependencyGraph structural model.
- WorkflowDefinition-to-DependencyGraph construction and DAG validation.
- Deterministic ExecutionPlanner with layered topological ExecutionGroups.
- Runtime ReadyTaskResolver separated from static planning.
- Executor port, capabilities, RunContext, explicit HandlerRegistry, and synchronous LocalExecutor.
- MetadataStore and UnitOfWork ports with transactional MemoryMetadataStore.
- Copy-on-write in-memory commit/rollback semantics and metadata contract tests.
- Sequential Runner connecting planning, state transitions, execution, and metadata persistence.
- Injectable Clock, Sleeper, and RuntimeIdFactory ports with UTC/sleep/UUID default adapters.
- Deterministic RuntimeEventFactory with per-run monotonic event sequencing.
- Atomic persisted state-transition plus RuntimeEvent UnitOfWork boundaries.
- RetryEngine with NONE/FIXED/LINEAR/EXPONENTIAL backoff and retry-category allowlists.
- Multi-attempt retry execution on the same TaskRun with TASK_RETRYING evidence.
- FAIL_FAST propagation with DEPENDENCY_FAILED and FAIL_FAST_ABORT skip reasons.
- TASK_SKIPPED events and terminal TASK_FAILED-only-after-retry-exhaustion semantics.
- Immutable RunManifest values and deterministic RunManifestBuilder reconstruction.
- Canonical RunManifest JSON serialization with schema version 1.
- Sensitive workflow parameter redaction in final execution evidence.
- Workflow/task/attempt/event manifest invariants for terminal runs.
- WORKFLOW_STARTED/SUCCEEDED/FAILED and TASK_READY/STARTED/RETRYING/SUCCEEDED/FAILED/SKIPPED runtime evidence.
- Running TaskAttempt persistence at TASK_STARTED and explicit attempt updates on completion.
- Single-attempt task execution with dependency output propagation.
- Artifact and external-run-reference persistence from successful TaskResult values.
- Executor contract tests and structured execution/handler errors.
- MetadataStore errors for not-found, duplicate, and invalid UnitOfWork state.
- Runtime errors for invalid workflow parameters and violated Runner invariants.
- Planning errors for invalid plans and violated planning preconditions.
- Graph errors for unknown, self, duplicate, and cyclic dependencies.
- DomainError, InvalidStateTransitionError, and TerminalStateError.
- DefinitionError, InvalidWorkflowDefinitionError, and DuplicateTaskDefinitionError.
- Public PyWorkflowKitError exception root.

### Changed

- TaskExecutionError now carries a retry classification category.
- Retryable failures create a new TaskAttempt while preserving the same TaskRun.

### Deprecated

### Removed

### Fixed

### Security
