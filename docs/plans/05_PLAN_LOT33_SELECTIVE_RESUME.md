# Plan d'Implémentation : LOT-33 — Reprise Sélective & Checkpoints

- **Statut** : Plan d'implémentation opérationnel
- **Milestone** : LOT-33
- **Phase** : Phase 2 (Ergonomie & Moteur Runtime V2)
- **Dépendance amont** : LOT-32 (`feat/v2-lot32-authoring-ergonomics`)
- **Document cadre** : Blueprint B (`docs/architecture/v2-selective-resume-and-recovery-specification.md`)
- **Branche de travail cible** : `feat/v2-lot33-selective-resume`

---

## 1. Objectifs & Périmètre du Lot

Le but de **LOT-33** est d'implémenter l'algorithme de reprise sélective au point d'échec (*Selective Resume*) :
1. **Marquage Déterministe vs Volatile** : Ajout du flag `is_deterministic: bool = True` sur `TaskDefinition`.
2. **Méthode `WorkflowRuntime.resume_run(...)`** : Capacité de relancer un workflow échoué en ne réexécutant que les tâches nécessaires.
3. **Réutilisation des Checkpoints** : Extraction des sorties mémoïsées dans la table `v2_task_output_checkpoints`.
4. **Filiation et Immuabilité** : Enregistrement de `resume_of_run_id` sur le nouveau run et émission des événements d'audit de réutilisation.
5. **Validation sur SQLite et PostgreSQL** : Vérification du comportement transactionnel sous les deux stores.

---

## 2. Fichiers à Modifier et Créer

```text
src/pyworkflowkit/
├── authoring/
│   └── definitions.py          # Ajout de is_deterministic sur TaskDefinition
│
├── runtime/
│   ├── workflow.py             # Implémentation de resume_run sur WorkflowRuntime
│   ├── reconciliation.py       # Algorithme topologique de sélection des tâches REUSED
│   └── entities.py             # Ajout de resume_of_run_id sur WorkflowRun
│
├── persistence/
│   ├── contracts.py            # Méthode load_task_checkpoints sur MetadataStore
│   ├── sqlite.py               # Implémentation SQLite de lecture des checkpoints
│   └── postgresql.py           # Implémentation PostgreSQL de lecture des checkpoints
│
└── states/
    └── enums.py                # Ajout de TaskRunStatus.REUSED (compatible avec SUCCEEDED)

tests/
├── unit/runtime/
│   └── test_v2_selective_resume.py         # Tests unitaires de l'algorithme de sélection
├── integration/
│   ├── test_v2_resume_sqlite.py            # Test d'intégration complet avec crash simulé
│   └── test_v2_resume_postgres.py          # Test d'intégration multi-processus PostgreSQL
```

---

## 3. Détail des Spécifications Techniques

### 3.1 Algorithme de Résolution Topologique
1. Charger les `TaskRuns` du run parent depuis le store.
2. Pour chaque nœud du DAG (dans l'ordre topologique) :
   - Si la tâche est en état `SUCCEEDED` dans le run parent ;
   - ET `task.is_deterministic == True` ;
   - ET tous ses parents directs ont été résolus en `REUSED` dans le run courant ;
   - **ALORS** : la tâche est marquée `REUSED`, son handler n'est pas appelé, et son checkpoint de sortie est injecté dans le contexte d'exécution.
   - **SINON** : la tâche est planifiée pour réexécution (`READY`).

### 3.2 Garantie d'Immuabilité
* Le run parent conserve son statut `FAILED` ou `CANCELLED`.
* Le nouveau run possède son propre `WorkflowRunId` avec `resume_of_run_id = parent_run_id`.
* Émission de l'événement `TaskReusedFromCheckpointEvent` pour chaque tâche mémoïsée.

---

## 4. Stratégie de Test

* **Scénario d'Échec et Reprise** :
  1. Définir un workflow à 5 tâches : $A \rightarrow B \rightarrow C \rightarrow D \rightarrow E$.
  2. Forcer l'échec de la tâche $C$. Vérifier que $A$ et $B$ réussissent et écrivent leur checkpoint.
  3. Corriger le handler de $C$ et appeler `runtime.resume_run(...)`.
  4. Vérifier que $A$ et $B$ sont marquées `REUSED` (durée 0s), que $C$, $D$, $E$ sont exécutées, et que le workflow global termine en `COMPLETED`.
* **Scénario Tâche Volatile** :
  - Déclarer $B$ avec `is_deterministic=False`. Vérifier que même si $B$ avait réussi, elle est réexécutée lors de la reprise.

---

## 5. Critères d'Acceptation (Definition of Done)

- [ ] `WorkflowRuntime.resume_run(...)` s'exécute avec succès et réutilise les checkpoints.
- [ ] Les tâches volatiles sont réexécutées conformément à la règle de propagation.
- [ ] Les événements d'audit `TaskReusedFromCheckpointEvent` sont enregistrés dans le store.
- [ ] Les tests d'intégration SQLite et PostgreSQL passent à 100%.
- [ ] Aucune régression sur le comportement standard de `WorkflowRuntime.run(...)`.
- [ ] `ruff` et `mypy --strict` sont à 0 défaut.
