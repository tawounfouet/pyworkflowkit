# PyWorkflowKit Packaging & Distribution

Status: RQ-05 — 0.9.0b2

## Objective

RQ-05 qualifies the exact artifacts that a package index or downstream installer will
consume.

The milestone adds no runtime capability. It makes package metadata, artifact contents,
installation behavior, optional extras, source-to-wheel reproducibility, and the stable
upgrade path executable release contracts.

## Distribution Contract

The machine-readable contract lives in:

```text
pyworkflowkit.contracts.distribution
```

with:

```python
DISTRIBUTION_CONTRACT_VERSION = "1"
DISTRIBUTION_TARGET_RELEASE = "1.0.0"
PACKAGE_NAME = "pyworkflowkit"
PYTHON_REQUIRES = ">=3.11"
```

The stable upgrade baseline is frozen as:

```text
version = 0.8.0
commit  = 70cf048ca7264c9c6caf79fd28801f0db50973c5
```

## Build backend

The build backend requirement is explicitly bounded:

```text
hatchling>=1.27,<2
```

The package continues to use:

```text
build-backend = hatchling.build
```

The build backend is therefore no longer an unconstrained environment input.

## Runtime dependencies

RQ-05 freezes the current direct runtime dependency ranges:

```text
alembic>=1.16,<2
pydantic>=2.13,<3
pydantic-settings>=2.11,<3
sqlalchemy>=2.0,<3
typer>=0.12,<1
```

This is not a dependency lock. Applications remain free to resolve compatible versions
inside those supported ranges.

## Optional extras

Published extras remain:

```text
postgres
dev
security
```

The development tools now also use explicit compatibility ranges so the distribution
metadata does not expose unbounded tool requirements.

Release Qualification creates isolated environments for each published extra and requires
`pip check` to succeed.

## Project metadata

RQ-05 qualifies well-known project URLs:

```text
Homepage
Documentation
Repository
Issues
Changelog
Security
```

The README remains the long package description. Its RQ-04 guide links are now absolute
GitHub links so the same README remains navigable when rendered outside the repository.

## Wheel contract

The wheel must be a pure-Python artifact:

```text
py3-none-any
Root-Is-Purelib: true
```

Required resources include:

```text
pyworkflowkit/__init__.py
pyworkflowkit/py.typed
pyworkflowkit/migrations/versions/0001_runtime_metadata.py
pyworkflowkit/migrations/versions/0002_task_output_checkpoints.py
pyworkflowkit/migrations/versions/0003_retry_eligible_at.py
```

Repository-only material must not leak into the wheel:

```text
.github/
docs/
examples/
tests/
typing-fixtures/
ecosystem-template/
reference-integrations/
qualification-integrations/
```

## Source distribution contract

RQ-05 makes the sdist scope explicit instead of relying on implicit VCS inclusion.

The source distribution contains only:

```text
pyproject.toml
README.md
CHANGELOG.md
SECURITY.md
src/pyworkflowkit/**
generated PKG-INFO
```

This is sufficient to rebuild the package while excluding CI configuration, tests,
examples, documentation corpus, and integration fixtures from the published source
archive.

## Wheel/sdist equivalence

Release Qualification performs:

```text
repository source
    ↓
official wheel + sdist
    ↓
pip wheel from official sdist
    ↓
rebuilt wheel
```

The official and rebuilt wheels must agree on:

```text
Name
Version
Requires-Python
Requires-Dist
console scripts
all pyworkflowkit package paths
```

This proves that the sdist is a complete source for the distributed Python package.

## Clean installation

A fresh virtual environment installs the official wheel using normal dependency
resolution and must satisfy:

```text
pip check
pyworkflow version
pyworkflowkit version
```

Both console names must report the current package version.

## Extras installation

Separate clean virtual environments install:

```text
pyworkflowkit[postgres]
pyworkflowkit[dev]
pyworkflowkit[security]
```

Each environment must pass `pip check`. The PostgreSQL extra additionally proves that
`psycopg` is importable.

## Stable upgrade path

The qualification pipeline checks out the exact 0.8.0 stable commit, builds its wheel,
and executes:

```text
clean environment
    ↓
install 0.8.0 wheel
    ↓
assert runtime version = 0.8.0
    ↓
pip install --upgrade current 0.9.0b2 wheel
    ↓
pip check
    ↓
assert runtime + CLI version = 0.9.0b2
```

Persistence schema upgrades remain covered separately by the SQLite/PostgreSQL migration
matrix; RQ-05 focuses on package/distribution upgrade semantics.

## License boundary

RQ-05 does not invent or select a software license. The repository currently has no
explicit license metadata, and choosing one is a project/legal decision rather than a
packaging inference.

This does not prevent the technical artifact qualification in RQ-05, but licensing can be
reviewed explicitly before the final 1.0 publication decision.

## Release qualification

Regular CI proves:

```text
build wheel + sdist
twine check
rebuild wheel from sdist
artifact metadata/content contract
RQ-05 reference contract
```

Release Qualification additionally proves:

```text
clean wheel installation
published extras installation
stable 0.8.0 → current upgrade
wheel/sdist equivalence
installed RQ-05 contract
```

## Exit criteria

```text
package version = 0.9.0b2
Distribution Contract v1 targets 1.0.0
build backend bounded
runtime dependency ranges frozen
published extras explicit and installable
well-known project URLs present
README distribution links are index-safe
wheel is pure Python
wheel contains py.typed and migration resources
wheel excludes repository-only files
sdist scope is explicit and minimal
wheel rebuilt from sdist is equivalent
clean core install passes pip check
all published extras pass pip check
0.8.0 -> 0.9.0b2 package upgrade succeeds
regular CI is green
built-artifact Release Qualification gate is green
```

## Next

RQ-06 — 1.0 Release Qualification.
