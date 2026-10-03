"""Diagnostic service for PyWorkflowKit environment, stores, and plugins."""

from __future__ import annotations

import importlib.util
import platform
import sqlite3
import sys
from typing import Any

from pyworkflowkit import __version__
from pyworkflowkit.plugins import PLUGIN_API_VERSION, PluginCatalog, PluginDiscovery, PluginType


class DoctorService:
    """Evaluates environment readiness, stores, telemetry, and plugins."""

    def __init__(
        self,
        discovery: PluginDiscovery | None = None,
        catalog: PluginCatalog | None = None,
    ) -> None:
        self.discovery = discovery or PluginDiscovery()
        self.catalog = catalog or PluginCatalog()

    def diagnose_environment(self) -> dict[str, Any]:
        """Diagnose system, python version, and available persistence backends."""
        has_psycopg = importlib.util.find_spec("psycopg") is not None
        has_otel = importlib.util.find_spec("opentelemetry") is not None

        return {
            "pyworkflowkit_version": __version__,
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "stores": {
                "memory": {"available": True, "status": "operational"},
                "sqlite": {
                    "available": True,
                    "version": sqlite3.sqlite_version,
                    "status": "operational",
                },
                "postgresql": {
                    "available": has_psycopg,
                    "status": "operational" if has_psycopg else "missing_dependency (psycopg)",
                },
            },
            "observability": {
                "opentelemetry": {
                    "available": has_otel,
                    "status": "installed"
                    if has_otel
                    else "optional_extra_missing (pyworkflowkit[otel])",
                }
            },
        }

    def diagnose_plugins(
        self,
        enabled_selectors: dict[PluginType, tuple[str, ...]] | None = None,
    ) -> tuple[bool, list[dict[str, Any]]]:
        """Check discovered or explicitly enabled plugins."""
        if enabled_selectors:
            report = self.discovery.enable_selected(catalog=self.catalog, enabled=enabled_selectors)
            results = [
                {
                    "name": result.plugin.name,
                    "type": result.plugin.plugin_type.value,
                    "status": result.status.value,
                    "error": result.error,
                }
                for result in report.results
            ]
            healthy = not report.has_errors
        else:
            candidates = self.discovery.discover()
            results = [
                {
                    "name": plugin.name,
                    "type": plugin.plugin_type.value,
                    "status": "discovered",
                    "error": None,
                }
                for plugin in candidates
            ]
            healthy = True

        return healthy, results

    def run_full_diagnosis(
        self,
        enabled_selectors: dict[PluginType, tuple[str, ...]] | None = None,
    ) -> dict[str, Any]:
        """Run complete environment and plugin diagnosis."""
        env = self.diagnose_environment()
        healthy, plugins = self.diagnose_plugins(enabled_selectors)

        return {
            "healthy": healthy,
            "environment": env,
            "plugin_api_version": PLUGIN_API_VERSION,
            "plugins": plugins,
        }


__all__ = ["DoctorService"]
