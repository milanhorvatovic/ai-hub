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

from .fs import FileSystem
from .process import ProcessRunner

_MARKDOWN_EXTENSIONS = (".md", ".markdown")
_SKIP_DIRS = frozenset(
    ("node_modules", ".git", "dist", "build", ".venv", "venv", "target")
)


def list_markdown_files(
    runner: ProcessRunner, root: str, fs: FileSystem | None = None,
) -> list[str]:
    """Return absolute paths to every markdown file under `root`. Empty list
    when there are none; never raises.

    `fs` is consulted only by the git-backed path to filter out index
    entries whose working-tree file has been deleted (`git ls-files
    --cached` still surfaces them). Default `None` uses `os.path.isfile`
    so production code keeps a zero-argument call AND matches the
    FileSystem.exists / OsFileSystem.exists contract (regular files
    only — a directory named `README.md` must not pass the filter or
    the downstream `read_text` would raise IsADirectoryError). Tests
    inject a `FakeFileSystem` so the synthesized paths can be marked
    existent.
    """
    git_listed = _try_git_ls_files(runner, root, fs)
    if git_listed is not None:
        return git_listed
    return _walk(root)


def _try_git_ls_files(
    runner: ProcessRunner, root: str, fs: FileSystem | None,
) -> list[str] | None:
    """Attempt `git ls-files`; return None when git is absent or the cwd is
    not a git repository (caller should fall back to filesystem walk).

    The listing intentionally includes both tracked AND
    untracked-but-not-ignored markdown files via `--cached --others
    --exclude-standard`. A bare `git ls-files *.md *.markdown` would
    silently drop newly created markdown files that have not been
    `git add`-ed yet, contradicting the skill's promise to inspect every
    markdown file under root that `.gitignore` doesn't exclude.
    """
    # The `--` separator is load-bearing: without it, a markdown file named
    # `--all.md` would be parsed as a (nonsensical) flag by `git ls-files`
    # rather than treated as a pathspec; with it, every following argument
    # is unambiguously a pathspec. `:(glob)**/*.md` / `:(glob)**/*.markdown`
    # uses git's explicit glob magic so recursion is independent of the
    # caller's GIT_GLOB_PATHSPECS / core.wildmatch config (the bare `*.md`
    # pathspec behaves differently across git versions and shells).
    result = runner.run(
        [
            "git", "ls-files",
            "--cached", "--others", "--exclude-standard",
            "--",
            ":(glob)**/*.md", ":(glob)**/*.markdown",
        ],
        cwd=root,
    )
    if result.returncode != 0:
        return None
    rels = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    # Deduplicate: --cached and --others can both surface the same path
    # in certain index states; preserve first-seen order.
    seen: set[str] = set()
    unique_rels: list[str] = []
    for rel in rels:
        if rel not in seen:
            seen.add(rel)
            unique_rels.append(rel)
    # Drop paths under any _SKIP_DIRS segment. The git listing is
    # unfiltered by construction — `git ls-files` tracks vendored files
    # when they've been committed, so a repo that checks in markdown
    # under `node_modules/` or `vendor-built/dist/` would surface those
    # entries. The walk fallback prunes the same set via os.walk's
    # dirnames mutation; the git path must apply the same contract or
    # the SKILL.md "skips node_modules / .git / dist / build / .venv /
    # venv / target" promise diverges between modes.
    unique_rels = [r for r in unique_rels if not _has_skip_segment(r)]
    # Filter to paths that actually exist on disk. `git ls-files --cached`
    # still surfaces an entry for a tracked file the user has deleted in
    # their working tree (the deletion isn't `git rm`-ed yet), but the
    # downstream audit would then read a non-existent path and emit a
    # misleading ERROR event. Honouring "what's on disk now" matches the
    # skill's intent of auditing real files.
    # Use `os.path.isfile` (regular files only) for the no-fs fallback
    # so a directory entry that happens to share a markdown filename
    # ("README.md/" — yes it can happen, especially under case-
    # insensitive filesystems) doesn't pass the filter and trigger an
    # IsADirectoryError downstream. `FileSystem.exists` / `OsFileSystem.exists`
    # already enforce regular-files-only.
    # Probe the same forward-slash-joined path this function returns, so
    # the existence check and the returned inventory name one identical
    # path on every host (os.path.join would insert backslashes on
    # Windows while the return value stays POSIX-normalized).
    exists = fs.exists if fs is not None else os.path.isfile
    return [
        joined
        for rel in unique_rels
        if exists(joined := _posix_join(root, rel))
    ]


def _walk(root: str) -> list[str]:
    """Stdlib-only filesystem walk respecting the same skip-dirs the bash
    `find` invocation used. Pure — no ProcessRunner needed for this path."""
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            if name.endswith(_MARKDOWN_EXTENSIONS):
                found.append(_posix_join(dirpath, name))
    return found


def _has_skip_segment(rel: str) -> bool:
    """True when any path segment of `rel` matches a skip-dir name.
    `rel` is a git-listed path (POSIX-slash) relative to the repo root."""
    return any(seg in _SKIP_DIRS for seg in rel.split("/"))


def _posix_join(root: str, rel: str) -> str:
    """Join with forward slashes so output is consistent across platforms.
    `git ls-files` returns POSIX-style paths, and downstream formatter
    binaries accept forward slashes on Windows too — keeping one separator
    in NDJSON output avoids mixed `/repo\\README.md` artifacts on Windows."""
    root_posix = root.replace("\\", "/").rstrip("/")
    rel_posix = rel.replace("\\", "/").lstrip("/")
    return f"{root_posix}/{rel_posix}"
