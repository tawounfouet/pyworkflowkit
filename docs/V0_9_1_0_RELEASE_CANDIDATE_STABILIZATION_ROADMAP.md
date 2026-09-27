# PyWorkflowKit 0.9 — 1.0 Release-Candidate Stabilization Roadmap

Status: **active — 0.9.0a1 / RQ-01**

## Objective

The 0.9 line prepares the existing runtime for a durable 1.0 contract. It is a
stabilization line, not a feature-expansion line.

```text
0.8.0
Ecosystem Interoperability
    ↓
0.9.x
1.0 Release-Candidate Stabilization
    ↓
1.0.0
Stable Embeddable Workflow Runtime
```

## Scope rule

A change may enter 0.9 when it closes an ambiguity, strengthens compatibility, improves
typing/documentation/packaging, or fixes a defect in an existing contract.

A change that creates a new product capability is deferred beyond 1.0 unless it is
strictly required to make an already-promised contract correct.

## Tracks

```text
RQ-01 Public API Freeze                    0.9.0a1   ACTIVE
RQ-02 Compatibility & Deprecation          0.9.0a2   NEXT
RQ-03 Typing & Static Contracts            0.9.0a3
RQ-04 Developer Experience & Documentation 0.9.0b1
RQ-05 Packaging & Distribution             0.9.0b2
RQ-06 1.0 Release Qualification            0.9.0rc1
                                           1.0.0
```

## RQ-01 — Public API Freeze

RQ-01 defines which facades are intended to survive into 1.0 and turns those surfaces
into executable compatibility evidence.

Frozen facades:

```text
pyworkflowkit
pyworkflowkit.ecosystem
pyworkflowkit.control_plane
pyworkflowkit.integrations
pyworkflowkit.plugins
pyworkflowkit.public_api
```

The contract is exposed through:

```python
from pyworkflowkit.public_api import (
    PUBLIC_API_CONTRACT_VERSION,
    PUBLIC_API_SURFACES,
    PUBLIC_API_TARGET_RELEASE,
    public_api_contract_snapshot,
)
```

Exit criteria:

```text
package version = 0.9.0a1
public API contract v1 exists
all frozen facades match their __all__
all exported names resolve
contract snapshot is deterministic and JSON portable
no active removal is introduced
regular CI is green
built-wheel Release Qualification gate is green
```

## RQ-02 — Compatibility & Deprecation

RQ-02 will audit aliases, defaults, exception compatibility, versioned schemas, CLI
contracts, persistence contracts, and the removal/deprecation policy. It must remove
ambiguity without silently breaking the RQ-01 surfaces.

## RQ-03 — Typing & Static Contracts

RQ-03 will pressure public Protocols, annotations, `py.typed`, Optional/None semantics,
callback signatures, plugin interfaces, and static-checker usability.

## RQ-04 — Developer Experience & Documentation

RQ-04 will qualify the first-use path from install to define/run/inspect/failure handling
without requiring knowledge of the internal architecture corpus.

## RQ-05 — Packaging & Distribution

RQ-05 will harden metadata, dependency bounds, optional extras, wheel/sdist completeness,
clean installation, upgrade installation, and distribution-facing documentation.

## RQ-06 — 1.0 Release Qualification

RQ-06 will compose the inherited runtime, persistence, security, ecosystem, compatibility,
typing, documentation, and packaging gates into the final 1.0 release-candidate gate.

## Non-goals

```text
new scheduler
background orchestration daemon
distributed worker fleet
message broker
Web UI
IAM / RBAC
new business-specific integration in core
new workflow semantics for their own sake
```
