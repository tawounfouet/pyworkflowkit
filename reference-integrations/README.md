# PyWorkflowKit reference integrations

These packages are M50 conformance fixtures, deliberately packaged as independent Python
distributions rather than modules inside the `pyworkflowkit` wheel.

They exercise real Python entry-point discovery and removal:

~~~text
reference-workload
    pyworkflowkit.workloads: reference-workload

reference-event-sink
    pyworkflowkit.events: reference-event-sink

reference-metadata
    pyworkflowkit.metadata: reference-metadata

reference-pyingestkit
    pyworkflowkit.workloads: pyingestkit-reference
~~~

## Architectural purpose

The packages prove:

~~~text
PyWorkflowKit core
    ↑
    │ dependency
external integration package
~~~

and reject:

~~~text
PyWorkflowKit core
    ↓
reference integration package
~~~

None of these packages are imported by `src/pyworkflowkit`.

## Qualification

`scripts/qualify_reference_integrations.py` performs, in an isolated virtual
environment:

~~~text
build PyWorkflowKit wheel
build each integration wheel
install PyWorkflowKit wheel
run core-only smoke
for each integration:
    install integration
    discover entry point
    explicitly enable it
    execute its scenario
    uninstall integration
    verify entry point disappeared
    run core-only smoke again
~~~

The PyIngestKit scenario additionally installs the real PyIngestKit repository pinned at
commit:

~~~text
a19264845e10769fb8fd8cd42c83193ae011f702
~~~

That pin currently reports PyIngestKit `1.0.1`.

The adapter uses the PyIngestKit public `Job`, `Pipeline`, `Step`, `Runner` and
`RunResult` contracts. PyWorkflowKit observes the entire ingestion execution as one
atomic external workload.

## Status

These packages are conformance assets, not separately supported production products.

M52 extracted the reusable `pyworkflowkit.ecosystem` authoring/conformance facade. The 0.8 stable transverse qualification reuses the event-sink and PyIngestKit packages alongside dedicated executor and broken-plugin fixtures.
