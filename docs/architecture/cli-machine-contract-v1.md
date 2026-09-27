# CLI and Machine Contract v1

Status: M43 — 0.7.0a3

## Purpose

M43 turns the existing PyWorkflowKit CLI into an explicit automation contract.

No command is renamed and no existing JSON shape is changed by this milestone. The
contract is formalized from the behavior already shipped by the 0.3-0.7 runtime.

## Contract version

~~~text
CLI_MACHINE_CONTRACT_VERSION = "1"
~~~

The CLI contract version is deliberately separate from:

~~~text
package version
RunManifest schema version
Plugin API version
~~~

A package release may evolve without requiring a machine-contract version bump when the
change is backward compatible.

## Command surface

Contract v1 contains:

~~~text
validate
plan
run
inspect
events
manifest
plugins
doctor
version
~~~

All console entry points resolve to the same application. `pwk` is the canonical short command:

~~~text
pwk
pyworkflowkit
pyworkflow
~~~

## Exit codes

Application-owned exit meanings are:

~~~text
0  success
2  validation / lookup / input-to-runtime validation failure
3  workflow run failure
4  doctor / plugin-health failure
~~~

Framework-level command-line parsing failures remain owned by Typer/Click and are not
redefined as a new PyWorkflowKit semantic category in M43.

## JSON error contract

Handled command failures requested with --json emit JSON on stderr with required keys:

~~~json
{"error":"...","exit_code":2}
~~~

Required keys:

~~~text
error
exit_code
~~~

The exit_code field must match the process exit code.

## JSON success contracts

### validate

Required keys:

~~~text
valid
workflow_id
workflow_version
task_count
~~~

### plan

Required keys:

~~~text
workflow_id
workflow_version
groups
~~~

Each groups[] item requires:

~~~text
index
tasks
~~~

### run / inspect

Required keys:

~~~text
run_id
workflow_id
workflow_version
status
created_at
started_at
finished_at
~~~

Timestamp fields remain nullable where the runtime state permits it.

### events

Required keys:

~~~text
run_id
events
~~~

Each events[] item requires:

~~~text
event_id
event_sequence
event_type
occurred_at
task_run_id
task_id
attempt_number
payload
~~~

### plugins

Required keys:

~~~text
count
plugins
~~~

Each plugins[] item requires:

~~~text
name
type
group
value
distribution
status
~~~

### doctor

Required keys:

~~~text
healthy
plugin_api_version
plugins
~~~

Each plugins[] item requires:

~~~text
name
type
status
error
~~~

### manifest

manifest --json delegates to the canonical RunManifest serializer.

Its top-level contract therefore remains governed by:

~~~text
schema_version = "1"
~~~

and the existing manifest task/attempt/artifact/external-ref/event structures.

M43 does not create a second incompatible manifest representation for the CLI.

## version command

version remains a plain one-line text contract:

~~~text
<installed-package-version>\n
~~~

It does not expose --json in machine-contract v1.

## Compatibility rules

Within CLI machine contract v1:

Compatible evolution includes:

~~~text
preserving all required keys and their meaning
adding optional information without changing existing semantics
adding new commands
adding new enum/string values only where the owning domain contract allows them
improving human-readable output
~~~

Changes requiring deprecation or a machine-contract version transition include:

~~~text
renaming/removing commands
changing application exit-code meaning
removing/renaming required JSON keys
changing a key to an incompatible value type or semantic meaning
moving a success payload from stdout to stderr
moving a handled error payload from stderr to stdout
changing manifest JSON independently of its schema version
~~~

Consumers should ignore unknown additive JSON keys.

Maintainers must still update executable reference contracts whenever additive fields
are introduced so additions are deliberate rather than accidental.

## Stream contract

~~~text
successful --json payload -> stdout
handled --json error      -> stderr
~~~

Human-readable output is not byte-for-byte frozen. Machine-readable JSON structure is.

## Scope boundary

M43 does not add:

~~~text
remote API
HTTP server
daemon
scheduler
new workflow semantics
new persistence schema
new plugin API version
~~~

## Next

M44 — Plugin Ecosystem Compatibility.
