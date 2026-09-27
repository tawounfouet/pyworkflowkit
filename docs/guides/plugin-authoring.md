# Plugin Authoring

Third-party integrations should start from the public Ecosystem SDK:

```python
from pyworkflowkit.ecosystem import ...
```

A complete executable example is:

```text
examples/03_ecosystem_plugin.py
```

## Minimal external-workload plugin

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

The SDK keeps plugin metadata aligned with the current Plugin API and preserves the
generic factory result type.

## Extension categories

The supported plugin categories are:

```text
executor
metadata
workload
event
```

Their Python entry-point groups are available through `ENTRY_POINT_GROUPS` and
`entry_point_group()`.

## Do not depend on implementation paths

RQ-02 classifies implementation module families such as `domain`, `ports`,
`application`, and `adapters` as internal import paths.

RQ-03 therefore makes `pyworkflowkit.ecosystem` self-contained for implementing the
public Protocols. A third-party package should not need internal imports to implement
`Executor`, `MetadataStore`, `UnitOfWork`, `RuntimeEventSink`, or
`ExternalWorkload`.

## Package discovery

Installed plugins use normal Python package entry points. The CLI can show candidates
without loading them:

```bash
pwk plugins --json
```

Use `pwk doctor` to explicitly check selected plugin compatibility.
