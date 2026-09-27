# PyWorkflowKit Typing & Static Contracts

Status: RQ-03 — 0.9.0a3

## Objective

RQ-03 qualifies PyWorkflowKit as a real PEP 561 typed library from the point of view of
an external consumer.

Internal `mypy --strict` is necessary but insufficient: it proves the implementation is
self-consistent, not that a third-party package can implement the public Protocols without
importing internal modules or falling back to `Any`.

## Typing contract

The machine-readable contract lives in:

```text
pyworkflowkit.contracts.typing
```

with:

```python
TYPING_CONTRACT_VERSION = "1"
TYPING_TARGET_RELEASE = "1.0.0"
TYPING_MARKER = "py.typed"
STATIC_TYPE_CHECKER = "mypy"
STATIC_TYPE_CHECKER_MODE = "strict"
```

The module remains internal release metadata under the existing
`pyworkflowkit.contracts.*` internal-prefix classification. The public guarantee is the
typing behavior of the RQ-01 frozen facades.

## PEP 561

The package already shipped an empty:

```text
src/pyworkflowkit/py.typed
```

RQ-03 turns that marker into a qualified release contract.

Release Qualification verifies the marker from the installed wheel rather than merely
checking that it exists in the source tree.

## Task handler contract

Before RQ-03 the runtime accepted only these handler shapes:

```python
Callable[[], object]
Callable[[RunContext], object]
```

but the declarative `@task` overload used an unconstrained `ParamSpec`. A function such
as:

```python
@task()
def invalid(a: int, b: int) -> int: ...
```

could therefore pass static typing even though no executor contract could invoke it.

RQ-03 aligns the decorator annotation with the existing runtime contract:

```text
TaskHandler
    =
Callable[[], object]
    |
Callable[[RunContext], object]
```

A dedicated negative typing fixture must fail under `mypy --strict` if a two-argument
handler becomes accepted again.

## Ecosystem Protocol closure

RQ-02 established that implementation modules such as `domain` and `ports` are not
stable direct-import surfaces.

RQ-03 found that several public Ecosystem SDK Protocols still referenced types that were
available only through those internal paths.

The Ecosystem SDK therefore re-exports the support types required to author compatible
implementations:

```text
Executor
├── TaskDefinition
├── TaskHandler
├── RunContext
├── TaskResult
├── ExecutorCapabilities
├── TimeoutCapability
└── CancellationCapability

MetadataStore / UnitOfWork
├── WorkflowRunId
├── TaskRunId
├── WorkflowRun
├── TaskRun
├── TaskAttempt
├── RuntimeEvent
├── ArtifactReference
└── ExternalRunRef

RuntimeEventSink
└── RuntimeEvent
```

These are existing types. RQ-03 does not introduce new runtime behavior; it repairs the
public typing closure of already-stable Protocols.

## External consumer fixture

The canonical strict consumer fixture is:

```text
typing-fixtures/public_consumer.py
```

It imports only frozen public facades and proves:

```text
@task / @workflow typing
Executor structural compatibility
MetadataStore structural compatibility
UnitOfWork structural compatibility
RuntimeEventSink structural compatibility
ExternalWorkload structural compatibility
TelemetryBackend structural compatibility
plugin_registration generic inference
WorkflowRuntimeProvider -> ControlPlaneProvider compatibility
```

A second fixture is intentionally invalid:

```text
typing-fixtures/invalid_task_handler.py
```

The release gate requires the first fixture to pass and the second fixture to fail.

## Supported Python typing matrix

The same public consumer contract is checked for:

```text
Python 3.11
Python 3.12
Python 3.13
```

using:

```text
mypy --strict --python-version <target>
```

## Reference integrations

The third-party reference executor and event sink are aligned to the public Ecosystem SDK
typing surface.

The reference executor now uses the exact public `TaskDefinition` and `TaskHandler`
types. The reference event sink obtains `RuntimeEvent` from `pyworkflowkit.ecosystem`
rather than the internal domain module.

The ecosystem template plugin factory also exposes an explicit
`RegisteredPlugin[TemplateWorkload]` return type.

## Release qualification

RQ-03 runs twice.

Regular CI:

```text
source installation
py.typed presence
RQ-03 reference acceptance
strict positive consumer fixture
strict public integration examples
negative invalid-task fixture must fail
Python 3.11 / 3.12 / 3.13 typing targets
```

Release Qualification:

```text
build wheel
install wheel outside source package resolution
verify installed py.typed
run strict consumer typing against installed distribution
require invalid task fixture to fail
matrix Python 3.11 / 3.12 / 3.13
```

## Exit criteria

```text
0.9.0a3 metadata consistent
Typing Contract v1
PEP 561 marker packaged
frozen facades covered
public Protocol support types closed through facades
valid external consumer passes strict typing
invalid task signature is rejected
generic plugin factory type inference preserved
control-plane structural typing preserved
all supported Python targets green
regular CI green
Release Qualification green
```

## Next

RQ-04 — Developer Experience & Documentation.
