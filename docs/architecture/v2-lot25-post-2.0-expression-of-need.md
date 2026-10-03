# PyWorkflowKit V2 — LOT-25 Post-2.0 Product Direction & 2.1 Expression of Need

Status: normative product proposal  
Milestone: LOT-25  
Target Line: PyWorkflowKit 2.1.0  
Baseline: PyWorkflowKit 2.0.0 at `2d335f8db463a2267306e41ecf0ec7e3d4eb2fd9`  
Frozen 2.0.0 Runtime Tree: `f0797a25b877a0379f578015787b58f06a74dea2`  

---

## 1. Executive Summary & Purpose

LOT-24 administratively and technically closed the construction of **PyWorkflowKit 2.0.0**. The V2 clean-slate architecture is in production:
- finite runtime state machines (`WorkflowState`, `TaskState`);
- immutable execution identity (`WorkflowRunId`, `TaskRunId`, `TaskAttemptId`);
- decoupled `MetadataStore` backends (In-Memory, SQLite, PostgreSQL);
- multi-executor registry (Inline, Thread, Async, Process, Subprocess);
- deterministic planning (`ExecutionPlan`, `WorkflowPlanner`);
- portable, versioned boundary wire codecs;
- optional companion framework integrations (`PyIngestKit 2.0`, `PyTransformKit 1.1`);
- verified Customer 360 beta gate and 100% green release matrices across Python 3.11–3.14.

**LOT-25 initiates the 2.1 evolution cycle.**  
In accordance with the repository's post-2.0 engineering policy, **no runtime implementation code is introduced in this lot**. LOT-25 serves as the formal **Expression of Need** (*Expression du besoin*). It captures user demands, operational learnings from 2.0, non-goals, and prioritizes the architectural capabilities to be specified in LOT-26 (Requirements Analysis) and designed in LOT-27 (Target Architecture).

---

## 2. Post-2.0 State of the Art & Gap Analysis

While PyWorkflowKit 2.0.0 established an unyielding formal core, practical application across real-world workloads exposed specific operational friction points:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ PyWorkflowKit 2.0 Core (Solid, Tested, Frozen)                          │
│  - ExecutionPlan & Deterministic DAG Planning                          │
│  - State Machine & Attempt Sequences                                   │
│  - SQLite / PostgreSQL Transactional Metadata Stores                   │
│  - Multi-Executor Adapters & Strict Boundary Codecs                    │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                         Real-World Usage Gaps
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
   Developer Friction       Production Operations      Release & Supply Chain
  - No static DAG linting   - Traceability across APM  - PyPI publication manual
  - Cycle checks at runtime  - No store retention/GC    - License metadata open
  - Verbose chained syntax  - Full replay only         - No provenance/SBOM
```

### 2.1 Developer Experience (DX) Gaps
- **Runtime-only DAG validation**: Cycle detection, disconnected tasks, or invalid dependencies currently fail only when compiling or executing the plan. Developers need instant static linting during definition.
- **Authoring verbosity**: Building complex multi-branch graphs currently requires repetitive `.add_task(...)` and explicit dependency linking.
- **Opaque local debugging**: Stepping through task failures or executing a dry-run without writing to persistent stores requires custom scaffolding.

### 2.2 Observability & Production Diagnostics Gaps
- **Internal-only event dispatching**: While `EventSink` records events, integrating with enterprise observability stacks (OpenTelemetry, Datadog, Prometheus) requires custom bridging.
- **Distributed trace fragmentation**: When workflows invoke microservices or companion frameworks (`PyIngestKit`, `PyTransformKit`), trace context propagation (`traceparent`, `tracestate`) is manual.
- **Post-mortem inspection**: `FailureEvidence` contains raw exception details but lacks structured formatting for instant CLI or log consumption.

### 2.3 Store Operations & Lifecycle Governance Gaps
- **Store bloat**: In high-frequency batch pipelines, SQLite and PostgreSQL stores accumulate historical runs indefinitely without built-in TTL, retention policies, or pruning mechanisms.
- **Coarse replay**: Recovery currently reruns the workflow from the start or relies on manual intervention, rather than allowing a deterministic **selective resume** from the point of failure.

### 2.4 Supply Chain & Release Engineering Gaps
- **Publication manual gate**: PyPI publication was deliberately omitted from 2.0.0 automation. The project needs automated, trusted OIDC publishing aligned with `pytransformkit`.
- **Software provenance**: Modern deployment environments require formal Software Bill of Materials (SBOM) and Sigstore attestations.
- **License clarity**: Project metadata must declare an explicit software license.

---

## 3. Inviolable Core Boundaries (Non-Goals)

To prevent architectural drift and maintain PyWorkflowKit's lightweight, embeddable nature, the following boundaries remain **strictly outside the core scope for the 2.x line**:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        PYWORKFLOWKIT CORE                              │
│             "HOW TO EXECUTE A DIRECTED WORKFLOW RELIABLY"              │
└────────────────────────────────────────────────────────────────────────┘
                                   ▲
                                   │ STRICT EXCLUSION
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         NON-GOALS (OUT OF CORE)                        │
│                                                                        │
│  ❌ Scheduler Engine          (Airflow, Dagster, Cron own "WHEN")       │
│  ❌ Distributed Worker Fleet   (Celery, Ray, K8s operators stay outside)│
│  ❌ Embedded Message Broker    (No mandatory Kafka, RabbitMQ, Redis)   │
│  ❌ Web UI / Control Plane     (No built-in web frontend or REST API)  │
│  ❌ IAM / RBAC / Multi-tenancy (Authentication is host platform domain)│
└────────────────────────────────────────────────────────────────────────┘
```

1. **Not a Scheduler**: External orchestrators, cron jobs, or event triggers determine *when* a workflow runs. PyWorkflowKit executes a workflow when invoked.
2. **Not a Distributed Cluster Fleet**: PyWorkflowKit manages local processes, threads, async event loops, and external workload references, but does not deploy or maintain an active worker cluster.
3. **Not a Message Broker**: Task coordination is handled via metadata stores, not distributed message queues.
4. **Not a Web Application**: Visualization and inspection tools must remain offline (CLI, static exports like Mermaid/HTML) rather than running web servers.
5. **Not an Identity Provider**: Security, user permissions, and multi-tenancy are owned by the enclosing system.

---

## 4. Target Personas & Core User Journeys

### Persona 1: The Data / ML Engineer
- **Profile**: Authors complex data pipelines combining ingestion (`PyIngestKit`), transformations (`PyTransformKit`), and model training.
- **Need**: Rapid authoring with IDE auto-completion, static verification of task graphs before running heavy compute, and dry-run execution with mock inputs.
- **Journey**:
  1. Define tasks using typed decorators.
  2. Combine tasks into a DAG with clear upstream/downstream semantics.
  3. Validate the DAG statically via `pwk validate`.
  4. Run dry-run locally to confirm execution order.
  5. Deploy to production runner.

### Persona 2: The Backend / Platform Engineer
- **Profile**: Embeds transactional, durable multi-step workflows inside API services or background workers.
- **Need**: Reliable execution state across restarts, concurrency safety via CAS, automatic retry policies, and zero store leaks.
- **Journey**:
  1. Trigger a workflow upon receiving a webhook.
  2. Persist state in PostgreSQL with idempotency tokens.
  3. Automatically resume interrupted workflows after pod restart.
  4. Rely on automated retention policies to prune completed runs after 30 days.

### Persona 3: The Site Reliability / Operations Engineer (SRE)
- **Profile**: Monitors workflow health, troubleshoots failures, and audits software supply chain in production.
- **Need**: Native OpenTelemetry trace context, standardized error logs, deterministic CLI inspection, and verifiable SBOM / release provenance.
- **Journey**:
  1. Observe workflow traces in Datadog/Jaeger with unified `WorkflowRunId` and `TaskRunId` tags.
  2. Inspect failed task attempt via `pwk inspect <run-id>`.
  3. Re-run only the failed branches after fixing underlying infrastructure.
  4. Verify package checksums and cryptographic attestations during CI deployment.

---

## 5. Detailed Expression of Need: The 9 Strategic Pillars

```text
                          PyWorkflowKit 2.1
                          Strategic Pillars
                                 │
     ┌───────────────┬───────────┼───────────┬───────────────┐
     ▼               ▼           ▼           ▼               ▼
 1. DX &         2. OTel &   3. Diag &   4. Recovery &   5. Store
 Authoring       Tracing     Dry-Run     Resume          Governance
     │               │           │           │               │
     └───────────────┼───────────┴───────────┼───────────────┘
                     ▼                       ▼
                 6. Executor             7. Supply Chain
                 Hardening               & Packaging
```

### Pillar 1: Developer Experience & Authoring Ergonomics
- **Static Graph Analysis**:
  - Immediate cycle detection during workflow construction.
  - Identification of orphan/dangling tasks that cannot execute.
  - Validation of input/output contracts between connected tasks.
- **Fluent & Declarative Chaining**:
  - Ergonomic syntax operators (e.g. `task_a >> task_b >> [task_c, task_d]`).
  - Sub-workflow composition: nesting an `ExecutionPlan` inside a parent workflow as a single logical task.
- **IDE & Static Typing**:
  - Full generic typing for task return values and dependency passing.

### Pillar 2: OpenTelemetry & Production Observability
- **Native Distributed Tracing (OTel)**:
  - Automatic span generation:
    - Root Span: `workflow.execute` with `workflow_run_id`, `workflow_name`, `status`.
    - Intermediate Span: `task.execute` with `task_run_id`, `task_name`.
    - Leaf Span: `task.attempt` with `task_attempt_id`, `attempt_number`, `executor_type`.
  - W3C Trace Context propagation across process/subprocess and external boundaries.
- **Structured Metrics**:
  - Execution duration histograms, retry counters, and concurrency gauges emitted to standard metric collectors.
- **Zero-Dependency Core**:
  - OpenTelemetry integration implemented as an optional extra (`pyworkflowkit[otel]`). Standard core must remain dependency-neutral.

### Pillar 3: Diagnostics, Debugging & Dry-Run
- **Interactive Dry-Run Mode**:
  - Ability to execute a workflow where task bodies are bypassed, verifying dependency order, state transitions, and store interactions without executing real workloads.
- **Rich Diagnostic Failure Reports**:
  - Structured error summaries with stack traces, failed task context, parameter snapshots, and suggested remediation steps.
- **Plan Export**:
  - Export execution plans to Mermaid diagram syntax and JSON schemas for documentation and CI review.

### Pillar 4: Recovery, Selective Resume & Concurrency Safety
- **Partial / Selective Resume**:
  - When a workflow fails after several successful tasks, allow resuming execution such that already completed, deterministic tasks are reused rather than recomputed.
  - Explicit marker for deterministic vs volatile tasks.
- **Atomic Concurrency (CAS)**:
  - Guard transitions with Compare-And-Swap (CAS) locking in SQLite and PostgreSQL to prevent race conditions when multiple workers attempt state transitions on the same run.

### Pillar 5: Store Governance & Lifecycle Management
- **Retention Policies**:
  - Configurable retention rules: e.g., retain successful runs for $N$ days, retain failed runs for $M$ days, retain maximum $K$ runs per workflow.
- **Store Garbage Collection (GC)**:
  - Programmatic API and CLI command (`pwk store prune`) to archive or delete expired runs, task attempts, and event records safely within database transactions.

### Pillar 6: Executor Hardening & Isolation
- **Cooperative Timeout & Hard Kill**:
  - Two-stage cancellation: graceful cancellation request (`SIGINT` / token check), followed by hard termination (`SIGKILL` / thread abort) if grace period expires.
- **Resource Constraints & Environment Isolation**:
  - Declarative resource hints (max execution time, memory cap warnings) on task definitions.
  - Subprocess executor environment sandboxing (explicit environment variable filtering).

### Pillar 7: Ecosystem & Sibling Framework Integration
- **PyIngestKit 2.0 Native Adapter**:
  - First-class task wrapper for `IngestionDefinition` and `IngestionRuntime.run(...)` providing automatic lineage linkage.
- **PyTransformKit 1.1 Native Adapter**:
  - Declarative schema validation step integrating `pytransformkit.schema_io` with automatic error code mapping.
- **Unified Customer 360 Reference Pipeline**:
  - Upgrade the Customer 360 reference implementation to showcase the end-to-end Ingest $\rightarrow$ Transform $\rightarrow$ Orchestrate pipeline.

### Pillar 8: Release Engineering, Supply Chain & Governance
- **PyPI Trusted Publishing**:
  - Automated release workflow via GitHub OIDC Trusted Publishing, matching the proven model of `pytransformkit`.
- **Software Bill of Materials (SBOM)**:
  - Automated generation of CycloneDX / SPDX SBOM on release.
- **Cryptographic Attestations**:
  - Sigstore artifact attestations tying release wheels to GitHub Actions workflow provenance.
- **License Decision**:
  - Formal selection and declaration of the project license in package metadata (e.g. MIT).

### Pillar 9: CLI Utility & Operator Tooling (`pwk`)
- **Inspection & Validation Commands**:
  - `pwk plan <workflow_file>`: Print ASCII DAG execution plan.
  - `pwk validate <workflow_file>`: Statically lint the workflow.
  - `pwk inspect <run-id>`: Display execution status, attempt history, and diagnostics.
  - `pwk store prune`: Execute store retention policies.

---

## 6. MoSCoW Prioritization Matrix for PyWorkflowKit 2.1

To ensure disciplined execution and prevent scope creep, the 9 pillars are categorized according to MoSCoW prioritization:

| Category | Capability / Pillar | Target Scope |
| :--- | :--- | :--- |
| **MUST HAVE** | **Pillar 1**: Static DAG Validation & Ergonomic Chaining | Core authoring improvement |
| **MUST HAVE** | **Pillar 4**: Selective Resume (Point-of-failure restart) | Core runtime enhancement |
| **MUST HAVE** | **Pillar 5**: Store Retention Policy & Pruning API | Production persistence safety |
| **MUST HAVE** | **Pillar 8**: PyPI Trusted Publishing & License Decision | Release engineering hygiene |
| **SHOULD HAVE** | **Pillar 2**: OpenTelemetry Tracing Bridge (`[otel]` extra) | Enterprise observability |
| **SHOULD HAVE** | **Pillar 3**: Interactive Dry-Run & Mermaid Export | Developer experience & CI |
| **SHOULD HAVE** | **Pillar 7**: First-Class PyIngestKit 2.0 & PyTransformKit 1.1 Adapters | Sibling framework synergy |
| **SHOULD HAVE** | **Pillar 9**: Lightweight Operator CLI (`pwk inspect/validate`) | Operational productivity |
| **COULD HAVE** | **Pillar 6**: Subprocess Environment Sandboxing | Advanced security hardening |
| **COULD HAVE** | **Pillar 8**: CycloneDX SBOM & Sigstore Attestations | Supply-chain hardening |
| **WON'T HAVE** | Web Control Plane / Dashboard / REST Server | Strict Non-Goal (Out of core) |
| **WON'T HAVE** | Centralized Distributed Worker Daemon / Fleet | Strict Non-Goal (Out of core) |
| **WON'T HAVE** | Cron / Time-based Event Scheduler | Strict Non-Goal (Out of core) |
| **WON'T HAVE** | User Authentication / RBAC / IAM System | Strict Non-Goal (Out of core) |

---

## 7. Invariance Guarantees & Compatibility Policy

The 2.1 line is governed by the **Compatible Evolution Policy** defined in `docs/V2_RELEASE_CLOSURE_AND_POST_2_0_ROADMAP.md`:

1. **Zero Root Breaking Changes**:
   - The 13 canonical root symbols of `pyworkflowkit` (`ExecutionPlan`, `WorkflowDefinition`, `TaskDefinition`, `WorkflowRun`, etc.) must maintain strict backward compatibility.
2. **Wire Contract Compatibility**:
   - All serialization wire contracts versioned at `1` (`correlation_context_v1`, `workflow_execution_reference_v1`, etc.) must remain decodable without migration. Any new wire contract must introduce version `2` with backward decoders.
3. **Store Schema Non-Destructive Migrations**:
   - Database migrations for SQLite and PostgreSQL must be purely additive (new columns with default values, new index tables). No existing columns or tables may be dropped or altered in a breaking manner.
4. **Zero Mandatory Dependencies**:
   - OpenTelemetry, PostgreSQL driver, and visualization packages must remain optional extras. Base PyWorkflowKit remains lightweight with standard dependencies.

---

## 8. Post-LOT-25 Delivery Roadmap

The 2.1 delivery sequence follows a four-stage normative process:

```text
┌────────────────────────────────────────────────────────┐
│ LOT-25: Expression of Need & Product Direction (THIS)  │
│  - User stories, non-goals, 9 pillars, MoSCoW matrix   │
└──────────────────────────┬─────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────┐
│ LOT-26: Requirements Analysis & Specification          │
│  - Formal functional requirements (FR)                 │
│  - Non-functional requirements (NFR)                   │
│  - Interface contracts & error catalog expansion       │
└──────────────────────────┬─────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────┐
│ LOT-27: Target Architecture & Interface Design         │
│  - Domain model extensions                             │
│  - Store migration strategy & CAS concurrency design   │
│  - OpenTelemetry bridge architecture                   │
└──────────────────────────┬─────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────┐
│ LOT-28 → LOT-3X: Incremental Implementation & QA       │
│  - Modular implementation lots                         │
│  - 2.1.0rc1 Candidate Qualification                   │
│  - 2.1.0 Stable Promotion & Trusted Publishing         │
└────────────────────────────────────────────────────────┘
```

---

## 9. LOT-25 Acceptance Criteria

LOT-25 is accepted and complete when:
- [x] Product direction and user needs for PyWorkflowKit 2.1 are formally articulated.
- [x] Gap analysis against 2.0.0 production experience is documented.
- [x] Core architectural non-goals (scheduler, worker fleet, message broker, web UI, IAM) are reaffirming and inviolable.
- [x] The 9 strategic pillars are categorized under the MoSCoW prioritization model.
- [x] Compatibility invariances (frozen 2.0 root, wire contracts, store schemas) are explicitly enforced.
- [x] The downstream roadmap (LOT-26 Requirements Analysis $\rightarrow$ LOT-27 Target Architecture) is defined.
- [x] Zero runtime code in `src/pyworkflowkit/**` has been altered.
