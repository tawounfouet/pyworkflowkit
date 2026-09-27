# Release Qualification

Status: active 0.9 → 1.0 release-candidate qualification pipeline.

## Purpose

Ordinary CI answers:

```text
Does the checked-out source tree pass its quality and runtime tests?
```

Release Qualification answers:

```text
Can the exact artifacts we intend to distribute be built, installed, upgraded,
typed, consumed, and exercised without violating the contracts frozen for 1.0?
```

Both are required.

## Release qualification contract

```text
RELEASE_QUALIFICATION_CONTRACT_VERSION = "1"
```

The aggregate snapshot now includes:

```text
package version
supported Python versions
CLI machine contract v1
Developer Experience contract v1
Distribution contract v1
RunManifest schema v1
Persistence schema v1
Plugin API v1
Typing contract v1
migration head
compatibility classification
```

Supported Python versions remain:

```text
3.11
3.12
3.13
```

## Workflow

The dedicated workflow is:

```text
.github/workflows/release-qualification.yml
```

It runs on:

```text
pull requests targeting main
manual workflow_dispatch
version tags matching v*
```

The workflow has read-only repository permissions and does not publish packages.

## Qualification graph

```text
Release metadata
      │
      ├─────────────────────────────────────────────┐
      ▼                                             ▼
Build wheel + sdist                         Source-backed contract gates
      │                                             │
      ├── artifact install 3.11/3.12/3.13          ├── contract snapshots
      ├── public API freeze                         ├── SQLite upgrades
      ├── compatibility/deprecation                 ├── PostgreSQL upgrades
      ├── strict static typing                      └── security
      ├── developer experience
      ├── packaging/distribution
      ├── ecosystem SDK
      ├── reference integrations
      ├── control-plane provider
      └── transverse 0.8 compatibility
                       │
                       ▼
             Release qualification gate
```

## Release metadata

Before artifact qualification:

```text
pyproject project.version exists
docs/releases/<version>.md exists
release note begins with "# PyWorkflowKit <version>"
CHANGELOG.md mentions <version>
tag, when present, equals v<version>
```

The reusable checker is:

```text
scripts/verify_release_metadata.py
```

## Artifact build

The release workflow builds:

```text
wheel
sdist
```

and performs:

```text
twine check
SHA-256 checksum generation
artifact upload to the workflow run
```

The artifacts are qualification inputs, not automatically published releases.

## Artifact installation

The official wheel is installed on:

```text
Python 3.11
Python 3.12
Python 3.13
```

The official sdist is also installed on Python 3.13.

Installed-artifact verification runs away from the source package path and checks the
aggregate release contract, migration resources, PEP 561 marker, and CLI version.

## RQ-01 — Public API

The built wheel must satisfy the frozen public-facade contract targeting 1.0.

## RQ-02 — Compatibility

The built wheel must preserve the compatibility/deprecation classification and ecosystem
compatibility window.

## RQ-03 — Static typing

The built wheel is checked with `mypy --strict` on Python 3.11, 3.12, and 3.13.

A positive external-consumer fixture must pass. An intentionally invalid two-argument
`@task` handler must fail.

## RQ-04 — Developer experience

The built wheel must support the complete first-use journey:

```text
version
validate
plan
run
inspect
events
manifest
SQLite cross-process persistence
public plugin authoring
```

## RQ-05 — Packaging and distribution

The distribution gate validates:

```text
project metadata
well-known project URLs
runtime dependency ranges
published extras
pure-Python wheel tag
wheel file scope
sdist file scope
py.typed
migration resources
console entry points
wheel rebuilt from sdist
clean core install
clean extra installs
pip check
stable 0.8.0 -> current package upgrade
```

The stable upgrade baseline is the exact 0.8.0 commit:

```text
70cf048ca7264c9c6caf79fd28801f0db50973c5
```

Database migration compatibility is still proven separately by the SQLite/PostgreSQL
historical upgrade matrix.

## Security

Blocking release checks remain:

```text
Bandit
pip-audit
detect-secrets
```

## Final gate

The final gate uses `if: always()` and explicitly requires success from every release
qualification family.

No individual green job can qualify a release when another required family fails.

## Tag behavior

For a tagged qualification:

```text
package version = X
tag             = vX
```

A mismatch fails before artifact qualification.

The workflow validates tags; it does not create them.

## Publication boundary

Release Qualification intentionally does not:

```text
upload to PyPI
create a GitHub Release
push tags
select a software license
publish containers
```

Those are separate mutating/project decisions. RQ-05 proves that the artifacts are
technically distributable; RQ-06 will compose all frozen evidence for the 1.0 release
candidate.
