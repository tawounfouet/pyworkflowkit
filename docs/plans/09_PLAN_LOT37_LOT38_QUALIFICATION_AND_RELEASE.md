# Plan d'Implémentation : LOT-37 & LOT-38 — Qualification Release Candidate (2.1.0rc1) & Promotion Stable (2.1.0)

- **Statut** : Plan d'implémentation opérationnel
- **Milestones** : LOT-37 (Qualification RC) & LOT-38 (Promotion Stable)
- **Phase** : Phase 4 (Stabilisation, Release Candidate & Promotion Stable)
- **Dépendance amont** : Tous les lots antérieurs (LOT-29 à LOT-36)
- **Documents cadres** : LOT-27 (`v2-lot27-target-architecture.md`), LOT-28 (`v2-lot28-test-matrix-and-implementation-roadmap.md`)
- **Branches de travail cibles** : `release/2.1.0rc1` $\rightarrow$ `main`

---

## 1. Objectifs & Périmètre des Lots

Les lots de clôture **LOT-37** et **LOT-38** matérialisent le passage de la suite de fonctionnalités 2.1 en production :

### LOT-37 : Qualification Globale Release Candidate (`v2.1.0rc1`)
1. **Élévation de Version** : Bumping vers `2.1.0rc1`.
2. **Matrice Complète d'Intégration** : Validation sur les versions de Python 3.11, 3.12, 3.13, et 3.14 sur Linux, macOS et Windows.
3. **Pipeline E2E Réel (Customer 360 v2)** : Exécution de bout en bout du pipeline de référence combinant :
   - Syntaxe fluide `task_a >> task_b`
   - Invocation via la nouvelle CLI (`pwk run`)
   - Simulation d'incident et reprise sélective (`--resume-from`)
   - Inspection du store et purge transactionnelle (`pwk store prune`)
   - Tracing OpenTelemetry actif avec spans parentées.
4. **Vérification d'Invariance 2.0** : Validation sans faille de `test_stable_release_v2.py`.

### LOT-38 : Promotion Stable & Clôture de Release (`v2.1.0`)
1. **Promotion de Version** : Bumping final vers `2.1.0` (suppression du suffixe `rc1`).
2. **Changelog & Release Notes Exhaustifs** : Rédaction de `docs/RELEASE_NOTES_2_1_0.md` détaillant toutes les nouveautés, migrations transparentes et benchmarks.
3. **Tag Git & Signature** : Création du tag annoté `v2.1.0` sur le commit de release qualifié.
4. **Déclenchement du Pipeline PyPI** : Publication automatique via OIDC Trusted Publishing, attachement du SBOM CycloneDX et des signatures Sigstore.
5. **Vérification Post-Déploiement (*Smoke Tests*)** : Installation depuis PyPI dans un environnement virtuel vierge et vérification de `pwk doctor`.

---

## 2. Fichiers à Modifier et Créer

```text
src/pyworkflowkit/
└── __init__.py                      # Bumping de version (__version__ = "2.1.0")

docs/
├── RELEASE_NOTES_2_1_0.md           # Notes de version exhaustives
└── examples/
    └── customer_360_v2.py           # Pipeline de démonstration et de validation de référence 2.1

CHANGELOG.md                         # Section [2.1.0] formalisée avec liens PR/commits

tests/
├── e2e/
│   └── test_customer_360_v2_e2e.py  # Scénario complet d'orchestration E2E 2.1
└── release/
    └── test_smoke_installed_wheel.py# Script de test de fumée sur la distribution construite
```

---

## 3. Détail des Spécifications Techniques

### 3.1 Pipeline de Référence `customer_360_v2.py`
Ce script servira d'étalon fonctionnel et d'exemple officiel dans la documentation :
```python
from pyworkflowkit.authoring import workflow, task
from pyworkflowkit.runtime import WorkflowRuntime
from pyworkflowkit.persistence import SQLiteMetadataStore

@task(id="ingest_customers")
def ingest_customers():
    return {"customers_count": 1000}

@task(id="ingest_orders")
def ingest_orders():
    return {"orders_count": 5000}

@task(id="reconcile_360")
def reconcile_360(ingest_customers, ingest_orders):
    return {"reconciled": True}

# Utilisation de la nouvelle syntaxe fluide d'authoring (LOT-32)
wf = workflow("customer_360_v2")(
    ingest_customers,
    ingest_orders,
    reconcile_360,
)
[ingest_customers, ingest_orders] >> reconcile_360

if __name__ == "__main__":
    store = SQLiteMetadataStore("customer_360.db")
    runtime = WorkflowRuntime(store=store)
    result = runtime.run(wf)
    print("Exécution terminée :", result.status)
```

### 3.2 Protocole de Qualification LOT-37 (RC Gate)
Le pipeline de qualification doit obligatoirement valider les étapes ordonnées :
```bash
# 1. Rigueur statique
uv run ruff check .
uv run mypy src tests

# 2. Invariance 2.0
uv run pytest tests/architecture/test_stable_release_v2.py
uv run pytest tests/architecture/test_cli_boundaries.py

# 3. Contrat CLI
uv run pytest tests/contract/cli/test_cli_public_contract_freeze.py

# 4. Tests unitaires et intégration (avec couverture)
uv run pytest --cov=src/pyworkflowkit --cov-report=term-missing tests/

# 5. Pipeline E2E
uv run python docs/examples/customer_360_v2.py

# 6. Test d'étanchéité de build
uv build
uv run --with twine twine check dist/*
```

### 3.3 Protocole de Promotion LOT-38 (Release Stable)
1. **Mise à jour documentaire & version** :
   - Fixer `__version__ = "2.1.0"` dans `src/pyworkflowkit/__init__.py`.
   - Mettre à jour `CHANGELOG.md` avec la date du jour.
   - Finaliser `docs/RELEASE_NOTES_2_1_0.md`.
2. **Commit de Release** :
   ```bash
   git commit -m "chore(release): prepare pyworkflowkit 2.1.0"
   ```
3. **Création du Tag Git** :
   ```bash
   git tag -a v2.1.0 -m "Release PyWorkflowKit 2.1.0"
   git push origin main --tags
   ```
4. **Création de la GitHub Release** :
   - Création de la release pointant vers le tag `v2.1.0`.
   - Déclenchement automatique du workflow `.github/workflows/publish-pypi.yml`.
5. **Smoke Test Post-Publication** :
   ```bash
   uv venv --python 3.12 /tmp/smoke-pwk
   source /tmp/smoke-pwk/bin/activate
   pip install pyworkflowkit==2.1.0
   pwk --version
   pwk doctor
   ```

---

## 4. Matrice de Qualification Multi-Environnements

| Système d'Exploitation | Python 3.11 | Python 3.12 | Python 3.13 | Python 3.14 |
| :--- | :---: | :---: | :---: | :---: |
| **Ubuntu 22.04 LTS** | ✅ Requis | ✅ Requis | ✅ Requis | ✅ Requis |
| **macOS 14 (Sonoma)** | ✅ Requis | ✅ Requis | ✅ Requis | ✅ Requis |
| **Windows Server 2022**| ✅ Requis | ✅ Requis | ✅ Requis | ✅ Requis |

---

## 5. Checklist de Validation Finale et Clôture de la Version 2.1.0

- [ ] L'ensemble des tests unitaires, d'intégration et d'architecture sont 100% verts sur tous les OS.
- [ ] Le contrat `contracts/cli_contract_v1.json` correspond exactement au comportement de la CLI publiée.
- [ ] Le pipeline `Customer 360 v2` a été validé sous incident simulé et reprise sélective (`resume_run`).
- [ ] Le build `sdist` et `wheel` est vérifié conforme et ne contient aucun résidu parasite.
- [ ] Le SBOM CycloneDX et les attestations Sigstore sont générés et joints à la release GitHub.
- [ ] Le paquet est disponible sur PyPI et installable via `pip install pyworkflowkit`.
- [ ] Le smoke test d'installation post-release confirme le bon fonctionnement de la commande `pwk`.
