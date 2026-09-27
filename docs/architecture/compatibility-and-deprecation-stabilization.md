# PyWorkflowKit Compatibility & Deprecation Stabilization

Status: RQ-02 — 0.9.0a2

## Objective

RQ-02 turns the pre-1.0 compatibility policy into executable evidence.

The milestone does not add workflow capabilities. It classifies the contracts already
present in PyWorkflowKit and removes ambiguity about what is stable, deprecated, internal,
or scheduled for removal before 1.0.

## Compatibility statuses

```text
stable
deprecated
internal
remove-before-1.0
```

The machine-readable contract lives in:

```text
pyworkflowkit.compatibility
```

with:

```python
COMPATIBILITY_CONTRACT_VERSION = "1"
COMPATIBILITY_TARGET_RELEASE = "1.0.0"
```

## Stable compatibility subjects

RQ-02 treats the following compatibility subjects as stable:

```text
RQ-01 frozen public facades
CLI machine contract v1
console script: pyworkflow
console script alias: pyworkflowkit
RuntimeSettings precedence/defaults
facade-exported exception types
RunManifest schema v1
Plugin API v1
persistence schema v1
published migration history through 0003_retry_eligible_at
control-plane provider contract v1
Ecosystem SDK contract v1
external-workload contract v1
portable reference contract v1
observability interoperability contract v1
deprecation policy
```

## Internal module paths

These module families remain implementation details unless a symbol is re-exported by one
of the frozen facades:

```text
pyworkflowkit.adapters.*
pyworkflowkit.application.*
pyworkflowkit.cli
pyworkflowkit.cli_contract
pyworkflowkit.compatibility
pyworkflowkit.config
pyworkflowkit.contracts.*
pyworkflowkit.declarative
pyworkflowkit.domain.*
pyworkflowkit.errors
pyworkflowkit.migrations.*
pyworkflowkit.ports.*
pyworkflowkit.release_contract
```

This distinction is important:

```text
stable symbol through frozen facade
    !=
stable implementation module path
```

For example, `RunContext` is stable when consumed from a frozen facade, while the
internal module path that currently defines it may evolve before or after 1.0 according
to compatibility policy.

## Exceptions

The 1.0-stable exception guarantee is deliberately narrow.

Stable exception imports are currently the exception types re-exported by frozen facades:

```text
pyworkflowkit.PyWorkflowKitError

pyworkflowkit.control_plane.ControlPlaneProviderError
pyworkflowkit.control_plane.ControlPlaneCapabilityError
```

The implementation module `pyworkflowkit.errors` remains the definition location but is
not itself promoted to an independently frozen facade by RQ-02.

## CLI aliases

Both documented console entry points remain stable:

```text
pyworkflow    -> pyworkflowkit.cli:main
pyworkflowkit -> pyworkflowkit.cli:main
```

The second name is therefore a supported alias, not an accidental duplicate script.

## Configuration

The source precedence contract is frozen as:

```text
explicit overrides
    >
TOML
    >
environment
    >
defaults
```

The default configuration values qualified by RQ-02 are:

```text
runtime.workspace                  = .pyworkflow
metadata.backend                   = memory
metadata.sqlite_path               = state/pyworkflow.sqlite3
metadata.sqlite_busy_timeout_ms    = 5000
metadata.sqlite_wal                = true
metadata.postgres_dsn              = null
metadata.postgres_pool_size        = 5
metadata.postgres_max_overflow     = 10
metadata.postgres_application_name = pyworkflowkit
```

A change to these defaults after 1.0 is therefore a compatibility decision rather than an
incidental refactor.

## Deprecation policy

RQ-02 starts with:

```text
ACTIVE_DEPRECATIONS = ()
deprecated subjects = ()
remove-before-1.0 subjects = ()
```

A normal deprecation introduced during 0.9 may target 1.0, but it may not be removed
inside the same 0.9 release line.

The existing emergency exception remains available only with an explicit concrete reason.

## Ecosystem SDK compatibility correction

RQ-02 identified a real contradiction inherited from the 0.8 line.

The Ecosystem SDK remained contract v1, but its compatibility window was still:

```text
>=0.8.0b1,<0.9
```

That range excludes the current 0.9 runtime even though none of the relevant contracts
changed.

RQ-02 corrects the compatibility window to:

```text
>=0.8.0b1,<1.0
```

and updates the ecosystem template, reference packages, qualification fixtures, and
conformance assertions accordingly.

The contract therefore becomes:

```text
series            = 0.8-0.9
minimum           = 0.8.0b1
maximum_exclusive = 1.0
SDK contract      = 1
```

## Release qualification

RQ-02 is qualified twice.

Regular CI validates the source/install development environment:

```text
compatibility classification
contract versions
console aliases
configuration defaults
exception exports
internal/public boundary
deprecation/removal state
ecosystem compatibility
```

Release Qualification additionally validates the built wheel and installs the ecosystem
template using normal dependency resolution against that wheel.

This specifically prevents an integration dependency range from silently excluding the
current release line again.

## Exit criteria

```text
0.9.0a2 metadata consistent
compatibility contract v1
all versioned contracts remain v1
no active deprecation
no remove-before-1.0 subject
CLI aliases stable
RuntimeSettings defaults stable
exception facade boundary explicit
implementation module families classified internal
Ecosystem SDK v1 supports 0.8 and 0.9
built-wheel dependency resolution succeeds
regular CI green
Release Qualification green
```

## Next

RQ-03 — Typing & Static Contracts.
