"""Execute the RQ-04 first-use journey against the active installation."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )


def _json_stdout(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise TypeError("expected a JSON object")
    return value


def _qualify_examples() -> dict[str, object]:
    results: dict[str, object] = {}

    hello = _json_stdout(_run(sys.executable, "examples/00_hello_world.py"))
    assert hello["status"] == "SUCCEEDED"
    assert hello["manifest_status"] == "SUCCEEDED"
    results["hello_world"] = hello

    retry = _json_stdout(_run(sys.executable, "examples/01_failure_and_retry.py"))
    assert retry == {
        "attempts": 2,
        "retry_event_observed": True,
        "status": "SUCCEEDED",
    }
    results["failure_and_retry"] = retry

    persistence = _json_stdout(_run(sys.executable, "examples/02_sqlite_persistence.py"))
    assert persistence["status"] == "SUCCEEDED"
    assert persistence["manifest_status"] == "SUCCEEDED"
    assert persistence["database_exists"] is True
    results["sqlite_persistence"] = persistence

    plugin = _json_stdout(_run(sys.executable, "examples/03_ecosystem_plugin.py"))
    assert plugin == {
        "instance": "ExampleWorkload",
        "name": "example-workload",
        "type": "workload",
    }
    results["ecosystem_plugin"] = plugin

    return results


def _qualify_cli() -> dict[str, object]:
    target = "examples.getting_started_workflow:demo"

    version = _run("pyworkflow", "version").stdout.strip()
    alias_version = _run("pyworkflowkit", "version").stdout.strip()
    assert version
    assert alias_version == version

    validated = _json_stdout(_run("pyworkflow", "validate", target, "--json"))
    assert validated["valid"] is True

    planned = _json_stdout(_run("pyworkflow", "plan", target, "--json"))
    assert planned["groups"] == [
        {"index": 0, "tasks": ["fetch"]},
        {"index": 1, "tasks": ["publish"]},
    ]

    with TemporaryDirectory() as directory:
        root = Path(directory)
        workspace = root / "workspace"
        config = root / "pyworkflowkit.toml"
        config.write_text(
            (
                f'[runtime]\nworkspace = "{workspace.as_posix()}"\n'
                '[metadata]\nbackend = "sqlite"\n'
                'sqlite_path = "runtime.sqlite3"\n'
                "sqlite_wal = false\n"
            ),
            encoding="utf-8",
        )

        executed = _json_stdout(
            _run(
                "pyworkflow",
                "run",
                target,
                "--config",
                str(config),
                "--json",
            )
        )
        assert executed["status"] == "SUCCEEDED"
        run_id = str(executed["run_id"])

        inspected = _json_stdout(
            _run("pyworkflow", "inspect", run_id, "--config", str(config), "--json")
        )
        assert inspected["status"] == "SUCCEEDED"

        events = _json_stdout(
            _run("pyworkflow", "events", run_id, "--config", str(config), "--json")
        )
        assert events["events"]

        manifest = _json_stdout(
            _run(
                "pyworkflow",
                "manifest",
                target,
                run_id,
                "--config",
                str(config),
                "--json",
            )
        )
        assert manifest["status"] == "SUCCEEDED"

    return {
        "version": version,
        "validated": True,
        "planned_groups": planned["groups"],
        "status": "SUCCEEDED",
        "events_observed": True,
        "manifest_status": "SUCCEEDED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable results.")
    args = parser.parse_args()

    payload = {
        "examples": _qualify_examples(),
        "cli": _qualify_cli(),
    }

    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print("RQ-04 developer experience qualification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
