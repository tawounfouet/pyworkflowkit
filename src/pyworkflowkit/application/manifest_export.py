"""Portable RunManifest export helpers."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from pyworkflowkit.application.manifest import RunManifestSerializer
from pyworkflowkit.domain.manifest import RunManifest


class RunManifestExporter:
    """Export canonical manifest JSON using an atomic local-file replacement."""

    def __init__(self, serializer: RunManifestSerializer | None = None) -> None:
        self._serializer = serializer or RunManifestSerializer()

    def export_json(
        self,
        manifest: RunManifest,
        path: str | Path,
    ) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(
                self._serializer.to_json(manifest) + "\n",
                encoding="utf-8",
            )
            temporary.replace(destination)
        finally:
            if temporary.exists():
                temporary.unlink()

        return destination


__all__ = ["RunManifestExporter"]
