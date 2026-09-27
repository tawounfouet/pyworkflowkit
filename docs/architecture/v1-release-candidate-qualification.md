# PyWorkflowKit 1.0 Release-Candidate Qualification

Status: RQ-06 — 0.9.0rc2

## Objective

RQ-06 composes the contracts and evidence already frozen by RQ-01 through RQ-05 into one
release-candidate decision for PyWorkflowKit 1.0.

It adds no runtime capability.

The release candidate answers one question:

```text
Can this exact artifact become PyWorkflowKit 1.0.0
without another functional change?
```

## Release-Candidate Contract

The machine-readable contract lives in:

```text
pyworkflowkit.contracts.release_candidate
```

with:

```python
RELEASE_CANDIDATE_CONTRACT_VERSION = "1"
RELEASE_CANDIDATE_VERSION = "0.9.0rc2"
RELEASE_CANDIDATE_TARGET_RELEASE = "1.0.0"
```

## Inherited stabilization tracks

The RC explicitly composes:

```text
RQ-01 — Public API Freeze
RQ-02 — Compatibility & Deprecation
RQ-03 — Typing & Static Contracts
RQ-04 — Developer Experience & Documentation
RQ-05 — Packaging & Distribution
```

Each inherited track must still expose:

```text
contract_version = 1
target_release   = 1.0.0
```

No track is silently redefined by RQ-06.

## Required qualification families

The final candidate requires success from:

```text
artifact-install
public-api-freeze
compatibility-deprecation
static-typing
developer-experience
packaging-distribution
reference-contracts
reference-integrations
control-plane-provider
ecosystem-sdk
transverse-v0-8
sqlite-upgrade
postgres-upgrade
security
```

These jobs cover the complete release promise:

```text
package installability
public API
compatibility
typing
first-use DX
distribution
contract snapshots
ecosystem packages
control-plane contract
interoperability
SQLite migrations
PostgreSQL migrations
security
```

## Aggregate release-candidate gate

Release Qualification now contains a dedicated:

```text
1.0 release candidate
```

job.

It uses `if: always()` and receives every inherited qualification family as a
dependency.

Its first action is to require every dependency result to be `success`. Only then does it:

```text
download the already-built wheel
install that exact wheel
run the RQ-06 reference contract
run the installed-artifact RC qualifier
```

The final existing `Release qualification gate` then requires the aggregate
release-candidate job itself to succeed.

This produces a two-level decision:

```text
individual qualification evidence
        ↓
1.0 release candidate aggregate gate
        ↓
Release qualification gate
```

## Compatibility blockers

A 1.0 candidate is rejected if the compatibility model contains either:

```text
deprecated
remove-before-1.0
```

subjects.

Internal implementation modules remain internal and are not blockers.

## Promotion policy

The RC freezes this promotion rule:

```text
same-qualified-code-version-metadata-only
```

After `0.9.0rc2` is qualified, promotion to `1.0.0` must not add:

```text
new workflow semantics
new executor behavior
new persistence behavior
new API surface
new plugin protocol
new configuration semantics
new runtime capability
```

Normal 1.0 promotion may update only release-facing metadata required to represent the
same qualified implementation as stable.

RC1 exposed an Ecosystem SDK compatibility ceiling defect: the v1 SDK window ended at
`<1.0`, excluding the intended stable target. RC2 corrects that public compatibility
metadata to `>=0.8.0b1,<2.0` and requalifies the complete release corpus.

If a later RC reveals another functional or compatibility defect, the fix belongs to
another release-candidate iteration before 1.0.

## Manual publication decision

Software license selection remains an explicit project/legal decision:

```text
software_license
```

RQ-06 does not invent a license or silently infer one.

The absence of that choice does not falsify technical RC qualification, but the decision
is recorded as manual release work before a public 1.0 publication.

## Candidate artifact

The candidate version is:

```text
0.9.0rc2
```

Its distribution still follows the RQ-05 contract:

```text
pure-Python wheel
source distribution
Python >= 3.11
upgrade baseline = stable 0.8.0
```

## Tag qualification

Release Qualification already runs for version tags.

For this candidate:

```text
package version = 0.9.0rc2
expected tag    = v0.9.0rc2
```

A tag/version mismatch fails during release metadata validation.

Tag creation and GitHub/PyPI publication remain separate mutating actions.

## Exit criteria

```text
package version = 0.9.0rc2
Release-Candidate Contract v1 targets 1.0.0
RQ-01 through RQ-05 remain contract v1 / target 1.0.0
no deprecated compatibility subject
no remove-before-1.0 compatibility subject
all inherited qualification families are required
installed wheel passes RQ-06 reference contract
installed wheel passes RC qualifier
regular CI is green
Release Qualification is green
aggregate 1.0 release-candidate gate is green
final Release qualification gate is green
promotion policy is same-qualified-code-version-metadata-only
```

## After RQ-06

If the candidate remains unchanged after qualification:

```text
0.9.0rc2 qualified code
        ↓
release metadata promotion only
        ↓
1.0.0
```

If a functional correction is required:

```text
0.9.0rc2
   ↓
fix
   ↓
0.9.0rc2
   ↓
full RQ-06 qualification again
   ↓
1.0.0
```
