"""Deterministic thread-safe in-memory V2 MetadataStore."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import RLock

from pyworkflowkit.errors import (
    DuplicateMetadataError,
    MetadataConflictError,
    MetadataInvariantError,
    MetadataNotFoundError,
)
from pyworkflowkit.persistence.contracts import (
    V2_METADATA_STORE_CONTRACT_VERSION,
    DeletedRecordsSummary,
    ManifestReference,
    MetadataStore,
    MetadataStoreMetadata,
    PruneReport,
    RetentionPolicy,
    StateEntityType,
    StateTransitionRecord,
)
from pyworkflowkit.runtime.entities import TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.runtime.evidence import (
    RuntimeEvent,
    TaskOutputCheckpoint,
    runtime_event_type_for_transition,
)
from pyworkflowkit.runtime.identity import TaskAttemptId, TaskRunId, WorkflowRunId
from pyworkflowkit.runtime.references import ExternalRunRef
from pyworkflowkit.states import TaskAttemptStatus, TaskRunStatus, WorkflowRunStatus
from pyworkflowkit.states.enums import WORKFLOW_TERMINAL_STATUSES

IN_MEMORY_SCHEMA_VERSION = "2"


@dataclass(slots=True)
class _MemoryState:
    workflow_runs: dict[WorkflowRunId, WorkflowRun] = field(default_factory=dict)
    task_runs: dict[TaskRunId, TaskRun] = field(default_factory=dict)
    task_attempts: dict[TaskAttemptId, TaskAttempt] = field(default_factory=dict)
    external_refs: dict[
        tuple[TaskAttemptId, str, str, str],
        ExternalRunRef,
    ] = field(default_factory=dict)
    transitions: list[StateTransitionRecord] = field(default_factory=list)
    output_checkpoints: dict[TaskRunId, TaskOutputCheckpoint] = field(default_factory=dict)
    manifests: dict[WorkflowRunId, ManifestReference] = field(default_factory=dict)
    next_transition_sequence: int = 1


class InMemoryMetadataStore:
    """Reference V2 MetadataStore for tests and simple process-local execution."""

    def __init__(self) -> None:
        self._state = _MemoryState()
        self._lock = RLock()

    def metadata(self) -> MetadataStoreMetadata:
        return MetadataStoreMetadata(
            contract_version=V2_METADATA_STORE_CONTRACT_VERSION,
            schema_version=IN_MEMORY_SCHEMA_VERSION,
            durable=False,
            supports_concurrent_writers=True,
            supports_atomic_batch=False,
        )

    def create_workflow_run(self, run: WorkflowRun) -> None:
        candidate = _clone_workflow_run(run)
        _require_initial_status(
            "WorkflowRun",
            str(candidate.run_id),
            candidate.status,
            WorkflowRunStatus.PENDING,
        )
        with self._lock:
            if candidate.run_id in self._state.workflow_runs:
                raise DuplicateMetadataError(
                    entity_type="WorkflowRun",
                    entity_id=str(candidate.run_id),
                )
            self._state.workflow_runs[candidate.run_id] = candidate
            self._append_transition(
                StateEntityType.WORKFLOW_RUN,
                str(candidate.run_id),
                None,
                candidate.status.value,
                candidate.created_at,
            )

    def get_workflow_run(self, run_id: WorkflowRunId) -> WorkflowRun:
        with self._lock:
            try:
                return _clone_workflow_run(self._state.workflow_runs[run_id])
            except KeyError as exc:
                raise MetadataNotFoundError(
                    entity_type="WorkflowRun",
                    entity_id=str(run_id),
                ) from exc

    def update_workflow_run(
        self,
        run: WorkflowRun,
        *,
        expected_status: WorkflowRunStatus,
        transitioned_at: datetime | None = None,
    ) -> None:
        candidate = _clone_workflow_run(run)
        with self._lock:
            current = self._workflow(candidate.run_id)
            _require_status(
                entity_type="WorkflowRun",
                entity_id=str(candidate.run_id),
                actual=current.status,
                expected=expected_status,
            )
            _require_workflow_identity(current, candidate)
            self._require_transition_timestamp(
                current.status.value,
                candidate.status.value,
                transitioned_at,
            )
            self._state.workflow_runs[candidate.run_id] = candidate
            if current.status is not candidate.status:
                self._append_transition(
                    StateEntityType.WORKFLOW_RUN,
                    str(candidate.run_id),
                    current.status.value,
                    candidate.status.value,
                    transitioned_at,
                )

    def list_workflow_runs(self) -> tuple[WorkflowRun, ...]:
        with self._lock:
            return tuple(
                _clone_workflow_run(self._state.workflow_runs[run_id])
                for run_id in sorted(self._state.workflow_runs, key=str)
            )

    def list_unfinished_workflow_runs(self) -> tuple[WorkflowRun, ...]:
        with self._lock:
            values = (
                run
                for run in self._state.workflow_runs.values()
                if run.status not in WORKFLOW_TERMINAL_STATUSES
            )
            return tuple(
                _clone_workflow_run(run)
                for run in sorted(values, key=lambda item: str(item.run_id))
            )

    def create_task_run(self, task_run: TaskRun) -> None:
        candidate = _clone_task_run(task_run)
        _require_initial_status(
            "TaskRun",
            str(candidate.task_run_id),
            candidate.status,
            TaskRunStatus.PENDING,
        )
        with self._lock:
            if candidate.task_run_id in self._state.task_runs:
                raise DuplicateMetadataError(
                    entity_type="TaskRun",
                    entity_id=str(candidate.task_run_id),
                )
            if candidate.workflow_run_id not in self._state.workflow_runs:
                raise MetadataNotFoundError(
                    entity_type="WorkflowRun",
                    entity_id=str(candidate.workflow_run_id),
                )
            self._state.task_runs[candidate.task_run_id] = candidate
            self._append_transition(
                StateEntityType.TASK_RUN,
                str(candidate.task_run_id),
                None,
                candidate.status.value,
                candidate.created_at,
            )

    def get_task_run(self, task_run_id: TaskRunId) -> TaskRun:
        with self._lock:
            try:
                return _clone_task_run(self._state.task_runs[task_run_id])
            except KeyError as exc:
                raise MetadataNotFoundError(
                    entity_type="TaskRun",
                    entity_id=str(task_run_id),
                ) from exc

    def update_task_run(
        self,
        task_run: TaskRun,
        *,
        expected_status: TaskRunStatus,
        transitioned_at: datetime | None = None,
    ) -> None:
        candidate = _clone_task_run(task_run)
        with self._lock:
            current = self._task(candidate.task_run_id)
            _require_status(
                entity_type="TaskRun",
                entity_id=str(candidate.task_run_id),
                actual=current.status,
                expected=expected_status,
            )
            _require_task_run_identity(current, candidate)
            self._require_transition_timestamp(
                current.status.value,
                candidate.status.value,
                transitioned_at,
            )
            self._state.task_runs[candidate.task_run_id] = candidate
            if current.status is not candidate.status:
                self._append_transition(
                    StateEntityType.TASK_RUN,
                    str(candidate.task_run_id),
                    current.status.value,
                    candidate.status.value,
                    transitioned_at,
                )

    def list_task_runs(self, workflow_run_id: WorkflowRunId) -> tuple[TaskRun, ...]:
        with self._lock:
            values = (
                task_run
                for task_run in self._state.task_runs.values()
                if task_run.workflow_run_id == workflow_run_id
            )
            return tuple(
                _clone_task_run(task_run)
                for task_run in sorted(
                    values,
                    key=lambda item: (item.task_key, str(item.task_run_id)),
                )
            )

    def append_task_attempt(self, attempt: TaskAttempt) -> None:
        candidate = _clone_task_attempt(attempt)
        _require_initial_status(
            "TaskAttempt",
            str(candidate.attempt_id),
            candidate.status,
            TaskAttemptStatus.PENDING,
        )
        with self._lock:
            if candidate.attempt_id in self._state.task_attempts:
                raise DuplicateMetadataError(
                    entity_type="TaskAttempt",
                    entity_id=str(candidate.attempt_id),
                )
            if candidate.task_run_id not in self._state.task_runs:
                raise MetadataNotFoundError(
                    entity_type="TaskRun",
                    entity_id=str(candidate.task_run_id),
                )

            existing = sorted(
                (
                    value
                    for value in self._state.task_attempts.values()
                    if value.task_run_id == candidate.task_run_id
                ),
                key=lambda item: item.attempt_number,
            )
            expected_number = len(existing) + 1
            if candidate.attempt_number != expected_number:
                raise MetadataInvariantError(
                    reason=(
                        f"TaskAttempt {candidate.attempt_id} must use attempt_number "
                        f"{expected_number}, got {candidate.attempt_number}"
                    )
                )

            self._state.task_attempts[candidate.attempt_id] = candidate
            self._append_transition(
                StateEntityType.TASK_ATTEMPT,
                str(candidate.attempt_id),
                None,
                candidate.status.value,
                candidate.created_at,
            )

    def get_task_attempt(self, attempt_id: TaskAttemptId) -> TaskAttempt:
        with self._lock:
            try:
                return _clone_task_attempt(self._state.task_attempts[attempt_id])
            except KeyError as exc:
                raise MetadataNotFoundError(
                    entity_type="TaskAttempt",
                    entity_id=str(attempt_id),
                ) from exc

    def update_task_attempt(
        self,
        attempt: TaskAttempt,
        *,
        expected_status: TaskAttemptStatus,
        transitioned_at: datetime | None = None,
    ) -> None:
        candidate = _clone_task_attempt(attempt)
        with self._lock:
            current = self._attempt(candidate.attempt_id)
            _require_status(
                entity_type="TaskAttempt",
                entity_id=str(candidate.attempt_id),
                actual=current.status,
                expected=expected_status,
            )
            _require_attempt_identity(current, candidate)
            self._require_transition_timestamp(
                current.status.value,
                candidate.status.value,
                transitioned_at,
            )
            self._state.task_attempts[candidate.attempt_id] = candidate
            if current.status is not candidate.status:
                self._append_transition(
                    StateEntityType.TASK_ATTEMPT,
                    str(candidate.attempt_id),
                    current.status.value,
                    candidate.status.value,
                    transitioned_at,
                )

    def list_task_attempts(self, task_run_id: TaskRunId) -> tuple[TaskAttempt, ...]:
        with self._lock:
            values = (
                attempt
                for attempt in self._state.task_attempts.values()
                if attempt.task_run_id == task_run_id
            )
            return tuple(
                _clone_task_attempt(attempt)
                for attempt in sorted(values, key=lambda item: item.attempt_number)
            )

    def append_external_run_ref(
        self,
        *,
        attempt_id: TaskAttemptId,
        external_ref: ExternalRunRef,
    ) -> None:
        if not isinstance(external_ref, ExternalRunRef):
            raise TypeError("external_ref must be an ExternalRunRef")
        with self._lock:
            if attempt_id not in self._state.task_attempts:
                raise MetadataNotFoundError(
                    entity_type="TaskAttempt",
                    entity_id=str(attempt_id),
                )
            key = _external_ref_key(attempt_id, external_ref)
            if key in self._state.external_refs:
                raise DuplicateMetadataError(
                    entity_type="ExternalRunRef",
                    entity_id=":".join(str(value) for value in key),
                )
            self._state.external_refs[key] = external_ref

    def list_external_run_refs(
        self,
        attempt_id: TaskAttemptId,
    ) -> tuple[ExternalRunRef, ...]:
        with self._lock:
            values = (
                external_ref
                for (owner_attempt_id, _, _, _), external_ref in self._state.external_refs.items()
                if owner_attempt_id == attempt_id
            )
            return tuple(
                sorted(
                    values,
                    key=lambda item: (item.provider, item.kind, item.external_run_id),
                )
            )

    def list_state_transitions(
        self,
        *,
        entity_type: StateEntityType | None = None,
        entity_id: str | None = None,
    ) -> tuple[StateTransitionRecord, ...]:
        with self._lock:
            values = self._state.transitions
            if entity_type is not None:
                if not isinstance(entity_type, StateEntityType):
                    raise TypeError("entity_type must be a StateEntityType or None")
                values = [item for item in values if item.entity_type is entity_type]
            if entity_id is not None:
                if not entity_id.strip():
                    raise ValueError("entity_id must not be empty when provided")
                values = [item for item in values if item.entity_id == entity_id]
            return tuple(values)

    def list_runtime_events(
        self,
        workflow_run_id: WorkflowRunId,
    ) -> tuple[RuntimeEvent, ...]:
        with self._lock:
            if workflow_run_id not in self._state.workflow_runs:
                raise MetadataNotFoundError(
                    entity_type="WorkflowRun",
                    entity_id=str(workflow_run_id),
                )
            events = [
                event
                for record in self._state.transitions
                if (event := self._event_for_transition(record)) is not None
                and event.workflow_run_id == workflow_run_id
            ]
            return tuple(events)

    def set_task_output_checkpoint(
        self,
        checkpoint: TaskOutputCheckpoint,
    ) -> None:
        if not isinstance(checkpoint, TaskOutputCheckpoint):
            raise TypeError("checkpoint must be a TaskOutputCheckpoint")
        with self._lock:
            task_run = self._task(checkpoint.task_run_id)
            if task_run.status not in {TaskRunStatus.SUCCEEDED, TaskRunStatus.REUSED}:
                raise MetadataInvariantError(
                    reason="TaskOutputCheckpoint requires a SUCCEEDED or REUSED TaskRun"
                )
            existing = self._state.output_checkpoints.get(checkpoint.task_run_id)
            if existing is not None and existing != checkpoint:
                raise MetadataConflictError(
                    entity_type="TaskOutputCheckpoint",
                    entity_id=str(checkpoint.task_run_id),
                    expected="unchanged or absent",
                    actual="different persisted checkpoint",
                )
            self._state.output_checkpoints[checkpoint.task_run_id] = checkpoint

    def get_task_output_checkpoint(
        self,
        task_run_id: TaskRunId,
    ) -> TaskOutputCheckpoint:
        with self._lock:
            try:
                return self._state.output_checkpoints[task_run_id]
            except KeyError as exc:
                raise MetadataNotFoundError(
                    entity_type="TaskOutputCheckpoint",
                    entity_id=str(task_run_id),
                ) from exc

    def set_manifest_reference(
        self,
        run_id: WorkflowRunId,
        reference: ManifestReference,
    ) -> None:
        if not isinstance(reference, ManifestReference):
            raise TypeError("reference must be a ManifestReference")
        with self._lock:
            if run_id not in self._state.workflow_runs:
                raise MetadataNotFoundError(
                    entity_type="WorkflowRun",
                    entity_id=str(run_id),
                )
            existing = self._state.manifests.get(run_id)
            if existing is not None and existing != reference:
                raise MetadataConflictError(
                    entity_type="ManifestReference",
                    entity_id=str(run_id),
                    expected="unchanged or absent",
                    actual="different persisted reference",
                )
            self._state.manifests[run_id] = reference

    def get_manifest_reference(self, run_id: WorkflowRunId) -> ManifestReference:
        with self._lock:
            try:
                return self._state.manifests[run_id]
            except KeyError as exc:
                raise MetadataNotFoundError(
                    entity_type="ManifestReference",
                    entity_id=str(run_id),
                ) from exc

    def prune_runs(
        self,
        policy: RetentionPolicy,
        *,
        dry_run: bool = False,
        batch_size: int = 500,
        now: datetime | None = None,
    ) -> PruneReport:
        if not isinstance(policy, RetentionPolicy):
            raise TypeError("policy must be a RetentionPolicy")
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")

        reference_now = now or datetime.now(UTC)
        if reference_now.tzinfo is None:
            reference_now = reference_now.replace(tzinfo=UTC)

        with self._lock:
            runs_by_workflow: dict[str, list[WorkflowRun]] = {}
            for run in self._state.workflow_runs.values():
                if policy.workflow_names and run.workflow_name not in policy.workflow_names:
                    continue
                runs_by_workflow.setdefault(run.workflow_name, []).append(run)

            scanned_workflows = len(runs_by_workflow)
            eligible_run_ids: list[WorkflowRunId] = []

            for _workflow_name, runs in runs_by_workflow.items():
                sorted_runs = sorted(
                    runs,
                    key=lambda r: (r.created_at, str(r.run_id)),
                    reverse=True,
                )

                for rank, run in enumerate(sorted_runs, start=1):
                    if run.status not in WORKFLOW_TERMINAL_STATUSES:
                        continue
                    if run.status not in policy.prune_states:
                        continue

                    cutoff_days = (
                        policy.retain_failed_runs_days
                        if run.status == WorkflowRunStatus.FAILED
                        and policy.retain_failed_runs_days is not None
                        else policy.retention_days
                    )
                    age_eligible = False
                    if cutoff_days is not None:
                        cutoff_date = reference_now - timedelta(days=cutoff_days)
                        age_eligible = run.created_at < cutoff_date

                    quota_eligible = False
                    if policy.max_runs_per_workflow is not None:
                        quota_eligible = rank > policy.max_runs_per_workflow

                    if age_eligible or quota_eligible:
                        eligible_run_ids.append(run.run_id)

            eligible_set = set(eligible_run_ids)
            str_eligible_set = {str(rid) for rid in eligible_set}

            target_task_runs = [
                tr for tr in self._state.task_runs.values() if tr.workflow_run_id in eligible_set
            ]
            target_task_run_ids = {tr.task_run_id for tr in target_task_runs}
            str_target_task_run_ids = {str(tid) for tid in target_task_run_ids}

            target_attempts = [
                ta
                for ta in self._state.task_attempts.values()
                if ta.task_run_id in target_task_run_ids
            ]
            target_attempt_ids = {ta.attempt_id for ta in target_attempts}
            str_target_attempt_ids = {str(aid) for aid in target_attempt_ids}

            target_external_refs = [
                k for k in self._state.external_refs if k[0] in target_attempt_ids
            ]

            target_checkpoints = [
                k for k in self._state.output_checkpoints if k in target_task_run_ids
            ]

            target_manifests = [k for k in self._state.manifests if k in eligible_set]

            target_transitions = [
                t
                for t in self._state.transitions
                if (
                    t.entity_type == StateEntityType.WORKFLOW_RUN
                    and t.entity_id in str_eligible_set
                )
                or (
                    t.entity_type == StateEntityType.TASK_RUN
                    and t.entity_id in str_target_task_run_ids
                )
                or (
                    t.entity_type == StateEntityType.TASK_ATTEMPT
                    and t.entity_id in str_target_attempt_ids
                )
            ]

            summary = DeletedRecordsSummary(
                workflow_runs=len(eligible_run_ids),
                task_runs=len(target_task_runs),
                task_attempts=len(target_attempts),
                events=len(target_transitions),
                checkpoints=len(target_checkpoints),
                external_refs=len(target_external_refs),
                manifests=len(target_manifests),
            )

            if not dry_run:
                for cp_id in target_checkpoints:
                    self._state.output_checkpoints.pop(cp_id, None)

                for ref_key in target_external_refs:
                    self._state.external_refs.pop(ref_key, None)

                transition_sequences_to_remove = {t.sequence for t in target_transitions}
                self._state.transitions = [
                    t
                    for t in self._state.transitions
                    if t.sequence not in transition_sequences_to_remove
                ]

                for att_id in target_attempt_ids:
                    self._state.task_attempts.pop(att_id, None)

                for tr_id in target_task_run_ids:
                    self._state.task_runs.pop(tr_id, None)

                for m_id in target_manifests:
                    self._state.manifests.pop(m_id, None)

                for r_id in eligible_run_ids:
                    self._state.workflow_runs.pop(r_id, None)

            return PruneReport(
                dry_run=dry_run,
                scanned_workflows=scanned_workflows,
                eligible_runs_to_prune=len(eligible_run_ids),
                deleted_records=summary,
            )

    def _workflow(self, run_id: WorkflowRunId) -> WorkflowRun:
        try:
            return self._state.workflow_runs[run_id]
        except KeyError as exc:
            raise MetadataNotFoundError(
                entity_type="WorkflowRun",
                entity_id=str(run_id),
            ) from exc

    def _task(self, task_run_id: TaskRunId) -> TaskRun:
        try:
            return self._state.task_runs[task_run_id]
        except KeyError as exc:
            raise MetadataNotFoundError(
                entity_type="TaskRun",
                entity_id=str(task_run_id),
            ) from exc

    def _attempt(self, attempt_id: TaskAttemptId) -> TaskAttempt:
        try:
            return self._state.task_attempts[attempt_id]
        except KeyError as exc:
            raise MetadataNotFoundError(
                entity_type="TaskAttempt",
                entity_id=str(attempt_id),
            ) from exc

    def _event_for_transition(
        self,
        record: StateTransitionRecord,
    ) -> RuntimeEvent | None:
        task_run_id: TaskRunId | None = None
        attempt_id: TaskAttemptId | None = None
        task_key: str | None = None
        attempt_number: int | None = None

        is_resume = False
        if record.entity_type is StateEntityType.WORKFLOW_RUN:
            workflow_run_id = WorkflowRunId.parse(record.entity_id)
            wf_run = self._state.workflow_runs.get(workflow_run_id)
            if wf_run is None:
                return None
            is_resume = wf_run.resume_of_run_id is not None
        elif record.entity_type is StateEntityType.TASK_RUN:
            task_run_id = TaskRunId.parse(record.entity_id)
            task_run = self._state.task_runs.get(task_run_id)
            if task_run is None:
                return None
            workflow_run_id = task_run.workflow_run_id
            task_key = task_run.task_key
        else:
            attempt_id = TaskAttemptId.parse(record.entity_id)
            attempt = self._state.task_attempts.get(attempt_id)
            if attempt is None:
                return None
            task_run = self._state.task_runs.get(attempt.task_run_id)
            if task_run is None:
                return None
            workflow_run_id = task_run.workflow_run_id
            task_run_id = task_run.task_run_id
            task_key = task_run.task_key
            attempt_number = attempt.attempt_number

        event_type = runtime_event_type_for_transition(
            entity_type=record.entity_type.value,
            from_status=record.from_status,
            to_status=record.to_status,
            attempt_number=attempt_number,
            is_resume=is_resume,
        )
        if event_type is None:
            return None

        return RuntimeEvent(
            sequence=record.sequence,
            event_id=f"{workflow_run_id}:event-{record.sequence}",
            event_type=event_type,
            workflow_run_id=workflow_run_id,
            task_run_id=task_run_id,
            attempt_id=attempt_id,
            task_key=task_key,
            attempt_number=attempt_number,
            occurred_at=record.occurred_at,
            from_status=record.from_status,
            to_status=record.to_status,
            payload={
                "entity_type": record.entity_type.value,
                "entity_id": record.entity_id,
            },
        )

    def _append_transition(
        self,
        entity_type: StateEntityType,
        entity_id: str,
        from_status: str | None,
        to_status: str,
        occurred_at: datetime | None,
    ) -> None:
        if occurred_at is None:
            raise MetadataInvariantError(reason="state transition evidence requires occurred_at")
        record = StateTransitionRecord(
            sequence=self._state.next_transition_sequence,
            entity_type=entity_type,
            entity_id=entity_id,
            from_status=from_status,
            to_status=to_status,
            occurred_at=occurred_at,
        )
        self._state.transitions.append(record)
        self._state.next_transition_sequence += 1

    @staticmethod
    def _require_transition_timestamp(
        current_status: str,
        candidate_status: str,
        transitioned_at: datetime | None,
    ) -> None:
        if current_status != candidate_status and transitioned_at is None:
            raise MetadataInvariantError(reason="status-changing update requires transitioned_at")


def _require_initial_status(
    entity_type: str,
    entity_id: str,
    actual: WorkflowRunStatus | TaskRunStatus | TaskAttemptStatus,
    expected: WorkflowRunStatus | TaskRunStatus | TaskAttemptStatus,
) -> None:
    if type(actual) is not type(expected) or actual != expected:
        raise MetadataInvariantError(
            reason=(
                f"new {entity_type} {entity_id} must begin in {expected.value}; got {actual.value}"
            )
        )


def _require_status(
    *,
    entity_type: str,
    entity_id: str,
    actual: WorkflowRunStatus | TaskRunStatus | TaskAttemptStatus,
    expected: WorkflowRunStatus | TaskRunStatus | TaskAttemptStatus,
) -> None:
    if type(actual) is not type(expected) or actual != expected:
        raise MetadataConflictError(
            entity_type=entity_type,
            entity_id=entity_id,
            expected=expected.value,
            actual=actual.value,
        )


def _require_workflow_identity(current: WorkflowRun, candidate: WorkflowRun) -> None:
    stable = (
        current.run_id == candidate.run_id
        and current.workflow_name == candidate.workflow_name
        and current.workflow_version == candidate.workflow_version
        and current.definition_fingerprint == candidate.definition_fingerprint
        and current.plan_fingerprint == candidate.plan_fingerprint
        and current.correlation == candidate.correlation
        and current.created_at == candidate.created_at
    )
    if not stable:
        raise MetadataInvariantError(reason="WorkflowRun immutable identity fields changed")


def _require_task_run_identity(current: TaskRun, candidate: TaskRun) -> None:
    stable = (
        current.task_run_id == candidate.task_run_id
        and current.workflow_run_id == candidate.workflow_run_id
        and current.task_key == candidate.task_key
        and current.created_at == candidate.created_at
    )
    if not stable:
        raise MetadataInvariantError(reason="TaskRun immutable identity fields changed")


def _require_attempt_identity(current: TaskAttempt, candidate: TaskAttempt) -> None:
    stable = (
        current.attempt_id == candidate.attempt_id
        and current.task_run_id == candidate.task_run_id
        and current.attempt_number == candidate.attempt_number
        and current.created_at == candidate.created_at
    )
    if not stable:
        raise MetadataInvariantError(reason="TaskAttempt immutable identity fields changed")


def _external_ref_key(
    attempt_id: TaskAttemptId,
    external_ref: ExternalRunRef,
) -> tuple[TaskAttemptId, str, str, str]:
    return (
        attempt_id,
        external_ref.provider,
        external_ref.kind,
        external_ref.external_run_id,
    )


def _clone_workflow_run(run: WorkflowRun) -> WorkflowRun:
    return WorkflowRun(
        run_id=run.run_id,
        workflow_name=run.workflow_name,
        workflow_version=run.workflow_version,
        definition_fingerprint=run.definition_fingerprint,
        plan_fingerprint=run.plan_fingerprint,
        correlation=run.correlation,
        created_at=run.created_at,
        _status=run.status,
        started_at=run.started_at,
        ended_at=run.ended_at,
        failure=run.failure,
        resume_of_run_id=run.resume_of_run_id,
    )


def _clone_task_run(task_run: TaskRun) -> TaskRun:
    return TaskRun(
        task_run_id=task_run.task_run_id,
        workflow_run_id=task_run.workflow_run_id,
        task_key=task_run.task_key,
        created_at=task_run.created_at,
        _status=task_run.status,
        started_at=task_run.started_at,
        ended_at=task_run.ended_at,
        skip_reason=task_run.skip_reason,
        block_reason=task_run.block_reason,
        failure=task_run.failure,
    )


def _clone_task_attempt(attempt: TaskAttempt) -> TaskAttempt:
    return TaskAttempt(
        attempt_id=attempt.attempt_id,
        task_run_id=attempt.task_run_id,
        attempt_number=attempt.attempt_number,
        created_at=attempt.created_at,
        _status=attempt.status,
        started_at=attempt.started_at,
        ended_at=attempt.ended_at,
        failure=attempt.failure,
    )


if not isinstance(InMemoryMetadataStore(), MetadataStore):
    raise TypeError("InMemoryMetadataStore must satisfy MetadataStore")


__all__ = [
    "IN_MEMORY_SCHEMA_VERSION",
    "InMemoryMetadataStore",
]
