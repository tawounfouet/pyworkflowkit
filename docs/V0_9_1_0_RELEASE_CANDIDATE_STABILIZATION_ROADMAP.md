# PyWorkflowKit 0.9 — 1.0 Release-Candidate Stabilization Roadmap

Status: **complete — 1.0.0 stable promotion prepared from RC2**

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
RQ-03 Typing & Static Contracts            0.9.0a3   ✅
RQ-04 Developer Experience & Documentation 0.9.0b1   ✅
RQ-05 Packaging & Distribution             0.9.0b2   ✅
RQ-06 1.0 Release Qualification            0.9.0rc1  ⚠ superseded
RQ-06 Ecosystem compatibility correction   0.9.0rc2  ✅
Stable promotion                            1.0.0     READY
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

RQ-04 qualifies the first-use path as executable release evidence rather than prose-only
documentation.

The milestone introduces a Developer Experience Contract v1 and validates:

- installation/version discovery;
- public `@task` / `@workflow` authoring;
- execution through `WorkflowRuntime`;
- event and manifest inspection;
- failure/retry behavior;
- SQLite persistence across runtime instances and CLI processes;
- the CLI journey `version → validate → plan → run → inspect → events → manifest`;
- first plugin authoring through `pyworkflowkit.ecosystem`;
- troubleshooting guidance for the most common boundary mistakes.

All first-use examples are statically inspected to ensure PyWorkflowKit imports use only
the documented `pyworkflowkit` and `pyworkflowkit.ecosystem` facades.

Exit criteria:

```text
package version = 0.9.0b1
Developer Experience Contract v1 targets 1.0.0
README contains an explicit Start here path
required first-use guides exist
first-use examples use only public authoring facades
hello-world / retry / SQLite / plugin examples execute successfully
complete CLI first-run journey succeeds
both console aliases report the same version
source CI is green
built-wheel Release Qualification gate is green
```

## RQ-05 — Packaging & Distribution

RQ-05 qualifies the exact distribution artifacts consumed by downstream users.

The milestone freezes:

- bounded Hatchling build-backend requirements;
- direct runtime dependency ranges;
- published optional extras;
- well-known project URLs and index-safe README links;
- pure-Python wheel contents and required package resources;
- an explicit minimal sdist scope;
- wheel reconstruction from the sdist;
- clean core and extra installations;
- the package upgrade path from the exact stable 0.8.0 commit.

Exit criteria:

```text
package version = 0.9.0b2
Distribution Contract v1 targets 1.0.0
build backend bounded
runtime dependencies/extras metadata qualified
wheel and sdist pass twine check
wheel contains py.typed + migration resources
repository-only files absent from artifacts
wheel rebuilt from sdist is equivalent
clean core and published-extra installs pass pip check
0.8.0 -> 0.9.0b2 package upgrade succeeds
regular CI is green
built-artifact Release Qualification gate is green
```

## RQ-06 — 1.0 Release Qualification

RQ-06 composes the inherited runtime, persistence, security, ecosystem, compatibility,
typing, documentation, and packaging gates into one final release-candidate decision.

The candidate introduces a Release-Candidate Contract v1 that freezes:

- current candidate version `0.9.0rc2`;
- target release `1.0.0`;
- RQ-01 through RQ-05 as required inherited tracks;
- every release-qualification job family required by the 1.0 promise;
- zero active `deprecated` / `remove-before-1.0` compatibility blockers;
- the promotion rule `same-qualified-code-version-metadata-only`;
- software-license selection as an explicit manual publication decision rather than an
  inferred package change.

The dedicated `1.0 release candidate` workflow job runs only after all inherited
qualification families report success, installs the same built wheel, and executes the
RQ-06 contract and installed-artifact qualifier.

Exit criteria:

```text
package version = 0.9.0rc2
Release-Candidate Contract v1 targets 1.0.0
RQ-01 through RQ-05 remain v1 and target 1.0.0
no active compatibility blocker
all inherited qualification families are required
installed wheel passes RQ-06 qualification
regular CI is green
Release Qualification is green
aggregate release-candidate gate is green
final release gate is green
1.0 promotion permits version/release metadata only
```

### RC1 → RC2 correction

The first stable-promotion qualification exposed one remaining public compatibility
defect:

```text
Ecosystem SDK v1
minimum           = 0.8.0b1
maximum_exclusive = 1.0
```

That ceiling excludes `1.0.0` itself.

RC2 corrects the same SDK v1 contract to:

```text
series            = 0.8-1.x
minimum           = 0.8.0b1
maximum_exclusive = 2.0
```

and aligns reference/template package dependency ceilings to `<2.0`.

RC2 passed the full RQ-06 corpus. The stable promotion is therefore prepared from that
exact qualified implementation under the metadata-only promotion policy.

## Stable promotion — 1.0.0

The stable branch follows:

```text
same-qualified-code-version-metadata-only
```

There are no implementation changes under `src/pyworkflowkit/**` relative to the
qualified RC2 commit.

Operational merge remains gated by external creation and tag-triggered qualification of:

```text
v0.9.0rc2
```

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
