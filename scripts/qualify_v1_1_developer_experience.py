"""Qualify the PyWorkflowKit 1.1 cross-surface Developer Experience contract."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from pyworkflowkit.contracts.developer_experience import (
    DX_V2_ADVANCED_USE_JOURNEY,
    DX_V2_CLI_COMMANDS,
    DX_V2_CONTRACT_VERSION,
    DX_V2_FIRST_USE_JOURNEY,
    DX_V2_TARGET_RELEASE,
    developer_experience_contract_snapshot_v2,
)

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        timeout=60,
    )


def _json_stdout(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise TypeError("expected a JSON object")
    return value


def _execute_notebook(relative_path: str) -> int:
    path = ROOT / relative_path
    notebook = json.loads(path.read_text(encoding="utf-8"))
    cells = notebook["cells"]
    if not isinstance(cells, list):
        raise TypeError(f"{relative_path}: cells must be a list")

    namespace: dict[str, object] = {
        "__name__": "__main__",
        "__file__": str(path),
    }
    executed = 0
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict) or cell.get("cell_type") != "code":
            continue
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(str(part) for part in source)
        if not isinstance(source, str):
            raise TypeError(f"{relative_path}: invalid code cell source")
        compiled = compile(source, f"{relative_path}#cell-{index}", "exec")
        exec(compiled, namespace)
        executed += 1
    return executed


def _qualify_cli() -> dict[str, object]:
    aliases = ("pwk", "pyworkflowkit", "pyworkflow")
    versions = {alias: _run(alias, "version").stdout.strip() for alias in aliases}
    canonical_version = versions["pwk"]
    assert canonical_version
    assert set(versions.values()) == {canonical_version}

    target = "examples.getting_started_workflow:demo"
    json_results = [_run(alias, "plan", target, "--json") for alias in aliases]
    assert all(result.stdout == json_results[0].stdout for result in json_results)
    planned = _json_stdout(json_results[0])
    assert planned["groups"]

    validated = _json_stdout(_run("pwk", "validate", target, "--json"))
    assert validated["valid"] is True

    human_plan = _run("pwk", "plan", target)
    assert "Execution Plan" in human_plan.stdout

    doctor = _run("pwk", "doctor")
    assert "Healthy" in doctor.stdout

    return {
        "canonical_cli": "pwk",
        "aliases": list(aliases),
        "alias_parity": True,
        "commands": list(DX_V2_CLI_COMMANDS),
        "json_contract": True,
        "rich_human_mode": True,
        "version": canonical_version,
    }


def _qualify_first_use() -> dict[str, object]:
    hello = _json_stdout(_run(sys.executable, "examples/00_hello_world.py"))
    assert hello["status"] == "SUCCEEDED"

    runtime = _json_stdout(_run(sys.executable, "examples/06_runtime.py"))
    assert runtime["status"] == "SUCCEEDED"

    notebook_cells = _execute_notebook("notebooks/01 - Hello Workflow.ipynb")
    assert notebook_cells > 0

    return {
        "journey": list(DX_V2_FIRST_USE_JOURNEY),
        "hello_world": "SUCCEEDED",
        "runtime": "SUCCEEDED",
        "notebook_cells": notebook_cells,
    }


def _qualify_advanced_use() -> dict[str, object]:
    plugin = _json_stdout(_run(sys.executable, "examples/19_plugin.py"))
    assert plugin["type"] == "workload"

    external = _json_stdout(_run(sys.executable, "examples/18_external_workload.py"))
    assert external["status"] == "SUCCEEDED"
    assert external["external_reference_count"] == 1

    pyingestkit = _json_stdout(
        _run(sys.executable, "examples/integrations/pyingestkit/atomic_job.py")
    )
    assert pyingestkit["status"] == "SUCCEEDED"
    assert pyingestkit["external_reference_count"] == 1

    control_plane = _json_stdout(_run(sys.executable, "examples/21_control_plane.py"))
    assert control_plane["valid"] is True
    assert control_plane["run_status"] == "SUCCEEDED"

    complete = _json_stdout(_run(sys.executable, "examples/complete/data_pipeline.py"))
    assert complete["run_status"] == "SUCCEEDED"
    assert complete["manifest_status"] == "SUCCEEDED"

    notebook_cells = _execute_notebook("notebooks/99 - Complete Workflow Lab.ipynb")
    assert notebook_cells > 0

    return {
        "journey": list(DX_V2_ADVANCED_USE_JOURNEY),
        "plugin": plugin["type"],
        "external_workload": external["status"],
        "pyingestkit": pyingestkit["status"],
        "control_plane": control_plane["run_status"],
        "complete_workflow": complete["run_status"],
        "notebook_cells": notebook_cells,
    }


def _qualify_contract() -> dict[str, object]:
    snapshot = developer_experience_contract_snapshot_v2()
    assert snapshot["contract_version"] == DX_V2_CONTRACT_VERSION == "2"
    assert snapshot["target_release"] == DX_V2_TARGET_RELEASE == "1.1.0"

    for collection in ("guides", "examples", "notebooks"):
        values = snapshot[collection]
        if not isinstance(values, list):
            raise TypeError(f"{collection} must be a list")
        for relative_path in values:
            if not isinstance(relative_path, str):
                raise TypeError(f"{collection} contains a non-string path")
            assert (ROOT / relative_path).is_file(), relative_path

    json.dumps(snapshot, allow_nan=False, sort_keys=True)
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable results.")
    args = parser.parse_args()

    payload = {
        "contract": _qualify_contract(),
        "cli": _qualify_cli(),
        "first_use": _qualify_first_use(),
        "advanced_use": _qualify_advanced_use(),
    }

    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print("PyWorkflowKit 1.1 transverse developer-experience qualification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
