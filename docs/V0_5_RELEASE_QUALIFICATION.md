# PyWorkflowKit 0.5.0 — Transverse Release Qualification

Date: 2026-09-26

## Objective

Promote the completed 0.5 development line to stable `0.5.0` without adding new
functional scope.

The qualification consolidates M32 through M36:

```text
M32 ProcessExecutor
M33 AsyncExecutor
M34 SubprocessExecutor
M35 Observability Plugins
M36 Security Hardening
```

## Release principle

The release candidate is acceptable only if the feature line works as one coherent
runtime and the contracts inherited from 0.1-0.4 remain stable.

No qualification change may silently alter:

```text
domain lifecycle semantics
RetryEngine authority
RuntimeEvent taxonomy
RunManifest schema
metadata persistence schema
Plugin API version
package-root public surface
PyIngestKit atomic-workload boundary
scheduler/control-plane boundary
```

## Transverse contract checks

`tests/reference/test_v0_5_release_qualification.py` freezes the cross-release contract.

### Executor capability matrix

```text
local       parallel=false timeout=none cancellation=none        async=false
thread      parallel=true  timeout=soft cancellation=none        async=false
process     parallel=true  timeout=hard cancellation=hard        async=false
async       parallel=true  timeout=soft cancellation=cooperative async=true
subprocess  parallel=true  timeout=hard cancellation=hard        async=false
```

### Public API

The package-root `__all__` remains intentionally small.

Advanced executors are not promoted to package-root imports merely because they are
stable within 0.5.

### Portable evidence

```text
RunManifest schema = 1
Plugin API          = 1
```

Neither version is changed by 0.5.0.

## Functional qualification

The reference suite covers:

- process isolation and transport;
- hard process timeout/cancellation;
- async fan-out and cooperative cancellation;
- subprocess argv safety and captured evidence;
- subprocess hard timeout/cancellation;
- subprocess environment isolation;
- executable/cwd/env/I/O policy enforcement;
- post-commit observability dispatch;
- observability sink failure isolation;
- external observability redaction;
- existing sequential, persistence, manifest, plugin, CLI, and concurrency reference
  scenarios.

## Persistence qualification

The release continues to qualify:

```text
MemoryMetadataStore
SQLiteMetadataStore
PostgreSQLMetadataStore
Alembic baseline migration
installed-wheel migration resources
```

No 0.5 feature requires a persistence-schema migration.

## Security qualification

Blocking CI security gates:

```text
Bandit
pip-audit
detect-secrets
```

GitHub Dependency Review is wired into pull requests. Full enforcement depends on the
repository Dependency Graph capability being enabled; platform unavailability is
reported explicitly rather than misrepresented as a dependency vulnerability.

## Build qualification

The release build must prove all three version surfaces are exactly `0.5.0`:

```text
importlib.metadata.version("pyworkflowkit")
pyworkflowkit.__version__
pyworkflow version
```

The wheel must install cleanly and contain migration resources.

## Supported Python

```text
3.11
3.12
3.13
```

All supported versions run the complete pytest suite with branch coverage >= 90%.

## Release decision

Promotion to `0.5.0` is permitted only when every blocking CI job on the release HEAD
is green.

The release branch is not a feature branch. Any failure discovered during qualification
must be corrected narrowly and requalified on the same final HEAD.

## Post-release roadmap

```text
0.5.0
  Hardened multi-executor runtime
        ↓
0.6.x
  Recovery / Resume / Reconciliation
        ↓
0.7-0.9
  Compatibility / Ecosystem / Stabilization
        ↓
1.0.0
  Stable embedded runtime core contract
```
