# Plan d'Implémentation : LOT-35 — Passerelle OpenTelemetry Tracing

- **Statut** : Plan d'implémentation opérationnel
- **Milestone** : LOT-35
- **Phase** : Phase 3 (Gouvernance du Store, Observabilité & Supply Chain)
- **Dépendance amont** : Phase 2 (LOT-32, LOT-33)
- **Document cadre** : Blueprint D (`docs/architecture/v2-opentelemetry-tracing-specification.md`)
- **Branche de travail cible** : `feat/v2-lot35-opentelemetry-tracing`

---

## 1. Objectifs & Périmètre du Lot

Le but de **LOT-35** est d'équiper PyWorkflowKit d'un support d'observabilité distribuée aux standards de l'industrie (OpenTelemetry Tracing) sans alourdir le noyau de base :
1. **Zéro Dépendance Core Imposée** : Le noyau s'exécute sans dépendance externe obligatoire (`opentelemetry-api` optionnel via l'extra `[otel]`).
2. **Pont de Télémétrie (`TelemetryBridge`)** : Interface abstraite avec implémentation `NoOpTelemetryBridge` (par défaut) et `OpenTelemetryBridge` (activée si OTel est installé et configuré).
3. **Hiérarchie à 3 Niveaux de Spans** :
   - Root Span : `workflow: <workflow_name>`
   - Child Span : `task: <task_id>`
   - Leaf Span : `attempt: <attempt_number>`
4. **Propagation de Contexte W3C TraceContext** :
   - Enrichissement de `CorrelationContext` avec `trace_id`, `span_id`, `traceparent`, `tracestate`, `baggage`.
   - Injection du header standard W3C `TRACEPARENT` dans les variables d'environnement des `SubprocessTaskExecutor`.
5. **Enregistrement des Exceptions & Statuts OTel** :
   - En cas d'échec de tâche ou de workflow, marquage du span comme `StatusCode.ERROR` avec enregistrement de l'exception (`record_exception`).

---

## 2. Fichiers à Modifier et Créer

```text
pyproject.toml                       # Ajout de l'extra optionnel [otel] (opentelemetry-api, opentelemetry-sdk)

src/pyworkflowkit/
├── core/
│   └── correlation.py               # Extension de CorrelationContext (traceparent, baggage)
├── runtime/
│   ├── telemetry.py                 # TelemetryBridge, NoOpTelemetryBridge, OpenTelemetryBridge
│   ├── engine.py                    # Instrumentation du WorkflowRuntime (gestion des contextes de span)
│   └── task_runner.py               # Spans pour les tâches et les tentatives (TaskAttempt)
└── executors/
    └── subprocess.py                # Injection de TRACEPARENT dans os.environ pour le sous-processus

tests/
├── unit/runtime/
│   ├── test_v2_telemetry_noop.py    # Vérification du fonctionnement transparent en l'absence d'OTel
│   └── test_v2_telemetry_bridge.py  # Tests unitaires du pont avec mocks d'OpenTelemetry
├── integration/
│   ├── test_v2_otel_hierarchy.py    # Validation de l'arbre complet de spans (Root -> Task -> Attempt)
│   └── test_v2_otel_subprocess.py   # Validation de l'héritage du TRACEPARENT dans un script enfant
```

---

## 3. Détail des Spécifications Techniques

### 3.1 Définition de l'Extra dans `pyproject.toml`
```toml
[project.optional-dependencies]
otel = [
    "opentelemetry-api>=1.20.0,<2.0.0",
]
```

Dans les environnements de test :
```toml
[dependency-groups]
dev = [
    # ...,
    "opentelemetry-sdk>=1.20.0,<2.0.0",
]
```

### 3.2 Interface `TelemetryBridge` et Détection Dynamique
Dans `src/pyworkflowkit/runtime/telemetry.py` :
```python
from abc import ABC, abstractmethod
from typing import Any, Iterator
from contextlib import contextmanager


class TelemetryBridge(ABC):
    @contextmanager
    @abstractmethod
    def start_workflow_span(
        self, workflow_name: str, run_id: str, correlation: Any
    ) -> Iterator[Any]: ...

    @contextmanager
    @abstractmethod
    def start_task_span(
        self, task_id: str, task_run_id: str, workflow_run_id: str
    ) -> Iterator[Any]: ...

    @contextmanager
    @abstractmethod
    def start_attempt_span(
        self, attempt_number: int, attempt_id: str, executor_type: str
    ) -> Iterator[Any]: ...

    @abstractmethod
    def inject_w3c_context(self, env: dict[str, str]) -> None: ...


class NoOpTelemetryBridge(TelemetryBridge):
    @contextmanager
    def start_workflow_span(
        self, workflow_name: str, run_id: str, correlation: Any
    ) -> Iterator[None]:
        yield None

    @contextmanager
    def start_task_span(
        self, task_id: str, task_run_id: str, workflow_run_id: str
    ) -> Iterator[None]:
        yield None

    @contextmanager
    def start_attempt_span(
        self, attempt_number: int, attempt_id: str, executor_type: str
    ) -> Iterator[None]:
        yield None

    def inject_w3c_context(self, env: dict[str, str]) -> None:
        pass


def get_telemetry_bridge() -> TelemetryBridge:
    """Détecte la présence d'OpenTelemetry et instancie le pont adéquat."""
    try:
        import opentelemetry.trace as trace

        # Si un TracerProvider valide est configuré, on charge le pont OTel
        return OpenTelemetryBridge(trace.get_tracer("pyworkflowkit"))
    except ImportError:
        return NoOpTelemetryBridge()
```

### 3.3 Hiérarchie des Spans et Gestion des Exceptions
Dans `OpenTelemetryBridge` :
- `start_workflow_span` :
  - Nom : `f"workflow: {workflow_name}"`
  - Attributs : `workflow.run_id`, `workflow.name`, `workflow.version`
  - Fin : `span.set_status(Status(StatusCode.OK))` ou `StatusCode.ERROR` + `span.record_exception(err)`
- `start_task_span` :
  - Nom : `f"task: {task_id}"`
  - Attributs : `task.id`, `task.run_id`, `workflow.run_id`
- `start_attempt_span` :
  - Nom : `f"attempt: {attempt_number}"`
  - Attributs : `task.attempt_id`, `attempt.number`, `executor.type`

### 3.4 Injection de `TRACEPARENT` dans `SubprocessTaskExecutor`
Lorsqu'une tâche de type `SubprocessTaskExecutor` est lancée :
```python
bridge = get_telemetry_bridge()
child_env = os.environ.copy()
bridge.inject_w3c_context(child_env)
# child_env contient désormais 'TRACEPARENT': '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
subprocess.Popen(..., env=child_env)
```

---

## 4. Plan de Test et Critères d'Acceptation

### 4.1 Tests Unitaires & Isolation Sans OTel
- **Test d'étanchéité** : Désactiver `opentelemetry` via monkeypatching d'import :
  - Vérifier que `WorkflowRuntime` s'exécute de façon 100% nominale sans avertissement.
  - Vérifier que `get_telemetry_bridge()` renvoie bien une instance de `NoOpTelemetryBridge`.

### 4.2 Tests d'Intégration avec `InMemorySpanExporter`
- Installer `opentelemetry-sdk` et configurer un `InMemorySpanExporter`.
- Exécuter un workflow à 3 tâches avec une tentative en échec puis succès :
  1. Vérifier la présence de 1 Root Span de workflow.
  2. Vérifier que chaque Span de tâche est parenté au Root Span (`parent_span_id == workflow_span_id`).
  3. Vérifier que chaque Attempt Span est parenté à son Task Span.
  4. Vérifier la présence de l'événement d'exception sur la tentative en échec.

### 4.3 Test d'Héritage W3C Subprocess
- Écrire un script Python enfant temporaire qui lit `os.environ.get("TRACEPARENT")`.
- Exécuter ce script via `SubprocessTaskExecutor`.
- Valider que le `trace_id` extrait dans le sous-processus correspond exactement au `trace_id` du moteur parent.

---

## 5. Checklist de Validation et Clôture

- [ ] L'extra `[otel]` est déclaré dans `pyproject.toml`.
- [ ] Aucun import direct non gardé de `opentelemetry` n'existe dans le runtime PyWorkflowKit (`test_cli_boundaries.py` et `test_otel_optionality.py`).
- [ ] La hiérarchie à 3 niveaux (Workflow $\rightarrow$ Task $\rightarrow$ Attempt) est rigoureusement respectée.
- [ ] La propagation W3C est validée sur les exécuteurs de sous-processus.
- [ ] 0 avertissement `ruff` et typage strict `mypy` validé.
- [ ] `test_stable_release_v2.py` passe à 100% (invariance des 13 symboles racines 2.0).
