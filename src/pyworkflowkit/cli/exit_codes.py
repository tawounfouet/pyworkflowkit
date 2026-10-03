"""Stable process exit codes for the PyWorkflowKit CLI."""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """Process exit codes defined by the CLI v1 candidate contract."""

    SUCCESS = 0
    USER_ERROR = 1  # Erreur de syntaxe de commande, flag invalide
    VALIDATION_ERROR = 2  # Échec de validation statique du workflow (cycle, orphelin)
    EXECUTION_FAILURE = 3  # Échec d'exécution du workflow (tâche en FAILED)
    SECURITY_ERROR = 4  # Violation de sécurité filesystem ou accès interdit
    DOCTOR_FAILURE = 4  # Compatibilité legacy doctor exit code
    STORE_ERROR = 5  # Erreur d'accès ou de transaction sur le MetadataStore
    INTERNAL_ERROR = 10  # Exception non interceptée (bug runtime)
    INTERRUPTED = 130  # Interruption utilisateur SIGINT (Ctrl+C)
    BROKEN_PIPE = 141  # SIGPIPE


__all__ = ["ExitCode"]
