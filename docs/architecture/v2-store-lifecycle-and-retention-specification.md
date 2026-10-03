# Spécification Technique : Cycle de Vie du Store & Rétention (Garbage Collection)
## Politiques de Rétention, Purge Transactionnelle & Maintenance des Métadonnées

- **Statut** : Spécification technique normative (Blueprint C)
- **Cible** : PyWorkflowKit 2.1.0 (`src/pyworkflowkit/persistence/`)
- **Document cadre** : LOT-26 (`v2-lot26-requirements-analysis.md`, exigences `FR-STORE-01` à `FR-STORE-04`)
- **Pilier LOT-25** : Pilier 5 (Store Lifecycle & Governance) — **MUST HAVE**

---

## 1. Problématique et Risque Opérationnel

En environnement de production (notamment avec des pipelines haute fréquence ou des workflows exécutés toutes les 5 minutes), les stores relationnels `SQLiteMetadataStore` et `PostgreSQLMetadataStore` accumulent rapidement un volume considérable d'enregistrements :
- chaque run engendre des lignes dans `v2_workflow_runs` ;
- chaque tâche génère des `v2_task_runs` et de multiples `v2_task_attempts` ;
- chaque tentative produit des dizaines de `v2_events` et des `v2_task_output_checkpoints`.

Sans politique d'assainissement automatique :
1. Les bases SQLite locales atteignent des gigaoctets et ralentissent les lectures.
2. Les tables PostgreSQL subissent un grossissement (*table bloat*) dégradant les temps de requête des requêtes d'orchestration courantes.
3. Il n'existe actuellement aucun moyen standardisé de purger l'historique sans risquer de corrompre les contraintes de clés étrangères.

---

## 2. Modèle de Configuration : `RetentionPolicy`

La gouvernance du cycle de vie repose sur un modèle Pydantic déclaratif :

```python
from datetime import timedelta
from pydantic import BaseModel, Field
from pyworkflowkit.states import WorkflowState


class RetentionPolicy(BaseModel):
    """Politique de rétention et de nettoyage des exécutions historiques."""

    retention_days: int | None = Field(
        default=30,
        ge=1,
        description="Âge maximal en jours des runs terminés à conserver."
    )
    max_runs_per_workflow: int | None = Field(
        default=100,
        ge=1,
        description="Nombre maximal de runs récents à conserver par nom de workflow."
    )
    prune_states: list[WorkflowState] = Field(
        default_factory=lambda: [WorkflowState.SUCCEEDED, WorkflowState.CANCELLED],
        description="États ciblés par la purge. Les runs FAILED peuvent être exclus pour audit."
    )
    retain_failed_runs_days: int | None = Field(
        default=90,
        description="Durée de rétention spécifique étendue pour les runs en FAILED."
    )
```

---

## 3. Protocole de Purge Transactionnelle Ordonnée

La suppression directe d'un run viole les contraintes de clés étrangères si elle n'est pas ordonnée avec précision. L'algorithme de purge s'exécute au sein d'une transaction isolée (`SERIALIZABLE` ou verrou exclusif court) selon l'ordre strict suivant :

```text
Identification des workflow_run_ids éligibles (SELECT selon RetentionPolicy)
                               │
                               ▼
        Découpage en lots bornés (batch_size = 500 runs)
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
        Transaction SQLite                  Transaction PostgreSQL
            │                                     │
            ▼                                     ▼
1. DELETE FROM v2_task_output_checkpoints WHERE workflow_run_id IN (...)
2. DELETE FROM v2_events                  WHERE workflow_run_id IN (...)
3. DELETE FROM v2_task_attempts           WHERE task_run_id IN (...)
4. DELETE FROM v2_task_runs               WHERE workflow_run_id IN (...)
5. DELETE FROM v2_workflow_runs           WHERE workflow_run_id IN (...)
            │                                     │
            └──────────────────┬──────────────────┘
                               ▼
                     COMMIT de la transaction
                               ▼
         Émission du PruneReport & Event d'audit
```

### 3.1 Protection Anti-Verrouillage (Batch Processing)
Pour éviter de verrouiller la base de données PostgreSQL ou SQLite pendant plusieurs dizaines de secondes lors de purges massives, le nettoyage traite les enregistrements par **lots bornés** (500 runs par transaction), avec un court relâchement de verrou entre chaque lot.

---

## 4. Mode Simulation (`--dry-run`)

Pour permettre aux opérateurs d'évaluer l'impact d'une politique de rétention sans risque :
* Le mode `dry_run=True` exécute les requêtes de comptage et de sélection (`SELECT COUNT(*) ...`).
* Il renvoie le `PruneReport` prévisionnel sans exécuter aucun `DELETE`.

```json
{
  "dry_run": true,
  "scanned_workflows": 12,
  "eligible_runs_to_prune": 1450,
  "estimated_deleted_records": {
    "workflow_runs": 1450,
    "task_runs": 8700,
    "task_attempts": 9200,
    "events": 54000,
    "checkpoints": 8500
  }
}
```

---

## 5. Spécification de l'Interface du `MetadataStore`

Le contrat abstrait `MetadataStore` est étendu de façon compatible :

```python
class MetadataStore(Protocol):
    """Protocole de persistance des métadonnées PyWorkflowKit."""

    ...

    def prune_runs(
        self,
        policy: RetentionPolicy,
        *,
        dry_run: bool = False,
        batch_size: int = 500,
    ) -> PruneReport:
        """Purge les runs historiques expirés selon la politique de rétention."""
        ...
```

Les implémentations `SQLiteMetadataStore` et `PostgreSQLMetadataStore` implémentent nativement cette méthode en utilisant les index existants pour optimiser les clauses `WHERE created_at < :cutoff_date`.
