# PyWorkflowKit — Migration V1 → V2

## Purpose

PyWorkflowKit 2.0 replaces the historical 1.x package root with the canonical V2
authoring, planning, runtime and persistence contracts.

Migration is explicit and one-way:

```text
V1 model
   ↓ explicit semantic conversion
pyworkflowkit._compat.v1_to_v2
   ↓
V2 model
```

PyWorkflowKit does not provide a generic V2→V1 downgrade path.

## Package-root change

The V2 root is intentionally narrow:

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

Historical 1.x root behavior remains available during migration only through:

```python
from pyworkflowkit._compat import v1_root
```

This compatibility facade is explicit. It is not part of the V2 root contract.

## Authoring migration

V1 definitions use the historical domain/declarative model. V2 definitions use:

```python
from pyworkflowkit import TaskDefinition, WorkflowDefinition
```

The migration helpers under `pyworkflowkit._compat.v1_to_v2` preserve semantic
information where a deterministic V2 equivalent exists and fail closed where ownership is
ambiguous.

Notably:

- V1 workflow parameters are not guessed into V2 task inputs;
- non-string V1 metadata is not silently coerced into the stricter portable V2 contract;
- legacy executor key `local` maps explicitly to the V2 inline executor identity;
- V1 HARD timeout semantics are not automatically claimed as equivalent when the V2
  execution boundary cannot prove the same behavior.

## Runtime identity migration

V2 execution identity is explicit and type-distinct:

```text
WorkflowRunId
TaskRunId
TaskAttemptId
CorrelationId
```

Migration of persisted execution evidence requires the source identifiers and semantic
fingerprints needed to preserve identity.

The migration contract fails closed when required information is missing, including:

- workflow definition fingerprint;
- execution-plan fingerprint;
- correlation identity;
- external attempt ownership where the V1 evidence is ambiguous;
- task-attempt creation time where required by V2 evidence.

## Retry history

V2 retry ownership is attempt-scoped:

```text
TaskRun
  ├── TaskAttempt #1
  ├── TaskAttempt #2
  └── TaskAttempt #N
```

Migration requires contiguous attempt numbers. Missing or ambiguous attempt history is not
invented.

Legacy failure fields and `retry_eligible_at` evidence are preserved as evidence when
available.

## External executions

V2 persists external execution ownership through `ExternalRunRef`.

For migrated evidence:

- provider and external run identity must remain explicit;
- external run kind is not guessed;
- unknown outcomes require reconciliation before retry;
- blind retry of an ambiguous external outcome is forbidden.

## Sibling frameworks

PyIngestKit and PyTransformKit remain optional siblings. PyWorkflowKit does not import
either framework as a core dependency.

The stable integration contract versions are:

```text
PyIngestKit integration contract     1
PyTransformKit integration contract  1
```

Boundary values are dependency-free mirrors and portable references. Raw credentials are
not accepted; opaque credential references may cross the boundary.

Retry ownership remains separated:

```text
PyWorkflowKit
  owns workload-attempt retry

PyIngestKit / PyTransformKit
  own provider-internal retry
```

## Persistence upgrade

The stable migration head is:

```text
0005_v2_task_output_checkpoints
```

The migration sequence includes:

```text
0001_runtime_metadata
0002_task_output_checkpoints
0003_retry_eligible_at
0004_v2_runtime_metadata
0005_v2_task_output_checkpoints
```

SQLite and PostgreSQL upgrade paths are blocking release-qualification gates on Python
3.11, 3.12 and 3.13.

## Recommended application migration sequence

1. Upgrade application imports away from the 1.x package root.
2. Use `pyworkflowkit._compat.v1_root` only where a temporary V1 bridge is still needed.
3. Convert definitions with the explicit V1→V2 migration helpers.
4. Resolve every fail-closed diagnostic rather than coercing unsupported semantics.
5. Upgrade durable metadata to migration head `0005_v2_task_output_checkpoints`.
6. Validate the V2 `ExecutionPlan` and definition fingerprints.
7. Reconcile ambiguous external executions before enabling retries.
8. Run application-specific recovery and restart scenarios.
9. Remove the V1 compatibility facade once the application is fully V2-native.

## Compatibility guarantee

PyWorkflowKit 2.0 freezes:

- the canonical V2 root;
- state vocabularies;
- execution identity types;
- Executor and MetadataStore contracts;
- versioned non-executable wire contracts;
- explicit plugin activation;
- optional sibling integration boundaries.

Compatibility code exists to make migration explicit, not to make V1 and V2
interchangeable.
