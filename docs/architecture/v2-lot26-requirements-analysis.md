# PyWorkflowKit V2 — LOT-26 Requirements Analysis & Specification

Status: normative specification  
Milestone: LOT-26  
Target Line: PyWorkflowKit 2.1.0  
Baseline: PyWorkflowKit 2.0.0 (`2d335f8db463a2267306e41ecf0ec7e3d4eb2fd9`)  
Depends on: LOT-25 (`docs/architecture/v2-lot25-post-2.0-expression-of-need.md`)  

---

## 1. Introduction & Objectif

Le document **LOT-25** a formalisé l'Expression du Besoin pour l'évolution de PyWorkflowKit vers sa ligne **2.1**, articulée autour de 9 piliers stratégiques et gouvernée par une stricte politique de compatibilité ascendante.

**LOT-26 constitue l'Analyse Formelle des Exigences**. Il traduit les besoins utilisateurs et opérationnels en :
- exigences fonctionnelles auditables (**FR**) ;
- exigences non-fonctionnelles et budgets opérationnels (**NFR**) ;
- frontières d'étanchéité et règles d'invariance contractuelle 2.0 ;
- matrice de traçabilité complète liant chaque exigence au modèle MoSCoW.

---

## 2. Invariants Architecturaux et Frontières 2.0

Toute évolution introduite dans la ligne 2.1 est soumise aux règles d'invariance suivantes :

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        RÈGLES D'INVARIANCE 2.0                         │
├────────────────────────────────────────────────────────────────────────┤
│ INV-01 : Racine publique 2.0 immuable (13 symboles canoniques)         │
│ INV-02 : Rétro-compatibilité stricte des codecs wire version 1         │
│ INV-03 : Migrations de stores (SQLite/PostgreSQL) 100% non-destructives │
│ INV-04 : Zéro dépendance obligatoire supplémentaire dans le core       │
│ INV-05 : Respect strict des Non-Goals (pas de scheduler, ni broker)    │
└────────────────────────────────────────────────────────────────────────┘
```

1. **`INV-01` — Immuabilité de la racine publique** : Les 13 symboles exportés par `pyworkflowkit` (`ExecutionPlan`, `WorkflowDefinition`, `TaskDefinition`, `WorkflowRun`, `TaskRun`, `TaskAttempt`, etc.) ne doivent subir aucune rupture de signature ou de sémantique.
2. **`INV-02` — Pérennité du Wire Contract V1** : Les payloads sérialisés (`correlation_context_v1`, `workflow_execution_reference_v1`, etc.) doivent rester décodables sans perte d'information.
3. **`INV-03` — Migrations additives des métadonnées** : Les schémas relationnels ne doivent supprimer aucune colonne ni altérer de clés primaires existantes.
4. **`INV-04` — Core léger sans dépendance imposée** : Les extensions OpenTelemetry (`pyworkflowkit[otel]`) et PostgreSQL (`pyworkflowkit[postgres]`) doivent demeurer strictement optionnelles.
5. **`INV-05` — Non-Goals sanctuarisés** : PyWorkflowKit reste un moteur d'exécution de graphes dirigé et n'embarque aucun scheduler temporel, démon de cluster distribué, ou serveur web.

---

## 3. Exigences Fonctionnelles (Functional Requirements)

### 3.1 Domaine CLI Modulaire & Outillage Opérateur (`FR-CLI`)

* **`FR-CLI-01` — Découpage Hexagonal du Package CLI** : La CLI doit être restructurée sous forme d'un sous-package modulaire `src/pyworkflowkit/cli/` séparant `commands/` (parsing Typer), `services/` (logique métier pure), `models/` (Pydantic), `rendering/` (présentation), `context.py` et `security.py`.
* **`FR-CLI-02` — Remplacement du Monolithe V1** : L'ancien fichier `src/pyworkflowkit/cli.py` doit être déprécié ou refondu pour n'utiliser que le runtime, le planner et les stores V2, éliminant tout import de `pyworkflowkit.application.*` ou `declarative.*`.
* **`FR-CLI-03` — Commande `pwk validate`** : Doit analyser statiquement une cible de workflow (`module:attribute` ou fichier), détecter les cycles, les dépendances introuvables et les tâches orphelines, et retourner un code d'erreur standardisé sans instancier d'exécuteur.
* **`FR-CLI-04` — Commande `pwk plan`** : Doit compiler le workflow en `ExecutionPlan` V2 et permettre un rendu sous trois formats : table ASCII, arbre Rich, ou syntaxe textuelle **Mermaid** exportable.
* **`FR-CLI-05` — Commande `pwk run`** : Doit permettre l'exécution managée d'un workflow avec options de sélection d'exécuteur (`--executor inline|thread|process`) et de store (`--store memory|sqlite|postgres`).
* **`FR-CLI-06` — Commande `pwk inspect`** : Doit interroger le `MetadataStore` pour restituer l'arbre des tentatives (`TaskAttempt`), les événements et le diagnostic d'échec (`FailureEvidence`) d'un `WorkflowRunId` donné.
* **`FR-CLI-07` — Commande `pwk doctor`** : Doit auditer l'environnement (version Python, SQLite, connectivité PostgreSQL, présence des extras optionnels) et générer un rapport de diagnostic complet.
* **`FR-CLI-08` — Double Rendu Hermétique (Human vs JSON)** : Chaque commande doit supporter le flag `--json` émettant un flux JSON conforme à un modèle Pydantic strict sur `stdout`, les messages d'avertissement ou de log étant déportés sur `stderr`.
* **`FR-CLI-09` — Codes de Sortie Normalisés** : La CLI doit utiliser une énumération `ExitCode` formelle (`0`=Succès, `1`=Erreur utilisateur, `2`=Erreur de validation statique, `3`=Échec d'exécution du workflow, `4`=Violation de sécurité/accès).
* **`FR-CLI-10` — Sécurité Filesystem & Imports** : Le module `cli/security.py` doit valider les chemins locaux, interdire les traversées de répertoires (*path traversal*), refuser les liens symboliques pointant hors du workspace, et limiter la taille maximale des fichiers inspectés.

---

### 3.2 Domaine Ergonomie d'Authoring & Validation Statique (`FR-DX`)

* **`FR-DX-01` — Chaining d'Exécution Fluide** : Le DSL d'authoring doit supporter des opérateurs ergonomiques de dépendance (ex. `task_a >> task_b >> [task_c, task_d]`) tout en préservant l'API explicite existante (`.add_task(..., depends_on=...)`).
* **`FR-DX-02` — Détection Statique Immédiate des Cycles** : Lors de la construction du graphe, l'ajout d'une dépendance formant un cycle doit lever immédiatement une `CircularDependencyError` explicite avant toute exécution.
* **`FR-DX-03` — Typage Générique des Tâches** : Les définitions de tâches (`TaskDefinition[T_Input, T_Output]`) doivent propager les informations de type statique pour permettre la validation par `mypy` et l'autocomplétion en IDE.
* **`FR-DX-04` — Composition de Sous-Graphes** : Permettre d'encapsuler un sous-workflow ou un `ExecutionPlan` en tant que tâche composite unitaire au sein d'un workflow parent.

---

### 3.3 Domaine Reprise Sélective & Checkpoints (`FR-RESUME`)

* **`FR-RESUME-01` — Reprise au Point de Rupture (*Selective Resume*)** : Le `WorkflowRuntime` doit être capable de reprendre l'exécution d'un workflow échoué ou annulé en identifiant les tâches ayant déjà réussi de manière déterministe.
* **`FR-RESUME-02` — Préservation de l'Historique des Runs** : Une reprise sélective doit générer un nouveau `WorkflowRunId` explicitement corrélé au run d'origine via `parent_run_id` ou `resume_of_run_id`.
* **`FR-RESUME-03` — Classification Déterministe vs Volatile** : Les tâches doivent pouvoir être annotées comme déterministes (sortie mémoïsable) ou volatiles (doit être rejouée même si elle avait réussi dans un run précédent).
* **`FR-RESUME-04` — Exploitation des Checkpoints de Sortie** : Utiliser la table existante `v2_task_output_checkpoints` pour réinjecter les sorties des tâches ancêtres validées sans réexécuter leur logique métier.
* **`FR-RESUME-05` — Validation d'Intégrité du Graphe Rejoué** : Le graphe du workflow doit être vérifié pour garantir que la définition n'a pas été modifiée entre le run d'origine et la reprise (vérification du fingerprint de structure).

---

### 3.4 Domaine Gouvernance du Store & Rétention (`FR-STORE`)

* **`FR-STORE-01` — Spécification des Règles de Rétention** : Définir un modèle de configuration de rétention supportant un âge maximal (`retention_days`) et un quota maximal de runs par workflow (`max_runs_per_workflow`).
* **`FR-STORE-02` — Purge Transactionnelle Ordonnée** : L'opération de purge doit s'exécuter dans une transaction atomique respectant l'ordre des contraintes d'intégrité référentielle : `v2_events` $\rightarrow$ `v2_task_attempts` $\rightarrow$ `v2_task_runs` $\rightarrow$ `v2_workflow_runs`.
* **`FR-STORE-03` — Commande CLI `pwk store prune`** : Fournir une commande d'administration permettant de purger les métadonnées expirées avec support de `--dry-run` indiquant le volume d'enregistrements ciblés.
* **`FR-STORE-04` — Verrouillage Optimiste / Concurrence (CAS)** : Sécuriser les transitions d'état concurrentes sur un même run via un mécanisme de Compare-And-Swap (CAS) ou versionnement de ligne pour PostgreSQL et SQLite.

---

### 3.5 Domaine Observabilité & Tracing OpenTelemetry (`FR-OTEL`)

* **`FR-OTEL-01` — Hiérarchie Canonique des Spans** : Lorsque l'extra `[otel]` est activé, l'exécution d'un workflow doit générer :
  - **Span Racine** : `workflow: {workflow_name}` avec attributs `workflow_run_id`, `status` ;
  - **Span Intermédiaire** : `task: {task_name}` avec attributs `task_run_id` ;
  - **Span Feuille** : `attempt: {attempt_number}` avec `task_attempt_id`, `executor_type`.
* **`FR-OTEL-02` — Propagation du Contexte W3C** : Le `CorrelationContext` de PyWorkflowKit doit porter et propager nativement les en-têtes `traceparent` et `tracestate` vers les exécuteurs subprocess et les intégrations externes.
* **`FR-OTEL-03` — Découplage de l'API Core** : Le code du noyau de PyWorkflowKit ne doit contenir aucune dépendance dure au SDK OpenTelemetry. Une interface `TelemetryBridge` no-op doit être active par défaut.

---

### 3.6 Domaine Synergie Écosystème (`FR-ECO`)

* **`FR-ECO-01` — Adaptateur Natif PyIngestKit 2.0** : Fournir une tâche wrapper permettant d'exécuter une `IngestionDefinition` PyIngestKit 2.0 et de lier automatiquement le `PublishedDataset` résultant au graphe de lineage du workflow.
* **`FR-ECO-02` — Étape de Validation PyTransformKit 1.1** : Fournir une tâche spécialisée pour la validation déclarative de schémas (`pytransformkit.schema_io`) avec propagation des erreurs typées.
* **`FR-ECO-03` — Pipeline Référence Customer 360 v2** : Mettre à jour l'exemple de référence Customer 360 pour démontrer l'enchaînement fluide `PyIngestKit` $\rightarrow$ `PyTransformKit` $\rightarrow$ `PyWorkflowKit`.

---

### 3.7 Domaine Release Engineering & Chaîne d'Approvisionnement (`FR-SUP`)

* **`FR-SUP-01` — PyPI Trusted Publishing OIDC** : Implémenter le workflow GitHub Actions de publication OIDC automatique sur publication de release GitHub, strictement calqué sur l'implémentation de `pytransformkit`.
* **`FR-SUP-02` — Génération de SBOM** : Intégrer la génération automatique d'un inventaire SBOM au format CycloneDX lors de la qualification d'artefact.
* **`FR-SUP-03` — Attestations Numériques Sigstore** : Générer et publier les attestations de provenance de build cryptographiques pour les archives wheel et sdist.
* **`FR-SUP-04` — Choix Formel de Licence** : Renseigner explicitement la licence logicielle (ex. MIT) dans le `pyproject.toml` et les métadonnées de package.

---

## 4. Exigences Non-Fonctionnelles (Non-Functional Requirements)

| Code | Domaine | Exigence / Budget mesurable |
| :--- | :--- | :--- |
| **`NFR-PERF-01`** | Latence CLI | Démarrage à froid de `pwk version` ou `pwk --help` inférieur à **70 ms**. |
| **`NFR-PERF-02`** | Overhead Tracing | L'activation de la passerelle OpenTelemetry ne doit pas induire plus de **3%** d'overhead sur le temps d'exécution total du runtime. |
| **`NFR-PERF-03`** | Efficacité Purge | La commande `pwk store prune` doit traiter les suppressions par lots bornés (batchs de 1 000 enregistrements) pour éviter le verrouillage prolongé de SQLite ou PostgreSQL. |
| **`NFR-SEC-01`** | Sécurité Chemins | Rejet strict de toute cible pointant vers un fichier hors de l'arborescence autorisée ou contenant des séquences `../` suspectes. |
| **`NFR-SEC-02`** | Audit Sécurité | 0 alerte Bandit de sévérité moyenne/haute et 0 vulnérabilité `pip-audit` sur les dépendances de production. |
| **`NFR-TEST-01`** | Couverture de Test | Maintien d'une couverture globale de tests supérieure à **90%** sur le package `src/pyworkflowkit/`. |
| **`NFR-TEST-02`** | Tests d'Architecture | Maintien de tests d'étanchéité stricts (`test_cli_boundaries.py`) interdisant l'importation de Typer ou Rich dans les modules du noyau runtime. |
| **`NFR-PORT-01`** | Portabilité | Qualification 100% verte sur la matrice officielle : Ubuntu, macOS, Windows et Python 3.11, 3.12, 3.13, 3.14. |

---

## 5. Matrice de Traçabilité MoSCoW (LOT-25 $\leftrightarrow$ LOT-26)

| Priorité MoSCoW | Pilier LOT-25 | Exigences Fonctionnelles (FR) | Exigences Non-Fonctionnelles (NFR) |
| :--- | :--- | :--- | :--- |
| **MUST HAVE** | **Pillar 1 : DX & Authoring** | `FR-CLI-01`, `FR-CLI-02`, `FR-CLI-03`, `FR-DX-01`, `FR-DX-02` | `NFR-PERF-01`, `NFR-TEST-02` |
| **MUST HAVE** | **Pillar 4 : Recovery & Resume** | `FR-RESUME-01`, `FR-RESUME-02`, `FR-RESUME-03`, `FR-RESUME-04`, `FR-STORE-04` | `NFR-TEST-01` |
| **MUST HAVE** | **Pillar 5 : Store Governance** | `FR-STORE-01`, `FR-STORE-02`, `FR-STORE-03` | `NFR-PERF-03` |
| **MUST HAVE** | **Pillar 8 : Release Engineering** | `FR-SUP-01`, `FR-SUP-04` | `NFR-SEC-02`, `NFR-PORT-01` |
| **SHOULD HAVE** | **Pillar 2 : Observabilité & OTel** | `FR-OTEL-01`, `FR-OTEL-02`, `FR-OTEL-03` | `NFR-PERF-02` |
| **SHOULD HAVE** | **Pillar 3 : Diagnostics & Dry-Run**| `FR-CLI-04`, `FR-CLI-06` | `NFR-PERF-01` |
| **SHOULD HAVE** | **Pillar 7 : Synergie Écosystème** | `FR-ECO-01`, `FR-ECO-02`, `FR-ECO-03` | `NFR-TEST-01` |
| **SHOULD HAVE** | **Pillar 9 : CLI Outillage** | `FR-CLI-05`, `FR-CLI-07`, `FR-CLI-08`, `FR-CLI-09`, `FR-CLI-10` | `NFR-SEC-01`, `NFR-PERF-01` |
| **COULD HAVE** | **Pillar 6 : Sandboxing Exécuteur**| `FR-DX-04` | `NFR-SEC-01` |
| **COULD HAVE** | **Pillar 8 : SBOM & Sigstore** | `FR-SUP-02`, `FR-SUP-03` | `NFR-SEC-02` |
| **WON'T HAVE** | Non-Goals (Scheduler, Web UI) | Exclus par conception (`INV-05`) | N/A |

---

## 6. Prochaines Étapes Documentaires

La validation des exigences formelles de LOT-26 ouvre la voie à la rédaction des **4 spécifications techniques détaillées (Blueprints)** :
1. **`v2-cli-specification-and-command-model.md`** : Définition formelle des commandes et contrats JSON de la CLI.
2. **`v2-selective-resume-and-recovery-specification.md`** : Algorithme de reprise ciblée et réutilisation des checkpoints.
3. **`v2-store-lifecycle-and-retention-specification.md`** : Protocole transactionnel de rétention et purge du store.
4. **`v2-opentelemetry-tracing-specification.md`** : Spécification de la passerelle OTel et propagation W3C.

L'ensemble convergera ensuite vers **LOT-27 (Architecture Cible Globale 2.1)** et **LOT-28 (Matrice de Qualification & Découpage en Lots)**.
