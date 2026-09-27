# Compatibility Policy

Status: M41 baseline — 0.7.0a1

## Purpose

PyWorkflowKit is still pre-1.0, but the 0.7-0.9 phase deliberately adopts a stronger
compatibility discipline than the minimum allowed by Semantic Versioning for 0.x
packages.

The objective is to reduce accidental API churn before 1.0.

## Contract classes

### Stable-intent contracts

Changes require explicit compatibility review and reference-test updates:

~~~text
package-root __all__
WorkflowRunStatus
TaskRunStatus
TaskAttemptStatus
RuntimeEventType
MetadataStore
UnitOfWork
CLI command names
CLI documented exit codes
RunManifest schema version
Plugin API version
migration history
~~~

### Advanced/internal surfaces

Advanced module imports remain usable but are not automatically promoted to the same
compatibility tier merely because they exist.

Examples include:

~~~text
ConcurrentRunner
ThreadExecutor
ProcessExecutor
AsyncExecutor
SubprocessExecutor
RecoveryInspector
ReconciliationService
~~~

Their behavior is still tested, but package-root stability is not implied.

## Compatible changes

Normally compatible:

~~~text
bug fixes preserving documented semantics
performance improvements
new optional capabilities
new additive fields where the owning contract explicitly permits them
new advanced-module APIs
new migration revisions that preserve supported upgrade paths
~~~

## Potentially breaking changes

Require explicit review:

~~~text
removing/renaming a package-root symbol
changing enum values
changing RuntimeEvent meaning
removing or changing required MetadataStore/UnitOfWork methods
renaming CLI commands
changing established exit-code meaning
changing machine-readable JSON keys incompatibly
changing Manifest schema without a version transition
changing Plugin API compatibility rules
rewriting migration history
~~~

## Change process

From M41 onward, a change to a stable-intent contract must do one of:

1. preserve compatibility and extend the relevant contract test;
2. introduce a documented deprecation path;
3. explicitly version the affected contract;
4. document a narrowly justified emergency break for security or invariant correctness.

Silent breaking changes are not accepted.

## Pre-1.0 note

This policy does not claim that every internal API is frozen before 1.0.

It establishes a controlled path toward the 1.0 stability review, whose final freeze
still includes top-level exports, exceptions, states/enums, CLI commands/exit codes,
Plugin API, MetadataStore, manifest schema, and configuration schema.
