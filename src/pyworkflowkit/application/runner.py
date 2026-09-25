"""Sequential embedded workflow runner."""

from collections.abc import Mapping
from datetime import datetime

from pyworkflowkit.application.events import RuntimeEventFactory
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.application.failure import FailurePropagator
from pyworkflowkit.application.planning import (
    DAGValidator,
    ExecutionPlanner,
    ReadyTaskResolver,
    build_dependency_graph,
)
from pyworkflowkit.application.retry import RetryEngine
from pyworkflowkit.application.state_machine import RunStateMachine
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import RuntimeEventType, TaskRunStatus
from pyworkflowkit.domain.graph import DependencyGraph
from pyworkflowkit.domain.ids import TaskId
from pyworkflowkit.domain.runtime import RuntimeEvent, TaskAttempt, TaskRun, WorkflowRun
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
from pyworkflowkit.ports.runtime import Clock, RuntimeIdFactory, Sleeper


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
        sleeper: Sleeper,
    ) -> None:
        self._metadata_store = metadata_store
        self._handler_registry = handler_registry
        self._executor = executor
        self._clock = clock
        self._id_factory = id_factory
        self._sleeper = sleeper
        self._validator = DAGValidator()
        self._planner = ExecutionPlanner()
        self._ready_resolver = ReadyTaskResolver()
        self._retry_engine = RetryEngine()
        self._failure_propagator = FailurePropagator()
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
        event_factory = RuntimeEventFactory(
            run_id=run.run_id,
            id_factory=self._id_factory,
        )
        task_runs_by_task_id = self._create_task_runs(
            run=run,
            plan_task_ids=plan.task_ids,
        )
        self._persist_initial_state(
            run=run,
            task_runs_by_task_id=task_runs_by_task_id,
        )

        workflow_started_at = self._clock.now()
        self._state_machine.start_workflow(run, at=workflow_started_at)
        self._persist_workflow_transition(
            run=run,
            event=event_factory.create(
                event_type=RuntimeEventType.WORKFLOW_STARTED,
                occurred_at=workflow_started_at,
            ),
        )

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

            task_ready_at = self._clock.now()
            self._state_machine.mark_task_ready(task_run)
            self._persist_task_transition(
                task_run=task_run,
                event=event_factory.create(
                    event_type=RuntimeEventType.TASK_READY,
                    occurred_at=task_ready_at,
                    task_run_id=task_run.task_run_id,
                    task_id=task_id,
                ),
            )

            started_at = self._clock.now()
            self._state_machine.start_task(task_run, at=started_at)
            attempt = self._new_attempt(
                task_run=task_run,
                attempt_number=1,
                started_at=started_at,
            )
            self._persist_task_start(
                task_run=task_run,
                attempt=attempt,
                event=event_factory.create(
                    event_type=RuntimeEventType.TASK_STARTED,
                    occurred_at=started_at,
                    task_run_id=task_run.task_run_id,
                    task_id=task_id,
                    attempt_number=1,
                ),
            )

            task_definition = task_definitions[task_id]
            result = self._execute_with_retry(
                run=run,
                task_run=task_run,
                attempt=attempt,
                task_definition=task_definition,
                handler=handlers[task_id],
                resolved_parameters=resolved_parameters,
                dependency_outputs={
                    upstream_task_id: outputs_by_task_id[upstream_task_id]
                    for upstream_task_id in graph.upstream_of(task_id)
                },
                graph=graph,
                plan_task_ids=plan.task_ids,
                task_runs_by_task_id=task_runs_by_task_id,
                event_factory=event_factory,
            )
            outputs_by_task_id[task_id] = result.output

        if any(
            task_run.status is not TaskRunStatus.SUCCEEDED
            for task_run in task_runs_by_task_id.values()
        ):
            raise RuntimeInvariantError(
                reason="workflow exhausted its plan before all tasks succeeded"
            )

        workflow_finished_at = self._clock.now()
        self._state_machine.succeed_workflow(run, at=workflow_finished_at)
        self._persist_workflow_transition(
            run=run,
            event=event_factory.create(
                event_type=RuntimeEventType.WORKFLOW_SUCCEEDED,
                occurred_at=workflow_finished_at,
            ),
        )
        return self._metadata_store.get_workflow_run(run.run_id)

    def _execute_with_retry(
        self,
        *,
        run: WorkflowRun,
        task_run: TaskRun,
        attempt: TaskAttempt,
        task_definition: TaskDefinition,
        handler: TaskHandler,
        resolved_parameters: Mapping[str, object],
        dependency_outputs: Mapping[TaskId, object],
        graph: DependencyGraph,
        plan_task_ids: tuple[TaskId, ...],
        task_runs_by_task_id: Mapping[TaskId, TaskRun],
        event_factory: RuntimeEventFactory,
    ) -> TaskResult:
        current_attempt = attempt

        while True:
            context = RunContext(
                workflow_run_id=run.run_id,
                task_run_id=task_run.task_run_id,
                attempt_id=current_attempt.attempt_id,
                task_id=task_run.task_id,
                attempt_number=current_attempt.attempt_number,
                workflow_parameters=resolved_parameters,
                dependency_outputs=dependency_outputs,
            )

            try:
                result = self._executor.execute(
                    task=task_definition,
                    handler=handler,
                    context=context,
                )
            except ExecutorError as exc:
                failed_at = self._clock.now()
                error_type, error_message, error_category = _normalize_executor_error(
                    exc
                )
                self._state_machine.fail_attempt(
                    current_attempt,
                    at=failed_at,
                    error_type=error_type,
                    error_message=error_message,
                    error_category=error_category,
                )

                decision = self._retry_engine.decide(
                    policy=task_definition.retry_policy,
                    attempt_number=current_attempt.attempt_number,
                    error=exc,
                )
                if decision.should_retry:
                    if decision.next_attempt_number is None:
                        raise RuntimeInvariantError(
                            reason="retry decision is missing next_attempt_number"
                        )

                    self._persist_retry_failure(
                        attempt=current_attempt,
                        event=event_factory.create(
                            event_type=RuntimeEventType.TASK_RETRYING,
                            occurred_at=failed_at,
                            task_run_id=task_run.task_run_id,
                            task_id=task_run.task_id,
                            attempt_number=current_attempt.attempt_number,
                            payload={
                                "error_type": error_type,
                                "error_category": error_category,
                                "delay_seconds": decision.delay_seconds,
                                "next_attempt_number": decision.next_attempt_number,
                            },
                        ),
                    )

                    if decision.delay_seconds > 0:
                        self._sleeper.sleep(decision.delay_seconds)

                    current_attempt = self._new_attempt(
                        task_run=task_run,
                        attempt_number=decision.next_attempt_number,
                        started_at=self._clock.now(),
                    )
                    self._persist_retry_attempt(current_attempt)
                    continue

                self._persist_terminal_failure(
                    run=run,
                    task_run=task_run,
                    attempt=current_attempt,
                    graph=graph,
                    plan_task_ids=plan_task_ids,
                    task_runs_by_task_id=task_runs_by_task_id,
                    event_factory=event_factory,
                    error_type=error_type,
                    error_category=error_category,
                )
                raise

            self._persist_execution_success(
                task_run=task_run,
                attempt=current_attempt,
                result=result,
                event=event_factory.create(
                    event_type=RuntimeEventType.TASK_SUCCEEDED,
                    occurred_at=self._clock.now(),
                    task_run_id=task_run.task_run_id,
                    task_id=task_run.task_id,
                    attempt_number=current_attempt.attempt_number,
                ),
            )
            return result

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

    def _new_attempt(
        self,
        *,
        task_run: TaskRun,
        attempt_number: int,
        started_at: datetime,
    ) -> TaskAttempt:
        return TaskAttempt(
            attempt_id=self._id_factory.new_task_attempt_id(
                task_run_id=task_run.task_run_id,
                attempt_number=attempt_number,
            ),
            task_run_id=task_run.task_run_id,
            attempt_number=attempt_number,
            started_at=started_at,
        )

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

    def _persist_workflow_transition(
        self,
        *,
        run: WorkflowRun,
        event: RuntimeEvent,
    ) -> None:
        with self._metadata_store.unit_of_work() as uow:
            uow.save_workflow_run(run)
            uow.add_event(event)
            uow.commit()

    def _persist_task_transition(
        self,
        *,
        task_run: TaskRun,
        event: RuntimeEvent,
    ) -> None:
        with self._metadata_store.unit_of_work() as uow:
            uow.save_task_run(task_run)
            uow.add_event(event)
            uow.commit()

    def _persist_task_start(
        self,
        *,
        task_run: TaskRun,
        attempt: TaskAttempt,
        event: RuntimeEvent,
    ) -> None:
        with self._metadata_store.unit_of_work() as uow:
            uow.save_task_run(task_run)
            uow.add_task_attempt(attempt)
            uow.add_event(event)
            uow.commit()

    def _persist_retry_failure(
        self,
        *,
        attempt: TaskAttempt,
        event: RuntimeEvent,
    ) -> None:
        with self._metadata_store.unit_of_work() as uow:
            uow.save_task_attempt(attempt)
            uow.add_event(event)
            uow.commit()

    def _persist_retry_attempt(self, attempt: TaskAttempt) -> None:
        with self._metadata_store.unit_of_work() as uow:
            uow.add_task_attempt(attempt)
            uow.commit()

    def _persist_execution_success(
        self,
        *,
        task_run: TaskRun,
        attempt: TaskAttempt,
        result: TaskResult,
        event: RuntimeEvent,
    ) -> None:
        finished_at = event.occurred_at
        self._state_machine.succeed_attempt(attempt, at=finished_at)
        self._state_machine.succeed_task(task_run, at=finished_at)

        with self._metadata_store.unit_of_work() as uow:
            uow.save_task_attempt(attempt)
            uow.save_task_run(task_run)
            uow.add_event(event)
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

    def _persist_terminal_failure(
        self,
        *,
        run: WorkflowRun,
        task_run: TaskRun,
        attempt: TaskAttempt,
        graph: DependencyGraph,
        plan_task_ids: tuple[TaskId, ...],
        task_runs_by_task_id: Mapping[TaskId, TaskRun],
        event_factory: RuntimeEventFactory,
        error_type: str,
        error_category: str,
    ) -> None:
        if attempt.finished_at is None:
            raise RuntimeInvariantError(
                reason="terminal failure requires a finished TaskAttempt"
            )
        finished_at = attempt.finished_at

        self._state_machine.fail_task(task_run, at=finished_at)
        skip_decisions = self._failure_propagator.plan_fail_fast(
            failed_task_id=task_run.task_id,
            graph=graph,
            task_runs_by_task_id=task_runs_by_task_id,
            plan_task_ids=plan_task_ids,
        )
        for decision in skip_decisions:
            self._state_machine.skip_task(
                task_runs_by_task_id[decision.task_id],
                reason=decision.reason,
                at=finished_at,
            )
        self._state_machine.fail_workflow(run, at=finished_at)

        events = [
            event_factory.create(
                event_type=RuntimeEventType.TASK_FAILED,
                occurred_at=finished_at,
                task_run_id=task_run.task_run_id,
                task_id=task_run.task_id,
                attempt_number=attempt.attempt_number,
                payload={
                    "error_type": error_type,
                    "error_category": error_category,
                },
            )
        ]
        events.extend(
            event_factory.create(
                event_type=RuntimeEventType.TASK_SKIPPED,
                occurred_at=finished_at,
                task_run_id=task_runs_by_task_id[decision.task_id].task_run_id,
                task_id=decision.task_id,
                payload={
                    "reason": decision.reason.value,
                    "failed_task_id": str(task_run.task_id),
                },
            )
            for decision in skip_decisions
        )
        events.append(
            event_factory.create(
                event_type=RuntimeEventType.WORKFLOW_FAILED,
                occurred_at=finished_at,
                payload={"failed_task_id": str(task_run.task_id)},
            )
        )

        with self._metadata_store.unit_of_work() as uow:
            uow.save_task_attempt(attempt)
            uow.save_task_run(task_run)
            for decision in skip_decisions:
                uow.save_task_run(task_runs_by_task_id[decision.task_id])
            uow.save_workflow_run(run)
            for event in events:
                uow.add_event(event)
            uow.commit()


def _normalize_executor_error(error: ExecutorError) -> tuple[str, str, str]:
    if isinstance(error, TaskExecutionError):
        return (
            error.error_type,
            error.error_message or error.error_type,
            error.error_category,
        )
    error_type = type(error).__name__
    return error_type, str(error) or error_type, error_type


__all__ = ["Runner"]
