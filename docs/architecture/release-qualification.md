# Release Qualification and Upgrade Matrix

Status: M46 completed in 0.7.0b1; qualified baseline: 0.7.0

## Purpose

M46 converts the compatibility work from M41 through M45 into a release-facing,
artifact-oriented qualification pipeline.

The ordinary CI answers:

~~~text
Does the checked-out source tree pass its quality and runtime tests?
~~~

Release Qualification answers:

~~~text
Can the package we are about to distribute be built, installed, upgraded, and consumed
without violating the compatibility contracts we have frozen?
~~~

Both are required.

## Release qualification contract

~~~text
RELEASE_QUALIFICATION_CONTRACT_VERSION = "1"
~~~

The contract aggregates:

~~~text
package version
supported Python versions
CLI machine contract version
RunManifest schema version
Plugin API version
Persistence schema contract version
migration head
~~~

For the stable 0.7.0 baseline:

~~~text
Python              3.11 / 3.12 / 3.13
CLI machine         1
RunManifest         1
Plugin API          1
Persistence schema  1
Migration head      0003_retry_eligible_at
~~~

## Workflow

The dedicated GitHub Actions workflow is:

~~~text
.github/workflows/release-qualification.yml
~~~

It runs on:

~~~text
pull requests targeting main
manual workflow_dispatch
version tags matching v*
~~~

The workflow has read-only repository permissions and does not publish packages.

## Qualification graph

~~~text
Release metadata
      │
      ├──────────────┐
      ▼              ▼
Build artifacts    Contract snapshots
      │              │
      ▼              ├── SQLite upgrade matrix
Artifact installs    ├── PostgreSQL upgrade matrix
      │              └── Security gates
      └──────────────┬───────────────
                     ▼
          Release qualification gate
~~~

## Release metadata gate

The source tree must satisfy:

~~~text
pyproject project.version exists
docs/releases/<version>.md exists
release note starts with "# PyWorkflowKit <version>"
CHANGELOG.md mentions <version>
tag, when present, equals v<version>
~~~

The reusable checker is:

~~~text
scripts/verify_release_metadata.py
~~~

Manual use:

~~~bash
python scripts/verify_release_metadata.py
python scripts/verify_release_metadata.py --tag v0.7.0b1
python scripts/verify_release_metadata.py --print-version
~~~

## Artifact build

The release workflow builds both:

~~~text
wheel
sdist
~~~

Then performs:

~~~text
twine check
SHA-256 checksum generation
artifact upload to the workflow run
~~~

These are qualification artifacts, not a package publication.

## Artifact installation matrix

The built wheel is installed on:

~~~text
Python 3.11
Python 3.12
Python 3.13
~~~

The built sdist is additionally installed on Python 3.13.

Crucially, installed-package verification runs from /tmp rather than the repository
checkout. This prevents an import from accidentally resolving the local src tree and
mistaking source-tree behavior for packaged-artifact behavior.

The installed artifact must expose:

~~~text
correct package version
release qualification contract v1
CLI machine contract v1
Manifest schema v1
Plugin API v1
Persistence schema v1
migration head 0003_retry_eligible_at
packaged migration resources 0001 / 0002 / 0003
working pyworkflow version command
~~~

## Contract snapshots

The full reference acceptance corpus is part of release qualification.

This includes the executable freezes introduced by:

~~~text
M41 public compatibility baseline
M42 deprecation semantics
M43 CLI machine contract
M44 plugin ecosystem contract
M45 migration lineage
M46 release qualification metadata
~~~

## Upgrade matrix

SQLite historical migration tests run on every supported Python:

~~~text
3.11
3.12
3.13
~~~

PostgreSQL 15 historical migration tests also run on every supported Python.

The tested upgrade origins remain:

~~~text
fresh
0001_runtime_metadata
0002_task_output_checkpoints
0003_retry_eligible_at
~~~

Historical-data preservation remains part of the M45 tests consumed by this matrix.

## Security gate

Release qualification repeats the blocking release-relevant security checks:

~~~text
Bandit
pip-audit
detect-secrets
~~~

A release candidate is not qualified merely because ordinary unit tests pass.

## Final gate

The Release qualification gate depends on every qualification family.

It can succeed only when all of these succeed:

~~~text
release metadata
artifact build
artifact install matrix
reference contracts
SQLite upgrade matrix
PostgreSQL upgrade matrix
security gates
~~~

This provides a single branch-protection / release-readiness signal.

## Tag behavior

For a tagged qualification:

~~~text
package version = 0.7.0
tag             = v0.7.0
~~~

Any mismatch fails before artifact qualification.

M46 validates tags; it does not create them automatically.

## Publication boundary

M46 intentionally does not:

~~~text
upload to PyPI
create a GitHub Release
push tags
sign artifacts
publish containers
~~~

Those are mutating distribution actions and remain separate from qualification until
the stable 0.7 release process is explicitly promoted.

## Next

Transverse 0.7 qualification, then 0.7.0 stable.
