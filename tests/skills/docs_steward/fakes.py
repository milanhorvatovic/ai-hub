"""Test doubles for the `ProcessRunner` and `FileSystem` ports.

`FakeProcessRunner` is configured with two dicts — one mapping binary names
to their absolute paths (controlling `which`), one mapping argv tuples to
`ProcessResult` values (controlling `run`). Calls to unknown binaries return
None from `which`; calls to unconfigured argv raise AssertionError so tests
fail loudly on accidental subprocess invocations. `stdin` is recorded in
the call log alongside argv/cwd; the key for `results` lookup is argv alone
(stdin-conditional results would over-couple tests to invocation details).

`FakeFileSystem` is configured with a dict of paths-to-content. `exists` is
True iff the path is in the dict; `read_text` returns the content; unknown
paths in `read_text` raise FileNotFoundError so behavior matches OsFileSystem.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from docs_steward.process import ProcessResult


@dataclass
class FakeProcessRunner:
    paths: dict[str, str] = field(default_factory=dict)
    results: dict[tuple[str, ...], ProcessResult] = field(default_factory=dict)
    calls: list[tuple[tuple[str, ...], str | None, str | None]] = field(default_factory=list)

    def which(self, name: str) -> str | None:
        return self.paths.get(name)

    def run(
        self,
        args: Sequence[str],
        cwd: str | None = None,
        stdin: str | None = None,
    ) -> ProcessResult:
        key = tuple(args)
        self.calls.append((key, cwd, stdin))
        if key not in self.results:
            raise AssertionError(
                f"FakeProcessRunner has no configured result for argv={key!r}; "
                f"calls so far: {self.calls!r}"
            )
        return self.results[key]


@dataclass
class FakeFileSystem:
    files: dict[str, str] = field(default_factory=dict)

    def exists(self, path: str) -> bool:
        return path in self.files

    def read_text(self, path: str) -> str:
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]
