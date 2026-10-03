# Spécification Technique de la CLI PyWorkflowKit (`pwk`)
## Architecture Hexagonale, Modèle de Commandes & Contrat Machine

- **Statut** : Spécification technique normative (Blueprint A)
- **Cible** : PyWorkflowKit 2.1.0 (`src/pyworkflowkit/cli/`)
- **Document cadre** : LOT-26 (`v2-lot26-requirements-analysis.md`)
- **Référence d'ingénierie** : `pytransformkit` 1.2.0 (Lots LOT-44 à LOT-59)

---

## 1. Objectifs Architecturaux de la CLI

La future CLI `pwk` (avec alias `pyworkflowkit`) remplace le composant monolithique V1 [`src/pyworkflowkit/cli.py`](file:///Users/awf/workspace/professionnal/webtech/packages/pyworkflowkit/src/pyworkflowkit/cli.py) par un sous-package modulaire conçu selon les règles suivantes :

1. **Native V2** : Connexion exclusive avec le moteur canonique (`WorkflowRuntime`, `WorkflowPlanner`, `ExecutionPlan`, `MetadataStore`, `TaskAttempt`).
2. **Architecture Hexagonale Découplée** :
   * Les contrôleurs Typer dans `commands/` ne contiennent aucune logique métier (uniquement parsing et routage).
   * La couche `services/` contient la logique métier pure, 100% testable en mémoire sans simulateur de terminal (`CliRunner`).
   * Les modèles de données d'entrée/sortie sont validés par Pydantic dans `models/`.
3. **Double Rendu Strict (Dual-Rendering)** :
   * Mode Humain : Interface terminal élégante via Rich (`rendering/human.py` : tables, arbres de DAG, syntaxe colorée).
   * Mode Machine (`--json`) : Émission d'un flux JSON strictement typé sur `stdout`, isolé de tout message d'erreur ou d'avertissement envoyé sur `stderr`.
4. **Sécurité Filesystem Hermétique** : Assainissement systématique des chemins de fichiers et des références de modules pour prévenir toute traversée de répertoire (*path traversal*).
5. **Contrat Machine Figé** : Snapshot JSON de l'ensemble des commandes, flags, codes d'erreur et payloads dans `contracts/cli_contract_v1.json`, contrôlé automatiquement en CI.

---

## 2. Arborescence Détaillée du Sous-Package `src/pyworkflowkit/cli/`

```text
src/pyworkflowkit/cli/
├── __init__.py                 # Point d'exportation principal et version de contrat
├── __main__.py                 # Entrée exécutable (python -m pyworkflowkit.cli)
├── app.py                      # Application racine Typer & intercepteur d'exceptions
├── bootstrap.py                # Détection dynamique des capacités ([postgres], [otel], sqlite)
├── context.py                  # CliContext (format human/json, verbosité, consoles, store)
├── exit_codes.py               # ExitCode (IntEnum formelle)
├── exceptions.py               # Hiérarchie d'exceptions typées (CliError, CliValidationError...)
├── security.py                 # Résolution sécurisée de modules et chemins
├── public_contract.py          # Définition programmatique du contrat machine CLI V1
│
├── commands/                   # Contrôleurs Typer fins (5 à 15 lignes par fichier)
│   ├── __init__.py
│   ├── version.py              # pwk version
│   ├── doctor.py               # pwk doctor
│   ├── validate.py             # pwk validate <target>
│   ├── plan.py                 # pwk plan <target> [--format human|json|mermaid]
│   ├── run.py                  # pwk run <target> [--executor ...] [--store ...] [--dry-run]
│   ├── inspect.py              # pwk inspect <workflow-run-id> [--store ...]
│   └── prune.py                # pwk store prune [--retention-days N] [--dry-run]
│
├── services/                   # Logique métier pure (indépendante de Typer)
│   ├── __init__.py
│   ├── version_service.py      # Lecture des métadonnées de package
│   ├── doctor_service.py       # Diagnostic de l'environnement, DB, packages
│   ├── validate_service.py     # Détection statique des cycles, orphelins et contrats
│   ├── plan_service.py         # Compilation ExecutionPlan & export Mermaid
│   ├── run_service.py          # Exécution managée avec WorkflowRuntime V2
│   ├── inspect_service.py      # Extraction de l'historique et des diagnostics d'échec
│   └── prune_service.py        # Application des politiques de rétention
│
├── models/                     # Schémas Pydantic des sorties structurées
│   ├── __init__.py
│   ├── reports.py              # PlanReport, ValidationReport, RunReport, DoctorReport, PruneReport
│   ├── errors.py               # CliErrorReport unifié (code, message, stack, context)
│   └── outputs.py              # Enveloppes génériques MachinePayload
│
└── rendering/                  # Présentation découplée
    ├── __init__.py
    ├── console.py              # Consoles Rich stdout/stderr configurées
    ├── human.py                # Rendu Rich (arbres de dépendance, badges d'état)
    ├── json.py                 # Sérialisation JSON normalisée
    └── tables.py               # Formatage des tableaux de tâches et d'événements
```

---

## 3. Codes de Sortie & Modèle d'Erreur

### 3.1 Énumération `ExitCode`
La CLI s'appuie sur une énumération stricte :

```python
from enum import IntEnum


class ExitCode(IntEnum):
    SUCCESS = 0
    USER_ERROR = 1             # Erreur de syntaxe de commande, flag invalide
    VALIDATION_ERROR = 2       # Échec de validation statique du workflow (cycle, orphelin)
    EXECUTION_FAILURE = 3      # Échec d'exécution du workflow (tâche en FAILED)
    SECURITY_ERROR = 4         # Violation de sécurité filesystem ou accès interdit
    STORE_ERROR = 5            # Erreur d'accès ou de transaction sur le MetadataStore
    INTERNAL_ERROR = 10        # Exception non interceptée (bug runtime)
```

### 3.2 Structure de Rapport d'Erreur (`CliErrorReport`)
En mode `--json`, toute erreur est émise sur `stdout` sous le schéma garanti :

```json
{
  "status": "error",
  "error": {
    "code": "PWK-CLI-002",
    "category": "VALIDATION_ERROR",
    "message": "Circular dependency detected: task_c -> task_a -> task_b -> task_c",
    "exit_code": 2,
    "details": {
      "cycle_path": ["task_c", "task_a", "task_b", "task_c"]
    }
  }
}
```

---

## 4. Spécification Détaillée des Commandes

### 4.1 `pwk validate`
- **Signature** : `pwk validate <target> [--strict/--no-strict] [--json]`
- **Rôle** : Charge la cible (`path/to/file.py:workflow_var` ou module), analyse la topologie du DAG sans rien exécuter.
- **Vérifications effectuées** :
  1. Détection de dépendances circulaires (algorithme de Tarjan / tri topologique).
  2. Détection de tâches orphelines (dépendances non déclarées).
  3. Détection de collisions d'identifiants de tâches (`TaskId`).
  4. Validation de la compatibilité des types de payload amont/aval si déclarés.
- **Rendu Humain** : Panneau Rich vert si le graphe est valide, liste d'anomalies rouge avec localisation si invalide.
- **Modèle JSON** : `ValidationReport` (`valid: bool`, `task_count: int`, `cycle_detected: bool`, `errors: list[ValidationErrorDetail]`).

---

### 4.2 `pwk plan`
- **Signature** : `pwk plan <target> [--format human|json|mermaid] [--output <file>]`
- **Rôle** : Compile la définition en `ExecutionPlan` V2 déterministe.
- **Options de rendu** :
  * `human` (défaut) : Arbre hiérarchique Rich montrant les niveaux d'exécution séquentiels et parallèles.
  * `mermaid` : Génère le diagramme Markdown Mermaid (`graph TD ...`) prêt à être collé dans la documentation ou les PRs GitHub.
  * `json` : Modèle `PlanReport` contenant la liste des tâches, dépendances, politiques de retry et timeouts.

---

### 4.3 `pwk run`
- **Signature** : `pwk run <target> [--executor inline|thread|process] [--max-workers N] [--store sqlite|postgres|memory] [--store-uri URI] [--dry-run] [--json]`
- **Rôle** : Instancie le `WorkflowRuntime` V2 et orchestre l'exécution complète.
- **Comportement en mode `--dry-run`** :
  * Les handlers de tâches ne sont pas appelés. Le runtime simule la séquence des états (`PENDING` $\rightarrow$ `RUNNING` $\rightarrow$ `COMPLETED`) et valide les transitions de métadonnées sans effet de bord.
- **Rendu Humain** : Tableau Rich mis à jour en temps réel avec barre de progression des tentatives et durées d'exécution.
- **Modèle JSON** : `RunReport` (`workflow_run_id: str`, `status: str`, `duration_seconds: float`, `tasks: list[TaskExecutionSummary]`).

---

### 4.4 `pwk inspect`
- **Signature** : `pwk inspect <workflow-run-id> [--store-uri URI] [--json]`
- **Rôle** : Se connecte au store persistant pour auditer un run passé.
- **Informations restituées** :
  * Métadonnées d'exécution : timestamps, identité, exécuteur utilisé.
  * Historique des tentatives par tâche (`TaskAttemptId`, tentative 1..$N$, code de sortie).
  * Détail du `FailureEvidence` si le run a échoué (type d'exception, message, traceback, variables de contexte).
- **Modèle JSON** : `InspectReport`.

---

### 4.5 `pwk doctor`
- **Signature** : `pwk doctor [--json]`
- **Rôle** : Vérifie l'état de l'environnement opérationnel :
  * Version du package et commit Git.
  * Disponibilité du moteur SQLite local.
  * Détection du pilote PostgreSQL (`psycopg`) et statut de l'extra `[postgres]`.
  * Détection du SDK OpenTelemetry et statut de l'extra `[otel]`.
  * Vérification des permissions d'écriture dans le répertoire de travail / cache.
- **Modèle JSON** : `DoctorReport`.

---

### 4.6 `pwk store prune`
- **Signature** : `pwk store prune [--store-uri URI] [--retention-days N] [--max-runs-per-workflow K] [--dry-run] [--json]`
- **Rôle** : Exécute la politique de rétention sur le `MetadataStore` (Pilier 5).
- **Garantie Transactionnelle** : La purge supprime en cascade les enregistrements dépendants (`events` $\rightarrow$ `attempts` $\rightarrow$ `task_runs` $\rightarrow$ `workflow_runs`) par lots bornés (batchs de 1 000 lignes) pour éviter tout verrouillage prolongé de la base.
- **Modèle JSON** : `PruneReport` (`scanned_runs: int`, `pruned_runs: int`, `deleted_records: dict[str, int]`, `dry_run: bool`).

---

## 5. Politique de Sécurité Filesystem (`security.py`)

Pour éviter tout vecteur d'exploitation lors du chargement de workflows locaux, `cli/security.py` applique :

```python
class PathSecurityValidator:
    """Valide les chemins de fichiers cibles avant chargement ou exécution."""

    @classmethod
    def resolve_target(cls, target_str: str) -> tuple[Path, str]:
        """Résout un target 'chemin/fichier.py:attribut' en chemin canonique vérifié."""
        ...
```

* **Périmètre workspace** : Le fichier cible doit résider dans le répertoire de travail courant ou un sous-répertoire explicitement autorisé.
* **Refus des liens symboliques dangereux** : Tout lien symbolique pointant vers des répertoires système sensibles (`/etc`, `/var`, hors du projet) est immédiatement rejeté avec l'erreur `PWK-CLI-SEC-001`.
* **Interdiction du Path Traversal** : Les segments `..` sont résolus canoniquement (`Path.resolve()`) et validés par rapport à la racine autorisée.
* **Quota de taille** : Les fichiers de workflows supérieurs à 10 Mo sont refusés pour prévenir les dénis de service par épuisement mémoire.

---

## 6. Schéma du Contrat Machine (`contracts/cli_contract_v1.json`)

Le contrat machine de la CLI est figé selon la structure :

```json
{
  "contract_name": "pyworkflowkit.cli",
  "contract_version": 1,
  "app_name": "pwk",
  "commands": {
    "validate": {
      "description": "Statically validate a workflow definition.",
      "arguments": ["target"],
      "options": ["--strict", "--json"],
      "exit_codes": [0, 1, 2, 4, 10]
    },
    "plan": {
      "description": "Compile and inspect the workflow execution plan.",
      "arguments": ["target"],
      "options": ["--format", "--output", "--json"],
      "exit_codes": [0, 1, 2, 4, 10]
    },
    "run": {
      "description": "Execute a workflow run.",
      "arguments": ["target"],
      "options": ["--executor", "--max-workers", "--store", "--store-uri", "--dry-run", "--json"],
      "exit_codes": [0, 1, 3, 4, 5, 10]
    },
    "inspect": {
      "description": "Inspect a completed or failed workflow run.",
      "arguments": ["workflow_run_id"],
      "options": ["--store-uri", "--json"],
      "exit_codes": [0, 1, 4, 5, 10]
    },
    "doctor": {
      "description": "Diagnose runtime environment and store capabilities.",
      "arguments": [],
      "options": ["--json"],
      "exit_codes": [0, 10]
    },
    "store_prune": {
      "description": "Prune expired historical runs according to retention policies.",
      "arguments": [],
      "options": ["--store-uri", "--retention-days", "--max-runs-per-workflow", "--dry-run", "--json"],
      "exit_codes": [0, 1, 4, 5, 10]
    }
  }
}
```

Ce fichier de contrat sera audité par un test de gel automatisé (`tests/contract/cli/test_cli_public_contract_freeze.py`) dès l'ouverture des lots d'implémentation.
