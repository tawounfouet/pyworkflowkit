"""DX05 acceptance for the canonical interactive notebook learning path."""

from __future__ import annotations

import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOKS = REPOSITORY_ROOT / "notebooks"

CANONICAL_NOTEBOOKS = (
    "00 - Environment and Setup.ipynb",
    "01 - Hello Workflow.ipynb",
    "02 - Tasks and Handlers.ipynb",
    "03 - Workflow Definitions.ipynb",
    "04 - Dependencies and DAG.ipynb",
    "05 - Execution Planning.ipynb",
    "06 - Workflow Runtime.ipynb",
    "07 - RunContext and Data Flow.ipynb",
    "08 - Failures and Retries.ipynb",
    "09 - Events and Evidence.ipynb",
    "10 - Run Manifest.ipynb",
    "11 - SQLite Persistence.ipynb",
    "12 - Configuration.ipynb",
    "13 - Concurrency.ipynb",
    "14 - Executors.ipynb",
    "15 - Plugins.ipynb",
    "16 - External Workloads.ipynb",
    "17 - PyIngestKit Integration.ipynb",
    "99 - Complete Workflow Lab.ipynb",
)

NOTEBOOK_REFERENCES = {
    "00 - Environment and Setup.ipynb": (
        "../docs/guides/00_ZERO_TO_HERO.md",
        "../examples/00_hello_world.py",
    ),
    "01 - Hello Workflow.ipynb": (
        "../docs/guides/01_INSTALLATION_AND_FIRST_WORKFLOW.md",
        "../examples/00_hello_world.py",
    ),
    "02 - Tasks and Handlers.ipynb": (
        "../docs/guides/02_TASKS_AND_HANDLERS.md",
        "../examples/01_tasks_and_handlers.py",
    ),
    "03 - Workflow Definitions.ipynb": (
        "../docs/guides/03_WORKFLOW_DEFINITIONS.md",
        "../examples/02_workflow_definitions.py",
    ),
    "04 - Dependencies and DAG.ipynb": (
        "../docs/guides/04_DEPENDENCIES_AND_DAG.md",
        "../examples/03_dependencies.py",
        "../examples/04_dag.py",
    ),
    "05 - Execution Planning.ipynb": (
        "../docs/guides/05_EXECUTION_PLANNING.md",
        "../examples/05_execution_plan.py",
    ),
    "06 - Workflow Runtime.ipynb": (
        "../docs/guides/06_WORKFLOW_RUNTIME.md",
        "../examples/06_runtime.py",
    ),
    "07 - RunContext and Data Flow.ipynb": (
        "../docs/guides/07_RUN_CONTEXT_AND_DATA_FLOW.md",
        "../examples/07_run_context.py",
    ),
    "08 - Failures and Retries.ipynb": (
        "../docs/guides/08_FAILURES_AND_RETRIES.md",
        "../examples/08_failure.py",
        "../examples/09_retry.py",
    ),
    "09 - Events and Evidence.ipynb": (
        "../docs/guides/09_EVENTS_AND_OBSERVABILITY.md",
        "../examples/10_events.py",
    ),
    "10 - Run Manifest.ipynb": (
        "../docs/guides/10_MANIFEST_AND_EVIDENCE.md",
        "../examples/11_manifest.py",
    ),
    "11 - SQLite Persistence.ipynb": (
        "../docs/guides/12_SQLITE_PERSISTENCE.md",
        "../examples/12_sqlite.py",
    ),
    "12 - Configuration.ipynb": (
        "../docs/guides/14_CONFIGURATION.md",
        "../examples/14_configuration.py",
    ),
    "13 - Concurrency.ipynb": (
        "../docs/guides/16_CONCURRENCY.md",
        "../examples/15_concurrency.py",
    ),
    "14 - Executors.ipynb": (
        "../docs/guides/18_EXECUTORS.md",
        "../examples/20_custom_executor.py",
    ),
    "15 - Plugins.ipynb": (
        "../docs/guides/19_PLUGINS_AND_ECOSYSTEM.md",
        "../examples/19_plugin.py",
    ),
    "16 - External Workloads.ipynb": (
        "../docs/guides/20_EXTERNAL_WORKLOADS.md",
        "../examples/18_external_workload.py",
    ),
    "17 - PyIngestKit Integration.ipynb": (
        "../docs/guides/24_PYINGESTKIT_INTEGRATION.md",
        "../examples/integrations/pyingestkit/atomic_job.py",
    ),
    "99 - Complete Workflow Lab.ipynb": (
        "../docs/guides/99_COMPLETE_REFERENCE_APPLICATION.md",
        "../examples/complete/data_pipeline.py",
    ),
}

FORBIDDEN_IMPORTS = (
    "from pyworkflowkit.application",
    "from pyworkflowkit.adapters",
    "from pyworkflowkit.domain",
    "from pyworkflowkit.ports",
    "import pyworkflowkit.application",
    "import pyworkflowkit.adapters",
    "import pyworkflowkit.domain",
    "import pyworkflowkit.ports",
)


def _load_notebook(name: str) -> dict[str, object]:
    return json.loads((NOTEBOOKS / name).read_text(encoding="utf-8"))


def _code_sources(notebook: dict[str, object]) -> list[str]:
    cells = notebook["cells"]
    assert isinstance(cells, list)
    return [
        str(cell["source"])
        for cell in cells
        if isinstance(cell, dict) and cell.get("cell_type") == "code"
    ]


def test_dx05_notebook_topology_is_complete() -> None:
    assert (NOTEBOOKS / "README.md").is_file()
    for name in CANONICAL_NOTEBOOKS:
        assert (NOTEBOOKS / name).is_file(), name


def test_dx05_notebooks_are_valid_v4_documents_without_saved_outputs() -> None:
    for name in CANONICAL_NOTEBOOKS:
        notebook = _load_notebook(name)
        assert notebook["nbformat"] == 4
        assert isinstance(notebook["cells"], list)
        assert notebook["cells"], name
        for cell in notebook["cells"]:
            assert isinstance(cell, dict)
            if cell.get("cell_type") == "code":
                assert cell.get("execution_count") is None
                assert cell.get("outputs") == []


def test_dx05_notebooks_reference_their_guide_and_scripts() -> None:
    for name, references in NOTEBOOK_REFERENCES.items():
        content = (NOTEBOOKS / name).read_text(encoding="utf-8")
        for reference in references:
            assert reference in content, f"{name}: {reference}"


def test_dx05_notebooks_use_public_import_surfaces() -> None:
    for name in CANONICAL_NOTEBOOKS:
        source = "\n".join(_code_sources(_load_notebook(name)))
        for forbidden in FORBIDDEN_IMPORTS:
            assert forbidden not in source, f"{name}: {forbidden}"


def test_dx05_all_notebook_code_cells_execute_cleanly() -> None:
    for name in CANONICAL_NOTEBOOKS:
        notebook = _load_notebook(name)
        namespace: dict[str, object] = {
            "__name__": "__main__",
            "__file__": str(NOTEBOOKS / name),
        }
        for index, source in enumerate(_code_sources(notebook)):
            code = compile(source, f"{name}#cell-{index}", "exec")
            exec(code, namespace)
