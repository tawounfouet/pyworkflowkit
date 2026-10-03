# Analyse Comparative d'Architecture CLI : PyWorkflowKit vs PyTransformKit
## Schéma Cible et Feuille de Route pour PyWorkflowKit 2.1

- **Auteur** : Équipe d'Ingénierie PyWorkflowKit / WebTech
- **Date** : Octobre 2026
- **Statut** : Document d'analyse technique & proposition d'architecture cible
- **Contexte** : Cadrage de l'évolution 2.1 (LOT-25 / LOT-26)
- **Références comparées** :
  - Standard de référence : `pytransformkit` 1.2.0 (Lots LOT-44 à LOT-59)
  - État des lieux analysé : `pyworkflowkit` 2.0.0 (`src/pyworkflowkit/cli.py` & `cli_rendering/`)

---

## 1. Contexte et Résumé Exécutif

PyWorkflowKit a franchi avec succès la livraison de sa version majeure **2.0.0 stable** (LOT-00 à LOT-24), dotant le framework d'un moteur d'exécution déterministe et rigoureux : machines à états finis, identité d'exécution stricte, stores de métadonnées transactionnels (SQLite, PostgreSQL), exécuteurs découplés et codecs wire portables.

Cependant, un audit approfondi de la surface opérationnelle révèle une anomalie architecturale majeure :
> **La CLI actuelle de PyWorkflowKit (`src/pyworkflowkit/cli.py`) est un composant monolithique hérité de l'ère V1.1. Elle n'a pas été refondue lors du passage à la V2 et continue d'importer les modules applicatifs obsolètes de la V1.**

En parallèle, le package compagnon `pytransformkit` vient d'achever la mise en œuvre de sa CLI 1.2.0 (lots LOT-44 à LOT-59). Cette réalisation fournit un modèle exemplaire d'architecture logicielle : séparation hexagonale stricte entre parsing Typer et services métier purs, validation de sécurité filesystem, double rendu (Rich coloré vs JSON machine contractuel figé en CI), et découplage absolu garantissant 100% de testabilité unitaire en mémoire.

Le présent document dresse l'état des lieux critique de la CLI de `pyworkflowkit`, établit la comparaison détaillée avec l'étalon `pytransformkit`, et définit l'architecture cible modulaire de la future CLI `pwk` pour la ligne **PyWorkflowKit 2.1**.

---

## 2. Analyse Critique de l'Existant (`pyworkflowkit/cli.py`)

L'inspection de [`src/pyworkflowkit/cli.py`](file:///Users/awf/workspace/professionnal/webtech/packages/pyworkflowkit/src/pyworkflowkit/cli.py) met en évidence plusieurs fragilités de conception :

### 2.1 Anachronisme Architectural : Couplage avec la V1 Legacy
Alors que `pyworkflowkit 2.0` promeut les espaces de noms `pyworkflowkit.runtime`, `pyworkflowkit.planning`, `pyworkflowkit.states`, `pyworkflowkit.persistence` et `pyworkflowkit.executors`, le fichier `cli.py` (lignes 15 à 45) importe exclusivement l'ancienne infrastructure V1 :

```python
# Extrait réel de src/pyworkflowkit/cli.py
from pyworkflowkit.application.manifest import RunManifestSerializer  # ❌ V1 legacy
from pyworkflowkit.application.planning import (                      # ❌ V1 legacy
    DAGValidator,
    ExecutionPlanner,
    build_dependency_graph,
)
from pyworkflowkit.application.runtime import WorkflowRuntime         # ❌ V1 legacy
from pyworkflowkit.config import RuntimeSettings                      # ❌ V1 legacy
from pyworkflowkit.declarative import WorkflowBuilder                 # ❌ V1 legacy
from pyworkflowkit.domain.definitions import WorkflowDefinition       # ❌ V1 legacy
from pyworkflowkit.domain.enums import WorkflowRunStatus              # ❌ V1 legacy
from pyworkflowkit.plugins import PluginCatalog, PluginDiscovery      # ❌ V1 legacy
```

**Conséquence** : La CLI actuelle est incapable de manipuler les objets canoniques de la V2 (`ExecutionPlan`, `WorkflowPlanner`, `TaskAttempt`, `SQLiteMetadataStore`, `PostgreSQLMetadataStore`, `TaskAttemptId`, `WorkflowRunId`). Elle est en déconnexion totale avec le cœur moderne du produit.

### 2.2 Monolithisme et Intrication Typer / Métier
Le fichier `cli.py` regroupe 430 lignes où la définition des arguments de ligne de commande Typer (`@app.command()`) est directement mêlée à la logique métier :
- résolution dynamique de modules Python via `import_module(module_name)` ;
- instanciation ad-hoc des runtimes ;
- manipulation directe des exceptions et flux de sortie.

**Conséquence** : Aucun test unitaire pur n'est possible sans instancier le CLI runner Typer (`CliRunner`). La logique d'inspection ou de validation ne peut être réutilisée programmatiquement par d'autres composants.

### 2.3 Absence de Frontière de Sécurité Filesystem
Le chargement des cibles (`target: module:attribute`) s'effectue via un import direct sans assainissement des chemins, sans vérification contre la traversée de répertoires (*path traversal*), et sans contrôle des liens symboliques.

### 2.4 Contrat Machine Ad-hoc et Non Garanti
L'option `--json` se contente de sérialiser des dictionnaires Python construits à la volée. Il n'existe aucun schéma Pydantic garantissant la structure des réponses JSON, ni de contrat gelé en CI assurant l'interopérabilité avec des outils tiers ou des pipelines d'automatisation.

---

## 3. Le Standard de Référence : `pytransformkit 1.2.0`

La structure introduite dans `pytransformkit` (lots LOT-44 à LOT-59) sépare rigoureusement chaque niveau de responsabilité selon les principes de l'architecture hexagonale :

```text
src/pytransformkit/cli/
├── __init__.py
├── __main__.py
├── app.py                      # Application racine Typer & gestion globale des erreurs
├── bootstrap.py                # Détection dynamique des capacités et modules optionnels
├── context.py                  # CliContext (format human/json, verbosité, isolation I/O)
├── exit_codes.py               # Enum ExitCode formelle (SUCCESS=0, USER_ERROR=1, etc.)
├── exceptions.py               # Hiérarchie d'exceptions typées (CliError, CliValidationError)
├── security.py                 # Assainissement des chemins, symlinks, quotas de taille
├── public_contract.py          # Définition du contrat machine v1
├── commands/                   # Contrôleurs Typer fins (5 à 15 lignes max par commande)
│   ├── version.py
│   ├── doctor.py
│   ├── engines.py
│   ├── schema.py
│   └── contract.py
├── services/                   # Services métier purs (100% testables sans Typer)
│   ├── version.py
│   ├── doctor.py
│   ├── engines.py
│   ├── schema.py
│   ├── schema_convert.py
│   └── contracts.py
├── models/                     # Modèles Pydantic pour les données et rapports JSON
│   ├── reports.py              # DoctorReport, SchemaReport, EngineReport
│   ├── errors.py               # CliErrorReport unifié
│   └── outputs.py              # MachinePayload envelopes
└── rendering/                  # Présentation entièrement découplée
    ├── console.py
    ├── human.py                # Rendu Rich (arbres, tableaux colorés, badges)
    ├── json.py                 # Rendu JSON machine strict
    ├── tables.py
    └── errors.py
```

### Forces architecturales de `pytransformkit` :
1. **Contrôleurs ultra-fins** : Les fichiers dans `commands/` ne font que parser les options Typer, instancier le `CliContext` et déléguer au `Service` correspondant.
2. **Couche Services autonome** : `SchemaService`, `DoctorService`, etc. prennent des chemins ou des modèles en entrée et renvoient des modèles Pydantic (`Report`). Ils sont testables en mémoire à la milliseconde sans runner CLI.
3. **Contrat Machine Gelé (`contracts/cli_contract_v1.json`)** : Chaque commande dispose d'un contrat JSON snapshoté en CI. Tout changement de nom de flag, de code d'erreur ou de clé JSON déclenche une alerte de rupture de compatibilité.
4. **Sécurité Filesystem (`security.py`)** : Résolution canonique des chemins, interdiction des lectures hors du périmètre alloué, protection contre les symlinks cycliques et contrôle des tailles maximales.
5. **Double Rendu Hermétique** : Le mode humain utilise Rich pour une expérience terminal élégante, tandis que le mode `--json` garantit un flux `stdout` propre, strictement parsable par `jq` ou un orchestrateur externe.

---

## 4. Matrice Comparative Détaillée (Gap Analysis)

| Dimension | `pytransformkit 1.2` | `pyworkflowkit 2.0` (Actuel) | Impact & Écart |
| :--- | :--- | :--- | :--- |
| **Organisation du code** | Package modulaire découpé en 6 sous-domaines étanches | Fichier unique `cli.py` (430 lignes) + `cli_rendering/` | **Majeur** : forte dette de couplage dans PWK |
| **Alignement Moteur** | 100% aligné sur le runtime moderne (`schema_io`, types canoniques) | ⚠️ Ancré dans les modules obsolètes V1.1 (`application.planning`, etc.) | **Critique** : la CLI actuelle ne manipule pas la V2 |
| **Découplage Typer / Métier** | Couche `services/` pure. Zéro dépendance à Typer dans la logique métier | Logique métier codée directement dans les fonctions décorées `@app.command()` | **Majeur** : empêche la réutilisation et alourdit les tests |
| **Sécurité Filesystem** | Assainissement systématique, détection de path-traversal et quotas | `import_module(module)` brut sans aucune isolation | **Élevé** : risque de crash ou d'effets de bord à l'import |
| **Contrat Machine (`--json`)** | Schémas Pydantic typés, contrat snapshoté dans `contracts/cli_contract_v1.json` | Dictionnaires ad-hoc sérialisés sans schéma formel | **Majeur** : non prédictible pour l'outillage CI/CD |
| **Codes de Sortie** | `ExitCode(IntEnum)` formelle (`SUCCESS=0`, `USER_ERROR=1`, `VALIDATION=2`...) | Dictionnaire partiel `CLI_EXIT_CODES` avec 3 codes génériques | **Moyen** : manque de précision pour les scripts appelants |
| **Architecture Tests** | `test_cli_boundaries.py` garantissant l'interdiction des fuites d'imports | Aucun test d'architecture dédié aux frontières de la CLI | **Élevé** : risque constant de régression |
| **Extensibilité** | Ajout d'une commande = 1 commande + 1 service + 1 modèle de rapport | Nécessite d'éditer le fichier monolithique `cli.py` | **Moyen** : friction d'évolution |

---

## 5. Architecture Cible pour PyWorkflowKit 2.1 (`pwk`)

Pour la ligne 2.1, nous proposons d'adopter intégralement l'architecture éprouvée de `pytransformkit` en adaptant les sous-domaines aux réalités de l'orchestration de workflows.

### 5.1 Arborescence Cible dans `src/pyworkflowkit/cli/`

```text
src/pyworkflowkit/cli/
├── __init__.py
├── __main__.py                 # Point d'entrée exécutable (python -m pyworkflowkit.cli)
├── app.py                      # Typer application racine & interception globale des erreurs
├── bootstrap.py                # Détection dynamique des capacités ([postgres], [otel], sqlite)
├── context.py                  # CliContext (format, json_mode, verbosité, console, store_override)
├── exit_codes.py               # ExitCode (0=Success, 1=UserError, 2=ValidationError, 3=ExecutionFailure...)
├── exceptions.py               # Hiérarchie CliError, CliValidationError, CliExecutionError...
├── security.py                 # Assainissement de l'import des workflows et vérification des chemins
├── public_contract.py          # Spécification programmatique du contrat machine CLI V1
│
├── commands/                   # Contrôleurs Typer fins
│   ├── __init__.py
│   ├── plan.py                 # pwk plan <target> [--format human|json|mermaid]
│   ├── validate.py             # pwk validate <target> [--strict]
│   ├── run.py                  # pwk run <target> [--executor inline|thread|process] [--store memory|sqlite|postgres]
│   ├── inspect.py              # pwk inspect <workflow-run-id> [--store ...]
│   ├── doctor.py               # pwk doctor (diagnostic pilotes, stores, dépendances)
│   ├── prune.py                # pwk store prune [--retention-days N] [--dry-run]
│   └── version.py              # pwk version
│
├── services/                   # Moteur métier pur V2 (testable unitairement sans Typer)
│   ├── __init__.py
│   ├── plan_service.py         # Compilation via WorkflowPlanner V2 & export de graphe
│   ├── validate_service.py     # Détection statique de cycles, orphelins et contrats de tâches
│   ├── run_service.py          # Exécution managée via WorkflowRuntime V2
│   ├── inspect_service.py      # Lecture des métadonnées, timeline des tentatives et FailureEvidence
│   ├── doctor_service.py       # Diagnostic de l'environnement d'exécution et des bases
│   ├── prune_service.py        # Application des politiques de rétention sur MetadataStore
│   └── version_service.py      # Extraction des métadonnées de version du package
│
├── models/                     # Modèles Pydantic pour les sorties structurées
│   ├── __init__.py
│   ├── reports.py              # PlanReport, ValidationReport, RunReport, InspectReport, DoctorReport
│   ├── errors.py               # CliErrorReport unifié (code, message, context, stack)
│   └── outputs.py              # Enveloppe générique de réponse
│
└── rendering/                  # Présentation découplée
    ├── __init__.py
    ├── console.py              # Instanciation contrôlée des consoles Rich
    ├── human.py                # Rendu visuel riche (arbres de dépendances, tables de statuts, panels)
    ├── json.py                 # Sérialisation JSON normalisée
    └── tables.py               # Formatage des tableaux de tâches et tentatives
```

### 5.2 Les Nouvelles Commandes Clés

1. **`pwk validate <target>`** :
   - Analyse statique du graphe de workflow avant exécution.
   - Détection préventive des cycles, des dépendances circulaires ou des tâches sans chemin d'exécution.
   - Sortie : `ValidationReport` (valide/invalide avec liste d'erreurs typées).

2. **`pwk plan <target>`** :
   - Compile le `WorkflowDefinition` en `ExecutionPlan` déterministe.
   - Modes de rendu : tableau ASCII, arbre hiérarchique Rich, ou syntaxe **Mermaid** exportable pour la documentation.
   - Sortie JSON : description complète des nœuds, arêtes, niveaux de concurrence et politiques de retry.

3. **`pwk run <target>`** :
   - Exécute le workflow via le véritable `WorkflowRuntime` V2.
   - Permet de surcharger dynamiquement l'exécuteur (`--executor thread --max-workers 4`) et le store de métadonnées (`--store sqlite:///runs.db`).
   - Rendu en direct de la séquence des tentatives (`TaskAttempt`) avec chronométrage.

4. **`pwk inspect <workflow-run-id>`** :
   - Se connecte au `MetadataStore` configuré pour inspecter un run existant.
   - Affiche l'historique complet des états, la liste des tâches réussies/échouées, et extrait le `FailureEvidence` structuré en cas d'erreur.

5. **`pwk doctor`** :
   - Vérifie la disponibilité des pilotes optionnels (`psycopg` pour PostgreSQL, drivers tiers).
   - Teste la connectivité aux stores configurés.
   - Affiche les versions de Python, SQLite, SQLAlchemy et des packages compagnons (`pytransformkit`, `pyingestkit`).

6. **`pwk store prune`** (Nouveauté Pilier 5) :
   - Permet de purger les exécutions anciennes selon une politique de rétention (ex. conserver 30 jours ou les 100 derniers runs).
   - Supporte un mode `--dry-run` simulant le nombre d'enregistrements libérés.

---

## 6. Alignement avec la Feuille de Route 2.1 (LOT-25 $\rightarrow$ LOT-26 $\rightarrow$ LOT-27)

L'introduction de cette nouvelle architecture CLI s'intègre harmonieusement dans les jalons définis pour PyWorkflowKit 2.1 :

```text
LOT-25 : Expression of Need & Product Direction (Validé)
         ├── Identification du besoin de refonte de la CLI (Piliers 1 & 9)
         └── Publication du présent document d'analyse comparative
                ↓
LOT-26 : Requirements Analysis & Contract Boundaries
         ├── Spécification formelle des exigences fonctionnelles (FR-CLI-01 à FR-CLI-10)
         ├── Définition des codes d'erreur CLI et de l'Enum ExitCode
         └── Rédaction de la politique de sécurité filesystem
                ↓
LOT-27 : Target Architecture & CLI Interface Specification
         ├── Modélisation Pydantic des rapports (`reports.py`)
         ├── Spécification du contrat machine `contracts/cli_contract_v1.json`
         └── Matrice des tests d'architecture étanches (`test_cli_boundaries.py`)
                ↓
Lots d'Implémentation Modulaire (ex. LOT-28 à LOT-33)
         ├── Implémentation isolée par sous-couche (Bootstrap → Services → Commands → Rendering)
         └── Qualification complète sur la matrice multi-OS et Python 3.11–3.14
```

---

## 7. Recommandations et Prochaines Actions

1. **Valider formellement la cible architecturale modulaire** pour la CLI `pwk`, en remplacement de l'ancien fichier `src/pyworkflowkit/cli.py`.
2. **Intégrer les exigences de la CLI dans LOT-26** (Analyse des Exigences), notamment les exigences d'exécution native V2, de sécurité des imports et de contrat JSON figé.
3. **Préserver la compatibilité binaire** des points d'entrée définis dans `pyproject.toml` (`pwk`, `pyworkflowkit`), en assurant une transition sans rupture pour les utilisateurs existants.
4. **Appliquer les tests d'étanchéité architecturale** dès la première phase d'implémentation pour garantir l'absence de régression ou de dépendance circulaire.

---
*Ce document sert de référence contractuelle pour la conception et l'implémentation de la CLI de PyWorkflowKit 2.1.*
