"""RQ-03 acceptance for static typing and external consumer contracts."""

from __future__ import annotations

import json
from importlib import import_module
from importlib.resources import files

from pyworkflowkit.compatibility import COMPATIBILITY_SUBJECTS, CompatibilityStatus
from pyworkflowkit.contracts.typing import (
    ECOSYSTEM_PROTOCOL_SUPPORT_EXPORTS,
    STATIC_TYPE_CHECKER,
    STATIC_TYPE_CHECKER_MODE,
    TYPING_CONTRACT_VERSION,
    TYPING_FACADES,
    TYPING_MARKER,
    TYPING_TARGET_RELEASE,
    typing_contract_snapshot,
)
from pyworkflowkit.public_api import PUBLIC_API_SURFACES
from pyworkflowkit.release_contract import REQUIRED_CONTRACT_VERSIONS, release_contract_snapshot


def test_rq03_typing_contract_targets_1_0() -> None:
    assert TYPING_CONTRACT_VERSION == "1"
    assert TYPING_TARGET_RELEASE == "1.0.0"
    assert TYPING_MARKER == "py.typed"
    assert STATIC_TYPE_CHECKER == "mypy"
    assert STATIC_TYPE_CHECKER_MODE == "strict"


def test_rq03_pep561_marker_is_packaged() -> None:
    marker = files("pyworkflowkit").joinpath(TYPING_MARKER)
    assert marker.is_file()


def test_rq03_all_frozen_facades_are_typing_targets() -> None:
    assert tuple(sorted(PUBLIC_API_SURFACES)) == TYPING_FACADES


def test_rq03_ecosystem_protocol_support_types_are_public() -> None:
    ecosystem = import_module("pyworkflowkit.ecosystem")
    frozen = set(PUBLIC_API_SURFACES["pyworkflowkit.ecosystem"])

    for exports in ECOSYSTEM_PROTOCOL_SUPPORT_EXPORTS.values():
        for name in exports:
            assert name in frozen
            assert name in ecosystem.__all__
            assert hasattr(ecosystem, name)


def test_rq03_typing_contract_is_stable_compatibility_evidence() -> None:
    matching = [
        subject
        for subject in COMPATIBILITY_SUBJECTS
        if subject.key == "typing.static_contract"
    ]
    assert len(matching) == 1
    assert matching[0].status is CompatibilityStatus.STABLE
    assert matching[0].contract_version == "1"


def test_rq03_snapshot_is_json_portable_and_part_of_release_contract() -> None:
    snapshot = typing_contract_snapshot()
    encoded = json.dumps(snapshot, allow_nan=False, sort_keys=True)

    assert json.loads(encoded) == snapshot
    assert dict(REQUIRED_CONTRACT_VERSIONS)["typing"] == "1"

    release_snapshot = release_contract_snapshot()
    assert release_snapshot["contracts"]["typing"] == "1"
    assert release_snapshot["typing"] == snapshot
