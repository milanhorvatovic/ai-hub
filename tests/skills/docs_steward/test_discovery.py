"""discovery.list_markdown_files — git-first with filesystem fallback."""

from __future__ import annotations

import os
import tempfile
import unittest

from docs_steward.discovery import list_markdown_files
from docs_steward.process import ProcessResult

from .fakes import FakeFileSystem, FakeProcessRunner


def _fs_with(root: str, *rels: str) -> FakeFileSystem:
    """Mark each relative path as existing under `root` for discovery's
    on-disk filter step. Content is empty (the filter only consults
    `exists`, not `read_text`)."""
    # Forward-slash join matches discovery's probe path exactly on every
    # host (discovery checks the POSIX-normalized path it returns).
    return FakeFileSystem(files={f"{root}/{rel}": "" for rel in rels})


class GitLsFilesPathTests(unittest.TestCase):
    def test_uses_git_ls_files_when_available(self) -> None:
        runner = FakeProcessRunner(
            results={
                ("git", "ls-files", "--cached", "--others", "--exclude-standard", "--", ":(glob)**/*.md", ":(glob)**/*.markdown"): ProcessResult(
                    0, "README.md\ndocs/intro.md\n", ""
                ),
            }
        )
        files = list_markdown_files(
            runner, "/repo", fs=_fs_with("/repo", "README.md", "docs/intro.md"),
        )
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
        self.assertEqual(
            list_markdown_files(runner, "/repo", fs=FakeFileSystem()), [],
        )

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
        files = list_markdown_files(
            runner, "/repo",
            fs=_fs_with("/repo", "README.md", "NEW_UNTRACKED.md"),
        )
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
        files = list_markdown_files(
            runner, "/repo", fs=_fs_with("/repo", "README.md", "docs/intro.md"),
        )
        self.assertEqual(files, ["/repo/README.md", "/repo/docs/intro.md"])

    def test_default_fallback_filters_out_directory_named_like_markdown(self) -> None:
        # Regression: the no-fs fallback previously used os.path.exists,
        # which accepts directories. A directory named like a markdown
        # file (`README.md/` — possible on case-insensitive filesystems
        # or via deliberate authoring) would slip through and the
        # downstream read_text would raise IsADirectoryError. The
        # fallback now uses os.path.isfile (regular files only), so the
        # directory entry is filtered out before the downstream read.
        with tempfile.TemporaryDirectory() as tmp:
            # Create one real file and one directory that the git
            # listing claims is a file.
            real_md = os.path.join(tmp, "real.md")
            with open(real_md, "w", encoding="utf-8") as fh:
                fh.write("# real\n")
            dir_named_like_md = os.path.join(tmp, "fake.md")
            os.makedirs(dir_named_like_md)

            runner = FakeProcessRunner(
                results={
                    ("git", "ls-files", "--cached", "--others", "--exclude-standard", "--", ":(glob)**/*.md", ":(glob)**/*.markdown"): ProcessResult(
                        0, "real.md\nfake.md\n", ""
                    ),
                }
            )
            # No fs override → falls through to os.path.isfile.
            files = list_markdown_files(runner, tmp)
            basenames = sorted(os.path.basename(f) for f in files)
            self.assertEqual(basenames, ["real.md"])

    def test_git_path_filters_paths_under_skip_dirs(self) -> None:
        # Regression: the walk fallback prunes node_modules / .git /
        # dist / build / .venv / venv / target via os.walk's dirnames
        # mutation, but the git-backed path returned every tracked path
        # unfiltered. A repo that checks in markdown under one of those
        # directories (vendored docs, built artifacts, .venv site-
        # packages docs) would surface them despite SKILL.md's skip
        # promise. The git path now applies the same contract.
        runner = FakeProcessRunner(
            results={
                ("git", "ls-files", "--cached", "--others", "--exclude-standard", "--", ":(glob)**/*.md", ":(glob)**/*.markdown"): ProcessResult(
                    0,
                    "README.md\n"
                    "node_modules/pkg/README.md\n"
                    "dist/built.md\n"
                    "vendor/.venv/site-packages/x.md\n"
                    "docs/intro.md\n",
                    "",
                ),
            }
        )
        files = list_markdown_files(
            runner, "/repo",
            fs=_fs_with(
                "/repo",
                "README.md",
                "node_modules/pkg/README.md",
                "dist/built.md",
                "vendor/.venv/site-packages/x.md",
                "docs/intro.md",
            ),
        )
        self.assertEqual(
            sorted(files),
            sorted(["/repo/README.md", "/repo/docs/intro.md"]),
        )

    def test_filters_out_index_entries_for_deleted_working_tree_files(self) -> None:
        # Regression: `git ls-files --cached` keeps an entry for a tracked
        # file the user has rm-ed but not `git rm`-ed. Downstream audit
        # would read a non-existent path and emit a misleading ERROR. The
        # discovery filter excludes any entry whose working-tree file is
        # gone — only paths that actually exist make it into the output.
        runner = FakeProcessRunner(
            results={
                ("git", "ls-files", "--cached", "--others", "--exclude-standard", "--", ":(glob)**/*.md", ":(glob)**/*.markdown"): ProcessResult(
                    0, "README.md\nremoved.md\n", ""
                ),
            }
        )
        # `removed.md` is in the listing but NOT in the fake fs.
        files = list_markdown_files(
            runner, "/repo", fs=_fs_with("/repo", "README.md"),
        )
        self.assertEqual(files, ["/repo/README.md"])


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
