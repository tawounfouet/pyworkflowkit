"""Machine-readable 1.0 release-candidate readiness contract."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from pyworkflowkit.compatibility import (
    COMPATIBILITY_CONTRACT_VERSION,
    COMPATIBILITY_TARGET_RELEASE,
)
from pyworkflowkit.contracts.developer_experience import (
    DX_CONTRACT_VERSION,
    DX_TARGET_RELEASE,
)
from pyworkflowkit.contracts.distribution import (
    DISTRIBUTION_CONTRACT_VERSION,
    DISTRIBUTION_TARGET_RELEASE,
)
from pyworkflowkit.contracts.typing import TYPING_CONTRACT_VERSION, TYPING_TARGET_RELEASE
from pyworkflowkit.public_api import PUBLIC_API_CONTRACT_VERSION, PUBLIC_API_TARGET_RELEASE

RELEASE_CANDIDATE_CONTRACT_VERSION = "1"
RELEASE_CANDIDATE_VERSION = "0.9.0rc1"
RELEASE_CANDIDATE_TARGET_RELEASE = "1.0.0"

STABILIZATION_TRACKS: Mapping[str, Mapping[str, str]] = MappingProxyType(
    {
        "RQ-01": MappingProxyType(
            {
                "name": "Public API Freeze",
                "contract_version": PUBLIC_API_CONTRACT_VERSION,
                "target_release": PUBLIC_API_TARGET_RELEASE,
            }
        ),
        "RQ-02": MappingProxyType(
            {
                "name": "Compatibility & Deprecation",
                "contract_version": COMPATIBILITY_CONTRACT_VERSION,
                "target_release": COMPATIBILITY_TARGET_RELEASE,
            }
        ),
        "RQ-03": MappingProxyType(
            {
                "name": "Typing & Static Contracts",
                "contract_version": TYPING_CONTRACT_VERSION,
                "target_release": TYPING_TARGET_RELEASE,
            }
        ),
        "RQ-04": MappingProxyType(
            {
                "name": "Developer Experience & Documentation",
                "contract_version": DX_CONTRACT_VERSION,
                "target_release": DX_TARGET_RELEASE,
            }
        ),
        "RQ-05": MappingProxyType(
            {
                "name": "Packaging & Distribution",
                "contract_version": DISTRIBUTION_CONTRACT_VERSION,
                "target_release": DISTRIBUTION_TARGET_RELEASE,
            }
        ),
    }
)

REQUIRED_QUALIFICATION_JOB_IDS: tuple[str, ...] = (
    "artifact-install",
    "public-api-freeze",
    "compatibility-deprecation",
    "static-typing",
    "developer-experience",
    "packaging-distribution",
    "reference-contracts",
    "reference-integrations",
    "control-plane-provider",
    "ecosystem-sdk",
    "transverse-v0-8",
    "sqlite-upgrade",
    "postgres-upgrade",
    "security",
)

PROMOTION_POLICY = "same-qualified-code-version-metadata-only"

MANUAL_1_0_PUBLICATION_DECISIONS: tuple[str, ...] = ("software_license",)


def release_candidate_contract_snapshot() -> dict[str, object]:
    """Return deterministic release-candidate readiness requirements."""

    return {
        "contract_version": RELEASE_CANDIDATE_CONTRACT_VERSION,
        "candidate_version": RELEASE_CANDIDATE_VERSION,
        "target_release": RELEASE_CANDIDATE_TARGET_RELEASE,
        "stabilization_tracks": {
            track: dict(values) for track, values in sorted(STABILIZATION_TRACKS.items())
        },
        "required_qualification_jobs": list(REQUIRED_QUALIFICATION_JOB_IDS),
        "promotion_policy": PROMOTION_POLICY,
        "manual_1_0_publication_decisions": list(MANUAL_1_0_PUBLICATION_DECISIONS),
    }


__all__ = [
    "MANUAL_1_0_PUBLICATION_DECISIONS",
    "PROMOTION_POLICY",
    "RELEASE_CANDIDATE_CONTRACT_VERSION",
    "RELEASE_CANDIDATE_TARGET_RELEASE",
    "RELEASE_CANDIDATE_VERSION",
    "REQUIRED_QUALIFICATION_JOB_IDS",
    "STABILIZATION_TRACKS",
    "release_candidate_contract_snapshot",
]
