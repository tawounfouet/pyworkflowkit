# Plan d'Implémentation : LOT-34 — Cycle de Vie du Store & Rétention Transactionnelle

- **Statut** : Plan d'implémentation opérationnel
- **Milestone** : LOT-34
- **Phase** : Phase 3 (Gouvernance du Store, Observabilité & Supply Chain)
- **Dépendance amont** : Phase 2 (LOT-33)
- **Document cadre** : Blueprint C (`docs/architecture/v2-store-lifecycle-and-retention-specification.md`)
- **Branche de travail cible** : `feat/v2-lot34-store-lifecycle-pruning`

---

## 1. Objectifs & Périmètre du Lot

Le but de **LOT-34** est de doter les stores de persistance de PyWorkflowKit d'un mécanisme de nettoyage et de rétention transactionnel :
1. **Modèle `RetentionPolicy`** : Définition des critères d'âge (`retention_days`), de quota par workflow (`max_runs_per_workflow`) et de filtrage par état.
2. **Méthode `MetadataStore.prune_runs(...)`** : Implémentation de la suppression ordonnée en cascade respectant l'intégrité référentielle sur `MemoryMetadataStore`, `SQLiteMetadataStore` et `PostgreSQLMetadataStore`.
3. **Traitement par Lots Bornés (*Batching*)** : Découpage par tranches de 500 runs par transaction pour éliminer tout risque de verrouillage prolongé de la base.
4. **Support du Mode Simulation (`dry_run=True`)** : Comptage prévisionnel des lignes sans suppression.
5. **Commande CLI `pwk store prune`** : Interface opérateur avec rapport d'assainissement structuré (`PruneReport`).

---

## 2. Fichiers à Modifier et Créer

```text
src/pyworkflowkit/
├── persistence/
│   ├── contracts.py            # Modèle RetentionPolicy et méthode prune_runs sur MetadataStore
│   ├── memory.py               # Implémentation du pruning en mémoire
│   ├── sqlite.py               # Implémentation transactionnelle par lots SQLite
│   └── postgresql.py           # Implémentation transactionnelle par lots PostgreSQL
│
└── cli/
    ├── commands/
    │   └── prune.py            # Contrôleur Typer pour `pwk store prune`
    ├── services/
    │   └── prune_service.py    # Service métier d'orchestration du pruning
    └── models/
        └── reports.py          # Modèle PruneReport (lignes scannées/supprimées par table)

tests/
├── unit/persistence/
│   └── test_v2_retention_policy.py         # Validation des règles de sélection
├── integration/
│   ├── test_v2_store_prune_sqlite.py       # Test de purge massive SQLite et intégrité
│   └── test_v2_store_prune_postgres.py     # Test de purge PostgreSQL sous concurrence
└── contract/cli/
    └── test_store_prune_contract.py        # Vérification du contrat de sortie CLI
```

---

## 3. Détail des Spécifications Techniques

### 3.1 Ordre de Suppression en Cascade
Dans une même transaction atomique :
1. `DELETE FROM v2_task_output_checkpoints WHERE workflow_run_id IN (...)`
2. `DELETE FROM v2_events WHERE workflow_run_id IN (...)`
3. `DELETE FROM v2_task_attempts WHERE task_run_id IN (SELECT task_run_id FROM v2_task_runs WHERE workflow_run_id IN (...))`
4. `DELETE FROM v2_task_runs WHERE workflow_run_id IN (...)`
5. `DELETE FROM v2_workflow_runs WHERE workflow_run_id IN (...)`

### 3.2 Commande CLI `pwk store prune`
```bash
# Simulation
pwk store prune --retention-days 30 --dry-run --json

# Exécution réelle
pwk store prune --retention-days 30 --max-runs-per-workflow 50
```

---

## 4. Stratégie de Test

* **Test de Non-Corruption** : Remplir une base SQLite avec 2 000 runs, exécuter `prune_runs(retention_days=10)`, vérifier que la base reste 100% cohérente et que `PRAGMA integrity_check` renvoie `ok`.
* **Test de Performance** : Vérifier que la suppression de 10 000 enregistrements prend moins de 1 seconde grâce aux index sur `created_at`.

---

## 5. Critères d'Acceptation (Definition of Done)

- [ ] `MetadataStore.prune_runs(...)` fonctionne de manière atomique sur SQLite et PostgreSQL.
- [ ] Le mode `--dry-run` simule le nombre exact d'enregistrements sans aucune suppression.
- [ ] La commande CLI `pwk store prune` est documentée et testée.
- [ ] Aucune violation de clé étrangère n'est possible lors des purges partielles.
- [ ] `ruff` et `mypy --strict` sont à 0 défaut.
