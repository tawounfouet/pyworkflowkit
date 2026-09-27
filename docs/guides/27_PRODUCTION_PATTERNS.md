# 27 — Production Patterns

## What you will learn

You will assemble the operational patterns that make an embedded workflow runtime reliable
without pretending it is a full orchestration platform.

## Prefer durable metadata when history matters

Use SQLite for durable local execution or PostgreSQL when the deployment requires a
server-backed multi-writer store.

## Keep workflow definitions versioned

Do not silently mutate an already-used workflow version. Treat executable behavior as an
explicitly versioned contract.

## Make retries intentional

Retry transient failures only. For external runtimes, designate exactly one retry owner.

## Prefer portable recovery evidence

For workflows expected to survive process failure, prefer durable references and
JSON-portable dependency outputs over opaque in-memory Python objects.

Useful evidence includes:

```text
ArtifactReference
ExternalRunRef
portable task output checkpoints
RuntimeEvent
RunManifest
```

## Protect secrets

- inject DSNs/secrets through environment or a secret manager;
- use redacted diagnostic views;
- avoid secret-bearing workflow metadata;
- remember that external observability is a data boundary.

## Treat plugins as trusted code

Plugin discovery is explicit and compatibility-aware, but PyWorkflowKit is not a sandbox
for untrusted Python.

## Use machine contracts for automation

```bash
pwk ... --json
```

Do not scrape human Rich output.

## Keep platform responsibilities outside the runtime

Scheduling, centralized IAM, fleet management, Web UI, and platform governance belong in a
control plane such as Ochestrix or another external system.

## Operational checklist

Before production use, verify:

- deterministic definition and versioning;
- durable metadata backend;
- retry ownership;
- executor capability compatibility;
- secret handling;
- observability sink policy;
- recovery/reconciliation expectations;
- installed package qualification;
- stable CLI/API contracts used by automation.

## Next chapter

Finish with [99 — Complete Reference Application](99_COMPLETE_REFERENCE_APPLICATION.md).
