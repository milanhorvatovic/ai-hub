"""cli.main — end-to-end through serialization, with patched runner."""

from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from docs_steward.cli import (
    _resolve_against_root,
    _resolve_config_against_cwd,
    _resolve_config_against_root,
    main,
)
from docs_steward.process import ProcessResult

from .fakes import FakeProcessRunner


class CliEndToEndTests(unittest.TestCase):
    def _run(self, runner: FakeProcessRunner, argv: list[str]) -> tuple[int, list[dict]]:
        buf = io.StringIO()
        with patch("docs_steward.cli.SubprocessRunner", return_value=runner), patch(
            "sys.stdout", buf
        ):
            code = main(argv)
        lines = [line for line in buf.getvalue().splitlines() if line.strip()]
        return code, [json.loads(line) for line in lines]

    def test_probe_no_tools_emits_one_missing_event_exit_3(self) -> None:
        code, events = self._run(FakeProcessRunner(), ["probe"])
        self.assertEqual(code, 3)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "missing")

    def test_recommend_tools_no_tools_yields_6_recommends(self) -> None:
        code, events = self._run(FakeProcessRunner(), ["recommend-tools"])
        self.assertEqual(code, 1)
        recommends = [e for e in events if e["event"] == "recommend"]
        self.assertEqual(len(recommends), 6)
        self.assertEqual([r["detail"]["priority_rank"] for r in recommends], [1, 2, 3, 4, 5, 6])

    def test_audit_baseline_override_skips_detection(self) -> None:
        cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results={
                ("git", "rev-parse", "--show-toplevel"): ProcessResult(
                    0, "/repo\n", ""
                ),
                cmd: ProcessResult(0, "", ""),
            },
        )
        code, events = self._run(runner, ["md-audit", "--baseline", ".prettierrc"])
        self.assertEqual(code, 0)
        selected = [e for e in events if e["event"] == "selected"][0]
        self.assertEqual(selected["detail"]["baseline"], ".prettierrc")

    def test_format_with_unwrap_propagates_flag_through_to_command(self) -> None:
        cmd = (
            "prettier",
            "--config",
            "/repo/.prettierrc",
            "--prose-wrap=never",
            "--write",
            "--parser",
            "markdown",
            "**/*.md",
            "**/*.markdown",
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results={
                ("git", "rev-parse", "--show-toplevel"): ProcessResult(0, "/repo\n", ""),
                cmd: ProcessResult(0, "foo.md 12ms\n", ""),
            },
        )
        code, events = self._run(
            runner, ["md-format", "--baseline", ".prettierrc", "--unwrap"]
        )
        self.assertEqual(code, 1)
        selected = [e for e in events if e["event"] == "selected"][0]
        self.assertTrue(selected["detail"]["unwrap"])
        self.assertIn("--prose-wrap=never", selected["detail"]["cmd"])

    def test_unknown_subcommand_exits_2(self) -> None:
        with self.assertRaises(SystemExit) as ctx, patch("sys.stderr", io.StringIO()):
            main(["bogus"])
        self.assertEqual(ctx.exception.code, 2)

    def test_md_audit_accepts_positional_files(self) -> None:
        # Per-file targeting (#1) via positional args. _files_or_none
        # resolves relative paths against the invocation cwd, so the
        # formatter argv carries the absolute path — patch os.getcwd so
        # the test runs as if the user was at /repo when they typed
        # `md-audit.py docs/intro.md`.
        cmd = (
            "prettier", "--config", "/repo/.prettierrc",
            "--check", "--parser", "markdown",
            "--", "/repo/docs/intro.md",
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results={
                ("git", "rev-parse", "--show-toplevel"): ProcessResult(0, "/repo\n", ""),
                cmd: ProcessResult(0, "", ""),
            },
        )
        with patch("docs_steward.cli.os.getcwd", return_value="/repo"):
            code, events = self._run(
                runner, ["md-audit", "--baseline", ".prettierrc", "docs/intro.md"],
            )
        self.assertEqual(code, 0)
        selected = [e for e in events if e["event"] == "selected"][0]
        self.assertEqual(selected["detail"]["files_scoped"], 1)

    def test_md_audit_quiet_filters_preamble(self) -> None:
        cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results={
                ("git", "rev-parse", "--show-toplevel"): ProcessResult(0, "/repo\n", ""),
                cmd: ProcessResult(
                    1, "Linting: 3 file(s)\nSummary: 1 error(s)\nfoo.md:1 MD040\n", "",
                ),
            },
        )
        code, events = self._run(
            runner, ["md-audit", "--baseline", ".prettierrc", "--quiet"],
        )
        self.assertEqual(code, 1)
        findings = [e for e in events if e["event"] == "finding"]
        self.assertEqual(len(findings), 1)
        self.assertIn("MD040", findings[0]["detail"])

    def test_md_format_dry_run_emits_would_change(self) -> None:
        audit_cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results={
                ("git", "rev-parse", "--show-toplevel"): ProcessResult(0, "/repo\n", ""),
                audit_cmd: ProcessResult(1, "foo.md\n", ""),
            },
        )
        code, events = self._run(
            runner, ["md-format", "--baseline", ".prettierrc", "--dry-run"],
        )
        self.assertEqual(code, 1)
        self.assertEqual(
            [e for e in events if e["event"] == "would-change"],
            [{"event": "would-change", "tool": "prettier", "detail": "foo.md"}],
        )

    def test_md_audit_emits_plugin_missing_when_mdformat_lacks_gfm(self) -> None:
        # mdformat selected, mdformat-gfm not installed, file has GFM table.
        # The audit should emit a plugin-missing event before the formatter runs.
        # Use --baseline that maps to mdformat (no markdownlint/prettier on PATH).
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            md_path = os.path.join(tmp, "table.md")
            with open(md_path, "w", encoding="utf-8") as fh:
                fh.write("| col | col |\n|---|---|\n| a | b |\n")

            # The CLI normalizes absolute paths to forward slashes
            # through _to_posix, so the formatter argv and the plugin-
            # missing event carry the POSIX-style form regardless of
            # host. Build the expectation accordingly.
            md_path_posix = md_path.replace("\\", "/")
            audit_cmd = ("mdformat", "--check", "--", md_path_posix)
            runner = FakeProcessRunner(
                paths={"mdformat": "/x/mdformat", "git": "/x/git"},
                results={
                    ("git", "rev-parse", "--show-toplevel"): ProcessResult(0, tmp + "\n", ""),
                    audit_cmd: ProcessResult(0, "", ""),
                },
            )
            code, events = self._run(
                runner, ["md-audit", "--baseline", "universal-subset", md_path],
            )
            self.assertEqual(code, 0)
            plugin_missing = [e for e in events if e["event"] == "plugin-missing"]
            self.assertEqual(len(plugin_missing), 1)
            self.assertEqual(plugin_missing[0]["detail"]["plugin"], "gfm")
            self.assertEqual(plugin_missing[0]["detail"]["file"], md_path_posix)

    def test_md_audit_plugin_missing_resolves_relative_files_against_root(self) -> None:
        # Same setup as the previous test, but the positional file argument
        # is relative ("table.md") and the process CWD is intentionally
        # unrelated. Without resolution the read would fail and no
        # plugin-missing event would be emitted; with resolution the read
        # hits <root>/table.md and the event fires.
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            md_path = os.path.join(tmp, "table.md")
            with open(md_path, "w", encoding="utf-8") as fh:
                fh.write("| col | col |\n|---|---|\n| a | b |\n")

            # _files_or_none now resolves relative paths against the
            # invocation cwd. Patch os.getcwd to the test tmpdir so the
            # resolved positional arg lands at tmp/table.md (matching
            # what the user expects when running from inside tmp).
            expected_md = tmp.replace("\\", "/").rstrip("/") + "/table.md"
            audit_cmd = ("mdformat", "--check", "--", expected_md)
            runner = FakeProcessRunner(
                paths={"mdformat": "/x/mdformat", "git": "/x/git"},
                results={
                    ("git", "rev-parse", "--show-toplevel"): ProcessResult(0, tmp + "\n", ""),
                    audit_cmd: ProcessResult(0, "", ""),
                },
            )
            with patch("docs_steward.cli.os.getcwd", return_value=tmp):
                code, events = self._run(
                    runner, ["md-audit", "--baseline", "universal-subset", "table.md"],
                )
            self.assertEqual(code, 0)
            plugin_missing = [e for e in events if e["event"] == "plugin-missing"]
            self.assertEqual(len(plugin_missing), 1)
            self.assertEqual(plugin_missing[0]["detail"]["plugin"], "gfm")
            # Event records the resolved (absolute) path so consumers can
            # locate the file regardless of where the CLI was invoked from.
            # _resolve_against_root emits forward-slash paths on every host,
            # so the expected value normalizes the os.path.join result to
            # forward slashes; on POSIX this is a no-op, on Windows it
            # rewrites the native backslash separator.
            expected_file = md_path.replace("\\", "/")
            self.assertEqual(plugin_missing[0]["detail"]["file"], expected_file)

    def test_md_audit_skips_plugin_check_when_tool_is_not_mdformat(self) -> None:
        # prettier selected → no plugin-missing event regardless of file content.
        cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results={
                ("git", "rev-parse", "--show-toplevel"): ProcessResult(0, "/repo\n", ""),
                cmd: ProcessResult(0, "", ""),
            },
        )
        code, events = self._run(runner, ["md-audit", "--baseline", ".prettierrc"])
        self.assertEqual(code, 0)
        self.assertEqual([e for e in events if e["event"] == "plugin-missing"], [])

    def test_md_fix_clean_yields_zero_delta(self) -> None:
        audit_cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results={
                ("git", "rev-parse", "--show-toplevel"): ProcessResult(0, "/repo\n", ""),
                audit_cmd: ProcessResult(0, "", ""),
            },
        )
        code, events = self._run(
            runner, ["md-fix", "--baseline", ".prettierrc"],
        )
        self.assertEqual(code, 0)
        deltas = [e for e in events if e["event"] == "delta"]
        self.assertEqual(len(deltas), 1)
        self.assertEqual(
            deltas[0]["detail"], {"resolved": 0, "still_open": 0, "new": 0},
        )


class ResolveAgainstRootTests(unittest.TestCase):
    def test_absolute_paths_pass_through(self) -> None:
        resolved = _resolve_against_root(("/repo/a.md", "/repo/b.md"), "/somewhere/else")
        self.assertEqual(resolved, ("/repo/a.md", "/repo/b.md"))

    def test_windows_absolute_paths_normalized_to_forward_slashes(self) -> None:
        # A user-supplied Windows path keeps drive-letter form but
        # backslashes are flipped to forward slashes so NDJSON output
        # and rendered cmd strings never mix the two separators alongside
        # discovery's POSIX-joined paths.
        resolved = _resolve_against_root(
            ("C:\\repo\\file.md", "D:/already/forward.md"), "/repo",
        )
        self.assertEqual(resolved, ("C:/repo/file.md", "D:/already/forward.md"))

    def test_posix_filename_with_colon_is_relative_not_absolute(self) -> None:
        # Regression: `_is_absolute` previously treated any string with
        # ':' at index 1 as a Windows drive-letter path. POSIX filenames
        # with a colon ('a:b.md', 'a:.editorconfig') were misclassified
        # as absolute, skipping the cwd-join and leaving the formatter
        # unable to locate them. The drive-letter check now requires
        # path[0] alpha + len>=3 + path[2] in ('/','\\\\').
        resolved = _resolve_against_root(("a:b.md", "x:.editorconfig"), "/repo")
        # Both should be joined to root, not pass through as absolute.
        self.assertEqual(resolved, ("/repo/a:b.md", "/repo/x:.editorconfig"))

    def test_drive_letter_form_requires_separator_after_colon(self) -> None:
        # `C:foo.md` (no separator after colon) is the cmd.exe-style
        # drive-relative path — uncommon, and not what _is_absolute
        # is meant to recognize. The tightened check requires a real
        # path separator at index 2.
        resolved = _resolve_against_root(("C:foo.md",), "/repo")
        self.assertEqual(resolved, ("/repo/C:foo.md",))

    def test_relative_paths_joined_to_root(self) -> None:
        # Forward-slash join regardless of host (production uses _posix_join
        # so the command line lands the same way on Linux, macOS, and
        # Windows CI — os.path.join on Windows would insert backslashes).
        resolved = _resolve_against_root(("docs/a.md", "b.md"), "/repo")
        self.assertEqual(resolved, ("/repo/docs/a.md", "/repo/b.md"))

    def test_mixed_paths(self) -> None:
        resolved = _resolve_against_root(("/abs/a.md", "rel/b.md"), "/repo")
        self.assertEqual(resolved, ("/abs/a.md", "/repo/rel/b.md"))

    def test_empty_files_returns_empty_tuple(self) -> None:
        self.assertEqual(_resolve_against_root((), "/repo"), ())


class ResolveConfigAgainstRootTests(unittest.TestCase):
    def test_none_passes_through(self) -> None:
        # None signals "use the bundled fallback" — must NOT be rewritten
        # to a path under root, or audit_frontmatter would receive a fake
        # path instead of routing through bundled_config_for().
        self.assertIsNone(_resolve_config_against_root(None, "/repo"))

    def test_absolute_path_passes_through(self) -> None:
        self.assertEqual(
            _resolve_config_against_root("/etc/yamllint.yaml", "/repo"),
            "/etc/yamllint.yaml",
        )

    def test_absolute_windows_path_normalized_to_forward_slashes(self) -> None:
        self.assertEqual(
            _resolve_config_against_root("C:\\repo\\.yamllint", "/repo"),
            "C:/repo/.yamllint",
        )


class ResolveConfigAgainstCwdTests(unittest.TestCase):
    """`--yamllint-config` resolves against the invocation cwd (where
    the user typed the command) to match how `_files_or_none` resolves
    positional file arguments. Patch os.getcwd so the tests are
    deterministic on every host."""

    def test_none_passes_through(self) -> None:
        self.assertIsNone(_resolve_config_against_cwd(None))

    def test_relative_path_resolves_against_cwd(self) -> None:
        with patch("docs_steward.cli.os.getcwd", return_value="/repo/subdir"):
            self.assertEqual(
                _resolve_config_against_cwd("local.yaml"),
                "/repo/subdir/local.yaml",
            )

    def test_dot_relative_path_preserves_dot_segment(self) -> None:
        # posix_join is a literal string join, not a normalize. `./` in
        # the input survives — file APIs treat <cwd>/./foo and <cwd>/foo
        # identically, so this is functionally fine. Pin the behaviour.
        with patch("docs_steward.cli.os.getcwd", return_value="/repo/subdir"):
            self.assertEqual(
                _resolve_config_against_cwd("./local.yaml"),
                "/repo/subdir/./local.yaml",
            )

    def test_absolute_path_passes_through_normalized(self) -> None:
        with patch("docs_steward.cli.os.getcwd", return_value="/repo/subdir"):
            self.assertEqual(
                _resolve_config_against_cwd("/etc/yamllint.yaml"),
                "/etc/yamllint.yaml",
            )
            self.assertEqual(
                _resolve_config_against_cwd("C:\\repo\\.yamllint"),
                "C:/repo/.yamllint",
            )

    def test_relative_path_joined_to_root(self) -> None:
        self.assertEqual(
            _resolve_config_against_root(".yamllint", "/repo"),
            "/repo/.yamllint",
        )

    def test_relative_path_with_subdir_joined_to_root(self) -> None:
        self.assertEqual(
            _resolve_config_against_root("config/.yamllint.yaml", "/repo"),
            "/repo/config/.yamllint.yaml",
        )


if __name__ == "__main__":
    unittest.main()
