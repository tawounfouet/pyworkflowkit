# PyWorkflowKit 0.7 — Compatibility and Stabilization Roadmap

Date: 2026-09-27

## Objective

The 0.7 line begins the hardening phase between the completed recovery runtime in 0.6
and the stable 1.0 contract.

The implementation roadmap already defines 0.7-0.9 as:

~~~text
Compatibility / Ecosystem / Stabilization
~~~

and identifies the main 1.0 blockers as unstable public contracts, undocumented
compatibility breaks, missing migration policy, missing security baseline, and missing
release automation.

0.7 therefore does not start by adding another runtime feature. It starts by making
compatibility explicit and executable.

## Product rule

~~~text
0.6 proved recovery
      ↓
0.7 freezes core compatibility expectations
      ↓
0.8 hardens ecosystem interoperability
      ↓
0.9 performs 1.0 release-candidate stabilization
      ↓
1.0 freezes the stable embedded runtime contract
~~~

## 0.7 milestone sequence

### M41 — Compatibility Contract Foundation — 0.7.0a1 ✅

Freeze the baseline contract inventory:

~~~text
package-root Python API
lifecycle enums
RuntimeEvent taxonomy
MetadataStore protocol
UnitOfWork protocol
CLI command names
CLI stable exit codes
RunManifest schema version
Plugin API version
supported Python baseline
migration head
~~~

M41 is intentionally contract/test/documentation work. It adds no new workflow state,
executor semantics, persistence behavior, or scheduling capability.

### M42 — Deprecation Policy and Compatibility Warnings — 0.7.0a2 ✅

Introduce the mechanics needed to evolve a pre-1.0 package without silent breakage:

~~~text
deprecation categories
warning classes
replacement guidance
minimum deprecation window
removal rules
security/invariant emergency exception
tests proving warnings are emitted once and at the correct boundary
~~~

### M43 — CLI and Machine Contract Freeze — 0.7.0a3 ✅

Freeze the automation-facing CLI surface:

~~~text
commands
exit codes
--json payload keys
error payload shape
version output
manifest JSON behavior
backward-compatible additions policy
~~~

### M44 — Plugin Ecosystem Compatibility — 0.7.0a4 ✅

Prepare third-party adapters to rely on explicit plugin compatibility:

~~~text
PluginDescriptor contract
Plugin API negotiation
entry-point group freeze
executor/metadata/workload/event category conformance
plugin compatibility diagnostics
third-party contract fixtures
~~~

### M45 — Persistence and Migration Compatibility — 0.7.0a5 ✅

Turn durable-state compatibility into an explicit upgrade promise:

~~~text
migration policy
supported upgrade origins
fresh install vs upgrade matrix
SQLite/PostgreSQL equivalence
old metadata readability
forward-only migration rules
backup/rollback documentation
~~~

### M46 — Release Automation and Upgrade Matrix — 0.7.0b1 ✅

Automate the pre-release qualification needed for 1.0:

~~~text
version consistency
build/install smoke
supported Python matrix
SQLite upgrade matrix
PostgreSQL upgrade matrix
reference acceptance
security gates
contract snapshots
release-note gate
~~~

## Stable 0.7 qualification ✅

Completed after M46:

~~~text
M41 Compatibility Foundation       ✅
M42 Deprecation                     ✅
M43 CLI contracts                   ✅
M44 Plugin compatibility            ✅
M45 Persistence/migrations          ✅
M46 Release automation              ✅
        ↓
Transverse 0.7 qualification        ✅
        ↓
0.7.0 stable                        ✅
~~~

## Scope exclusions

0.7 does not own:

~~~text
scheduler
background daemon
distributed coordinator
worker fleet
web UI
RBAC/IAM
multi-tenant control plane
new business-specific workload semantics
exactly-once claims
~~~

A feature proposal that belongs to those areas is not accepted merely because the
project is in a hardening phase.

## Exit condition for the line

0.7 is complete because a maintainer can now answer, with executable evidence:

Which PyWorkflowKit contracts may an application or adapter rely on, how are changes
announced, and how do we prove that an upgrade did not silently break them?


## Final status

~~~text
0.7.0 stable
    ↓
0.8 Ecosystem Interoperability
~~~

The next canonical roadmap is:

~~~text
docs/V0_8_ECOSYSTEM_INTEROPERABILITY_ROADMAP.md
~~~
