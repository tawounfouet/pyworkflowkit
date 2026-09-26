# M36 — Security Hardening

M36 closes the functional 0.5.x roadmap with explicit security guardrails around runtime
boundaries that can expose privilege, environment data, process output, or telemetry.

## Scope

The source architecture already establishes three constraints:

1. Local Python handlers execute with the privileges of the hosting process.
2. LocalExecutor is not sandboxed and must not be described as safe for untrusted code.
3. Sensitive values must not be propagated casually through observability or execution
   boundaries.

M36 therefore hardens boundaries without inventing an operating-system sandbox.

## Trust model

```text
trusted Python code
    LocalExecutor
    ThreadExecutor
    AsyncExecutor

isolated Python process
    ProcessExecutor
    ≠ security sandbox

external child process
    SubprocessExecutor
    + policy guardrails
    ≠ security sandbox
```

Installed plugins are also executable Python code and are trusted by default.

## SubprocessSecurityPolicy

SubprocessExecutor now accepts an explicit policy:

```python
SubprocessExecutor(
    security_policy=SubprocessSecurityPolicy(...),
)
```

The policy can constrain:

```text
allowed executables
allowed cwd roots
allowed environment keys
parent environment inheritance
stdin size
captured stdout size
captured stderr size
```

## Default subprocess posture

The default policy deliberately changes one M34 behavior:

```text
parent environment inheritance
    M34: inherited when env is omitted
    M36: disabled by default
```

This reduces accidental propagation of:

```text
tokens
cloud credentials
database credentials
CI secrets
private environment configuration
```

A command may still provide an explicit environment.

## Executable allowlist

When configured:

```python
allowed_executables=frozenset({sys.executable})
```

the command's exact `argv[0]` must be present in the allowlist.

M36 intentionally does not perform implicit PATH resolution and then compare a different
canonical executable. The command value remains explicit.

## Working-directory roots

A policy can constrain cwd:

```text
allowed root
    /srv/workflows

allowed
    /srv/workflows/job-a

denied
    /etc
    /tmp/unapproved
```

Paths are resolved before containment comparison.

## Environment policy

The effective child environment is:

```text
explicit SubprocessCommand.env
        OR
parent environment only when inherit_environment=True
        OR
empty environment
```

When `allowed_env_keys` is configured:

- explicit command environments containing unapproved keys are rejected;
- inherited environments are reduced to approved keys.

This is a boundary control, not a secret manager.

## I/O size boundaries

Default limits:

```text
stdin   1 MiB
stdout 10 MiB
stderr 10 MiB
```

A violation becomes:

```text
SubprocessSecurityError
error_category = security_policy
```

The captured-output check is a framework evidence boundary. It is not a kernel memory,
disk, pipe, CPU, or process-tree quota.

Large payloads should continue to use artifact/reference patterns instead of inline
TaskResult values.

## shell=False remains mandatory

M36 does not add shell execution.

```text
SubprocessCommand.argv
        ↓
Popen(..., shell=False)
```

M34's literal argv guarantee remains intact.

## ObservabilitySecurityPolicy

M35 established:

```text
committed RuntimeEvent
        ↓
RuntimeEventSink
```

M36 inserts a security projection boundary:

```text
committed RuntimeEvent
        ↓
ObservabilitySecurityPolicy
        ↓
redacted RuntimeEvent projection
        ↓
RuntimeEventSink
```

The durable event is not modified.

## Sensitive-key redaction

External sink payloads recursively redact values whose keys match the existing structured
logging sensitive-key policy, including concepts such as:

```text
password
passwd
secret
token
api_key
authorization
credential
private_key
```

Nested mappings, lists, and tuples reuse the same recursive redaction primitives already
used by structured logging.

## Sink exception messages

A plugin exception may itself contain:

```text
credentials
tokens
paths
remote response bodies
PII
```

Therefore the default observability security policy stores:

```text
error_type = actual exception class
error_message = <redacted>
```

An explicit debugging policy may expose a bounded message length.

## Durable evidence vs external projection

M36 preserves this distinction:

```text
MetadataStore RuntimeEvent
    durable source of truth

RuntimeEventSink event
    redacted external projection
```

No persistence schema migration is required.

## Supply-chain CI

The 0.5.x release gate now includes a dedicated Security job.

### Bandit

Static security analysis covers package source.

Intentional shell-free subprocess usage may require a narrowly scoped Bandit suppression
when the scanner reports the known subprocess primitive itself.

### pip-audit

Installed Python dependencies are checked against vulnerability advisories.

### detect-secrets

Package source is scanned for candidate committed credentials.

### Dependency review

Pull requests use GitHub dependency review to surface newly introduced vulnerable
dependency changes.

## What M36 does not provide

M36 does not provide:

- safe execution of untrusted Python code;
- seccomp;
- namespaces;
- chroot;
- containers;
- virtual machines;
- privilege dropping;
- user switching;
- CPU quotas;
- RAM quotas;
- disk quotas;
- network policy;
- file-descriptor quotas;
- process-tree containment;
- remote sandboxing;
- a secret-management platform;
- RBAC/IAM.

Those remain operating-system, deployment-platform, Ochestrix, or external security
responsibilities.

## Compatibility

M36 intentionally keeps unchanged:

- workflow/task/attempt lifecycle enums;
- RuntimeEvent taxonomy;
- RuntimeEvent persistence schema;
- RunManifest schema;
- MetadataStore schema;
- executor capability enums;
- retry semantics;
- timeout semantics;
- cancellation semantics;
- plugin API version.

Behavioral hardening is limited to subprocess environment defaults, explicit subprocess
policy enforcement, observability projection redaction, and release-security gates.

## Acceptance gates

M36 is qualified by:

- parent-environment isolation by default;
- explicit environment support;
- executable allowlist;
- cwd-root allowlist;
- environment-key allowlist;
- stdin size boundary;
- stdout size boundary;
- stderr size boundary;
- SubprocessSecurityError normalization;
- async completion security violation propagation;
- recursive observability payload redaction;
- durable event immutability;
- sink exception-message redaction;
- explicit bounded debug-message opt-in;
- Bandit;
- pip-audit;
- detect-secrets;
- dependency review;
- Python 3.11 / 3.12 / 3.13;
- Ruff;
- strict mypy;
- branch coverage;
- reference acceptance;
- wheel/version smoke;
- PostgreSQL regression contract.

## Next

After M36 qualification, the 0.5.x functional roadmap is complete.

The next activity is transverse release qualification and promotion to `0.5.0` stable.
