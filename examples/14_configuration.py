"""Canonical RuntimeSettings precedence and redaction example."""

from __future__ import annotations

import json
from pathlib import Path

from pyworkflowkit import RuntimeSettings

settings = RuntimeSettings.load(
    overrides={
        "runtime": {"workspace": Path(".pyworkflow-example")},
        "metadata": {
            "backend": "sqlite",
            "sqlite_path": "example.sqlite3",
            "sqlite_wal": False,
        },
    }
)

print(
    json.dumps(
        {
            "backend": settings.metadata.backend,
            "sqlite_path": str(settings.metadata.sqlite_path),
            "workspace": str(settings.runtime.workspace),
        },
        sort_keys=True,
    )
)
