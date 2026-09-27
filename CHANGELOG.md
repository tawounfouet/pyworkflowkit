# Changelog

All notable changes to PyWorkflowKit will be documented in this file.

The project follows Semantic Versioning for released package lines and PEP 440 for Python pre-releases.

## Unreleased

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security

## 1.1.0a1 - 2026-09-27

### Added

- Canonical short CLI entry point `pwk`.
- Installed console-script parity qualification across `pwk`, `pyworkflowkit`, and `pyworkflow`.
- DX01 release qualification for version, JSON output, command behavior, and exit-code parity.

### Changed

- Beginner-facing CLI documentation now uses `pwk` by default.
- The frozen 1.0 release-candidate qualification is treated as a historical 1.x compatibility baseline instead of requiring the current package version to remain exactly `1.0.0`.
- CI and packaging qualification derive the current package version from release metadata instead of hard-coding `1.0.0`.
- Development Status classifier moves to Alpha for the 1.1 pre-release line.

### Deprecated

- No CLI alias is deprecated. `pyworkflowkit` and `pyworkflow` remain supported.

### Removed

- Nothing.

### Fixed

- Future 1.x releases are no longer blocked by 1.0-only package-version assertions in CI qualification.

### Security

- No security contract changes.

## 1.0.0 - 2026-09-27

### Added

- First stable PyWorkflowKit release.
- Stable release note documenting the qualified RQ-01 through RQ-06 lineage.
- Stable promotion lineage from the fully qualified `0.9.0rc2` candidate.

### Changed

- Package version promoted from `0.9.0rc2` to `1.0.0`.
- Development Status classifier promoted from Beta to Production/Stable.
- Release qualification expectations validate the stable artifact while preserving the RC2 lineage.

### Deprecated

- No active deprecations.

### Removed

- No runtime capability is removed.

### Fixed

- No functional code change is introduced by the stable promotion.

### Security

- The stable artifact inherits the fully qualified RQ-06 security, migration, distribution, typing, ecosystem, and compatibility gates.

## 0.9.0rc2 - 2026-09-27

### Added

- Second 1.0 release candidate qualification after the stable-promotion compatibility audit.
- Full RQ-06 requalification for the corrected Ecosystem SDK v1 runtime window.

### Changed

- Ecosystem SDK v1 compatibility series expands from `0.8-0.9` to `0.8-1.x`.
- Ecosystem SDK v1 maximum exclusive runtime version expands from `1.0` to `2.0`.
- Reference/template/qualification integration package ceilings expand from `<1.0` to `<2.0`.
- Release-candidate identity advances from `0.9.0rc1` to `0.9.0rc2`.

### Deprecated

- No active deprecations.

### Removed

- No runtime capability is removed.

### Fixed

- The intended stable `1.0.0` runtime is no longer excluded by the Ecosystem SDK v1 compatibility contract or reference integration dependency ranges.

### Security

- RC2 inherits the complete RQ-06 security qualification corpus.

## 0.9.0rc1 - 2026-09-27

### Added

- RQ-06 Release-Candidate Contract v1 targeting `1.0.0`.
- Aggregate `1.0 release candidate` job that requires every inherited release-qualification family.
- Installed-artifact RC qualifier for the exact built wheel.
- Explicit promotion policy: `same-qualified-code-version-metadata-only`.
- Manual 1.0 publication-decision registry, currently containing software-license selection.

### Changed

- The development line advances from `0.9.0b2` to `0.9.0rc1`.
- The aggregate release contract now includes `release_candidate=1`.
- RQ-01 through RQ-05 are treated as inherited, immutable stabilization inputs to RQ-06.

### Deprecated

- No active deprecations.

### Removed

- No runtime capability is removed.

### Fixed

- Release qualification now has an explicit aggregate candidate decision instead of relying only on parallel green jobs.
- A direct 1.0 promotion is now contractually limited to the same qualified implementation with release/version metadata changes only.

### Security

- RQ-06 inherits the blocking Bandit, pip-audit, detect-secrets, migration, artifact, ecosystem, and compatibility gates.

## 0.9.0b2 - 2026-09-27

### Added

- RQ-05 Distribution Contract v1 targeting `1.0.0`.
- Explicit wheel/sdist content qualification, including required resources and repository-only exclusions.
- Wheel reconstruction from the published sdist with package-path and metadata equivalence checks.
- Fresh virtual-environment install qualification for core and every published extra.
- Package upgrade qualification from the exact stable `0.8.0` commit.

### Changed

- The development line advances from `0.9.0b1` to `0.9.0b2`.
- Hatchling is bounded to `>=1.27,<2`.
- Development tooling extras use explicit compatibility ranges instead of unbounded requirements.
- Project metadata now includes Homepage, Documentation, Repository, Issues, Changelog, and Security URLs.
- README guide links are absolute for package-index rendering.
- The sdist is explicitly limited to package sources, build metadata, README, changelog, and security policy.

### Deprecated

- No active deprecations.

### Removed

- Repository-only CI, tests, examples, documentation corpus, typing fixtures, and integration fixtures are excluded from the published source distribution.

### Fixed

- Distribution contents no longer depend on implicit VCS inclusion behavior.
- The package now proves that its official sdist can rebuild an equivalent wheel.

### Security

- Published extras and clean installations are validated with `pip check`.

## 0.9.0b1 - 2026-09-27

### Added

- RQ-04 Developer Experience Contract v1 targeting `1.0.0`.
- Explicit README `Start here` path and first-use guide set for API, CLI, retries, persistence, plugin authoring, and troubleshooting.
- Executable public examples for hello-world, failure/retry, SQLite persistence, and ecosystem plugin authoring.
- Import-safe decorated workflow fixture for the CLI journey.
- Source and built-wheel developer-experience qualification gates covering the complete first-run CLI lifecycle.

### Changed

- The development line advances from `0.9.0a3` to `0.9.0b1`.
- `examples/00_hello_world.py` now uses the stable package facade instead of internal runner/store/executor construction.
- Recommended onboarding documentation now starts from `pyworkflowkit` and `pyworkflowkit.ecosystem`, while advanced implementation documentation remains separate.

### Deprecated

- No active deprecations.

### Removed

- No runtime capability is removed.

### Fixed

- The repository's first example no longer teaches internal implementation imports as the normal user path.
- CLI `module:attribute` workflow targets now resolve explicit modules from the current working directory when using the installed console script.
- Cross-process CLI inspection is documented and qualified with a durable SQLite backend instead of the default in-memory store.

### Security

## 0.9.0a3 - 2026-09-27

### Added

- RQ-03 Typing Contract v1 targeting `1.0.0`.
- Strict external-consumer typing fixtures and a negative unsupported-task-signature fixture.
- Python 3.11/3.12/3.13 static typing qualification in regular CI and Release Qualification.
- Built-wheel verification of the PEP 561 `py.typed` marker.

### Changed

- The development line advances from `0.9.0a2` to `0.9.0a3`.
- The Ecosystem SDK re-exports the existing support types required to implement its public Executor, MetadataStore, UnitOfWork, and RuntimeEventSink Protocols without importing internal module paths.
- Reference executor/event-sink integrations now type against the public ecosystem facade.
- Ecosystem template plugin registration has an explicit generic return type.

### Deprecated

- No active deprecations.

### Removed

- No runtime capability is removed.

### Fixed

- `@task` static typing now rejects handler signatures outside the executable zero-argument / single-RunContext contract.
- Public Protocol annotations no longer force third-party authors to rely on RQ-02-internal import paths for their support types.

### Security

## 0.9.0a2 - 2026-09-27

### Added

- RQ-02 machine-readable compatibility classification with `stable`, `deprecated`, `internal`, and `remove-before-1.0` statuses.
- Frozen console-script aliases, RuntimeSettings precedence/defaults, stable facade exception exports, and internal module-prefix boundaries.
- Compatibility snapshot integrated into the release qualification contract.
- Dedicated source and built-wheel RQ-02 qualification gates.

### Changed

- The development line advances from `0.9.0a1` to `0.9.0a2`.
- Ecosystem SDK v1 compatibility is extended from `>=0.8.0b1,<0.9` to `>=0.8.0b1,<1.0`, preserving interoperability across the 0.8 and 0.9 stabilization lines.
- Reference and qualification integration package dependency bounds are aligned with the same `<1.0` window.
- Direct imports from implementation module families such as `application`, `domain`, `adapters`, `ports`, and migration implementation modules are explicitly non-frozen; facade re-exports remain the compatibility boundary.

### Deprecated

- No active deprecations.

### Removed

- No pre-1.0 removal is scheduled.

### Fixed

- Removed the self-contradictory ecosystem compatibility ceiling that excluded PyWorkflowKit 0.9 while Ecosystem SDK contract v1 remained unchanged.

### Security

## 0.9.0a1 - 2026-09-27

### Added

- RQ-01 Public API Freeze with machine-readable `pyworkflowkit.public_api` contract v1 targeting `1.0.0`.
- Executable freeze of the intentional package-root, ecosystem, control-plane, integrations, plugins, and public-api facades.
- Dedicated regular-CI and built-wheel Release Qualification gates for the frozen public API surface.
- 0.9 → 1.0 stabilization roadmap defining RQ-01 through RQ-06 without new feature expansion.

### Changed

- The development line advances from stable `0.8.0` to `0.9.0a1`.
- Public facade drift must now be an explicit compatibility decision rather than an incidental `__all__` change.

### Deprecated

- No active deprecations are introduced by RQ-01.

### Removed

### Fixed

### Security

## 0.8.0 - 2026-09-27

### Added

- Transverse 0.8 stable qualification covering core-only execution, a third-party executor plugin, real PyIngestKit external workload execution, optional observability, public control-plane operation, and broken-plugin isolation in one installed environment.
- Dedicated `qualification-integrations` fixtures and `scripts/qualify_v0_8_transverse.py` stable release gate.

- M52 Ecosystem SDK & Conformance Matrix with a dedicated `pyworkflowkit.ecosystem` authoring facade.
- Machine-readable ecosystem compatibility snapshot covering Python support, contract versions, entry-point groups, and the explicit `>=0.8.0b1,<0.9` support window.
- `plugin_registration()`, `entry_point_group()`, and dependency-free plugin conformance helpers for external package authors.
- Independently buildable ecosystem integration template using only the consolidated SDK facade.
- Ecosystem SDK wheel qualification across Python 3.11, 3.12, and 3.13 in regular CI and Release Qualification.
- M51 Control-Plane Provider Contract v1 with a dedicated `pyworkflowkit.control_plane` public surface, runtime-checkable provider protocol, stable operation identifiers, and portable schemas.
- WorkflowRuntimeProvider for schema-first validation, static inspection, synchronous execution, run inspection, redacted runtime events, manifest/lineage retrieval, recovery assessment, reconciliation, and resume.
- Explicit capability negotiation reporting external scheduling ownership, synchronous execution, and unsupported external cancellation.
- ControlPlaneProviderError / ControlPlaneCapabilityError plus wheel-level provider conformance in CI and Release Qualification.
- M50 independently packaged reference integration wheels for workload, event sink, metadata, and PyIngestKit boundaries.
- Isolated-venv integration qualification covering wheel build, install, real entry-point discovery, explicit enablement, scenario execution, uninstall, disappearance from discovery, and core-only execution after removal.
- Real PyIngestKit 1.0.1 cross-project qualification pinned to commit `a19264845e10769fb8fd8cd42c83193ae011f702`, executed as one atomic ExternalWorkload.
- Dedicated Reference integration packages CI job and required Release Qualification gate.
- M49 Observability Interoperability Contract v1 with vendor-neutral telemetry events, correlations, metrics, projections, backends, and RuntimeTelemetrySink.
- Generic runtime counters/histograms for committed events, workflow/task lifecycle, retries, and durations with bounded-cardinality labels.
- Dependency-free OpenTelemetryBackend accepting injected tracer/meter objects instead of making OpenTelemetry a core dependency.
- M49 acceptance coverage for committed-event projection, domain-ID correlation, redaction, retry metrics, duration metrics, and telemetry-backend failure isolation.
- M48 Portable Reference & Integration Evidence Contract v1 with stable provider-name validation, absolute URI validation, strict JSON-portable metadata checks, and explicit reference portability helpers.
- `ReferenceInteroperabilityError` for deterministic provider / URI / metadata contract diagnostics.
- Durable M48 acceptance proving exact foreign identifier/URI preservation through serialization and SQLite persistence.
- Manifest redaction coverage for sensitive artifact and external-reference metadata plus deterministic lineage ordering.
- M47 External Workload Contract v1 with `ExternalWorkload`, `ExternalWorkloadResult`, `ExternalWorkloadAdapter`, and `external_workload_task()`.
- Generic external-runtime retry ownership through `ExternalRetryOwner`, preventing nested retry multiplication when the foreign runtime owns retries.
- Portable `ExternalRunRef` evidence and artifact propagation for successful external workloads.
- `ExternalWorkloadError` failure normalization with preserved error categories through the trusted-Python executor boundary.
- Dedicated `pyworkflowkit.integrations` public surface and M47 unit/reference acceptance coverage.

### Changed

- The 0.8 ecosystem interoperability line is promoted from `0.8.0b1` to stable `0.8.0` after transverse qualification.
- WORKLOAD plugin conformance preserves the generic Plugin API category so adapter factories such as the canonical PyIngestKit integration remain valid; the ExternalWorkload protocol applies to the workload ultimately composed for execution.
- The development line advances to `0.8.0b1`; M47-M51 are now exposed through a consolidated third-party authoring and conformance surface.
- Ecosystem compatibility is executable across Python 3.11/3.12/3.13 rather than documentary only.
- The development line advances to `0.8.0a5`; external control planes can now operate PyWorkflowKit through portable public contracts rather than runtime internals.
- Control-plane run summaries omit raw parameters and control-plane runtime events apply defensive sensitive-key redaction.
- Scheduling remains external, while unsupported cancellation is declared explicitly instead of being simulated.
- The development line advances to `0.8.0a4`; ecosystem interoperability is now exercised through independently built and removable wheels.
- Optional integrations remain explicitly installed/enabled by the application; PyWorkflowKit does not dynamically install plugins.
- The PyIngestKit reference adapter now lives outside the core wheel and consumes the real PyIngestKit public runtime API during conformance.
- The development line advances to `0.8.0a3`; telemetry remains a secondary projection over durable RuntimeEvent evidence.
- Runtime identifiers are carried as event/span correlation attributes but are deliberately excluded from metric labels to avoid high-cardinality series.
- OpenTelemetry interoperability is provided through injected API objects rather than a mandatory package dependency.
- The development line advances to `0.8.0a2`; M48 strengthens portable evidence without making the stable 0.7 reference constructors stricter.
- M47 external workloads now consume the M48 provider / URI / metadata portability contract before emitting TaskResult evidence.
- RunManifest projections now recursively redact sensitive keys from artifact and external-reference metadata while durable stored evidence remains unchanged.
- Execution lineage now explicitly sorts attempts, artifacts, and external references rather than relying on MetadataStore return order.
- The development line advances to `0.8.0a1` and begins ecosystem interoperability without changing the stable 0.7 package-root API.
- External workload timeout/cancellation remain governed by existing TaskDefinition and Executor capabilities rather than a competing remote lifecycle model.

### Deprecated

### Removed

### Fixed

### Security

## 0.7.0 - 2026-09-27

### Added

- M46 release qualification contract v1 aggregating supported Python, CLI, manifest, plugin, persistence, and migration-head compatibility metadata.
- Dedicated Release Qualification workflow with wheel/sdist build, Twine metadata validation, SHA-256 checksums, artifact upload, installed-artifact smoke tests, contract snapshots, SQLite/PostgreSQL upgrade matrices, security gates, and a single aggregate release gate.
- Release metadata verifier enforcing version/release-note/CHANGELOG consistency and optional `v<version>` tag matching.
- Artifact installation qualification for wheel on Python 3.11/3.12/3.13 and sdist on Python 3.13 from outside the repository checkout.
- M45 persistence schema contract v1 with frozen migration lineage, explicit current-head metadata, and supported upgrade-origin declarations.
- MigrationCompatibilityError plus early rejection of unknown database revisions and unknown explicit migration targets.
- Immutable Git-blob fingerprint acceptance for published migrations 0001/0002/0003.
- SQLite and PostgreSQL historical-data upgrade qualification from 0001 and 0002 through current head, including current MetadataStore reads and post-upgrade UnitOfWork writes.
- M44 public plugin compatibility contract suite with reusable registration reports, stable diagnostic issue codes, explicit entry-point group/type mappings, and opt-in instance conformance checks.
- Third-party plugin contract documentation showing direct compatibility tests without requiring installed entry-point metadata.
- M44 reference coverage freezing Plugin API v1 categories, descriptor shape, entry-point groups, diagnostics, and external-author conformance workflow.
- M43 CLI machine-contract v1 with explicit command inventory, application exit codes, required JSON top-level/nested keys, shared handled-error shape, and executable CLI acceptance snapshots.
- M43 documentation defining compatible additive JSON evolution versus breaking command/key/type/stream/exit-code changes.
- M42 deprecation infrastructure with typed categories, visible warning classes, versioned DeprecationSpec metadata, once-per-identity emission, decorator support, and an explicit active-deprecation catalog.
- Enforced normal deprecation removal no earlier than the next minor release line, with a documented emergency security/invariant exception.
- M42 unit and reference coverage for warning categories, caller stack location, duplicate suppression, decorator behavior, and policy validation.
- M41 Compatibility Contract Foundation with executable freezes for package-root API, lifecycle/event vocabularies, MetadataStore/UnitOfWork protocols, CLI command/exit-code surface, Manifest schema v1, and Plugin API v1.
- 0.7 compatibility/stabilization roadmap and compatibility policy documentation.
- 0.7.0a1 release note establishing the first pre-1.0 hardening milestone.

### Changed

- The 0.7 compatibility/stabilization line is transversely qualified and promoted from `0.7.0b1` to stable `0.7.0`.
- Release qualification validates tags but deliberately does not publish to PyPI, create GitHub Releases, or push tags.
- Durable stores now reject unknown/future Alembic revisions before attempting an upgrade rather than delegating ambiguous compatibility to Alembic internals.
- Plugin registration validation remains side-effect-free and never invokes plugin factories; instance conformance is an explicit caller-controlled step.
- `manifest --json` is explicitly governed by RunManifest schema v1 rather than a competing CLI-specific manifest schema.
- README roadmap now marks 0.6 stable and 0.7 as the active compatibility-contract line.

### Deprecated

### Removed

### Fixed

### Security

## 0.6.0 - 2026-09-27

### Added

- Transverse 0.6 release qualification freezing recovery, reconciliation, resume, retry-wait, migration, evidence, and public-surface contracts.
- M40 durable non-blocking retry eligibility through TaskAttempt.retry_eligible_at.
- Alembic revision 0003_retry_eligible_at for SQLite and PostgreSQL metadata stores.
- ConcurrentRunner retry-deadline coordination without blocking Sleeper calls.
- Recovery classification for retry-waiting TaskRuns with explicit next retry eligibility.
- Durable SQLite restart acceptance for retry wait → same TaskRun / next TaskAttempt resume.
- M39 same-WorkflowRun resume semantics with durable task-output checkpoints.
- WorkflowRuntime.resume_run() recovery facade.
- Runner.resume() preserving completed TaskRuns and continuing existing event sequence.
- Durable JSON-portable output checkpoint storage across Memory, SQLite, and PostgreSQL metadata stores.
- Alembic revision 0002_task_output_checkpoints.
- ResumeError for explicit unsafe-resume rejection.
- ACC-RECOVERY-002 durable SQLite restart acceptance.
- M38 Reconciliation with provider-specific ExternalRunVerifier contracts and registry.
- Normalized external statuses: RUNNING, SUCCEEDED, FAILED, CANCELLED, NOT_FOUND, UNKNOWN.
- ReconciliationService for read-only classification of ambiguous persisted work.
- Reconciliation dispositions: CONFIRMED_SUCCEEDED, CONFIRMED_FAILED, CONFIRMED_CANCELLED, STILL_RUNNING, MANUAL_REQUIRED.
- Durable SQLite reconciliation acceptance after restart.
- WorkflowRuntime register_external_run_verifier() and reconcile_run() facade methods.
- M37 Recovery Foundation with read-only persisted-run recovery assessment.
- RecoveryLiveness classification: terminal, active, stale_candidate, and unknown.
- ResumeEligibility classification without performing resume: not_eligible, eligible, and requires_reconciliation.
- Stable task-run idempotency metadata using task_run_id across attempts.
- MetadataStore.list_workflow_runs() for recovery candidate discovery across Memory and SQLAlchemy backends.
- WorkflowRuntime recovery_assessment() and stale_run_candidates() diagnostic facade methods.
- Durable SQLite crash-state acceptance proving stale detection after process/store restart.
- Explicit ambiguity detection for RUNNING TaskRuns, RUNNING TaskAttempts, and non-terminal external work.

### Changed

- The 0.6 recovery line is qualified and promoted to stable 0.6.0.
- ConcurrentRunner replaces retry sleeps with wall-clock retry_eligible_at evidence plus local monotonic deadlines, allowing unrelated READY work to continue during backoff.
- Sequential Runner retains simple blocking execution while persisting retry eligibility before sleeping.
- Recovery and reconciliation treat an explicit retry wait as known runtime intent rather than ambiguous RUNNING work.
- Successful small TaskResult outputs are checkpointed only when representable as strict portable JSON.
- Resume continues the same WorkflowRun and never re-executes already-SUCCEEDED tasks by default.
- Reconciled external success/failure/cancellation is translated into explicit runtime state transitions before remaining work continues.
- Missing durable dependency output, STILL_RUNNING external work, MANUAL_REQUIRED reconciliation, workflow-definition mismatch, or inconsistent persisted state blocks resume explicitly.
- M38 verifies external status before any resume decision.
- M37 stale detection continues to use durable timestamps/events without heartbeats or leases.

### Deprecated

### Removed

### Fixed

### Security

## 0.5.0 - 2026-09-26

### Added

- M36 SubprocessSecurityPolicy with executable, cwd, environment, stdin, and captured-output guardrails.
- Default subprocess environment isolation: parent environment variables are not inherited unless explicitly enabled.
- SubprocessSecurityError with stable security_policy retry/error category.
- ObservabilitySecurityPolicy with recursive sensitive-key redaction for external event sinks.
- Default redaction of observability sink exception messages.
- Dedicated Security CI gate with Bandit, pip-audit, detect-secrets, and pull-request dependency review.
- M36 unit and reference acceptance coverage for environment isolation, allowlists, size boundaries, and observability redaction.
- M35 committed-runtime-event observability plugin boundary through RuntimeEventSink.
- ObservabilityDispatcher with deterministic fan-out and isolated sink failures.
- Runtime-level event sink registration through WorkflowRuntime.register_event_sink().
- Typed EVENT plugin registry integration for RuntimeEventSink factories and entry points.
- Post-commit observability dispatch shared by sequential and concurrent runners.
- Observability acceptance coverage proving durable-event ordering and backend-failure isolation.
- M34 SubprocessExecutor for shell-free external-program execution through explicit argv.
- Immutable SubprocessCommand and captured SubprocessResult contracts.
- Natural stdout, stderr, and return-code capture without global Python stream redirection.
- SubprocessExecutionError carrying non-zero exit evidence and retry category subprocess_exit.
- Hard per-handle subprocess termination for timeout and cancellation through the existing ConcurrentRunner contract.
- Explicit stdin, cwd, environment, and encoding inputs for external commands while keeping shell=False mandatory.
- M34 unit and reference acceptance coverage for literal argv handling, capture, spawn failures, non-zero exits, hard timeout, cancellation, and cleanup.
- M33 AsyncExecutor backed by a dedicated asyncio event loop and explicit awaitable-handler contract.
- Explicit AsyncExecutor port plus async handler type aliases without replacing the stable synchronous Executor port.
- ExecutorCapabilities.supports_async declaration for capability-aware composition.
- Cooperative per-handle cancellation through asyncio.Task.cancel().
- ConcurrentRunner cancellation polling generalized to cancellable executors and cooperative cancellation coordination.
- Async soft-timeout integration preserving the existing ExecutionTimeoutError / RetryEngine contract.
- M33 unit and reference acceptance coverage for native awaiting, fan-out, context propagation, soft timeout, cooperative cancellation, and lifecycle.
- M32 ProcessExecutor with bounded process isolation and explicit spawn-time serialization checks.
- Process-safe RunContext and TaskResult transport snapshots that keep MappingProxyType inside the domain boundary.
- Hard timeout and hard cancellation capabilities backed by per-handle child-process termination.
- Process worker error translation into existing TaskExecutionError / ExecutorError completion semantics.
- ConcurrentRunner support for structural concurrent executors instead of ThreadExecutor-only coordination.
- Hard-cancellation coordinator semantics and periodic cancellation polling for hard-terminable executors.
- M32 unit and reference acceptance coverage for isolation, serialization, error transfer, cleanup, and hard timeout.

### Changed

- SubprocessExecutor now applies a security policy before process creation and before captured output crosses the executor boundary.
- SubprocessExecutor no longer inherits the parent process environment by default.
- External observability sinks receive redacted RuntimeEvent payloads by default while durable RuntimeEvent evidence remains unchanged.
- Runtime events are now published to observability sinks only after their metadata UnitOfWork commit succeeds.
- Observability plugins are explicitly secondary projections: sink failures do not alter workflow state or durable evidence.
- The 0.5 executor family now covers in-process threads, isolated Python processes, asyncio workloads, and shell-free external programs behind the same coordinator-owned completion model.
- ConcurrentRunner now distinguishes hard termination from cooperative executor cancellation while preserving coordinator-owned state transitions.
- Concurrent timeout retries now wait for physical execution cleanup before redispatching the same task attempt lineage.

### Deprecated

### Removed

### Fixed

### Security

## 0.4.0 - 2026-09-26

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

- Thread-safe CancellationController with deterministic first-request semantics.
- ConcurrentRunner cancellation that stops new dispatch and normalizes PENDING/READY tasks to CANCELLED.
- Natural completion coordination for already-RUNNING ThreadExecutor attempts.
- Cancellation-aware retry suppression after a request has been observed.
- KeyboardInterrupt normalization into the same graceful cancellation path.
- WORKFLOW_CANCELLED evidence carrying cancellation reason and undispatched-task count.
- M30 reference coverage for external cancellation, running-attempt drain, and graceful shutdown semantics.

- Domain-level TimeoutMode with NONE, SOFT, and HARD task semantics.
- Backward-compatible timeout_seconds normalization to SOFT when no explicit mode is supplied.
- Executor timeout-capability validation before run creation.
- ExecutionTimeoutError normalized as a TaskExecutionError with error_category="timeout".
- Deadline-aware ConcurrentRunner completion waits using monotonic time.
- Soft-timeout late-completion suppression while preserving the physical worker slot until the thread returns.
- Timeout failures routed through RetryEngine, with same-task retry deferred until the timed-out physical execution completes.
- Serialization and declarative API support for timeout_mode.
- M31 reference coverage for terminal soft timeout and timeout retry integration.

### Changed

- The execution line now supports bounded concurrent READY-task dispatch while preserving coordinator-owned runtime state transitions.
- Task timeout declarations now carry explicit NONE/SOFT/HARD semantics with backward-compatible timeout_seconds-to-SOFT normalization.
- The package root public API adds TimeoutMode while advanced concurrency components remain on their dedicated application/adapter import paths.

### Deprecated

### Removed

### Fixed

- Explicitly injected empty CompletionQueue instances are preserved by ThreadExecutor instead of being replaced by a default queue.

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
