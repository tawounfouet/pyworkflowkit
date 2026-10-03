# Plan d'Implémentation : LOT-30 — Services & Commandes d'Inspection CLI

- **Statut** : Plan d'implémentation opérationnel
- **Milestone** : LOT-30
- **Phase** : Phase 1 (Nouvelle CLI Modulaire Hexagonale)
- **Dépendance amont** : LOT-29 (`feat/v2-lot29-cli-foundations`)
- **Branche de travail cible** : `feat/v2-lot30-cli-inspection-services`

---

## 1. Objectifs & Périmètre du Lot

Le but de **LOT-30** est d'implémenter les trois commandes d'analyse et d'inspection sans exécution :
1. **`pwk validate <target>`** : Analyse statique de la topologie du DAG (détection des cycles, dépendances manquantes, tâches orphelines) avec génération de `ValidationReport`.
2. **`pwk plan <target>`** : Compilation du workflow en `ExecutionPlan` V2 avec rendu au choix : arbre Rich, tableau ASCII ou syntaxe textuelle **Mermaid** (`graph TD`) pour la documentation.
3. **`pwk inspect <run-id>`** : Connexion au `MetadataStore` pour auditer un run passé, extraire la chronologie des `TaskAttempt` et le rapport d'échec structuré `FailureEvidence`.
4. Écriture des services métier purs correspondants (`ValidateService`, `PlanService`, `InspectService`) sans aucune dépendance directe à Typer.

---

## 2. Fichiers à Créer et Modifier

```text
src/pyworkflowkit/cli/
├── commands/
│   ├── validate.py             # Contrôleur Typer mince pour validate
│   ├── plan.py                 # Contrôleur Typer mince pour plan
│   └── inspect.py              # Contrôleur Typer mince pour inspect
│
├── services/
│   ├── validate_service.py     # Détection statique de cycles et validation de topologie
│   ├── plan_service.py         # Compilation ExecutionPlan et export Mermaid
│   └── inspect_service.py      # Interrogation MetadataStore et extraction FailureEvidence
│
├── models/
│   └── reports.py              # Ajout de ValidationReport, PlanReport, InspectReport
│
└── rendering/
    ├── human.py                # Enrichissement du rendu Rich pour validate, plan et inspect
    ├── json.py                 # Sérialisation JSON pour les nouveaux rapports
    └── tables.py               # Rendu des dépendances et chronologie des tentatives
```

---

## 3. Détail des Spécifications Techniques des Services

### 3.1 `ValidateService`
* Prend en entrée une cible `target: str` (résolue et assainie par `security.py`).
* Charge dynamiquement la `WorkflowDefinition` V2.
* Utilise le tri topologique pour vérifier l'absence de cycles.
* Renvoie un `ValidationReport` Pydantic :
  ```python
  class ValidationReport(BaseModel):
      target: str
      valid: bool
      task_count: int
      cycle_detected: bool
      errors: list[ValidationErrorDetail] = []
      warnings: list[str] = []
  ```

### 3.2 `PlanService`
* Compile la définition via `WorkflowPlanner().plan(workflow_def)`.
* Supporte trois formats d'export :
  - `human` : Arbre Rich montrant la hiérarchie et les niveaux de concurrence.
  - `mermaid` : Génère le bloc Mermaid :
    ```mermaid
    graph TD
      task_a["task_a (inline)"] --> task_b["task_b (thread)"]
    ```
  - `json` : Émet le schéma `PlanReport` décrivant les tâches, les dépendances et les politiques de retry.

### 3.3 `InspectService`
* Prend en entrée un `WorkflowRunId`.
* Charge depuis le `MetadataStore` configuré :
  - le `WorkflowRun` et ses timestamps ;
  - la liste des `TaskRun` associés ;
  - l'historique complet des `TaskAttempt` (durées, statuts, exécuteurs) ;
  - les `v2_events` pertinents ;
  - le diagnostic d'échec unifié `FailureEvidence` si le statut est `FAILED`.

---

## 4. Stratégie de Test

| Fichier de Test | Nature | Rôle |
| :--- | :--- | :--- |
| `tests/unit/cli/test_cli_validate_service.py` | Unitaire | Valide la détection de cycles et d'orphelins en mémoire pure. |
| `tests/unit/cli/test_cli_plan_service.py` | Unitaire | Vérifie la compilation du plan et l'exactitude de la syntaxe Mermaid. |
| `tests/unit/cli/test_cli_inspect_service.py` | Unitaire | Valide la reconstruction de l'arbre d'audit depuis un store SQLite simulé. |
| `tests/contract/cli/test_validate_contract.py` | Contrat | Vérifie le format de sortie JSON de `pwk validate --json`. |
| `tests/contract/cli/test_plan_contract.py` | Contrat | Vérifie le format de sortie JSON de `pwk plan --json`. |
| `tests/contract/cli/test_inspect_contract.py` | Contrat | Vérifie le format de sortie JSON de `pwk inspect --json`. |

---

## 5. Critères d'Acceptation (Definition of Done)

- [ ] `pwk validate <target>` détecte les cycles et renvoie `ExitCode.VALIDATION_ERROR` (code 2) en cas d'erreur.
- [ ] `pwk plan <target> --format mermaid` produit un graphe Mermaid valide.
- [ ] `pwk inspect <run-id>` restitue l'historique des tentatives et le `FailureEvidence` complet.
- [ ] Les sorties `--json` sont validées par leurs schémas Pydantic respectifs.
- [ ] 100% des tests unitaires et de contrat sont verts.
- [ ] `ruff check .` et `mypy --strict` passent sans avertissement.
