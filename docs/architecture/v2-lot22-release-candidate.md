# PyWorkflowKit V2 — LOT-22 Release Candidate Freeze

## Status

LOT-22 is the V2 release-candidate qualification lot.

Target:

```text
2.0.0rc1
```

It introduces no new functional roadmap scope. Its purpose is to freeze the public V2
contract and prove that LOT-00 through LOT-21 compose as one releasable artifact.

## Root promotion

The migration-era 1.1 root is replaced by the canonical V2 root defined since LOT-00 by
`V2_ROOT_TARGET_ALLOWLIST`.

The frozen root is intentionally small:

```text
ExecutionPlan
PyWorkflowKitError
RetryPolicy
TaskAttempt
TaskAttemptId
TaskDefinition
TaskRun
TaskRunId
TimeoutPolicy
WorkflowDefinition
WorkflowResult
WorkflowRun
WorkflowRunId
WorkflowRuntime
__version__
```

The old 1.0 root tuple remains in `pyworkflowkit.public_api.PUBLIC_API_SURFACES` as
historical migration evidence. It is no longer required to equal the live 2.0 root.

## Release evidence manifest

The canonical RC manifest is:

```text
pyworkflowkit.contracts.v2_release_candidate
    .v2_release_candidate_evidence_manifest()
```

It composes the already-qualified V2 snapshots rather than redefining them.

Included contracts:

```text
architecture
root_api
authoring
planning
states
runtime
retry
timeout
executor
metadata_store
wire
plugins
pyingestkit
pytransformkit
migration
```

The manifest is deterministic and JSON-portable.

## Frozen identities

The following identity types are compatibility-critical for the 2.0 line:

```text
CorrelationId
WorkflowRunId
TaskRunId
TaskAttemptId
```

They remain distinct runtime types even when their textual values are equal.

## Frozen Protocols

LOT-22 freezes the protocol member sets for:

```text
WorkloadDescriptor
Executor
CancellableExecutor
MetadataStore
ExternalRunVerifier
V2RuntimeEventSink
```

Changing one of these after RC qualification is a contract change and requires an RC
reset rather than an ordinary blocker fix.

## Complete qualification

The release candidate requires:

```text
root API snapshot
Python 3.11 / 3.12 / 3.13
Ruff / format / mypy
DAG / planning
state machines
retry / backoff
timeout / cancellation
Executor conformance
MetadataStore conformance
recovery / reconciliation fault injection
wire golden fixtures
plugin compatibility
security
sibling adapter conformance
optional dependency isolation
wheel install
sdist install
Customer 360
V1 migration fixtures
docs / examples
release evidence manifest
```

Existing CI and Release Qualification families remain inherited evidence. LOT-22 adds a
dedicated installed-artifact V2 RC gate rather than weakening or replacing historical
gates.

## Installed-artifact proof

The script:

```text
scripts/qualify_v2_release_candidate.py
```

runs outside the source package directory against the built wheel and verifies:

- installed version is exactly `2.0.0rc1`;
- root exports exactly match the V2 allowlist;
- the aggregate manifest reports the candidate and target release;
- stable identities and contract families are present;
- the RC change policy forbids architecture redesign.

Wheel/sdist installation and Customer 360 continue to be exercised by the artifact
matrix.

## Change policy

Once the RC is fully green:

```text
blocker fixes only
no architecture redesign
no new public capability
no compatibility-contract reshaping
```

Any non-blocker contract change resets the RC qualification.

## Exit criteria

```text
[ ] package version is 2.0.0rc1
[ ] canonical V2 root is promoted and frozen
[ ] historical 1.0 API snapshot remains available as migration evidence
[ ] states are frozen
[ ] execution identities are frozen
[ ] Protocol member sets are frozen
[ ] aggregate evidence manifest is deterministic and JSON portable
[ ] Python 3.11 / 3.12 / 3.13 pass
[ ] Ruff / format / mypy pass
[ ] planning/state/retry/timeout tests pass
[ ] Executor and MetadataStore conformance pass
[ ] recovery/reconciliation fault tests pass
[ ] wire golden fixtures pass
[ ] plugin compatibility passes
[ ] sibling adapter conformance passes
[ ] optional dependencies remain isolated
[ ] wheel and sdist installs pass
[ ] Customer 360 passes
[ ] V1 migration fixtures pass
[ ] docs/examples pass
[ ] security gates pass
[ ] CI is green
[ ] Release Qualification is green
```
