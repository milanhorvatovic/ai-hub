"""discovery.list_markdown_files — git-first with filesystem fallback."""

from __future__ import annotations

import os
import tempfile
import unittest

from docs_steward.discovery import list_markdown_files
from docs_steward.process import ProcessResult

from .fakes import FakeProcessRunner


class GitLsFilesPathTests(unittest.TestCase):
    def test_uses_git_ls_files_when_available(self) -> None:
        runner = FakeProcessRunner(
            results={
                ("git", "ls-files", "--cached", "--others", "--exclude-standard", "--", ":(glob)**/*.md", ":(glob)**/*.markdown"): ProcessResult(
                    0, "README.md\ndocs/intro.md\n", ""
                ),
            }
        )
        files = list_markdown_files(runner, "/repo")
        self.assertEqual(
            sorted(files),
            sorted(["/repo/README.md", "/repo/docs/intro.md"]),
        )

    def test_git_returns_empty_when_no_markdown(self) -> None:
        runner = FakeProcessRunner(
            results={
                ("git", "ls-files", "--cached", "--others", "--exclude-standard", "--", ":(glob)**/*.md", ":(glob)**/*.markdown"): ProcessResult(0, "", ""),
            }
        )
        self.assertEqual(list_markdown_files(runner, "/repo"), [])

    def test_includes_untracked_files_via_others_flag(self) -> None:
        # `git ls-files --cached --others --exclude-standard *.md *.markdown`
        # surfaces both tracked AND untracked-but-not-ignored markdown.
        # Without --others, freshly created files would be silently skipped.
        runner = FakeProcessRunner(
            results={
                ("git", "ls-files", "--cached", "--others", "--exclude-standard", "--", ":(glob)**/*.md", ":(glob)**/*.markdown"): ProcessResult(
                    0, "README.md\nNEW_UNTRACKED.md\n", ""
                ),
            }
        )
        files = list_markdown_files(runner, "/repo")
        self.assertEqual(
            sorted(files),
            sorted(["/repo/README.md", "/repo/NEW_UNTRACKED.md"]),
        )

    def test_deduplicates_paths_that_surface_twice(self) -> None:
        # Defensive: certain index states can surface a path in both the
        # --cached and --others halves of the listing; dedup preserves
        # first-seen order and reports each path exactly once.
        runner = FakeProcessRunner(
            results={
                ("git", "ls-files", "--cached", "--others", "--exclude-standard", "--", ":(glob)**/*.md", ":(glob)**/*.markdown"): ProcessResult(
                    0, "README.md\ndocs/intro.md\nREADME.md\n", ""
                ),
            }
        )
        files = list_markdown_files(runner, "/repo")
        self.assertEqual(files, ["/repo/README.md", "/repo/docs/intro.md"])


class WalkFallbackTests(unittest.TestCase):
    def test_walk_used_when_git_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "docs"))
            os.makedirs(os.path.join(tmp, "node_modules", "pkg"))
            for path in [
                os.path.join(tmp, "README.md"),
                os.path.join(tmp, "docs", "intro.markdown"),
                os.path.join(tmp, "ignored.txt"),
                os.path.join(tmp, "node_modules", "pkg", "DEEP.md"),  # must be skipped
            ]:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write("placeholder\n")

            runner = FakeProcessRunner(
                results={
                    ("git", "ls-files", "--cached", "--others", "--exclude-standard", "--", ":(glob)**/*.md", ":(glob)**/*.markdown"): ProcessResult(
                        128, "", "not a git repository"
                    ),
                }
            )
            files = list_markdown_files(runner, tmp)
            basenames = sorted(os.path.basename(f) for f in files)
            self.assertEqual(basenames, ["README.md", "intro.markdown"])

    def test_walk_skips_standard_excluded_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for skip in (".git", "node_modules", "dist", "build", ".venv", "venv", "target"):
                os.makedirs(os.path.join(tmp, skip))
                with open(os.path.join(tmp, skip, "f.md"), "w", encoding="utf-8") as fh:
                    fh.write("x\n")
            with open(os.path.join(tmp, "ok.md"), "w", encoding="utf-8") as fh:
                fh.write("ok\n")

            runner = FakeProcessRunner(
                results={
                    ("git", "ls-files", "--cached", "--others", "--exclude-standard", "--", ":(glob)**/*.md", ":(glob)**/*.markdown"): ProcessResult(128, "", ""),
                }
            )
            files = list_markdown_files(runner, tmp)
            self.assertEqual(len(files), 1)
            self.assertTrue(files[0].endswith("ok.md"))


if __name__ == "__main__":
    unittest.main()
