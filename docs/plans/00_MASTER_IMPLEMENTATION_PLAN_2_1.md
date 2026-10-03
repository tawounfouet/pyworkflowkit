# PyWorkflowKit 2.1 — Master Implementation Plan
## Séquence d'Exécution, Dépendances & Matrice des Livrables

- **Statut** : Plan d'implémentation directeur (Master Plan)
- **Cible** : PyWorkflowKit 2.1.0
- **Baseline** : PyWorkflowKit 2.0.0 (`2d335f8db463a2267306e41ecf0ec7e3d4eb2fd9`)
- **Documents cadres** : LOT-25 à LOT-28, Blueprints A à D

---

## 1. Vue d'Ensemble de la Ligne 2.1

La livraison de la ligne PyWorkflowKit 2.1 s'articule autour de 10 lots techniques d'implémentation (LOT-29 à LOT-38) regroupés en 4 phases d'ingénierie séquentielles :

```text
┌────────────────────────────────────────────────────────────────────────┐
│ PHASE 1 : NOUVELLE CLI MODULAIRE HEXAGONALE                            │
│  ├── LOT-29 : Socle CLI, Bootstrap, Sécurité & Diagnostic             │
│  ├── LOT-30 : Services & Commandes d'Inspection (validate, plan, ...) │
│  └── LOT-31 : Commande d'Exécution (run), Dual-Rendering & Freeze      │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────┐
│ PHASE 2 : ERGONOMIE D'AUTHORING & REPRISE SÉLECTIVE DU RUNTIME         │
│  ├── LOT-32 : Ergonomie d'Authoring & Validation Statique (>>)        │
│  └── LOT-33 : Reprise Sélective au Point d'Échec (Checkpoints)        │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────┐
│ PHASE 3 : GOUVERNANCE DU STORE, OBSERVABILITÉ & SUPPLY CHAIN           │
│  ├── LOT-34 : Cycle de Vie & Rétention Transactionnelle du Store       │
│  ├── LOT-35 : Passerelle OpenTelemetry Tracing ([otel] & W3C)          │
│  └── LOT-36 : Automatisation Release OIDC, SBOM & Licence              │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────┐
│ PHASE 4 : QUALIFICATION DE LIGNE & PROMOTION STABLE                    │
│  ├── LOT-37 : Qualification Complète 2.1.0rc1 (Customer 360 v2)        │
│  └── LOT-38 : Promotion Stable PyWorkflowKit 2.1.0 & Clôture           │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Graphe des Dépendances entre Lots

```text
LOT-29 (Socle CLI)
  │
  ├──► LOT-30 (Services & Inspection)
  │      │
  │      └──► LOT-31 (Exécution & Contrat Gelé)
  │             │
LOT-32 (Authoring >>) ──┐
  │                     ▼
  └─────────────► LOT-33 (Selective Resume)
                        │
LOT-34 (Store Retention)┤
LOT-35 (OTel Tracing) ──┤
LOT-36 (OIDC & SBOM)  ──┤
                        ▼
                  LOT-37 (Qualification 2.1.0rc1)
                        │
                        ▼
                  LOT-38 (Publication Stable 2.1.0)
```

---

## 3. Index des Plans d'Implémentation Détaillés

Les plans techniques individuels sont disponibles dans les documents suivants :

1. **[`01_PLAN_LOT29_CLI_FOUNDATIONS.md`](file:///Users/awf/workspace/professionnal/webtech/packages/pyworkflowkit/docs/plans/01_PLAN_LOT29_CLI_FOUNDATIONS.md)** : Socle modulaire Typer, isolation `CliContext`, vérification des chemins `security.py`, bootstrap dynamique et commandes `version` et `doctor`.
2. **[`02_PLAN_LOT30_CLI_INSPECTION_SERVICES.md`](file:///Users/awf/workspace/professionnal/webtech/packages/pyworkflowkit/docs/plans/02_PLAN_LOT30_CLI_INSPECTION_SERVICES.md)** : Moteur de services purs et commandes `pwk validate`, `pwk plan` (Mermaid/ASCII) et `pwk inspect`.
3. **[`03_PLAN_LOT31_CLI_RUN_AND_CONTRACT_FREEZE.md`](file:///Users/awf/workspace/professionnal/webtech/packages/pyworkflowkit/docs/plans/03_PLAN_LOT31_CLI_RUN_AND_CONTRACT_FREEZE.md)** : Commande `pwk run` V2, simulation `--dry-run`, dual-rendering Rich/JSON et gel contractuel dans `contracts/cli_contract_v1.json`.
4. **[`04_PLAN_LOT32_AUTHORING_ERGONOMICS.md`](file:///Users/awf/workspace/professionnal/webtech/packages/pyworkflowkit/docs/plans/04_PLAN_LOT32_AUTHORING_ERGONOMICS.md)** : Chaining déclaratif `task_a >> task_b`, détection immédiate de cycles et typage statique strict.
5. **[`05_PLAN_LOT33_SELECTIVE_RESUME.md`](file:///Users/awf/workspace/professionnal/webtech/packages/pyworkflowkit/docs/plans/05_PLAN_LOT33_SELECTIVE_RESUME.md)** : Moteur de reprise sélective `WorkflowRuntime.resume_run`, discrimination déterministe/volatile et réutilisation de `v2_task_output_checkpoints`.
6. **[`06_PLAN_LOT34_STORE_LIFECYCLE_PRUNING.md`](file:///Users/awf/workspace/professionnal/webtech/packages/pyworkflowkit/docs/plans/06_PLAN_LOT34_STORE_LIFECYCLE_PRUNING.md)** : Purge transactionnelle ordonnée par lots dans SQLite et PostgreSQL, modèle `RetentionPolicy` et commande `pwk store prune`.
7. **[`07_PLAN_LOT35_OPENTELEMETRY_TRACING.md`](file:///Users/awf/workspace/professionnal/webtech/packages/pyworkflowkit/docs/plans/07_PLAN_LOT35_OPENTELEMETRY_TRACING.md)** : Extra optionnel `pyworkflowkit[otel]`, pontage `TelemetryBridge`, hiérarchie des spans et propagation W3C `traceparent`.
8. **[`08_PLAN_LOT36_RELEASE_AUTOMATION_AND_SUPPLY_CHAIN.md`](file:///Users/awf/workspace/professionnal/webtech/packages/pyworkflowkit/docs/plans/08_PLAN_LOT36_RELEASE_AUTOMATION_AND_SUPPLY_CHAIN.md)** : Workflow OIDC PyPI Trusted Publishing, génération SBOM CycloneDX, attestations Sigstore et formalisation de licence.
9. **[`09_PLAN_LOT37_LOT38_QUALIFICATION_AND_RELEASE.md`](file:///Users/awf/workspace/professionnal/webtech/packages/pyworkflowkit/docs/plans/09_PLAN_LOT37_LOT38_QUALIFICATION_AND_RELEASE.md)** : Matrice multi-OS / Python 3.11–3.14, qualification de release candidate 2.1.0rc1 et promotion stable 2.1.0.

---

## 4. Règles d'Ingénierie pour chaque Lot

Chaque lot d'implémentation doit respecter le protocole strict :
1. **Branche dédiée** : `feat/v2-lotXX-<nom-du-lot>` créée depuis `main`.
2. **Aucune régression 2.0** : Validation continue par `test_stable_release_v2.py`.
3. **Étanchéité des frontières** : Aucun import de Typer dans le core runtime (`test_cli_boundaries.py`).
4. **Zéro tolérance linter** : 100% propre sous `ruff check .` et `mypy --strict`.
5. **Couverture de code** : Maintien de $\ge 90\%$ de couverture sur les nouveaux modules créés.
