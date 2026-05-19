"""Filesystem port + concrete os-backed adapter.

`FileSystem` is the surface every module uses for file-existence checks; no
module imports `os.path` directly for that purpose. Production code wires
`OsFileSystem`; tests inject `FakeFileSystem` from `tests/fakes.py`.
"""

from __future__ import annotations

import os.path
from typing import Protocol


class FileSystem(Protocol):
    def exists(self, path: str) -> bool:
        """True iff `path` resolves to an existing regular file."""
        ...

    def read_text(self, path: str) -> str:
        """Read `path` as UTF-8 text. Raises OSError on missing or unreadable
        files; callers in services treat that as a file-level WARN/FAIL event
        rather than propagating to the CLI layer."""
        ...


class OsFileSystem:
    """Stdlib-backed `FileSystem`. Considers only regular files (not dirs)."""

    def exists(self, path: str) -> bool:
        return os.path.isfile(path)

    def read_text(self, path: str) -> str:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
