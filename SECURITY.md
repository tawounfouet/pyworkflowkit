# Security Policy

PyWorkflowKit is currently on a pre-stable development line. The latest stable line is
0.4.x while 0.5.x is being hardened for promotion.

## Security model

PyWorkflowKit is a Python workflow runtime, not a security sandbox.

Local Python handlers and installed plugins execute with the privileges of the hosting
Python process and must be treated as trusted code unless an external process, container,
virtual machine, or remote sandbox provides isolation.

```text
LocalExecutor
ThreadExecutor
AsyncExecutor
    = trusted in-process code

ProcessExecutor
    = process isolation, not a security sandbox

SubprocessExecutor
    = external child process + policy guardrails,
      not operating-system sandboxing
```

## Subprocess boundary

0.5.0a5 introduces `SubprocessSecurityPolicy`.

The default policy:

- keeps `shell=False`;
- does not inherit the parent environment;
- limits stdin to 1 MiB;
- limits captured stdout to 10 MiB;
- limits captured stderr to 10 MiB.

Optional controls can restrict:

- exact executable strings;
- allowed working-directory roots;
- environment keys;
- whether parent environment inheritance is permitted.

Captured-output limits are framework boundary limits. They do not represent kernel-level
CPU, RAM, disk, network, file-descriptor, or process-tree resource isolation.

## Observability boundary

Durable RuntimeEvents remain authoritative and unchanged.

Before committed events are sent to external observability sinks, M36 recursively redacts
payload values whose keys look sensitive, including password, token, secret, API-key,
authorization, credential, and private-key fields.

Sink exception messages are redacted by default.

This redaction is defense-in-depth. Applications should still avoid placing secrets,
credentials, raw sensitive bodies, or unnecessary personal data in RuntimeEvent payloads.

## Secrets

PyWorkflowKit is not a secret manager.

Prefer references or external providers instead of embedding credentials in:

- workflow definitions;
- RuntimeEvent payloads;
- command arguments;
- manifests;
- logs;
- plugin descriptors.

## Supply-chain checks

The repository CI includes dedicated security checks for:

- Bandit static analysis;
- pip-audit dependency vulnerability scanning;
- detect-secrets scanning of package source;
- GitHub dependency review on pull requests, when the repository Dependency Graph is enabled.

Bandit, pip-audit, and detect-secrets are blocking CI gates. Dependency Review is already
wired into CI but currently degrades to an explicit warning if GitHub reports that the
repository Dependency Graph is unavailable. Enabling Dependency Graph makes that review
fully effective without changing the workflow definition.

These checks reduce risk but do not prove absence of vulnerabilities.

## Reporting a vulnerability

Please avoid filing public issues that contain exploit details, credentials, tokens, or
other sensitive information.

Use GitHub's private vulnerability reporting feature for this repository when available.
If private reporting is unavailable, contact the repository maintainer privately through
the maintainer's GitHub profile before publishing sensitive details.

## Supported versions

The 0.4.x line is the current stable development baseline. The 0.5.x line remains
pre-stable until its transverse release qualification is complete.
