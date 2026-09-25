# Changelog

All notable changes to PyWorkflowKit will be documented in this file.

The project follows Semantic Versioning for released package lines and PEP 440 for Python pre-releases.

## Unreleased

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
- Injectable Clock and RuntimeIdFactory ports with UTC/UUID default adapters.
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

### Deprecated

### Removed

### Fixed

### Security
