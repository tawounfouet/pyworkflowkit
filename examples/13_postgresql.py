"""Canonical PostgreSQL configuration example without requiring a live server."""

from __future__ import annotations

import json

from pyworkflowkit import RuntimeSettings


settings = RuntimeSettings.load(
    overrides={
        "metadata": {
            "backend": "postgres",
            "postgres_dsn": "postgresql+psycopg://example:secret@localhost/pyworkflowkit",
            "postgres_application_name": "pyworkflowkit-example",
        }
    }
)

redacted = settings.redacted_dict()

print(
    json.dumps(
        {
            "backend": settings.metadata.backend,
            "dsn": redacted["metadata"]["postgres_dsn"],
            "opens_connection": False,
            "optional_extra": "pyworkflowkit[postgres]",
        },
        sort_keys=True,
    )
)
