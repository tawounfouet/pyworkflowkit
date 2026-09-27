# 19 — Plugins and Ecosystem

## What you will learn

You will extend PyWorkflowKit through the frozen ecosystem authoring facade without
depending on internal implementation modules.

## Public SDK

Third-party integrations should start from:

```python
from pyworkflowkit.ecosystem import ...
```

The SDK exports the public extension contracts, plugin metadata helpers, conformance tools,
external-workload contracts, and control-plane provider contracts.

## Plugin categories

```text
executor
metadata
workload
event
```

Installed plugins use normal Python package entry points.

## Minimal registration shape

```python
from pyworkflowkit.ecosystem import (
    ExternalWorkloadResult,
    PluginType,
    RegisteredPlugin,
    RunContext,
    plugin_registration,
)


class ExampleWorkload:
    def run(self, *, context: RunContext) -> ExternalWorkloadResult:
        return ExternalWorkloadResult(
            external_run_id=f"example-{context.task_run_id}",
            succeeded=True,
        )


def plugin() -> RegisteredPlugin[ExampleWorkload]:
    return plugin_registration(
        name="example-workload",
        plugin_type=PluginType.WORKLOAD,
        factory=ExampleWorkload,
        plugin_version="0.1.0",
    )
```

## Discovery and diagnostics

```bash
pwk plugins
pwk doctor
```

Use `--json` for automation.

## Compatibility rule

A third-party package should not need to import `domain`, `ports`, `application`, or
`adapters` implementation paths when the ecosystem facade exports the required contract.

If the frozen facade is insufficient, treat that as a compatibility issue rather than
silently coupling to internals.

## Related example

Canonical companion: [`examples/19_plugin.py`](../../examples/19_plugin.py).

The historical `examples/03_ecosystem_plugin.py` example remains available for compatibility.

## Related notebook

Canonical notebook: [`15 - Plugins.ipynb`](<../../notebooks/15 - Plugins.ipynb>).

## Next chapter

Continue with [20 — External Workloads](20_EXTERNAL_WORKLOADS.md).
