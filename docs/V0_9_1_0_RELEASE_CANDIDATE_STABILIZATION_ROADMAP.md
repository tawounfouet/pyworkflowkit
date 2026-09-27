# PyWorkflowKit 0.9 — 1.0 Release-Candidate Stabilization Roadmap

Status: **active — 0.9.0a3 / RQ-03**

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
RQ-01 Public API Freeze                    0.9.0a1   ✅
RQ-02 Compatibility & Deprecation          0.9.0a2   ✅
RQ-03 Typing & Static Contracts            0.9.0a3   ACTIVE
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

RQ-02 classifies existing contracts as `stable`, `deprecated`, `internal`, or
`remove-before-1.0`. It freezes the documented console aliases and RuntimeSettings
defaults, cross-checks every versioned v1 contract, narrows stable exception imports to
frozen facade re-exports, and keeps implementation module paths explicitly internal.

The audit also fixes one 0.9 compatibility inconsistency: Ecosystem SDK v1 now declares
`>=0.8.0b1,<1.0` instead of excluding the current 0.9 line with `<0.9`.

Exit criteria:

```text
package version = 0.9.0a2
compatibility classification contract v1
all versioned public contracts remain v1
console aliases pyworkflow / pyworkflowkit remain installed
RuntimeSettings precedence and defaults are frozen
stable exception exports resolve through frozen facades
internal module prefixes do not overlap public facades
no active deprecation
no remove-before-1.0 subject
Ecosystem SDK v1 supports 0.8 and 0.9 (<1.0)
regular CI is green
built-wheel Release Qualification gate is green
```

## RQ-03 — Typing & Static Contracts

RQ-03 qualifies the frozen facades as real external-consumer typing surfaces rather than
relying only on internal source-tree `mypy --strict`.

The milestone keeps the existing PEP 561 `py.typed` marker, adds a machine-readable
Typing Contract v1, and tests consumer code against Python 3.11, 3.12, and 3.13.

It also closes two typing gaps discovered by the audit:

- `@task` now accepts statically only the signatures the runtime can execute: zero
  arguments or one `RunContext`;
- `pyworkflowkit.ecosystem` re-exports the support types needed to implement its public
  `Executor`, `MetadataStore`, `UnitOfWork`, and `RuntimeEventSink` Protocols without
  importing internal module paths.

Exit criteria:

```text
package version = 0.9.0a3
Typing Contract v1 targets 1.0.0
py.typed is present in the installed wheel
all frozen facades are typing targets
public-consumer fixture passes mypy --strict
invalid two-argument @task handler fails static typing
Executor / MetadataStore / UnitOfWork / RuntimeEventSink are implementable from public facades
plugin_registration preserves generic factory result types
WorkflowRuntimeProvider satisfies ControlPlaneProvider structurally
typing passes for Python 3.11 / 3.12 / 3.13
regular CI is green
built-wheel Release Qualification gate is green
```

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
