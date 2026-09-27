# 23 — Control Plane

## What you will learn

You will understand how an external platform can operate PyWorkflowKit through a portable
provider contract without moving platform governance into the runtime.

## Public surface

```python
from pyworkflowkit.control_plane import (
    ControlPlaneProvider,
    WorkflowRuntimeProvider,
)
```

The provider surface is schema-first and exposes portable validation, inspection,
execution, evidence, recovery, reconciliation, resume, and capability information.

## Boundary

```text
Control plane
    scheduling / governance / IAM / UI
          ↓
ControlPlaneProvider
          ↓
PyWorkflowKit runtime
    validation / execution / evidence
```

A control plane does not send arbitrary Python function objects across the provider
boundary. The provider exposes explicit portable operations.

## Capability negotiation

Providers report what they support rather than implying every platform feature exists.
External scheduling ownership remains outside PyWorkflowKit.

## Ochestrix relationship

In the project architecture, Ochestrix is the natural control-plane layer. PyWorkflowKit
remains the embedded workflow runtime underneath it.

## Common mistakes

- adding scheduler ownership to PyWorkflowKit because a control plane needs schedules;
- exposing internal runner objects over a provider boundary;
- claiming unsupported external cancellation;
- treating provider schemas as domain entities.

## Related example

DX04 target: `examples/21_control_plane.py`.

## Next chapter

Continue with [24 — PyIngestKit Integration](24_PYINGESTKIT_INTEGRATION.md).
