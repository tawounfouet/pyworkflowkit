"""DX04 acceptance for the canonical executable example suite."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = REPOSITORY_ROOT / "examples"
GUIDES = REPOSITORY_ROOT / "docs" / "guides"

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


GUIDE_EXAMPLE_REFERENCES = {
    "00_ZERO_TO_HERO.md": ("examples/00_hello_world.py",),
    "01_INSTALLATION_AND_FIRST_WORKFLOW.md": ("examples/01_tasks_and_handlers.py",),
    "02_TASKS_AND_HANDLERS.md": ("examples/01_tasks_and_handlers.py",),
    "03_WORKFLOW_DEFINITIONS.md": ("examples/02_workflow_definitions.py",),
    "04_DEPENDENCIES_AND_DAG.md": (
        "examples/03_dependencies.py",
        "examples/04_dag.py",
    ),
    "05_EXECUTION_PLANNING.md": ("examples/05_execution_plan.py",),
    "06_WORKFLOW_RUNTIME.md": ("examples/06_runtime.py",),
    "07_RUN_CONTEXT_AND_DATA_FLOW.md": ("examples/07_run_context.py",),
    "08_FAILURES_AND_RETRIES.md": (
        "examples/08_failure.py",
        "examples/09_retry.py",
    ),
    "09_EVENTS_AND_OBSERVABILITY.md": ("examples/10_events.py",),
    "10_MANIFEST_AND_EVIDENCE.md": ("examples/11_manifest.py",),
    "11_METADATA_STORE.md": ("examples/12_sqlite.py",),
    "12_SQLITE_PERSISTENCE.md": ("examples/12_sqlite.py",),
    "13_POSTGRESQL_PERSISTENCE.md": ("examples/13_postgresql.py",),
    "14_CONFIGURATION.md": ("examples/14_configuration.py",),
    "16_CONCURRENCY.md": ("examples/15_concurrency.py",),
    "17_TIMEOUTS_AND_CANCELLATION.md": (
        "examples/16_timeout.py",
        "examples/17_cancellation.py",
    ),
    "19_PLUGINS_AND_ECOSYSTEM.md": ("examples/19_plugin.py",),
    "20_EXTERNAL_WORKLOADS.md": ("examples/18_external_workload.py",),
    "21_CUSTOM_EXECUTOR.md": ("examples/20_custom_executor.py",),
    "23_CONTROL_PLANE.md": ("examples/21_control_plane.py",),
    "24_PYINGESTKIT_INTEGRATION.md": ("examples/integrations/pyingestkit/atomic_job.py",),
    "27_PRODUCTION_PATTERNS.md": ("examples/complete/data_pipeline.py",),
    "99_COMPLETE_REFERENCE_APPLICATION.md": ("examples/complete/data_pipeline.py",),
}

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
            f"{relative_path} failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
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


def test_dx04_guides_reference_real_canonical_examples() -> None:
    for guide_name, references in GUIDE_EXAMPLE_REFERENCES.items():
        guide = (GUIDES / guide_name).read_text(encoding="utf-8")
        for reference in references:
            assert reference in guide, f"{guide_name}: {reference}"
