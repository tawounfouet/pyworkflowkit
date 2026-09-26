# M40 — Non-blocking Retry

M40 is the fourth and final functional milestone of the PyWorkflowKit 0.6.x recovery line.

## Requirement

```text
replace blocking sleeps with:

retry eligible_at

for concurrent/long-lived runtime
```

M40 implements that requirement without turning PyWorkflowKit into a scheduler.

## Retry authority

`RetryEngine` still owns retry policy decisions. The runtime converts a retry delay into:

```text
retry_eligible_at = failed_at + delay_seconds
```

The failed `TaskAttempt` persists this timestamp. `TaskRun` remains `RUNNING` between attempts, and no new lifecycle enum is introduced.

## Concurrent runtime

Before M40 the concurrent coordinator called `Sleeper.sleep(delay)` after a retryable failure. That blocked coordination. M40 removes those retry sleeps from `ConcurrentRunner`.

```text
Attempt N FAILED
      ↓
persist retry_eligible_at
      ↓
release capacity
      ↓
other READY tasks may run
      ↓
retry deadline due
      ↓
Attempt N+1
```

The in-process coordinator uses a monotonic retry deadline, while the persisted contract keeps the timezone-aware wall-clock `retry_eligible_at`.

The completion wait considers active timeout deadlines, pending retry deadlines, and cancellation polling. The earliest deadline wins.

## Sequential runtime

The simple sequential `Runner` retains its blocking `Sleeper` behavior. It now persists `retry_eligible_at` before sleeping, making crash-during-backoff recovery explicit. The roadmap scopes non-blocking behavior to concurrent/long-lived runtime.

## Recovery

A persisted retry wait has the following shape:

```text
WorkflowRun RUNNING
TaskRun RUNNING
latest TaskAttempt FAILED
retry_eligible_at != null
no RUNNING TaskAttempt
```

Before eligibility, M37 classifies it as `ACTIVE` with reason `retry_wait_not_yet_eligible`. After the deadline and stale threshold, it becomes a `STALE_CANDIDATE` that is resume-eligible if no other ambiguity exists.

M38 skips this state because it is explicit runtime intent, not ambiguous active external work.

M39 resumes the same `WorkflowRun` and same `TaskRun` by creating Attempt N+1 once the deadline is due. If the deadline is still in the future, resume is rejected without mutation.

## Persistence

M40 adds Alembic revision:

```text
0001_runtime_metadata
        ↓
0002_task_output_checkpoints
        ↓
0003_retry_eligible_at
```

The `task_attempts.retry_eligible_at` column is nullable. Memory, SQLite, and PostgreSQL persistence round-trip it.

## Events

The existing `TASK_RETRYING` event remains authoritative and now includes `delay_seconds`, `retry_eligible_at`, and `next_attempt_number`. No new `RuntimeEventType` is introduced.

## Compatibility

M40 does not change lifecycle enum sets, RunManifest schema version 1, Plugin API version 1, RetryPolicy structure, RetryEngine ownership, or Executor capability contracts.

## Reference acceptance

The M40 reference scenario persists a failed Attempt 1 with a retry deadline to SQLite, closes the store, creates a new runtime, verifies recovery classification, and resumes Attempt 2 on the same TaskRun. The reopened database verifies both attempts and the retained retry deadline.

## Out of scope

M40 does not implement cron scheduling, delayed workflow starts, a background daemon, distributed timers, leases, worker heartbeats, or autonomous recovery polling.

## Next

M40 completes the functional M37–M40 scope. The next step is transverse qualification and promotion to `0.6.0` stable.
