"""Markdown file discovery.

`list_markdown_files(runner, root)` prefers `git ls-files` (respects
`.gitignore`) and falls back to a `find`-equivalent walk implemented in
pure Python when git is unavailable. Returns absolute paths.

Skipped directories match the SKILL.md inventory step — `node_modules`,
`.git`, `dist`, `build`, `.venv`, `venv`, `target`. The walk is breadth-
agnostic; paths are returned in OS traversal order (which differs by
platform — callers that need stable ordering should `sorted()` the result).
"""

from __future__ import annotations

import os

from .process import ProcessRunner


_MARKDOWN_EXTENSIONS = (".md", ".markdown")
_SKIP_DIRS = frozenset(
    ("node_modules", ".git", "dist", "build", ".venv", "venv", "target")
)


def list_markdown_files(runner: ProcessRunner, root: str) -> list[str]:
    """Return absolute paths to every markdown file under `root`. Empty list
    when there are none; never raises."""
    git_listed = _try_git_ls_files(runner, root)
    if git_listed is not None:
        return git_listed
    return _walk(root)


def _try_git_ls_files(runner: ProcessRunner, root: str) -> list[str] | None:
    """Attempt `git ls-files`; return None when git is absent or the cwd is
    not a git repository (caller should fall back to filesystem walk)."""
    result = runner.run(
        ["git", "ls-files", "*.md", "*.markdown"], cwd=root
    )
    if result.returncode != 0:
        return None
    rels = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return [os.path.join(root, rel) for rel in rels]


def _walk(root: str) -> list[str]:
    """Stdlib-only filesystem walk respecting the same skip-dirs the bash
    `find` invocation used. Pure — no ProcessRunner needed for this path."""
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            if name.endswith(_MARKDOWN_EXTENSIONS):
                found.append(os.path.join(dirpath, name))
    return found
