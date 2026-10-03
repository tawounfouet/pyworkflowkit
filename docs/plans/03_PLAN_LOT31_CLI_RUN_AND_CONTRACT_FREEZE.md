# Plan d'Implémentation : LOT-31 — Commande d'Exécution, Rendu Machine & Contrat Gelé

- **Statut** : Plan d'implémentation opérationnel
- **Milestone** : LOT-31
- **Phase** : Phase 1 (Nouvelle CLI Modulaire Hexagonale)
- **Dépendance amont** : LOT-30 (`feat/v2-lot30-cli-inspection-services`)
- **Branche de travail cible** : `feat/v2-lot31-cli-run-and-contract-freeze`

---

## 1. Objectifs & Périmètre du Lot

Le but de **LOT-31** est d'achever la Phase 1 en dotant la CLI de sa capacité d'exécution managée et en scellant contractuellement son interface machine :
1. **Commande `pwk run`** : Exécution pilotée par le véritable `WorkflowRuntime` V2 avec options de configuration dynamique des exécuteurs et des stores.
2. **Mode Simulation `--dry-run`** : Simulation de la séquence d'exécution et des transitions d'états sans exécuter le code des handlers de tâches.
3. **Dual-Rendering Avancé** : Rendu Rich en direct (barres de progression, tableaux dynamiques de tâches) vs flux JSON machine strict.
4. **Gel du Contrat Machine (`contracts/cli_contract_v1.json`)** : Création du snapshot formel de l'ensemble des commandes, options et schémas JSON, protégé par un test de gel en CI.
5. **Durcissement des Sorties Machine** : Garantir l'absence totale de pollution sur `stdout` en mode `--json` (redirection de tous les logs et avertissements vers `stderr`).

---

## 2. Fichiers à Créer et Modifier

```text
contracts/
└── cli_contract_v1.json        # Snapshot formel du contrat machine de la CLI V1

src/pyworkflowkit/cli/
├── commands/
│   └── run.py                  # Contrôleur Typer mince pour `pwk run`
│
├── services/
│   └── run_service.py          # Service d'exécution orchestrant le WorkflowRuntime V2
│
├── models/
│   └── reports.py              # Ajout de RunReport, TaskExecutionSummary
│
├── public_contract.py          # Définition programmatique du contrat CLI V1
│
└── rendering/
    ├── human.py                # Progression temps réel Rich pour les tâches en cours
    └── json.py                 # Émission du RunReport normalisé

tests/contract/cli/
├── test_cli_public_contract_freeze.py  # Test de non-drift du fichier cli_contract_v1.json
├── test_machine_output_hardening.py    # Test de pureté du flux stdout en mode --json
└── test_run_contract.py                # Test de contrat sur la sortie de pwk run
```

---

## 3. Détail des Spécifications Techniques

### 3.1 `RunService`
* Instancie le `WorkflowRuntime` V2 avec les paramètres fournis.
* Gère les options de surcharge :
  - `--executor` : instancie `InlineExecutor`, `ThreadExecutor` ou `ProcessExecutor`.
  - `--store` : connecte `MemoryMetadataStore`, `SQLiteMetadataStore` ou `PostgreSQLMetadataStore`.
* En mode `dry_run=True` :
  - Intercepte les handlers de tâches pour renvoyer des sorties simulées.
  - Valide la chaîne complète de planification et de persistance sans déclencher les calculs réels.
* Renvoie un `RunReport` Pydantic :
  ```python
  class RunReport(BaseModel):
      workflow_run_id: str
      workflow_name: str
      status: WorkflowState
      dry_run: bool
      duration_seconds: float
      tasks_total: int
      tasks_succeeded: int
      tasks_failed: int
      tasks: list[TaskExecutionSummary]
  ```

### 3.2 Contrat Machine Gelé (`contracts/cli_contract_v1.json`)
Calqué sur le standard de `pytransformkit`, ce fichier capture :
* Toutes les commandes exposées (`validate`, `plan`, `run`, `inspect`, `doctor`, `version`).
* La liste exacte des arguments positionnels et options.
* La liste des codes de sortie autorisés pour chaque commande.
* Le schéma JSON des rapports retournés en mode `--json`.

---

## 4. Stratégie de Test

| Fichier de Test | Nature | Rôle |
| :--- | :--- | :--- |
| `tests/unit/cli/test_cli_run_service.py` | Unitaire | Teste l'exécution managée en mémoire et le mode dry-run. |
| `tests/contract/cli/test_cli_public_contract_freeze.py` | Contrat | Compare l'API CLI active contre `contracts/cli_contract_v1.json`. |
| `tests/contract/cli/test_machine_output_hardening.py` | Contrat | Vérifie que `stdout` est strictement un JSON valide même avec des warnings. |
| `tests/contract/cli/test_run_contract.py` | Contrat | Valide le comportement de retour et les codes d'erreur en cas d'échec de tâche. |

---

## 5. Critères d'Acceptation (Definition of Done)

- [ ] `pwk run <target>` exécute avec succès un workflow V2 réel.
- [ ] `pwk run <target> --dry-run` valide la séquence sans exécuter les handlers.
- [ ] Le contrat `contracts/cli_contract_v1.json` est généré et figé.
- [ ] Le test de gel `test_cli_public_contract_freeze.py` passe à 100%.
- [ ] Le test de pureté `test_machine_output_hardening.py` confirme que rien ne pollue `stdout`.
- [ ] La Phase 1 (CLI Modulaire) est déclarée complète et qualifiée.
