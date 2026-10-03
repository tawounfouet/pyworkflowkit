# PyWorkflowKit V2 — LOT-27 Target Architecture 2.1

Status: normative architectural design  
Milestone: LOT-27  
Target Line: PyWorkflowKit 2.1.0  
Baseline: PyWorkflowKit 2.0.0 (`2d335f8db463a2267306e41ecf0ec7e3d4eb2fd9`)  
Depends on: LOT-25, LOT-26, Blueprints A, B, C, D  

---

## 1. Vue d'Ensemble & Vision Architecturales 2.1

PyWorkflowKit 2.0.0 a établi un noyau déterministe d'exécution de graphes. **La ligne 2.1 transforme ce noyau dur en un écosystème hautement ergonomique, observable, gouverné et sécurisé**, tout en conservant l'invariance absolue des contrats 2.0.

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        PYWORKFLOWKIT 2.1 ARCHITECTURE                  │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│   [ COUCHE OPÉRATEUR & INTERFACE ]                                     │
│   ┌──────────────────────────────────────────────────────────────┐     │
│   │ CLI Modulaire pwk (commands/, services/, models/, rendering/)│     │
│   └──────────────────────────────┬───────────────────────────────┘     │
│                                  │                                     │
│   [ COUCHE COMPILATION & AUTHORING ]                                   │
│   ┌──────────────────────────────────────────────────────────────┐     │
│   │ WorkflowDefinition (Chaining >>, TaskDefinition[T_In, T_Out])│     │
│   │ WorkflowPlanner (Validation Statique, Cycle Detection)       │     │
│   │ ExecutionPlan (Topologie déterministe, export Mermaid/ASCII) │     │
│   └──────────────────────────────┬───────────────────────────────┘     │
│                                  │                                     │
│   [ COUCHE MOTEUR RUNTIME V2 ]   ▼                                     │
│   ┌──────────────────────────────────────────────────────────────┐     │
│   │ WorkflowRuntime (State Machine, Attempt Sequence, CAS Lock)  │     │
│   │ Selective Resume Engine (Point-of-failure restart)           │     │
│   │ TelemetryBridge (OpenTelemetry Spans & W3C Context)          │     │
│   └──────────────┬───────────────────────────────┬───────────────┘     │
│                  │                               │                     │
│   [ EXÉCUTION ]  ▼                [ PERSISTANCE ]▼                     │
│   ┌──────────────────────────┐    ┌──────────────────────────────────┐ │
│   │ Multi-Executor Registry  │    │ MetadataStore (SQLite/PostgreSQL)│ │
│   │ (Inline, Thread, Async,  │    │  ├── Checkpoint Memoization      │ │
│   │  Process, Subprocess)    │    │  └── Retention & Pruning Engine  │ │
│   └──────────────────────────┘    └──────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Décomposition des Composants & Modules 2.1

### 2.1 Sous-Package `pyworkflowkit.cli`
Remplacement intégral de l'ancien monolithe `cli.py` :
* **`app.py`** : Point d'entrée Typer, capture globale des exceptions `CliError` et mappage vers les codes de sortie `ExitCode`.
* **`context.py`** : Porteur de contexte `CliContext` assurant l'étanchéité des sorties (`stdout` pour les données, `stderr` pour les logs).
* **`security.py`** : Validation stricte des chemins de fichiers et prévention des traversées de répertoires (*path traversal*).
* **`commands/`** : Contrôleurs Typer minces pour `plan`, `validate`, `run`, `inspect`, `doctor`, `prune`, `version`.
* **`services/`** : Logique métier pure encapsulée, découplée de Typer, testable en mémoire unitairement.
* **`models/`** : Schémas Pydantic garantissant le contrat machine de sortie `--json`.
* **`rendering/`** : Moteur de présentation séparé (Rich coloré vs JSON machine strict).

### 2.2 Extension d'Authoring `pyworkflowkit.authoring`
* **Opérateurs de flux** : Implémentation de `__rshift__` (`>>`) sur `TaskDefinition` pour permettre la syntaxe déclarative `task_a >> task_b >> [task_c, task_d]`.
* **Validation statique préventive** : Détection des cycles lors de l'appel à `WorkflowDefinition.add_task` ou `WorkflowDefinition.validate()`, levant une `CircularDependencyError` avant même la compilation du plan.

### 2.3 Moteur de Reprise Sélective `pyworkflowkit.runtime.reconciliation`
* **Réutilisation de Checkpoints** : Le moteur lit les `v2_task_output_checkpoints` du run précédent pour marquer les tâches déterministes déjà validées comme `REUSED`.
* **Traçabilité de Filiation** : Allocation d'un nouveau `WorkflowRunId` avec pointeur `resume_of_run_id` pour respecter l'immuabilité historique.

### 2.4 Moteur de Rétention `pyworkflowkit.persistence`
* **Protocole `prune_runs`** : Extension transactionnelle sur `SQLiteMetadataStore` et `PostgreSQLMetadataStore`.
* **Suppression en cascade par lots** : Élimination ordonnée (`checkpoints` $\rightarrow$ `events` $\rightarrow$ `attempts` $\rightarrow$ `task_runs` $\rightarrow$ `workflow_runs`) par batchs de 500 enregistrements pour préserver la disponibilité de la base de données.

### 2.5 Passerelle de Télémétrie `pyworkflowkit.runtime.telemetry`
* **`TelemetryBridge`** : Abstraction de pontage permettant l'émission de spans OpenTelemetry sans introduire de dépendance dure dans le core.
* **Propagation W3C** : Transport transparent du `traceparent` via `CorrelationContext` et injection dans les variables d'environnement des exécuteurs de sous-processus.

---

## 3. Frontières d'Étanchéité et Règles d'Import

Pour garantir la pérennité architecturale, des tests d'architecture automatisés (`tests/architecture/test_cli_boundaries.py` et `test_runtime_boundaries.py`) imposeront :

```text
Interdictions d'import :
1. src/pyworkflowkit/runtime/**    INTERDIT D'IMPORTER  src/pyworkflowkit/cli/**
2. src/pyworkflowkit/planning/**   INTERDIT D'IMPORTER  src/pyworkflowkit/cli/**
3. src/pyworkflowkit/persistence/** INTERDIT D'IMPORTER src/pyworkflowkit/cli/**
4. src/pyworkflowkit/** (core)     INTERDIT D'IMPORTER  opentelemetry (en dur)
5. src/pyworkflowkit/cli/**        INTERDIT D'IMPORTER  pyworkflowkit.application.* (v1 legacy)
```

Ces règles assurent que la CLI dépend du runtime, mais que le runtime n'a aucune conscience de la CLI, garantissant l'embarquabilité complète de PyWorkflowKit comme bibliothèque pure.

---

## 4. Garanties de Non-Régression Contractuelle 2.0

| Élément | Contrat 2.0.0 | Statut dans la cible 2.1 |
| :--- | :--- | :--- |
| **Racine du Package** | 13 symboles (`ExecutionPlan`, `WorkflowDefinition`...) | **100% préservé** (aucun symbole retiré, signatures rétro-compatibles) |
| **Codecs Wire** | Contrats wire version 1 (`correlation_context_v1`, etc.) | **100% consommables** sans migration requise |
| **Bases Relationnelles** | Migrations 0001 à 0005 | **100% compatibles**, schémas enrichis de façon purement additive |
| **Exécuteurs Existants** | Inline, Thread, Async, Process, Subprocess | **100% maintenus**, enrichis de la propagation W3C `traceparent` |
