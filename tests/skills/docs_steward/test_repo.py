"""repo.repo_root — git success + fallback semantics."""

from __future__ import annotations

import unittest

from docs_steward.process import ProcessResult
from docs_steward.repo import repo_root

from .fakes import FakeProcessRunner


class RepoRootTests(unittest.TestCase):
    def test_git_success_returns_stripped_path(self) -> None:
        runner = FakeProcessRunner(
            results={
                ("git", "rev-parse", "--show-toplevel"): ProcessResult(
                    0, "/repo/root\n", ""
                ),
            }
        )
        self.assertEqual(repo_root(runner, cwd="/anywhere"), "/repo/root")

    def test_git_failure_returns_fallback_cwd(self) -> None:
        runner = FakeProcessRunner(
            results={
                ("git", "rev-parse", "--show-toplevel"): ProcessResult(
                    128, "", "not a git repository"
                ),
            }
        )
        self.assertEqual(repo_root(runner, cwd="/outside"), "/outside")

    def test_empty_stdout_falls_back_even_with_exit_0(self) -> None:
        runner = FakeProcessRunner(
            results={
                ("git", "rev-parse", "--show-toplevel"): ProcessResult(0, "  \n", ""),
            }
        )
        self.assertEqual(repo_root(runner, cwd="/cwd"), "/cwd")


if __name__ == "__main__":
    unittest.main()
