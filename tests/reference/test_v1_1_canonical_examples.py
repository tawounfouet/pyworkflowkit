"""DX04 acceptance for the canonical executable example suite."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = REPOSITORY_ROOT / "examples"

CANONICAL_EXAMPLES = (
    "00_hello_world.py",
    "01_tasks_and_handlers.py",
    "02_workflow_definitions.py",
    "03_dependencies.py",
    "04_dag.py",
    "05_execution_plan.py",
    "06_runtime.py",
    "07_run_context.py",
    "08_failure.py",
    "09_retry.py",
    "10_events.py",
    "11_manifest.py",
    "12_sqlite.py",
    "13_postgresql.py",
    "14_configuration.py",
    "15_concurrency.py",
    "16_timeout.py",
    "17_cancellation.py",
    "18_external_workload.py",
    "19_plugin.py",
    "20_custom_executor.py",
    "21_control_plane.py",
)

EXTENDED_EXAMPLES = (
    "integrations/pyingestkit/atomic_job.py",
    "complete/data_pipeline.py",
)

FORBIDDEN_CORE_IMPORTS = (
    "from pyworkflowkit.application",
    "from pyworkflowkit.adapters",
    "from pyworkflowkit.domain",
    "from pyworkflowkit.ports",
    "import pyworkflowkit.application",
    "import pyworkflowkit.adapters",
    "import pyworkflowkit.domain",
    "import pyworkflowkit.ports",
)


def test_dx04_canonical_example_topology_is_complete() -> None:
    assert (EXAMPLES / "README.md").is_file()
    for relative_path in (*CANONICAL_EXAMPLES, *EXTENDED_EXAMPLES):
        assert (EXAMPLES / relative_path).is_file(), relative_path


def test_dx04_canonical_examples_do_not_import_internal_runtime_modules() -> None:
    for relative_path in CANONICAL_EXAMPLES:
        content = (EXAMPLES / relative_path).read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_CORE_IMPORTS:
            assert forbidden not in content, f"{relative_path}: {forbidden}"


def test_dx04_canonical_examples_execute_as_clean_processes() -> None:
    for relative_path in (*CANONICAL_EXAMPLES, *EXTENDED_EXAMPLES):
        completed = subprocess.run(
            [sys.executable, str(EXAMPLES / relative_path)],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )

        assert completed.returncode == 0, (
            f"{relative_path} failed\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
        payload = json.loads(completed.stdout)
        assert isinstance(payload, dict), relative_path


def test_dx04_postgresql_example_is_server_independent() -> None:
    completed = subprocess.run(
        [sys.executable, str(EXAMPLES / "13_postgresql.py")],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    )

    payload = json.loads(completed.stdout)
    assert payload["opens_connection"] is False
    assert payload["optional_extra"] == "pyworkflowkit[postgres]"
