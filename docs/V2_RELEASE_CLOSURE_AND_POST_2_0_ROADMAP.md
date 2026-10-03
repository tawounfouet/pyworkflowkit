# PyWorkflowKit V2 — Release Closure and Post-2.0 Roadmap

## Purpose

LOT-24 closes the PyWorkflowKit V2 construction phase after publication of the stable
`v2.0.0` release.

This lot is intentionally non-functional:

- it does not change `src/pyworkflowkit/**`;
- it does not introduce a new package version;
- it does not redefine the V2 runtime contract;
- it does not open the 2.1 development line.

Its role is to establish a durable post-release baseline from which maintenance and
future evolution can be planned without rewriting the meaning of 2.0.

## Closed release baseline

The published stable release is:

```text
version                 2.0.0
tag                     v2.0.0
qualified commit        3e96765be0d1e068348960e8ccce4f19fda9f31f
src/pyworkflowkit tree  f0797a25b877a0379f578015787b58f06a74dea2
release date            2026-10-03
GitHub Release          published
```

The runtime tree is exactly the same tree frozen for `2.0.0rc1`.

The release therefore retains the stable-promotion rule:

```text
same-qualified-code-version-metadata-only
```

LOT-24 does not alter that lineage.

## Final qualification evidence

The final post-merge main baseline completed:

```text
commit                  3e96765be0d1e068348960e8ccce4f19fda9f31f
CI run                  37148494189
CI workflow             success
Release Qualification   37148494157
RQ                      32/32
V2 RC lineage gate      success
V2 stable gate          success
final release gate      success
```

The stable tag was then created at that exact qualified commit and requalified:

```text
tag                     v2.0.0
annotated tag object    839854ceb84e07c6dff262a143609963b7b87d6d
target commit           3e96765be0d1e068348960e8ccce4f19fda9f31f
tag RQ run              37148666745
tag RQ                  32/32
finalization run        37148656845
finalization            success
```

The GitHub Release contains the qualified distribution artifacts:

```text
pyworkflowkit-2.0.0-py3-none-any.whl
sha256 66509f4af774ab82c96c763f1829b6921b537f22542e620ba0fb42b6e1e7d18a

pyworkflowkit-2.0.0.tar.gz
sha256 187b486a374a881209d9f6c8c83321e227910fa90643014a833ff4d03f0111e2

SHA256SUMS
published
```

PyPI publication was deliberately not part of the release operation.

## Canonical V2 public root

The stable package-root API remains:

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

Historical 1.x root behavior is not restored into this namespace. Migration remains
explicit through the compatibility surfaces documented in
`docs/migration/V1_TO_V2.md`.

## Compatibility baseline

The published 2.0 compatibility baseline is:

```text
state contract                v1
executor contract             v4
metadata-store contract       v2
wire contract family          v1
plugin API                    v2
V1→V2 migration contract      v1
release qualification         v1
migration head                0005_v2_task_output_checkpoints
Python                        3.11 / 3.12 / 3.13
```

Compatibility promises remain contract-based. Internal implementation details are not
promoted into public API simply because they exist in the repository.

## Stable execution boundary

PyWorkflowKit 2.0 owns reliable execution of a generic dependency graph.

The stable runtime includes:

- deterministic workflow validation and planning;
- explicit workflow/task/attempt identities;
- retry and timeout policies;
- sequential and concurrent coordination;
- inline, thread, process, async, and subprocess execution adapters;
- durable SQLite persistence;
- optional PostgreSQL persistence;
- runtime events, manifests, lineage and observability extension points;
- recovery assessment, reconciliation and same-run resume;
- durable bounded task-output checkpoints;
- explicit plugin activation;
- optional opaque sibling integration boundaries.

The following remain outside the core product boundary:

```text
future scheduling
background orchestration daemon
distributed worker fleet
message broker ownership
web control plane
IAM / RBAC
multi-tenant governance
business-specific workflow semantics
operating-system sandboxing
```

These exclusions are architecture decisions, not missing 2.0 features.

## Release-engineering closure

The temporary `.github/workflows/finalize-v2.0.0.yml` workflow existed only to perform
the one-time stable release operation:

```text
qualified main
    ↓
create v2.0.0
    ↓
requalify tag
    ↓
publish qualified GitHub Release
```

After successful publication it has no continuing product responsibility.

LOT-24 removes that one-shot workflow instead of leaving a version-specific release
automation active indefinitely.

The reusable release infrastructure that remains is:

```text
.github/workflows/ci.yml
.github/workflows/release-qualification.yml
```

Any future publication automation must be version-agnostic and designed as its own lot.

## Observed post-2.0 cleanup

The repository audit performed for LOT-24 found no open pull request, no open issue,
and no repository TODO/FIXME marker at the time the lot was opened.

The following concrete cleanup items were identified:

1. the README roadmap still described 0.9 as the current development line;
2. the final `2.0.0` qualification report stopped before the actual tag publication
   evidence;
3. the one-shot `finalize-v2.0.0.yml` workflow remained installed after successful use.

LOT-24 closes those documentation/release-operation inconsistencies.

## Explicit unresolved publication decisions

The following are not silently solved by LOT-24:

### PyPI publication

The GitHub Release is published, but PyPI publication remains an explicit future
decision. No workflow is allowed to infer that publishing a GitHub Release also grants
permission to publish to PyPI.

### Software license

The project metadata still does not select a software license. Existing architecture
documentation treats license selection as an explicit project/legal decision.

Until that decision is made, LOT-24 does not invent license metadata.

### Supply-chain signing and attestations

The 2.0 GitHub Release publishes SHA-256 checksums, but the repository does not currently
define an SBOM, Sigstore provenance, or artifact-attestation contract.

This is a possible future hardening area, not a retroactive requirement for 2.0.

## Version policy after 2.0

### 2.0.x — maintenance line

The 2.0.x line is reserved for backward-compatible maintenance:

- bug fixes;
- security fixes;
- documentation corrections;
- packaging corrections;
- CI/release-engineering corrections;
- dependency-range maintenance;
- compatibility fixes that preserve the frozen 2.0 public contracts.

A 2.0.x release must not use a patch version to smuggle in a new architecture.

### 2.1.x — compatible evolution

A future 2.1 line may add capabilities only when they preserve the 2.0 compatibility
baseline.

Candidate themes may include:

- improved release/distribution automation;
- supply-chain evidence such as SBOM/provenance;
- additional diagnostics and developer experience;
- compatible observability improvements;
- additional qualified adapters or executor capabilities;
- richer ecosystem integration contracts.

These are candidates, not committed scope. A dedicated 2.1 expression of need and
architecture must decide the actual content.

### 3.x — breaking evolution

Changes that require breaking stable 2.x contracts belong in a future major line.

Examples include:

- incompatible package-root changes;
- incompatible state vocabulary changes;
- incompatible executor or MetadataStore contracts;
- incompatible wire formats;
- incompatible persistence semantics;
- removal of compatibility surfaces before their deprecation policy permits it.

No 3.x scope is opened by LOT-24.

## Post-2.0 decision sequence

The next planning sequence is:

```text
LOT-24
V2 release closure
        ↓
post-2.0 baseline frozen
        ↓
maintenance backlog classification
        ↓
2.1 expression of need
        ↓
2.1 requirements analysis
        ↓
2.1 target architecture
        ↓
2.1 implementation roadmap
```

The 2.1 line must therefore begin with product and contract analysis, not directly with
implementation.

## LOT-24 qualification evidence

The first complete LOT-24 qualification after correcting README distribution portability
completed on:

```text
qualified HEAD          18d228b3d6fc740dd60102655ef571d1cbb2e10a
CI run                  37150187503
CI                      24/24 ✅
Release Qualification   37150187490
RQ                      32/32 ✅
V2 RC lineage gate          ✅
V2 stable promotion gate    ✅
Final release gate          ✅
```

The only defect found during qualification was a relative Markdown link added to the
package README. The existing distribution contract correctly rejected that link because
the README is also package metadata. The link was replaced with a portable textual path;
the packaging gate then passed.

This evidence-recording commit remains documentation-only. The complete blocking matrix
must rerun green on the final PR HEAD before merge.

## LOT-24 acceptance criteria

LOT-24 is complete when all of the following are true:

- [x] `v2.0.0` is published.
- [x] final main qualification evidence is recorded.
- [x] final tag qualification evidence is recorded.
- [x] the stable runtime tree is recorded.
- [x] the post-2.0 version policy is explicit.
- [x] PyPI and license decisions remain explicit rather than inferred.
- [x] the one-shot V2 finalization workflow is removed.
- [x] README no longer claims that 0.9 is the current development line.
- [x] no runtime source is changed by LOT-24.
- [x] LOT-24 PR CI is green.
- [x] LOT-24 PR Release Qualification is green.

Once the two repository gates above are green and the PR is merged, the V2 release
construction phase is considered administratively closed.
