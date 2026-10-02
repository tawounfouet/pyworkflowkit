# PyWorkflowKit V2 — LOT-00 Architecture Baseline

Status: implementation baseline  
Target: PyWorkflowKit 2.0.0  
Baseline source: PyWorkflowKit 1.1.0 at `fd80d697315604a6eb9835908aad55bff16b0c38`

## Purpose

LOT-00 protects the V2 migration before domain or runtime behavior changes.

It establishes:

- semantic package namespaces;
- an explicit V2 namespace/stability registry;
- a target root allowlist;
- optional sibling import ownership;
- a one-way compatibility boundary;
- architecture tests;
- a V1 → V2 migration ledger;
- Customer 360 and migration-evidence fixture baselines.

LOT-00 is intentionally additive. The stable 1.1 root API remains unchanged until
later lots deliberately replace individual contracts.

## V2 semantic namespaces

The target user-facing grammar is:

```text
pyworkflowkit.authoring
pyworkflowkit.planning
pyworkflowkit.runtime
pyworkflowkit.states
pyworkflowkit.policies
pyworkflowkit.executors
pyworkflowkit.persistence
pyworkflowkit.serialization
pyworkflowkit.lineage
pyworkflowkit.diagnostics
pyworkflowkit.plugins
pyworkflowkit.integrations
```

`pyworkflowkit.control_plane` remains provisional.

`pyworkflowkit.ecosystem` is classified as a compatibility facade and must not receive
new canonical V2 functionality.

## Transitional facade policy

The new namespaces initially re-export qualified 1.1 implementations when the semantic
owner already matches.

This is deliberate:

```text
new public semantic path
        ↓
existing qualified implementation
        ↓
later lot replaces/adapts implementation
```

A transitional re-export must not create a second domain implementation.

## Root migration policy

The 1.1 root remains frozen during LOT-00.

The V2 target root is intentionally narrower and is recorded by
`V2_ROOT_TARGET_ALLOWLIST`.

Notable future changes include:

```text
RunContext
    removed from canonical root

TaskResult
    split into precise result contracts

TimeoutMode
    replaced by TimeoutPolicy

WorkflowResult
    added

WorkflowRunId / TaskRunId / TaskAttemptId
    promoted as canonical runtime identities
```

## Sibling import boundary

PyIngestKit and PyTransformKit remain optional.

Canonical rule:

```text
pyingestkit
    may only be imported by
    pyworkflowkit.integrations.pyingestkit...

pytransformkit
    may only be imported by
    pyworkflowkit.integrations.pytransformkit...
```

The base package import must never require either sibling.

## Compatibility boundary

`pyworkflowkit._compat` is a migration-only namespace.

Allowed dependency direction:

```text
legacy consumer
    ↓
_compat
    ↓
canonical implementation
```

Forbidden:

```text
canonical V2 implementation
    ↓
_compat
```

## LOT-00 migration ledger

| V1 capability | V2 owner | LOT-00 action | Later lot |
|---|---|---|---|
| `domain.definitions` | `authoring` | facade | LOT-02 |
| `declarative` | `authoring` | facade | LOT-02 |
| `application.planning` | `planning` | facade | LOT-03 |
| `domain.graph` | `planning._graph` | classify internal | LOT-03 |
| runtime entities | `runtime` | facade | LOT-04 |
| lifecycle enums | `states` | facade | LOT-04 |
| retry/failure/timeout values | `policies` | facade | LOT-07/08 |
| executor port/adapters | `executors` | facade/classify | LOT-06/13/14 |
| MetadataStore/adapters | `persistence` | facade | LOT-05/10/17 |
| strict schemas/codecs | `serialization` | facade | LOT-15 |
| execution lineage | `lineage` | facade | LOT-12 |
| inspection | `diagnostics` | facade | LOT-11/12 |
| `ecosystem` | compatibility only | no new V2 code | LOT-21 |
| PyIngestKit integration | qualified integration | preserve current boundary | LOT-18 |
| PyTransformKit integration | qualified integration | reserve boundary | LOT-19 |
| `compatibility.py` | `_compat` | one-way access path | LOT-21 |

## Architecture gates

LOT-00 tests enforce:

- every transitional V2 semantic namespace has explicit `__all__`;
- exported names are unique and resolvable;
- the stable 1.1 root export set is unchanged;
- the V2 architecture snapshot is deterministic and JSON serializable;
- sibling imports cannot leak into core modules;
- canonical V2 facades cannot depend on `pyworkflowkit._compat`;
- `pyworkflowkit.ecosystem` is not considered canonical V2.

## Exit criteria

LOT-00 is complete when:

```text
semantic namespace skeleton exists
architecture metadata exists
architecture tests pass
base package remains sibling-independent
1.1 root remains regression-safe
compatibility boundary is one-way
migration evidence is recorded
Customer 360 fixture baseline exists
clean package qualification passes
```

No LOT-01 domain semantic change is included in LOT-00.
