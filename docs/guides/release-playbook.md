# Guide Opérateur : Release Playbook PyWorkflowKit

Ce document formalise la procédure standard de publication d'une version de **PyWorkflowKit** sur PyPI et GitHub Releases, conformément aux exigences de sécurité de la chaîne d'approvisionnement logicielle (OIDC Trusted Publishing, SBOM CycloneDX, attestations Sigstore).

---

## 1. Prérequis & Sécurité

- **Zéro Token Statique** : Aucune clé d'API PyPI longue durée n'est utilisée. L'authentification repose exclusivement sur **PyPI Trusted Publishing (OIDC)** lié au dépôt GitHub `tawounfouet/pyworkflowkit`.
- **Intégrité Cryptographique** : Les distributions (`sdist` et `wheel`) sont systématiquement accompagnées de :
  - Un fichier d'inventaire **CycloneDX SBOM** (`dist/pyworkflowkit-cyclonedx.json`).
  - Les empreintes cryptographiques SHA-256 (`dist/SHA256SUMS`).
  - Une attestation de provenance de build **Sigstore** générée par GitHub (`actions/attest-build-provenance`).
- **Qualification Stricte** : La branche `main` doit avoir 100% de ses checks CI validés (matrice de versions Python, tests unitaires et intégration, typage strict, linting, sécurité).

---

## 2. Déroulement d'une Publication

### Étape 1 : Validation locale de build et du SBOM
Avant de poser le tag de release, valider la reproductibilité du build en local :

```bash
# Nettoyage et compilation des artefacts
rm -rf dist/
uv build

# Validation de l'intégrité des métadonnées
uv run twine check dist/*

# Génération du SBOM CycloneDX
uv run --with cyclonedx-bom cyclonedx-py environment -o dist/pyworkflowkit-cyclonedx.json

# Calcul des hashs SHA256
cd dist && sha256sum * > SHA256SUMS && cd ..
```

Vérifier la présence :
- Du fichier `LICENSE` (Apache-2.0).
- Du fichier `README.md`.
- Des métadonnées conformes dans `dist/*.whl` et `dist/*.tar.gz`.

---

### Étape 2 : Création du Tag Git
Une fois le commit qualifié et mergé sur la branche `main` :

```bash
VERSION="2.1.0" # Remplacer par la version ciblée
TAG="v${VERSION}"

git checkout main
git pull origin main

# Création du tag annoté
git tag -a "${TAG}" -m "Release ${TAG}"

# Push du tag sur le dépôt distant
git push origin "${TAG}"
```

---

### Étape 3 : Création de la GitHub Release
La publication PyPI est orchestrée automatiquement par le workflow `.github/workflows/publish-pypi.yml` lors de la publication d'une release GitHub.

1. Se rendre sur `https://github.com/tawounfouet/pyworkflowkit/releases/new`.
2. Sélectionner le tag existant `vX.Y.Z`.
3. Titre de la release : `PyWorkflowKit X.Y.Z`.
4. Renseigner les notes de version issues de `CHANGELOG.md`.
5. Cliquer sur **Publish release**.

---

### Étape 4 : Déroulement Automatique du Workflow (`publish-pypi.yml`)
Le déclenchement `release: types: [published]` exécute les actions suivantes :
1. `uv build` : Construction du wheel et du sdist.
2. `cyclonedx-py` : Génération du SBOM machine-readable.
3. `sha256sum` : Calcul des empreintes SHA-256 de chaque artefact.
4. `actions/attest-build-provenance` : Signature et enregistrement de l'attestation Sigstore auprès de GitHub.
5. `softprops/action-gh-release` : Téléversement automatique des distributions, du SBOM et des checksums sur la GitHub Release.
6. `pypa/gh-action-pypi-publish` : Publication sécurisée sur PyPI via OIDC token exchange.

---

### Étape 5 : Vérification Post-Publication (Smoke Test)
Tester l'installation depuis le miroir public PyPI dans un environnement isolé :

```bash
# Environnement virtuel jetable
python3 -m venv /tmp/pwk-test-env
source /tmp/pwk-test-env/bin/activate

# Installation depuis PyPI
pip install --no-cache-dir pyworkflowkit==${VERSION}

# Vérification du CLI
pwk version
pwk doctor

# Nettoyage
deactivate
rm -rf /tmp/pwk-test-env
```
