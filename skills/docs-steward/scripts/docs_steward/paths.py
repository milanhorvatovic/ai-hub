"""Cross-host path helpers.

The orchestrator regularly receives paths in three shapes — POSIX
absolute (`/etc/foo`), Windows drive-letter (`C:\\foo` or `C:/foo`),
and relative — from sources that don't agree on the host the CLI is
running under (git ls-files emits POSIX, WSL users type POSIX, Windows
CI agents type drive-letter). These helpers give every call site one
shared answer so the absolute-vs-relative branching and the
separator-normalization for downstream emission don't drift across
cli.py and runner.py.

Public API:
- `is_absolute(path)`: cross-platform absolute-path check.
- `to_posix(path)`: forward-slash normalization.
- `posix_join(root, rel)`: forward-slash join.
"""

from __future__ import annotations


def is_absolute(path: str) -> bool:
    """Cross-platform absolute-path check.

    Returns True for POSIX-leading-slash form (`/etc/foo`, also a UNC-
    style `\\\\share\\foo` leading backslash) AND for the Windows drive-
    letter form (`C:\\foo` or `C:/foo`). `os.path.isabs` would say
    `/etc/foo` is NOT absolute on Windows (no drive), which is fine for
    native Windows code but inappropriate here — the orchestrator
    regularly receives POSIX-style paths from git ls-files and from
    users running under WSL / Git Bash.

    The drive-letter check requires:
      - path[0] is an ASCII alpha (single drive letter)
      - len >= 3
      - path[2] is a path separator ('/' or '\\')

    The narrower check rejects POSIX filenames that incidentally have
    a colon at index 1 (`a:b.md`, `a:.editorconfig` — colons in
    filenames are legal on POSIX) which the looser path[1]==':' test
    would have misclassified as absolute.
    """
    if not path:
        return False
    if path[0] in ("/", "\\"):
        return True
    if (
        len(path) >= 3
        and path[0].isalpha()
        and path[1] == ":"
        and path[2] in ("/", "\\")
    ):
        return True
    return False


def to_posix(path: str) -> str:
    """Normalize a path's separators to forward slashes."""
    return path.replace("\\", "/")


def posix_join(root: str, rel: str) -> str:
    """Join `rel` against `root` with forward slashes, host-independent.

    Downstream formatters (Prettier, markdownlint, mdformat, dprint,
    remark) all accept forward slashes on Windows; normalizing here
    keeps NDJSON output and command lines consistent across hosts and
    avoids `os.path.join('/repo', '.prettierrc')` producing
    `/repo\\.prettierrc` on Windows."""
    root_norm = to_posix(root).rstrip("/")
    rel_norm = to_posix(rel).lstrip("/")
    return f"{root_norm}/{rel_norm}"
