"""LOT-21 V1 migration and Customer 360 beta reference acceptance."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pyworkflowkit
from pyworkflowkit._compat import v1_to_v2


def test_lot21_migration_surface_remains_explicit_and_off_root() -> None:
    required = {
        "migrate_workflow_definition",
        "migrate_task_definition",
        "migrate_workflow_run",
        "migrate_task_run",
        "migrate_task_attempt",
        "migrate_task_attempt_sequence",
        "migrate_external_run_ref",
        "export_v1_runtime_metadata",
        "import_v1_runtime_metadata",
        "migration_contract_snapshot",
    }

    assert required.issubset(set(v1_to_v2.__all__))
    for name in required:
        assert name not in pyworkflowkit.__all__


def test_lot21_migration_snapshot_freezes_fail_closed_posture() -> None:
    snapshot = v1_to_v2.migration_contract_snapshot()

    assert snapshot == {
        "contract_version": "1",
        "namespace": "pyworkflowkit._compat",
        "direction": "v1_to_v2_only",
        "generic_aliases_preserved": False,
        "default_executor_mapping": {"local": "inline"},
        "hard_timeout_automatic_mapping": False,
        "workflow_parameters_automatic_mapping": False,
        "workflow_run_requires_external_fingerprints": True,
        "workflow_run_requires_external_correlation": True,
        "task_attempt_requires_external_created_at": True,
        "retry_history_requires_contiguous_attempt_numbers": True,
        "external_run_kind_requires_explicit_input": True,
        "legacy_failure_fields_preserved_as_evidence": True,
        "legacy_retry_eligible_at_preserved_as_evidence": True,
        "semantic_metadata_export_import": True,
        "semantic_metadata_external_attempt_ownership": None,
        "ambiguous_external_attempt_ownership_invented": False,
    }


def test_lot21_customer360_beta_script_is_executable_from_consumer_context() -> None:
    repository = Path(__file__).resolve().parents[2]
    script = repository / "scripts" / "qualify_v2_customer360_beta.py"

    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd="/tmp",
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["contract"] == "pyworkflowkit.customer360_beta"
    assert payload["contract_version"] == "1"
    assert payload["happy_path"] == {
        "dependency_count": 3,
        "external_run_count": 5,
        "task_count": 4,
        "transform_attempts": 2,
        "workflow_status": "SUCCEEDED",
    }
    assert payload["security_negative"] == {
        "error_code": "PWK-PYTRANSFORMKIT-NONPORTABLE-INPUT",
        "sibling_calls": 0,
        "workflow_status": "FAILED",
    }
    assert payload["incompatible_contracts"] == {
        "pyingestkit_result": True,
        "pyingestkit_workload": True,
        "pytransformkit_result": True,
        "pytransformkit_workload": True,
    }
