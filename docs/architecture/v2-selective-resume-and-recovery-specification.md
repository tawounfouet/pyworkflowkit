# Spécification Technique : Reprise Sélective & Checkpoints (Selective Resume)
## Algorithme de Redémarrage au Point d'Échec et Réutilisation Déterministe

- **Statut** : Spécification technique normative (Blueprint B)
- **Cible** : PyWorkflowKit 2.1.0 (`src/pyworkflowkit/runtime/reconciliation.py` & `workflow.py`)
- **Document cadre** : LOT-26 (`v2-lot26-requirements-analysis.md`, exigences `FR-RESUME-01` à `FR-RESUME-05`)
- **Pilier LOT-25** : Pilier 4 (Recovery, Selective Resume & Idempotency) — **MUST HAVE**

---

## 1. Problématique et Valeur Métier

Dans PyWorkflowKit 2.0.0, lorsqu'un workflow échoue après l'exécution de 9 tâches lourdes sur 10 (ex. extraction de données massives, calculs complexes), la relance nécessite actuellement de rejouer l'ensemble du workflow depuis la première tâche, gaspillant du temps de calcul, des entrées/sorties réseau et des ressources CPU/GPU.

**L'objectif de la Reprise Sélective (*Selective Resume*)** est de permettre de redémarrer un workflow échoué ou annulé en réutilisant automatiquement les résultats des tâches ayant déjà réussi, sans les réexécuter, pour concentrer l'effort de calcul strictement sur la tâche défaillante et ses dépendances aval.

---

## 2. Principes Fondamentaux et Taxonomie

```text
Run d'origine (FAILED) :
  Task A (SUCCEEDED) ──► Task B (SUCCEEDED) ──► Task C (FAILED) ──► Task D (PENDING)
         │                     │                     │                    │
         ▼                     ▼                     ▼                    ▼
     Checkpoint A          Checkpoint B           (Aucun)              (Aucun)

Nouveau Run (RESUME) :
  Task A (REUSED)   ──► Task B (REUSED)   ──► Task C (RUNNING) ──► Task D (PENDING)
  (injecte Checkpoint A)  (injecte Checkpoint B)   (réexécutée)         (attendra C)
```

### 2.1 Distinction Déterministe vs Volatile
Toutes les tâches ne peuvent pas être mémoïsées sans danger. PyWorkflowKit 2.1 introduit la distinction explicite sur `TaskDefinition` :

* **Tâche Déterministe (`is_deterministic=True`, par défaut)** :
  * Pour des entrées identiques, produit toujours la même sortie sans effet de bord critique non reproductible.
  * Son checkpoint de sortie peut être réutilisé lors d'une reprise sélective.
* **Tâche Volatile (`is_deterministic=False`)** :
  * Interagit avec l'environnement extérieur (lecture d'une horloge, capteur temps réel, token temporaire, suppression de ressource).
  * Doit **toujours** être réexécutée lors d'une reprise, même si elle avait réussi dans le run d'origine.

### 2.2 Règle d'Immuabilité des Runs
Une reprise sélective ne modifie **jamais** l'enregistrement du run échoué.
* Le run d'origine reste scellé avec son statut `FAILED` et son `WorkflowRunId` initial.
* La reprise génère un **nouveau** `WorkflowRunId`.
* Le lien de filiation est enregistré dans les métadonnées : `resume_of_run_id = original_run_id`.

---

## 3. Modèle de Données & Checkpoints

La migration de base de données `0005_v2_task_output_checkpoints.py` a déjà préparé le schéma relationnel nécessaire :

```sql
CREATE TABLE v2_task_output_checkpoints (
    task_run_id VARCHAR(64) PRIMARY KEY,
    workflow_run_id VARCHAR(64) NOT NULL,
    task_id VARCHAR(128) NOT NULL,
    output_payload JSON NOT NULL,
    output_checksum VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    FOREIGN KEY (workflow_run_id) REFERENCES v2_workflow_runs(workflow_run_id)
);
```

Chaque fois qu'une tâche déterministe franchit la transition vers l'état `SUCCEEDED`, son résultat est sérialisé et persisté dans `v2_task_output_checkpoints`.

---

## 4. Algorithme de Résolution de Graphe de Reprise

Lors de l'appel à `WorkflowRuntime.resume_run(original_run_id, ...)` :

```text
Entrée : original_run_id, workflow_definition
                       │
                       ▼
1. Validation d'intégrité du graphe (Fingerprint Check)
   Le fingerprint structurel du workflow courant DOIT correspondre à l'original.
                       │
                       ▼
2. Lecture de l'historique du run original depuis le MetadataStore
   Chargement de tous les TaskRuns et des Checkpoints associés.
                       │
                       ▼
3. Classification topologique des nœuds du DAG :
   Pour chaque tâche T dans le tri topologique :
     - Si T.status == SUCCEEDED dans le run d'origine
       ET T.is_deterministic == True
       ET TOUS les ancêtres de T ont le statut REUSED :
           ==> T est marquée REUSED
           ==> Sa sortie est pré-chargée depuis le checkpoint
     - Sinon :
           ==> T est marquée READY (à réexécuter)
                       │
                       ▼
4. Instanciation du nouveau WorkflowRun
   - Génération de new_run_id
   - Enregistrement des TaskRuns avec statut REUSED ou PENDING
   - Exécution orchestrée des tâches restantes
```

### 4.1 Règle de Propagation de la Volatilité
Dès qu'une tâche est réexécutée (parce qu'elle était en échec ou volatile), **toutes ses descendantes en aval doivent obligatoirement être réexécutées**, même si certaines avaient réussi dans le run d'origine.

---

## 5. Spécification de l'API Python

```python
class WorkflowRuntime:
    """Moteur d'exécution V2 de PyWorkflowKit."""

    def resume_run(
        self,
        original_run_id: WorkflowRunId | str,
        definition: WorkflowDefinition,
        *,
        store: MetadataStore | None = None,
        executor: TaskExecutor | None = None,
        force_recompute_tasks: list[str] | None = None,
    ) -> WorkflowResult:
        """Reprend sélectivement l'exécution d'un run échoué ou annulé.

        Args:
            original_run_id: Identifiant du run parent à reprendre.
            definition: Définition du workflow (doit correspondre au run parent).
            store: Store de métadonnées (utilise le store par défaut si None).
            executor: Exécuteur à utiliser pour les tâches restantes.
            force_recompute_tasks: Liste facultative d'identifiants de tâches à
                forcer en réexécution même si elles avaient réussi.

        Returns:
            WorkflowResult: Résultat du nouveau run de reprise.

        Raises:
            WorkflowNotFoundError: Si original_run_id n'existe pas dans le store.
            InvalidRunStateForResumeError: Si le run d'origine est toujours RUNNING.
            GraphTopologyMismatchError: Si la définition a été altérée.
        """
        ...
```

---

## 6. Événements et Auditabilité de Reprise

Pour garantir une traçabilité totale dans le journal d'événements (`v2_events`) :

1. `WorkflowResumeInitiatedEvent` :
   - Émis à l'initialisation du nouveau run.
   - Contient : `new_run_id`, `original_run_id`, `reused_task_count`, `remaining_task_count`.
2. `TaskReusedFromCheckpointEvent` :
   - Émis pour chaque tâche dont le résultat est réinjecté sans exécution.
   - Contient : `task_id`, `original_task_run_id`, `checkpoint_checksum`.

Ces événements garantissent que les rapports d'audit (ex. `pwk inspect`) distinguent clairement les tâches réellement calculées des tâches mémoïsées.
