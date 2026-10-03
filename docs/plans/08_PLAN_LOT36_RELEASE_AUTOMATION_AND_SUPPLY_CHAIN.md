# Plan d'Implémentation : LOT-36 — Automatisation Release, PyPI Trusted Publishing, SBOM & Supply Chain

- **Statut** : Plan d'implémentation opérationnel
- **Milestone** : LOT-36
- **Phase** : Phase 3 (Gouvernance du Store, Observabilité & Supply Chain)
- **Dépendance amont** : LOT-31, LOT-34, LOT-35
- **Document cadre** : LOT-26 (`v2-lot26-requirements-analysis.md`, exigences `FR-SUP-01` à `FR-SUP-03`)
- **Branche de travail cible** : `feat/v2-lot36-release-automation-and-supply-chain`

---

## 1. Objectifs & Périmètre du Lot

Le but de **LOT-36** est d'élever l'infrastructure de publication et la chaîne d'approvisionnement logicielle (*Software Supply Chain*) de PyWorkflowKit au standard d'excellence établi sur `pytransformkit` :
1. **PyPI Trusted Publishing (OIDC)** : Élimination totale des tokens d'API longue durée au profit de l'authentification OpenID Connect native entre GitHub Actions et PyPI.
2. **Génération Systématique de SBOM CycloneDX** : Production d'un inventaire machine-readable (`cyclonedx.json`) pour chaque distribution wheel et sdist.
3. **Attestations Cryptographiques Sigstore** : Signature et publication des attestations de provenance de build GitHub (`actions/attest-build-provenance`).
4. **Formalisation Juridique de la Licence** : Déclaration explicite et standardisée SPDX (MIT ou Apache-2.0 selon politique d'entreprise) dans `pyproject.toml` et présence du fichier `LICENSE`.
5. **Workflow de Publication Déclenché par GitHub Release** : Automatisation sans intervention manuelle déclenchée sur événement `release: types: [published]`.

---

## 2. Fichiers à Modifier et Créer

```text
.github/
└── workflows/
    ├── publish-pypi.yml             # Workflow de publication officiel OIDC + SBOM + Attestations
    └── release-qualification.yml    # Pipeline de vérification de pré-publication (Dry-run build)

pyproject.toml                       # Mise à niveau des métadonnées (License-Expression, URLs projet)
LICENSE                              # Fichier canonique de licence textuelle complète

docs/
└── guides/
    └── release-playbook.md          # Guide opérateur de publication d'une version
```

---

## 3. Détail des Spécifications Techniques

### 3.1 Formalisation des Métadonnées dans `pyproject.toml`
Mise à jour conforme aux standards PEP 621 et PEP 639 :
```toml
[project]
name = "pyworkflowkit"
dynamic = ["version"]
description = "Deterministic, auditable and resilient workflow orchestration toolkit for Python data engineering."
readme = "README.md"
requires-python = ">=3.11"
license = { text = "Apache-2.0" }
# Ou standard PEP 639 si supporté par hatchling :
# license = "Apache-2.0"
authors = [
    { name = "Webtech Engineering", email = "engineering@webtech.fr" }
]
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: Developers",
    "Intended Audience :: Information Technology",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Topic :: Software Development :: Libraries :: Application Frameworks",
    "Typing :: Typed",
]

[project.urls]
Homepage = "https://github.com/tawounfouet/pyworkflowkit"
Documentation = "https://github.com/tawounfouet/pyworkflowkit/tree/main/docs"
Repository = "https://github.com/tawounfouet/pyworkflowkit.git"
Changelog = "https://github.com/tawounfouet/pyworkflowkit/blob/main/CHANGELOG.md"
Issues = "https://github.com/tawounfouet/pyworkflowkit/issues"
```

### 3.2 Spécification du Workflow `.github/workflows/publish-pypi.yml`
```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

permissions:
  contents: read

jobs:
  build-and-publish:
    name: Build distributions and publish to PyPI
    runs-on: ubuntu-latest
    permissions:
      id-token: write     # OIDC requis pour PyPI Trusted Publishing
      contents: write     # Requis pour attacher le SBOM et les hashs à la Release GitHub
      attestations: write # Requis pour Sigstore build provenance

    environment:
      name: pypi
      url: https://pypi.org/p/pyworkflowkit

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Build sdist and wheel
        run: uv build

      - name: Generate CycloneDX SBOM
        run: |
          uv run --with cyclonedx-bom cyclonedx-py environment --outfile dist/pyworkflowkit-cyclonedx.json

      - name: Generate SHA256 Checksums
        run: |
          cd dist
          sha256sum * > SHA256SUMS
          cd ..

      - name: Generate Artifact Attestations (Sigstore)
        uses: actions/attest-build-provenance@v1
        with:
          subject-path: "dist/*"

      - name: Attach artifacts to GitHub Release
        uses: softprops/action-gh-release@v2
        if: startsWith(github.ref, 'refs/tags/')
        with:
          files: |
            dist/*

      - name: Publish package distributions to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: dist/
```

---

## 4. Plan de Test et Critères d'Acceptation

### 4.1 Test en Mode Simulation Local
- Exécuter la commande `uv build` localement.
- Valider l'intégrité de la distribution avec `twine check dist/*` ou `uv publish --dry-run`.
- Inspecter l'archive `.tar.gz` (sdist) pour vérifier la présence du fichier `LICENSE`, du `README.md` et l'absence absolue de fichiers de test ou de fichiers `.pyc`.
- Inspecter la roue `.whl` pour vérifier que le contrat machine `src/pyworkflowkit/contracts/cli_contract_v1.json` est bien embarqué dans le package installé.

### 4.2 Validation du SBOM CycloneDX
- Lancer la génération SBOM et valider la conformité du schéma JSON avec le standard CycloneDX 1.5/1.6 :
  ```bash
  uv run --with cyclonedx-bom cyclonedx-py environment --outfile test-sbom.json
  ```
- Vérifier que toutes les dépendances directes et transitives sont inventoriées avec leurs licences respectives.

### 4.3 Validation de la Configuration PyPI
- Configurer l'environnement GitHub `pypi` avec le Trusted Publisher pointant vers le dépôt `tawounfouet/pyworkflowkit` et le workflow `publish-pypi.yml`.

---

## 5. Checklist de Validation et Clôture

- [ ] Le fichier `LICENSE` existe à la racine du dépôt.
- [ ] Les métadonnées `pyproject.toml` sont conformes aux standards PEP 621 et PEP 639.
- [ ] Le workflow `.github/workflows/publish-pypi.yml` utilise `id-token: write` sans token statique.
- [ ] La génération de SBOM CycloneDX et les sommes SHA256 sont intégrées au build.
- [ ] Les attestations de provenance Sigstore sont configurées.
- [ ] Le contrat `cli_contract_v1.json` est confirmé inclus dans le wheel.
