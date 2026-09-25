# Changelog

All notable changes to PyWorkflowKit will be documented in this file.

The project follows Semantic Versioning for released package lines and PEP 440 for Python pre-releases.

## Unreleased

### Added

- Strict Pydantic v2 serialization contracts for definitions and runtime evidence.
- Explicit Domain ↔ Schema mappers without Pydantic dependencies in domain objects.
- Neutral persistence Row DTOs for runtime entities, artifacts, and external references.
- Explicit Domain ↔ Row persistence mappings with UTC normalization.
- Canonical schema JSON codec with extra-field rejection and no implicit string fallback.
- SerializationError with structured path/type/reason context.

### Changed

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
