"""Sequential embedded workflow runner."""

from collections.abc import Mapping

from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.application.planning import (
    DAGValidator,
    ExecutionPlanner,
    ReadyTaskResolver,
    build_dependency_graph,
)
from pyworkflowkit.application.state_machine import RunStateMachine
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import TaskRunStatus
from pyworkflowkit.domain.ids import TaskId, TaskRunId
from pyworkflowkit.domain.runtime import TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.domain.values import TaskResult
from pyworkflowkit.errors import (
    ExecutorError,
    ExecutorNotFoundError,
    InvalidHandlerError,
    InvalidWorkflowParametersError,
    RuntimeInvariantError,
    TaskExecutionError,
)
from pyworkflowkit.ports.executor import Executor, RunContext, TaskHandler
from pyworkflowkit.ports.metadata_store import MetadataStore
from pyworkflowkit.ports.runtime import Clock, RuntimeIdFactory


class Runner:
    """Execute a validated workflow sequentially in the current process."""

    def __init__(
        self,
        *,
        metadata_store: MetadataStore,
        handler_registry: HandlerRegistry,
        executor: Executor,
        clock: Clock,
        id_factory: RuntimeIdFactory,
    ) -> None:
        self._metadata_store = metadata_store
        self._handler_registry = handler_registry
        self._executor = executor
        self._clock = clock
        self._id_factory = id_factory
        self._validator = DAGValidator()
        self._planner = ExecutionPlanner()
        self._ready_resolver = ReadyTaskResolver()
        self._state_machine = RunStateMachine()

    def run(
        self,
        workflow: WorkflowDefinition,
        *,
        parameters: Mapping[str, object] | None = None,
    ) -> WorkflowRun:
        """Run one workflow synchronously and return its final WorkflowRun."""
        graph = build_dependency_graph(workflow)
        self._validator.validate(workflow, graph)
        plan = self._planner.build_plan(workflow, graph)

        resolved_parameters = self._resolve_parameters(
            workflow=workflow,
            supplied=parameters or {},
        )
        handlers = self._preflight_handlers(workflow)

        run = WorkflowRun(
            run_id=self._id_factory.new_workflow_run_id(),
            workflow_id=workflow.workflow_id,
            workflow_version=workflow.version,
            parameters=resolved_parameters,
            created_at=self._clock.now(),
        )
        task_runs_by_task_id = self._create_task_runs(
            run=run,
            plan_task_ids=plan.task_ids,
        )
        self._persist_initial_state(
            run=run,
            task_runs_by_task_id=task_runs_by_task_id,
        )

        self._state_machine.start_workflow(run, at=self._clock.now())
        self._save_workflow_run(run)

        task_definitions = {task.task_id: task for task in workflow.tasks}
        outputs_by_task_id: dict[TaskId, object] = {}

        for task_id in plan.task_ids:
            task_run = task_runs_by_task_id[task_id]
            persisted_runs = self._load_task_runs_by_task_id(run)
            persisted_task_run = persisted_runs[task_id]

            if not self._ready_resolver.is_ready(
                task_run=persisted_task_run,
                graph=graph,
                task_runs_by_task_id=persisted_runs,
            ):
                raise RuntimeInvariantError(
                    reason=f"planned task '{task_id}' is not runtime-ready"
                )

            self._state_machine.mark_task_ready(task_run)
            self._save_task_run(task_run)

            started_at = self._clock.now()
            self._state_machine.start_task(task_run, at=started_at)
            self._save_task_run(task_run)

            attempt = TaskAttempt(
                attempt_id=self._id_factory.new_task_attempt_id(
                    task_run_id=task_run.task_run_id,
                    attempt_number=1,
                ),
                task_run_id=task_run.task_run_id,
                attempt_number=1,
                started_at=started_at,
            )
            task_definition = task_definitions[task_id]
            context = RunContext(
                workflow_run_id=run.run_id,
                task_run_id=task_run.task_run_id,
                attempt_id=attempt.attempt_id,
                task_id=task_id,
                attempt_number=1,
                workflow_parameters=resolved_parameters,
                dependency_outputs={
                    upstream_task_id: outputs_by_task_id[upstream_task_id]
                    for upstream_task_id in graph.upstream_of(task_id)
                },
            )

            try:
                result = self._executor.execute(
                    task=task_definition,
                    handler=handlers[task_id],
                    context=context,
                )
            except ExecutorError as exc:
                self._persist_execution_failure(
                    run=run,
                    task_run=task_run,
                    attempt=attempt,
                    error=exc,
                )
                raise

            self._persist_execution_success(
                task_run=task_run,
                attempt=attempt,
                result=result,
            )
            outputs_by_task_id[task_id] = result.output

        if any(
            task_run.status is not TaskRunStatus.SUCCEEDED
            for task_run in task_runs_by_task_id.values()
        ):
            raise RuntimeInvariantError(
                reason="workflow exhausted its plan before all tasks succeeded"
            )

        self._state_machine.succeed_workflow(run, at=self._clock.now())
        self._save_workflow_run(run)
        return self._metadata_store.get_workflow_run(run.run_id)

    def _resolve_parameters(
        self,
        *,
        workflow: WorkflowDefinition,
        supplied: Mapping[str, object],
    ) -> dict[str, object]:
        declared = {parameter.name: parameter for parameter in workflow.parameters}
        unknown = tuple(sorted(set(supplied) - set(declared)))
        if unknown:
            rendered = ", ".join(unknown)
            raise InvalidWorkflowParametersError(
                reason=f"unknown workflow parameters: {rendered}"
            )

        resolved: dict[str, object] = {}
        for parameter in workflow.parameters:
            if parameter.name in supplied:
                resolved[parameter.name] = supplied[parameter.name]
            elif parameter.required:
                raise InvalidWorkflowParametersError(
                    reason=f"required workflow parameter '{parameter.name}' is missing"
                )
            else:
                resolved[parameter.name] = parameter.default
        return resolved

    def _preflight_handlers(
        self,
        workflow: WorkflowDefinition,
    ) -> dict[TaskId, TaskHandler]:
        handlers: dict[TaskId, TaskHandler] = {}
        for task in workflow.tasks:
            if task.executor_key != self._executor.key:
                raise ExecutorNotFoundError(executor_key=task.executor_key)
            if task.handler_ref is None:
                raise InvalidHandlerError(
                    task_id=task.task_id,
                    reason="handler_ref is required for Runner execution",
                )
            handlers[task.task_id] = self._handler_registry.resolve(task.handler_ref)
        return handlers

    def _create_task_runs(
        self,
        *,
        run: WorkflowRun,
        plan_task_ids: tuple[TaskId, ...],
    ) -> dict[TaskId, TaskRun]:
        created_at = self._clock.now()
        return {
            task_id: TaskRun(
                task_run_id=self._id_factory.new_task_run_id(
                    run_id=run.run_id,
                    task_id=task_id,
                ),
                run_id=run.run_id,
                task_id=task_id,
                created_at=created_at,
            )
            for task_id in plan_task_ids
        }

    def _persist_initial_state(
        self,
        *,
        run: WorkflowRun,
        task_runs_by_task_id: Mapping[TaskId, TaskRun],
    ) -> None:
        with self._metadata_store.unit_of_work() as uow:
            uow.add_workflow_run(run)
            for task_run in task_runs_by_task_id.values():
                uow.add_task_run(task_run)
            uow.commit()

    def _load_task_runs_by_task_id(
        self,
        run: WorkflowRun,
    ) -> dict[TaskId, TaskRun]:
        return {
            task_run.task_id: task_run
            for task_run in self._metadata_store.list_task_runs(run.run_id)
        }

    def _save_workflow_run(self, run: WorkflowRun) -> None:
        with self._metadata_store.unit_of_work() as uow:
            uow.save_workflow_run(run)
            uow.commit()

    def _save_task_run(self, task_run: TaskRun) -> None:
        with self._metadata_store.unit_of_work() as uow:
            uow.save_task_run(task_run)
            uow.commit()

    def _persist_execution_success(
        self,
        *,
        task_run: TaskRun,
        attempt: TaskAttempt,
        result: TaskResult,
    ) -> None:
        finished_at = self._clock.now()
        self._state_machine.succeed_attempt(attempt, at=finished_at)
        self._state_machine.succeed_task(task_run, at=finished_at)

        with self._metadata_store.unit_of_work() as uow:
            uow.add_task_attempt(attempt)
            uow.save_task_run(task_run)
            for artifact in result.artifacts:
                uow.add_artifact(
                    task_run_id=task_run.task_run_id,
                    artifact=artifact,
                )
            for external_ref in result.external_refs:
                uow.add_external_run_ref(
                    task_run_id=task_run.task_run_id,
                    external_ref=external_ref,
                )
            uow.commit()

    def _persist_execution_failure(
        self,
        *,
        run: WorkflowRun,
        task_run: TaskRun,
        attempt: TaskAttempt,
        error: ExecutorError,
    ) -> None:
        finished_at = self._clock.now()
        error_type, error_message = _normalize_executor_error(error)

        self._state_machine.fail_attempt(
            attempt,
            at=finished_at,
            error_type=error_type,
            error_message=error_message,
        )
        self._state_machine.fail_task(task_run, at=finished_at)
        self._state_machine.fail_workflow(run, at=finished_at)

        with self._metadata_store.unit_of_work() as uow:
            uow.add_task_attempt(attempt)
            uow.save_task_run(task_run)
            uow.save_workflow_run(run)
            uow.commit()


def _normalize_executor_error(error: ExecutorError) -> tuple[str, str]:
    if isinstance(error, TaskExecutionError):
        return error.error_type, error.error_message or error.error_type
    return type(error).__name__, str(error) or type(error).__name__


__all__ = ["Runner"]
