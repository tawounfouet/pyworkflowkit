"""DX03 acceptance for the canonical Zero-to-Hero guide architecture."""

from __future__ import annotations

from pathlib import Path

GUIDES = Path(__file__).resolve().parents[2] / "docs" / "guides"

CANONICAL_CHAPTERS = (
    "00_ZERO_TO_HERO.md",
    "01_INSTALLATION_AND_FIRST_WORKFLOW.md",
    "02_TASKS_AND_HANDLERS.md",
    "03_WORKFLOW_DEFINITIONS.md",
    "04_DEPENDENCIES_AND_DAG.md",
    "05_EXECUTION_PLANNING.md",
    "06_WORKFLOW_RUNTIME.md",
    "07_RUN_CONTEXT_AND_DATA_FLOW.md",
    "08_FAILURES_AND_RETRIES.md",
    "09_EVENTS_AND_OBSERVABILITY.md",
    "10_MANIFEST_AND_EVIDENCE.md",
    "11_METADATA_STORE.md",
    "12_SQLITE_PERSISTENCE.md",
    "13_POSTGRESQL_PERSISTENCE.md",
    "14_CONFIGURATION.md",
    "15_CLI_ZERO_TO_HERO.md",
    "16_CONCURRENCY.md",
    "17_TIMEOUTS_AND_CANCELLATION.md",
    "18_EXECUTORS.md",
    "19_PLUGINS_AND_ECOSYSTEM.md",
    "20_EXTERNAL_WORKLOADS.md",
    "21_CUSTOM_EXECUTOR.md",
    "22_CUSTOM_METADATA_STORE.md",
    "23_CONTROL_PLANE.md",
    "24_PYINGESTKIT_INTEGRATION.md",
    "25_TESTING_WORKFLOWS.md",
    "26_DEBUGGING_AND_TROUBLESHOOTING.md",
    "27_PRODUCTION_PATTERNS.md",
    "99_COMPLETE_REFERENCE_APPLICATION.md",
)

NEXT_CHAPTER = {
    current: following
    for current, following in zip(CANONICAL_CHAPTERS, CANONICAL_CHAPTERS[1:], strict=True)
}

LEGACY_REDIRECTS = {
    "getting-started.md": "01_INSTALLATION_AND_FIRST_WORKFLOW.md",
    "failures-and-retries.md": "08_FAILURES_AND_RETRIES.md",
    "persistence-and-evidence.md": "12_SQLITE_PERSISTENCE.md",
    "cli-workflow.md": "15_CLI_ZERO_TO_HERO.md",
    "plugin-authoring.md": "19_PLUGINS_AND_ECOSYSTEM.md",
    "pyingestkit-adapter.md": "24_PYINGESTKIT_INTEGRATION.md",
    "troubleshooting.md": "26_DEBUGGING_AND_TROUBLESHOOTING.md",
}

FORBIDDEN_BEGINNER_IMPORTS = (
    "from pyworkflowkit.application",
    "from pyworkflowkit.adapters",
    "from pyworkflowkit.domain",
    "from pyworkflowkit.ports",
    "import pyworkflowkit.application",
    "import pyworkflowkit.adapters",
    "import pyworkflowkit.domain",
    "import pyworkflowkit.ports",
)


def test_dx03_canonical_guide_topology_is_complete() -> None:
    assert (GUIDES / "README.md").is_file()
    for chapter in CANONICAL_CHAPTERS:
        assert (GUIDES / chapter).is_file(), chapter


def test_dx03_index_links_every_canonical_chapter() -> None:
    index = (GUIDES / "README.md").read_text(encoding="utf-8")
    for chapter in CANONICAL_CHAPTERS:
        assert f"]({chapter})" in index, chapter
    assert "Planned in DX03" not in index


def test_dx03_each_chapter_links_to_the_next_learning_step() -> None:
    for chapter, next_chapter in NEXT_CHAPTER.items():
        content = (GUIDES / chapter).read_text(encoding="utf-8")
        assert f"]({next_chapter})" in content, f"{chapter} -> {next_chapter}"


def test_dx03_beginner_guides_use_public_import_surfaces() -> None:
    for chapter in CANONICAL_CHAPTERS[:16]:
        content = (GUIDES / chapter).read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_BEGINNER_IMPORTS:
            assert forbidden not in content, f"{chapter}: {forbidden}"


def test_dx03_beginner_cli_examples_use_canonical_pwk_command() -> None:
    for chapter in CANONICAL_CHAPTERS[:16]:
        content = (GUIDES / chapter).read_text(encoding="utf-8")
        shell_lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip().startswith(("pwk ", "pyworkflowkit ", "pyworkflow "))
        ]
        for line in shell_lines:
            assert line.startswith("pwk "), f"{chapter}: {line}"


def test_dx03_legacy_guide_paths_redirect_to_canonical_chapters() -> None:
    for legacy, canonical in LEGACY_REDIRECTS.items():
        content = (GUIDES / legacy).read_text(encoding="utf-8")
        assert canonical in content, f"{legacy} -> {canonical}"
        assert "preserved for compatibility" in content
