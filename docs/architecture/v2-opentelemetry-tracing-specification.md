# Spécification Technique : Observabilité & Tracing OpenTelemetry
## Passerelle de Télémétrie Distribuée, Hiérarchie de Spans & Propagation W3C

- **Statut** : Spécification technique normative (Blueprint D)
- **Cible** : PyWorkflowKit 2.1.0 (`src/pyworkflowkit/runtime/telemetry.py`)
- **Document cadre** : LOT-26 (`v2-lot26-requirements-analysis.md`, exigences `FR-OTEL-01` à `FR-OTEL-03`)
- **Pilier LOT-25** : Pilier 2 (OpenTelemetry & Production Observability) — **SHOULD HAVE**

---

## 1. Objectifs & Exigences Métier

Dans un écosystème d'entreprise moderne, les workflows de données ne s'exécutent pas en vase clos : ils sont déclenchés par des API, appellent des services externes, ou alimentent des data lakes. 

**L'objectif de cette spécification est d'intégrer le standard OpenTelemetry (OTel)** au cœur du cycle de vie d'exécution de PyWorkflowKit :
1. Rendre chaque exécution de workflow immédiatement visualisable dans les outils APM (Jaeger, Datadog, Grafana Tempo, Dynatrace).
2. Corréler nativement les identifiants d'exécution de PyWorkflowKit (`WorkflowRunId` $\rightarrow$ `TaskRunId` $\rightarrow$ `TaskAttemptId`) avec les `TraceId` et `SpanId` standards.
3. Propager le contexte de trace W3C (`traceparent`, `tracestate`) à travers les barrières de sous-processus et de services distants.
4. **Garantir le principe de Zéro Dépendance Imposée** : le core reste 100% autonome sans la bibliothèque `opentelemetry-api` si l'extra optionnel n'est pas demandé.

---

## 2. Modèle d'Arborescence des Spans (Span Hierarchy)

Chaque exécution orchestre une hiérarchie stricte à 3 niveaux :

```text
Trace (TraceId: 4bf92f3577b34da6a3ce929d0e0e4736)
  │
  └── [Root Span] workflow: Customer360ETL
        │  Attributes:
        │    workflow.run_id = "wfr_01J9X..."
        │    workflow.name = "Customer360ETL"
        │    workflow.status = "COMPLETED"
        │
        ├── [Child Span] task: extract_customers
        │     │  Attributes:
        │     │    task.id = "extract_customers"
        │     │    task.run_id = "tkr_01J9Y..."
        │     │
        │     └── [Leaf Span] attempt: 1
        │           Attributes:
        │             task.attempt_id = "att_01J9Z..."
        │             attempt.number = 1
        │             executor.type = "inline"
        │             attempt.status = "SUCCEEDED"
        │
        └── [Child Span] task: transform_orders
              │  Attributes:
              │    task.id = "transform_orders"
              │    task.run_id = "tkr_01J9W..."
              │
              ├── [Leaf Span] attempt: 1 (FAILED - Timeout)
              │     Attributes:
              │       attempt.number = 1
              │       error = true
              │       exception.type = "TimeoutError"
              │
              └── [Leaf Span] attempt: 2 (SUCCEEDED)
                    Attributes:
                      attempt.number = 2
                      attempt.status = "SUCCEEDED"
```

---

## 3. Propagation du Contexte W3C TraceContext

PyWorkflowKit utilise son entité existante `CorrelationContext` pour véhiculer les informations de traçabilité :

```python
class CorrelationContext(BaseModel):
    """Contexte de corrélation transverse pour l'observabilité."""

    correlation_id: str
    trace_id: str | None = None
    span_id: str | None = None
    traceparent: str | None = None
    tracestate: str | None = None
    baggage: dict[str, str] = Field(default_factory=dict)
```

### 3.1 Injection dans les Exécuteurs Subprocess & Process
Pour les exécuteurs isolés (`SubprocessExecutor`, `ProcessExecutor`) :
* Le `traceparent` actif est automatiquement injecté dans l'environnement du sous-processus via la variable standard `TRACEPARENT`.
* Le code exécuté dans le sous-processus peut ainsi rattacher ses propres spans enfants au span d'attempt parent sans perte de filiation.

---

## 4. Architecture de Découplage (`TelemetryBridge`)

Pour que PyWorkflowKit ne devienne pas tributaire du package lourd `opentelemetry-sdk` :

```text
┌────────────────────────────────────────────────────────┐
│               WorkflowRuntime Core                     │
│  (ne connaît que TelemetryBridge abstrait)             │
└──────────────────────────┬─────────────────────────────┘
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
┌──────────────────────────┐ ┌───────────────────────────┐
│   NoOpTelemetryBridge    │ │   OpenTelemetryBridge     │
│ (Actif par défaut dans   │ │ (Activé uniquement avec   │
│  le core standard)       │ │  l'extra pyworkflowkit[otel])│
│  Overhead < 0.05%        │ │  Génère les spans réels   │
└──────────────────────────┘ └───────────────────────────┘
```

### 4.1 Interface `TelemetryBridge`
```python
class TelemetryBridge(Protocol):
    """Interface abstraite de pontage de télémétrie."""

    def start_workflow_span(self, run: WorkflowRun) -> ContextManager[Any]:
        ...

    def start_task_span(self, task_run: TaskRun) -> ContextManager[Any]:
        ...

    def start_attempt_span(self, attempt: TaskAttempt) -> ContextManager[Any]:
        ...

    def record_exception(self, exc: Exception, context: Mapping[str, Any]) -> None:
        ...
```

En l'absence de l'extra `[otel]`, `NoOpTelemetryBridge` utilise des gestionnaires de contexte vides (`nullcontext`) qui sont éliminés à l'optimisation bytecode par l'interpréteur Python.
