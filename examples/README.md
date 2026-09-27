# PyWorkflowKit canonical examples

DX04 defines the executable learning companions for the Zero-to-Hero guides.

## Canonical sequence

```text
00_hello_world.py
01_tasks_and_handlers.py
02_workflow_definitions.py
03_dependencies.py
04_dag.py
05_execution_plan.py
06_runtime.py
07_run_context.py
08_failure.py
09_retry.py
10_events.py
11_manifest.py
12_sqlite.py
13_postgresql.py
14_configuration.py
15_concurrency.py
16_timeout.py
17_cancellation.py
18_external_workload.py
19_plugin.py
20_custom_executor.py
21_control_plane.py
```

Then continue with:

```text
integrations/pyingestkit/atomic_job.py
complete/data_pipeline.py
```

Every canonical script is designed to execute from a clean development installation with:

```bash
python examples/<script>.py
```

The PostgreSQL example validates configuration only and deliberately does not require a
live PostgreSQL server. The PyIngestKit example uses the normalized adapter contract and
does not require the concrete PyIngestKit package.

Historical examples such as `01_failure_and_retry.py`, `02_sqlite_persistence.py`,
and `03_ecosystem_plugin.py` remain available for compatibility.
