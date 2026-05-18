"""Repository-root resolution via git, with cwd fallback.

Pure function taking a `ProcessRunner` and an optional fallback `cwd`. When
git is unavailable or the cwd is not inside a working tree, returns the
fallback. Never raises.
"""

from __future__ import annotations

import os

from .process import ProcessRunner


def repo_root(runner: ProcessRunner, cwd: str | None = None) -> str:
    """Return the absolute path to the enclosing git working tree, or `cwd`
    when not in a repo. When `cwd` is None, uses `os.getcwd()`."""
    fallback = cwd if cwd is not None else os.getcwd()
    result = runner.run(["git", "rev-parse", "--show-toplevel"], cwd=fallback)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return fallback
