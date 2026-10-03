# PyWorkflowKit V2 — LOT-28 Test Matrix, Acceptance Criteria & Implementation Roadmap 2.1

Status: normative execution roadmap  
Milestone: LOT-28  
Target Line: PyWorkflowKit 2.1.0  
Baseline: PyWorkflowKit 2.0.0 (`2d335f8db463a2267306e41ecf0ec7e3d4eb2fd9`)  
Depends on: LOT-25, LOT-26, LOT-27, Blueprints A, B, C, D  

---

## 1. Introduction & Objectif d'Exécution

Après la formalisation de l'Expression du Besoin (**LOT-25**), l'Analyse des Exigences (**LOT-26**), les Spécifications Détaillées (Blueprints A à D) et l'Architecture Cible (**LOT-27**), **LOT-28 établit la feuille de route d'implémentation opérationnelle et la matrice de test** pour la livraison de PyWorkflowKit 2.1.

Ce document définit :
1. Le découpage modulaire en lots d'implémentation séquentiels (LOT-29 à LOT-38).
2. La matrice complète des critères d'acceptation et des tests de conformité.
3. La stratégie de qualification continue garantissant la non-régression de la ligne stable 2.0.

---

## 2. Découpage Modulaire des Lots d'Implémentation (LOT-29 $\rightarrow$ LOT-38)

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        PHASE 1 : NOUVELLE CLI MODULAIRE                │
├────────────────────────────────────────────────────────────────────────┤
│ LOT-29 : Socle CLI, Bootstrap, Sécurité & Diagnostic                   │
│          (Package cli/, context, exit_codes, security, version, doctor)│
│ LOT-30 : Services & Commandes d'Inspection (validate, plan, inspect)   │
│ LOT-31 : Commande d'Exécution (run), Rendu Machine & Contrat Gelé      │
│          (contracts/cli_contract_v1.json, dual-rendering human/json)   │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────┐
│                        PHASE 2 : ERGONOMIE & MOTEUR RUNTIME            │
├────────────────────────────────────────────────────────────────────────┤
│ LOT-32 : Ergonomie d'Authoring & Validation Statique (Opérateur >>)    │
│ LOT-33 : Reprise Sélective & Checkpoints (Selective Resume at failure) │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────┐
│                        PHASE 3 : GOUVERNANCE DU STORE & OIDC           │
├────────────────────────────────────────────────────────────────────────┤
│ LOT-34 : Cycle de Vie & Rétention du Store (prune_runs transactionnel) │
│ LOT-35 : Passerelle OpenTelemetry Tracing ([otel] extra & W3C context) │
│ LOT-36 : Automatisation Release, PyPI Trusted Publishing, SBOM & Licence│
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────┐
│                        PHASE 4 : QUALIFICATION & RELEASE               │
├────────────────────────────────────────────────────────────────────────┤
│ LOT-37 : Qualification Complète 2.1.0rc1 (Customer 360 v2 & Matrices)  │
│ LOT-38 : Promotion Stable PyWorkflowKit 2.1.0 & Clôture de Ligne       │
└────────────────────────────────────────────────────────────────────────┘
```

---

### Description Détaillée des Lots

#### LOT-29 — Socle CLI, Bootstrap, Sécurité & Diagnostic
* **Objectif** : Création du sous-package `src/pyworkflowkit/cli/` avec son armature fondamentale.
* **Livrables** : `app.py`, `context.py`, `exit_codes.py`, `exceptions.py`, `security.py`, `bootstrap.py`, commandes `version` et `doctor`.
* **Tests** : Tests d'architecture initiaux `test_cli_boundaries.py` interdisant l'import de Typer dans le core.

#### LOT-30 — Services & Commandes d'Inspection (`validate`, `plan`, `inspect`)
* **Objectif** : Implémentation des services métier purs et des commandes d'inspection sans exécuter de workflow.
* **Livrables** : `validate_service.py`, `plan_service.py` (avec rendu Mermaid), `inspect_service.py`.
* **Tests** : 100% de couverture unitaire sur les services sans simulation de terminal.

#### LOT-31 — Commande d'Exécution (`run`), Rendu Machine & Contrat Gelé
* **Objectif** : Finalisation de la CLI avec l'exécution managée V2, le support `--dry-run` et le gel du contrat machine.
* **Livrables** : `run_service.py`, `rendering/human.py` (Rich), `rendering/json.py`, `contracts/cli_contract_v1.json`.
* **Tests** : `test_cli_public_contract_freeze.py` et validation de la compatibilité des flux stdout/stderr.

#### LOT-32 — Ergonomie d'Authoring & Validation Statique
* **Objectif** : Introduction de la syntaxe de flux déclarative et détection précoce des erreurs de graphe.
* **Livrables** : Opérateur `>>` sur `TaskDefinition`, validation immédiate des cycles dans `pyworkflowkit.authoring`.
* **Tests** : Tests de propriétés Hypothesis sur des graphes complexes aléatoires.

#### LOT-33 — Reprise Sélective & Réutilisation Déterministe
* **Objectif** : Capacité de redémarrer un workflow au point d'échec sans recalculer les tâches déterministes validées.
* **Livrables** : Méthode `WorkflowRuntime.resume_run`, exploitation de `v2_task_output_checkpoints`.
* **Tests** : Scénarios d'intégration réels avec simulation de crashs et vérification des gains de temps de calcul.

#### LOT-34 — Cycle de Vie du Store & Rétention Transactionnelle
* **Objectif** : Prévention du bloat des bases SQLite et PostgreSQL par purge ordonnée.
* **Livrables** : `RetentionPolicy`, implémentations `prune_runs` dans SQLite et PostgreSQL, commande `pwk store prune`.
* **Tests** : Vérification de la non-corruption des contraintes de clés étrangères sous fortes volumétries.

#### LOT-35 — Passerelle OpenTelemetry Tracing
* **Objectif** : Export standardisé des spans sans polluer le core.
* **Livrables** : Extra `pyworkflowkit[otel]`, `OpenTelemetryBridge`, injection du `TRACEPARENT` dans les sous-processus.
* **Tests** : Validation de la hiérarchie des spans avec un collecteur OTel en mémoire.

#### LOT-36 — Automatisation Release, PyPI Trusted Publishing, SBOM & Licence
* **Objectif** : Élever la chaîne d'approvisionnement logicielle au niveau de `pytransformkit`.
* **Livrables** : `.github/workflows/publish-pypi.yml` (OIDC), génération CycloneDX SBOM, déclaration formelle de la licence.
* **Tests** : Validation des workflows GitHub Actions en environnement isolé.

#### LOT-37 — Qualification Complète 2.1.0rc1
* **Objectif** : Requalification globale de toutes les matrices d'intégration.
* **Livrables** : Mise à jour du pipeline Customer 360 v2, exécution des matrices Python 3.11 à 3.14.
* **Tests** : Release candidate gate 100% verte.

#### LOT-38 — Promotion Stable PyWorkflowKit 2.1.0
* **Objectif** : Scellage et publication officielle de la version stable 2.1.0.
* **Livrables** : Tag `v2.1.0`, GitHub Release avec attestations Sigstore, publication PyPI automatique.

---

## 3. Matrice de Qualification & Critères d'Acceptation Globaux

Pour qu'un lot soit validé et intégré dans la branche `main` :

| Niveau | Porte de Qualité | Critère Exigé |
| :--- | :--- | :--- |
| **Linters & Typage** | Ruff & Mypy | 0 avertissement, 100% typé sous mode strict |
| **Sécurité** | Bandit & pip-audit | 0 vulnérabilité, 0 avertissement de sévérité moyenne ou haute |
| **Couverture** | pytest-cov | Couverture globale $\ge 90\%$ sur `src/pyworkflowkit/` |
| **Architecture** | test_cli_boundaries.py | Aucune importation illicite (étanchéité stricte noyau/CLI) |
| **Contrat Machine** | test_cli_public_contract_freeze.py | Zéro drift non versionné du fichier `cli_contract_v1.json` |
| **Portabilité** | CI Multi-OS | 100% vert sur Ubuntu, macOS et Windows (Python 3.11, 3.12, 3.13, 3.14) |
| **Invariance 2.0** | test_stable_release_v2.py | Les 13 symboles de la racine 2.0 restent intacts |

---

## 4. Conclusion & Transition vers l'Exécution

Avec la validation de ce document **LOT-28**, la conception normative de **PyWorkflowKit 2.1** est intégralement achevée. La suite logique immédiate est l'ouverture du premier lot technique d'implémentation : **LOT-29 (Socle CLI, Bootstrap & Sécurité)**.
