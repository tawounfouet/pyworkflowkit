"""Security policies for external-process execution boundaries."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class _CommandView(Protocol):
    @property
    def argv(self) -> tuple[str, ...]: ...

    @property
    def cwd(self) -> str | None: ...

    @property
    def env(self) -> Mapping[str, str] | None: ...

    @property
    def stdin(self) -> str | None: ...

    @property
    def encoding(self) -> str: ...


@dataclass(frozen=True, slots=True)
class SubprocessSecurityPolicy:
    """Explicit guardrails for SubprocessExecutor.

    This policy reduces accidental exposure and command-surface breadth. It is not an
    operating-system sandbox and does not make untrusted code safe.
    """

    allowed_executables: frozenset[str] | None = None
    allowed_cwd_roots: tuple[str, ...] = ()
    allowed_env_keys: frozenset[str] | None = None
    inherit_environment: bool = False
    max_stdin_bytes: int | None = 1_048_576
    max_stdout_bytes: int | None = 10_485_760
    max_stderr_bytes: int | None = 10_485_760

    def __post_init__(self) -> None:
        for field_name, value in (
            ("max_stdin_bytes", self.max_stdin_bytes),
            ("max_stdout_bytes", self.max_stdout_bytes),
            ("max_stderr_bytes", self.max_stderr_bytes),
        ):
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, int):
                    raise TypeError(f"{field_name} must be an integer or None")
                if value < 0:
                    raise ValueError(f"{field_name} must be greater than or equal to 0")

        roots = tuple(str(Path(root).resolve()) for root in self.allowed_cwd_roots)
        object.__setattr__(self, "allowed_cwd_roots", roots)

        if self.allowed_executables is not None:
            object.__setattr__(
                self,
                "allowed_executables",
                frozenset(self.allowed_executables),
            )
        if self.allowed_env_keys is not None:
            object.__setattr__(
                self,
                "allowed_env_keys",
                frozenset(self.allowed_env_keys),
            )

    def validate(self, command: _CommandView) -> None:
        """Validate command inputs before process creation."""

        executable = command.argv[0]
        if self.allowed_executables is not None and executable not in self.allowed_executables:
            raise ValueError("executable is not allowed by subprocess security policy")

        if command.cwd is not None and self.allowed_cwd_roots:
            cwd = Path(command.cwd).resolve()
            allowed = any(
                cwd == Path(root) or cwd.is_relative_to(Path(root))
                for root in self.allowed_cwd_roots
            )
            if not allowed:
                raise ValueError("cwd is outside allowed subprocess roots")

        if command.env is not None and self.allowed_env_keys is not None:
            disallowed = sorted(set(command.env) - set(self.allowed_env_keys))
            if disallowed:
                raise ValueError("explicit environment contains disallowed keys")

        if command.stdin is not None:
            self._validate_size(
                "stdin",
                len(command.stdin.encode(command.encoding)),
                self.max_stdin_bytes,
            )

    def environment_for(self, command: _CommandView) -> dict[str, str]:
        """Return the environment allowed to cross the subprocess boundary."""

        if command.env is not None:
            environment = dict(command.env)
        elif self.inherit_environment:
            environment = dict(os.environ)
        else:
            environment = {}

        if self.allowed_env_keys is not None:
            environment = {
                key: value for key, value in environment.items() if key in self.allowed_env_keys
            }
        return environment

    def validate_captured_output(
        self,
        *,
        command: _CommandView,
        stdout: str,
        stderr: str,
    ) -> None:
        """Validate captured evidence before it is exposed as a TaskResult/error."""

        self._validate_size(
            "stdout",
            len(stdout.encode(command.encoding, errors="replace")),
            self.max_stdout_bytes,
        )
        self._validate_size(
            "stderr",
            len(stderr.encode(command.encoding, errors="replace")),
            self.max_stderr_bytes,
        )

    @staticmethod
    def _validate_size(label: str, actual: int, maximum: int | None) -> None:
        if maximum is not None and actual > maximum:
            raise ValueError(f"{label} exceeds subprocess security policy limit")


__all__ = ["SubprocessSecurityPolicy"]
