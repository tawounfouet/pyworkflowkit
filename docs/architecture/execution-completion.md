# Execution handle and completion transfer

M27 introduces the value and transport primitives required before a concurrent
executor can be added.

## ExecutionHandle

An `ExecutionHandle` identifies one submitted task attempt without exposing a
thread, Future, process, or event-loop object to the coordinator.

```text
ExecutionHandle
├── handle_id
├── attempt_id
└── executor_key
```

The handle is deliberately opaque. Executor-specific implementation objects stay
inside the executor adapter.

## AttemptCompletion

A worker reports one terminal outcome:

```text
AttemptCompletion
├── handle
├── TaskResult
└── ExecutorError
```

Exactly one of `result` or `error` is present.

The completion object does not transition workflow state. It only transfers the
worker outcome back to the coordinator.

## CompletionQueue

`CompletionQueue` is a thread-safe FIFO used to move terminal attempt outcomes from
workers toward the future concurrent coordinator.

It supports blocking reads, non-blocking reads, and draining currently available
completions.

## Ownership rule

```text
worker
  executes workload
  produces AttemptCompletion
        ↓
CompletionQueue
        ↓
coordinator
  owns state transitions
```

This preserves the M29 architectural rule before M29 itself is implemented.

## Boundary

M27 does not add:

- ThreadPoolExecutor;
- task submission;
- parallel dispatch;
- cancellation;
- timeout enforcement;
- concurrent state transitions.

M28 will introduce the first executor that creates and resolves ExecutionHandle
values.
