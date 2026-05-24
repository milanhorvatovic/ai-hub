"""Process port + concrete subprocess adapter.

Every module that needs to run a subprocess or look up a binary on PATH
depends on the `ProcessRunner` Protocol — not on `subprocess` or `shutil`
directly. Tests pass `FakeProcessRunner` from `tests/fakes.py`; production
code wires `SubprocessRunner`. This is the single seam that isolates the
package from the host environment.

`SubprocessRunner` augments `PATH` with a curated list of shim and install
directories (mise, asdf, pipx, brew, cargo, bun, pnpm, volta). The harness
shell the skill runs under is typically non-interactive and skips the shell
activation (`eval "$(mise activate ...)"`) that would otherwise put those
shims on `PATH`. Augmenting here keeps the skill working regardless of how
the tool was installed — without requiring the user to mutate their shell
init for the harness.
"""

from __future__ import annotations

import os
import os.path
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

_SHIM_FALLBACK_DIRS: tuple[str, ...] = (
    "~/.local/share/mise/shims",   # mise (formerly rtx)
    "~/.asdf/shims",                # asdf
    "~/.local/bin",                 # pipx, pip --user, uv
    "/opt/homebrew/bin",            # Homebrew on Apple Silicon
    "/usr/local/bin",               # Homebrew on Intel; manual installs
    "~/.cargo/bin",                 # cargo install
    "~/.bun/bin",                   # bun
    "~/Library/pnpm",               # pnpm on macOS
    "~/.volta/bin",                 # volta
)


def _augment_path(base_path: str, extras: Sequence[str]) -> str:
    """Append every existing extras dir to base_path, deduplicated."""
    existing = base_path.split(os.pathsep) if base_path else []
    seen = set(existing)
    merged = list(existing)
    for raw in extras:
        expanded = os.path.expanduser(raw)
        if expanded in seen:
            continue
        if os.path.isdir(expanded):
            merged.append(expanded)
            seen.add(expanded)
    return os.pathsep.join(merged)


@dataclass(frozen=True)
class ProcessResult:
    """What a subprocess call returns. `stdout` and `stderr` are decoded text;
    callers are responsible for splitting / stripping. `returncode` follows
    POSIX convention (0 = success, non-zero = failure)."""

    returncode: int
    stdout: str
    stderr: str


class ProcessRunner(Protocol):
    """Anything that can locate a binary on PATH and execute it."""

    def which(self, name: str) -> str | None:
        """Return the absolute path to `name` if on PATH, else None."""
        ...

    def run(
        self,
        args: Sequence[str],
        cwd: str | None = None,
        stdin: str | None = None,
    ) -> ProcessResult:
        """Execute `args` (no shell), optionally in `cwd`, optionally piping
        `stdin` into the child process. Never raises on non-zero exit —
        callers inspect `ProcessResult.returncode`."""
        ...


class SubprocessRunner:
    """Stdlib-backed `ProcessRunner` with shim-aware `PATH` augmentation.

    Pass `extra_path_dirs=()` to disable augmentation (e.g. in CI where you
    want a strict PATH). Default extends PATH with mise / asdf / pipx / brew
    / cargo / bun / pnpm / volta directories so binaries installed by any of
    those tools resolve correctly even when the harness shell hasn't run
    the corresponding activation.
    """

    def __init__(self, extra_path_dirs: Sequence[str] = _SHIM_FALLBACK_DIRS) -> None:
        self._env = os.environ.copy()
        self._env["PATH"] = _augment_path(self._env.get("PATH", ""), extra_path_dirs)

    def which(self, name: str) -> str | None:
        return shutil.which(name, path=self._env["PATH"])

    def run(
        self,
        args: Sequence[str],
        cwd: str | None = None,
        stdin: str | None = None,
    ) -> ProcessResult:
        try:
            completed = subprocess.run(  # noqa: S603 — args list, no shell
                list(args),
                cwd=cwd,
                input=stdin,
                capture_output=True,
                text=True,
                # Force UTF-8 decode rather than the platform default. Windows
                # CI runs default to cp1252, which raises UnicodeDecodeError
                # on prettier's `…` ellipsis, smart quotes from yamllint
                # messages, em-dashes in finding text, and any unicode path
                # bytes. Every supported formatter emits UTF-8; errors are
                # `replace`-substituted so a stray non-UTF-8 byte degrades to
                # a placeholder character instead of crashing the runner.
                encoding="utf-8",
                errors="replace",
                check=False,
                env=self._env,
            )
        except FileNotFoundError as exc:
            # `which()` resolved a path that does not exist (stale shim,
            # broken symlink, race between `which` and `run`). Surface as
            # POSIX "command not found" — caller-side error handling
            # already covers non-zero exits, and the alternative is
            # callers wrapping every run() in try/except.
            return ProcessResult(returncode=127, stdout="", stderr=str(exc))
        except PermissionError as exc:
            # Binary exists but is not executable (chmod -x, mounted with
            # noexec, ACL-denied). POSIX shells exit 126 in this case.
            return ProcessResult(returncode=126, stdout="", stderr=str(exc))
        except OSError as exc:
            # Catch-all for the remaining exec-time OS errors (ENOEXEC,
            # ENOTDIR mid-path, ELOOP, ENAMETOOLONG, etc.). Same rationale
            # as the two narrower handlers above — propagating would force
            # every caller to wrap run() in a try/except and would crash
            # the CLI on a non-fatal toolchain hiccup. 126 is the closest
            # POSIX shell convention for "command exists but cannot be
            # executed."
            return ProcessResult(returncode=126, stdout="", stderr=str(exc))
        return ProcessResult(
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )
