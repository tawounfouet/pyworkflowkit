# PyWorkflowKit V2 — LOT-01 Execution Identity and Shared Boundary Values

Status: implementation baseline  
Target milestone: `2.0.0a1`  
Depends on: LOT-00 Repository and Architecture Baseline

## Purpose

LOT-01 establishes the canonical V2 values used to identify, correlate and explain
workflow execution across process and framework boundaries.

The governing rule is:

```text
native execution identity
    !=
correlation identity
    !=
external provider identity
```

## Canonical execution identifiers

PyWorkflowKit V2 now owns runtime-distinct immutable identifiers:

```text
WorkflowRunId
TaskRunId
TaskAttemptId
CorrelationId
```

Each identifier supports:

```python
identifier = WorkflowRunId.new()
identifier = WorkflowRunId.parse("W-42")
text = str(identifier)
```

The textual value is opaque. The implementation deliberately accepts opaque strings
rather than forcing one storage scheme; `new()` currently produces UUID text.

The runtime type is authoritative:

```text
WorkflowRunId("same")
    !=
TaskRunId("same")
    !=
TaskAttemptId("same")
    !=
CorrelationId("same")
```

There is intentionally no universal `RunId`.

## Transitional coexistence with 1.1 identifiers

PyWorkflowKit 1.1 uses `NewType(str)` identifiers under:

```text
pyworkflowkit.domain.ids
```

LOT-01 does not mutate those types because the frozen 1.1 root and persistence code still
depend on them.

The V2 canonical identities live under:

```text
pyworkflowkit.runtime
```

Migration direction:

```text
1.1 domain.ids
    ↓
LOT-01 V2 typed IDs
    ↓
LOT-04 runtime entities
    ↓
LOT-05/10/17 persistence
    ↓
LOT-22 root/API freeze
```

No new V2 implementation should adopt the legacy NewType identifiers.

## CorrelationContext

`CorrelationContext` is the portable correlation DTO.

It may carry:

```text
correlation_id
causation_id
parent_execution_id

workflow_run_id
task_run_id
task_attempt_id

ingestion_run_id
transformation_execution_id

trace_id
span_id
```

This allows:

```text
WorkflowRun W-42
    ↓
TaskAttempt TA-3
    ↓
TransformationExecution T-913
```

to share:

```text
CorrelationId C-42
```

without pretending that `W-42`, `TA-3` and `T-913` are the same identity.

## WorkflowExecutionReference

`WorkflowExecutionReference` is the minimal portable reference another bounded context
needs in order to refer to a WorkflowRun.

It contains:

```text
workflow_run_id
workflow_definition_id
status?
started_at?
owner
namespace
contract_version
```

It does not expose TaskRun or TaskAttempt internals.

## ExternalRunRef

LOT-01 introduces the V2 boundary form of `ExternalRunRef`.

It carries:

```text
provider
external_run_id
kind
status_hint?
status_locator?
correlation_id?
causation_id?
metadata
namespace
contract_version
```

The value is explicitly authority-neutral.

Possessing an ExternalRunRef does not grant the ability to:

```text
cancel
retry
reconcile
delete
mutate
```

Capability/authority is introduced by later integration and executor contracts.

The legacy 1.1 `ExternalRunRef` remains untouched for regression compatibility until
the runtime/persistence migration lots move to the V2 representation.

## Structured failure evidence

LOT-01 adds:

```text
FailureCategory
Retryability
OutcomeUncertainty
FailureEvidence
```

The failure taxonomy is aligned with the PyKit execution boundary vocabulary, including:

```text
transient
timeout
cancelled
contract_violation
side_effect_failed
unknown_outcome
external_provider
```

Retryability distinguishes:

```text
retryable
non_retryable
unknown
retryable_after_reconciliation
```

Uncertainty distinguishes:

```text
known
unknown
requires_reconciliation
```

A provider/sibling failure therefore does not need to be flattened into exception text.

## RetryDecision skeleton

The first V2 retry disposition vocabulary is:

```text
RETRY
DO_NOT_RETRY
RECONCILE
ABORT
CANCEL
ESCALATE
```

LOT-01 only freezes the disposition vocabulary.

LOT-07 owns:

- RetryPolicy V2;
- retry budgets and deadlines;
- delay/jitter;
- evidence-driven decision evaluation;
- retry event/diagnostic integration.

## Diagnostic

Structured diagnostics now carry:

```text
code
severity
summary
details

workflow_run_id?
task_run_id?
task_attempt_id?
correlation_id?

source_component?
decision_context?
related_policy?
source_framework
```

Supported severities:

```text
debug
info
warning
error
critical
```

The aim is that retry, skip, recovery and reconciliation decisions can eventually be
understood without parsing log messages.

## Wire-contract skeletons

LOT-01 records contract identity/version descriptors for:

```text
pykit.correlation_context
pykit.failure_evidence
pyworkflowkit.workflow_execution_reference
pyworkflowkit.external_run_ref
pyworkflowkit.diagnostic
```

This is intentionally not the final codec layer.

LOT-15 owns:

```text
canonical JSON
strict decoding
golden fixtures
payload limits
migration/upcasting
non-executable deserialization
```

The invariant already established is:

```text
contract_version
    !=
package_version
```

## Qualified public surfaces

LOT-01 values are exposed through semantic namespaces:

```python
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    ExternalRunRef,
    TaskAttemptId,
    TaskRunId,
    WorkflowExecutionReference,
    WorkflowRunId,
)

from pyworkflowkit.diagnostics import (
    Diagnostic,
    DiagnosticSeverity,
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)

from pyworkflowkit.policies import RetryDecision
```

The stable 1.1 package root remains unchanged during the migration.

## Exit criteria

LOT-01 is complete when:

```text
[ ] WorkflowRunId is immutable and typed
[ ] TaskRunId is immutable and typed
[ ] TaskAttemptId is immutable and typed
[ ] IDs remain runtime-distinct even for equal text
[ ] no universal RunId exists
[ ] CorrelationContext is separate from native IDs
[ ] WorkflowExecutionReference is portable/minimal
[ ] ExternalRunRef is immutable and authority-neutral
[ ] FailureEvidence preserves retryability and uncertainty
[ ] RetryDecision vocabulary exists
[ ] Diagnostic is structured
[ ] boundary wire contract identities/versions exist
[ ] root 1.1 freeze still passes
[ ] architecture gates remain green
[ ] full CI/release qualification passes
```

## Next lot

After qualification:

```text
LOT-02 — WorkflowDefinition and TaskDefinition
```

LOT-02 will move from execution identity to canonical workflow authoring and define
`TaskDefinition` as exactly one workload boundary.
