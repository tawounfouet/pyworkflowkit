# PyWorkflowKit interactive notebooks

DX05 is the interactive experimentation companion to the Zero-to-Hero guides and the
canonical executable scripts.

The notebooks deliberately do **not** copy each `.py` example cell by cell. They follow:

```text
Concept
   ↓
Construction
   ↓
Inspection
   ↓
Modification
   ↓
Execution
   ↓
Observation
   ↓
Experiment
```

## Notebook sequence

1. [00 - Environment and Setup.ipynb](<00%20-%20Environment%20and%20Setup.ipynb>)
2. [01 - Hello Workflow.ipynb](<01%20-%20Hello%20Workflow.ipynb>)
3. [02 - Tasks and Handlers.ipynb](<02%20-%20Tasks%20and%20Handlers.ipynb>)
4. [03 - Workflow Definitions.ipynb](<03%20-%20Workflow%20Definitions.ipynb>)
5. [04 - Dependencies and DAG.ipynb](<04%20-%20Dependencies%20and%20DAG.ipynb>)
6. [05 - Execution Planning.ipynb](<05%20-%20Execution%20Planning.ipynb>)
7. [06 - Workflow Runtime.ipynb](<06%20-%20Workflow%20Runtime.ipynb>)
8. [07 - RunContext and Data Flow.ipynb](<07%20-%20RunContext%20and%20Data%20Flow.ipynb>)
9. [08 - Failures and Retries.ipynb](<08%20-%20Failures%20and%20Retries.ipynb>)
10. [09 - Events and Evidence.ipynb](<09%20-%20Events%20and%20Evidence.ipynb>)
11. [10 - Run Manifest.ipynb](<10%20-%20Run%20Manifest.ipynb>)
12. [11 - SQLite Persistence.ipynb](<11%20-%20SQLite%20Persistence.ipynb>)
13. [12 - Configuration.ipynb](<12%20-%20Configuration.ipynb>)
14. [13 - Concurrency.ipynb](<13%20-%20Concurrency.ipynb>)
15. [14 - Executors.ipynb](<14%20-%20Executors.ipynb>)
16. [15 - Plugins.ipynb](<15%20-%20Plugins.ipynb>)
17. [16 - External Workloads.ipynb](<16%20-%20External%20Workloads.ipynb>)
18. [17 - PyIngestKit Integration.ipynb](<17%20-%20PyIngestKit%20Integration.ipynb>)
19. [99 - Complete Workflow Lab.ipynb](<99%20-%20Complete%20Workflow%20Lab.ipynb>)

## Execution model

Every code cell is ordinary Python. No notebook magic is required for the canonical path,
which means CI can validate and execute the notebooks without introducing Jupyter into the
PyWorkflowKit runtime dependencies.

For interactive use, open the files with JupyterLab, Jupyter Notebook, VS Code, PyCharm, or
another Notebook v4-compatible environment using the same Python environment in which
PyWorkflowKit is installed.

## Boundaries

Notebooks are for exploration and object inspection. Console-script packaging, shell exit
codes, PostgreSQL server provisioning, package publication, and long-running platform
operations remain better suited to guides, scripts, CI, or external infrastructure.
