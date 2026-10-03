# Plan d'Implémentation : LOT-29 — Socle CLI, Bootstrap, Sécurité & Diagnostic

- **Statut** : Plan d'implémentation opérationnel
- **Milestone** : LOT-29
- **Phase** : Phase 1 (Nouvelle CLI Modulaire Hexagonale)
- **Dépendance amont** : `main` (`2d335f8db463a2267306e41ecf0ec7e3d4eb2fd9`)
- **Branche de travail cible** : `feat/v2-lot29-cli-foundations`

---

## 1. Objectifs & Périmètre du Lot

Le but de **LOT-29** est d'établir les fondations architecturales du nouveau sous-package `src/pyworkflowkit/cli/`, en transposant directement l'ingénierie validée de `pytransformkit` :
1. Mise en place de l'application racine Typer (`app.py`) avec intercepteur global d'erreurs.
2. Formalisation des codes de sortie (`exit_codes.py`) et des exceptions typées (`exceptions.py`).
3. Création du porteur de contexte unifié (`context.py` : `CliContext`).
4. Implémentation du filtre de sécurité filesystem (`security.py` : protection path traversal et symlinks).
5. Mécanisme de détection dynamique des extras optionnels (`bootstrap.py`).
6. Première paire de commandes et services opérationnels : `pwk version` et `pwk doctor`.
7. Tests d'étanchéité architecturale initiaux (`tests/architecture/test_cli_boundaries.py`).

---

## 2. Fichiers à Créer et Responsabilités

```text
src/pyworkflowkit/cli/
├── __init__.py                 # Export de app, ExitCode, CliContext
├── __main__.py                 # Point d'entrée exécutable (python -m pyworkflowkit.cli)
├── app.py                      # Typer app racine, invoke_without_command, exception handler
├── bootstrap.py                # Probing dynamique des dépendances optionnelles (psycopg, otel)
├── context.py                  # Classe CliContext (format human/json, verbosité, consoles)
├── exit_codes.py               # Enum ExitCode (SUCCESS=0, USER_ERROR=1, SECURITY_ERROR=4, etc.)
├── exceptions.py               # Hiérarchie CliError, CliSecurityError, CliUsageError
├── security.py                 # PathSecurityValidator (contrôle de traversal, symlinks, quotas)
│
├── commands/
│   ├── __init__.py
│   ├── version.py              # Contrôleur Typer mince pour `pwk version`
│   └── doctor.py               # Contrôleur Typer mince pour `pwk doctor`
│
├── services/
│   ├── __init__.py
│   ├── version_service.py      # Logique pure d'inspection de version (testable en mémoire)
│   └── doctor_service.py       # Logique pure de diagnostic d'environnement
│
├── models/
│   ├── __init__.py
│   ├── reports.py              # VersionReport, DoctorReport (Pydantic)
│   └── errors.py               # CliErrorReport unifié (Pydantic)
│
└── rendering/
    ├── __init__.py
    ├── console.py              # Isolation des instances Console Rich (stdout vs stderr)
    ├── human.py                # Rendu Rich human-friendly pour doctor/version
    └── json.py                 # Rendu JSON normalisé machine
```

---

## 3. Détail des Spécifications Techniques

### 3.1 `exit_codes.py`
```python
from enum import IntEnum


class ExitCode(IntEnum):
    SUCCESS = 0
    USER_ERROR = 1
    VALIDATION_ERROR = 2
    EXECUTION_FAILURE = 3
    SECURITY_ERROR = 4
    STORE_ERROR = 5
    INTERNAL_ERROR = 10
```

### 3.2 `security.py` — `PathSecurityValidator`
* Doit interdire les segments `..` menant hors du workspace courant.
* Doit vérifier avec `Path.resolve()` que la cible ne pointe pas vers des répertoires système sensibles (`/etc`, `/sys`, etc.).
* Doit rejeter les fichiers dont la taille excède 10 Mo (`MaxFileSizeExceededError`).

### 3.3 `context.py` — `CliContext`
* Porteur des options globales : `format: Literal["human", "json"]`, `verbose: bool`, `quiet: bool`.
* Encapsule deux consoles Rich indépendantes :
  - `console` dirigée vers `sys.stdout` (uniquement pour les données).
  - `err_console` dirigée vers `sys.stderr` (pour les avertissements, erreurs, logs).

---

## 4. Stratégie de Test & Fichiers de Tests

| Fichier de Test | Nature | Rôle |
| :--- | :--- | :--- |
| `tests/unit/cli/test_cli_bootstrap.py` | Unitaire | Vérifie la détection correcte des extras `postgres` et `otel`. |
| `tests/unit/cli/test_cli_context.py` | Unitaire | Valide le comportement de `CliContext` et l'isolation des flux. |
| `tests/unit/cli/test_cli_exit_codes.py` | Unitaire | Vérifie l'immutabilité et les valeurs entières des `ExitCode`. |
| `tests/unit/cli/test_cli_security.py` | Unitaire | Éprouve le rejet des traversées de répertoires et des symlinks illicites. |
| `tests/unit/cli/test_cli_version_service.py`| Unitaire | Teste `VersionService` en mémoire pure sans Typer. |
| `tests/unit/cli/test_cli_doctor_service.py` | Unitaire | Teste `DoctorService` avec simulation de dépendances manquantes. |
| `tests/architecture/test_cli_boundaries.py` | Architecture | **Critique** : Vérifie qu'aucun module du core n'importe `pyworkflowkit.cli`, et que la CLI n'importe aucun module V1 legacy (`application.*`). |

---

## 5. Critères d'Acceptation (Definition of Done)

- [ ] Le sous-package `src/pyworkflowkit/cli/` est créé et respecte l'arborescence hexagonale.
- [ ] `pwk version` et `pwk version --json` s'exécutent avec succès.
- [ ] `pwk doctor` et `pwk doctor --json` diagnostiquent l'environnement proprement.
- [ ] La validation de sécurité `security.py` bloque 100% des cas de traversée de répertoires.
- [ ] Tous les nouveaux tests passent au vert (`pytest tests/unit/cli/`).
- [ ] Le test d'architecture `test_cli_boundaries.py` confirme l'absence de régression ou de fuite d'imports.
- [ ] `ruff check .` et `mypy --strict` sont à 0 défaut.
- [ ] Couverture $\ge 90\%$ sur le nouveau sous-package.
