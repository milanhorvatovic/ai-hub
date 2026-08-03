"""cli.main — end-to-end through serialization, with patched runner + fs."""

from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from docs_steward.baseline import UNIVERSAL_SUBSET
from docs_steward.bundled_config import bundled_config_for
from docs_steward.cli import (
    YAMLLINT_REPO_CANDIDATES,
    _discover_repo_yamllint_config,
    _frontmatter_pass,
    _lint_pass,
    _resolve_against_root,
    _resolve_config_against_cwd,
    main,
)
from docs_steward.events import EventType
from docs_steward.process import ProcessResult
from docs_steward.selector import AuditPlan, PlannedPass
from docs_steward.tools import Tool

from .fakes import FakeFileSystem, FakeProcessRunner

_GIT_TOPLEVEL = ("git", "rev-parse", "--show-toplevel")
_GIT_LS_FILES = (
    "git", "ls-files", "--cached", "--others", "--exclude-standard",
    "--", ":(glob)**/*.md", ":(glob)**/*.markdown",
)


def _repo_fs(*config_names: str, readme: str = "# Title\n") -> FakeFileSystem:
    """FakeFileSystem seeded with /repo/README.md plus named root configs."""
    files = {"/repo/README.md": readme}
    for name in config_names:
        files[f"/repo/{name}"] = ""
    return FakeFileSystem(files=files)


def _repo_results(
    extra: dict[tuple[str, ...], ProcessResult] | None = None,
) -> dict[tuple[str, ...], ProcessResult]:
    """Baseline argv→result map: repo root at /repo, inventory of README.md."""
    results = {
        _GIT_TOPLEVEL: ProcessResult(0, "/repo\n", ""),
        _GIT_LS_FILES: ProcessResult(0, "README.md\n", ""),
    }
    results.update(extra or {})
    return results


def _prettier_plan(lint_baseline: str | None = None) -> AuditPlan:
    linter = (
        PlannedPass(Tool.MARKDOWNLINT_CLI2, lint_baseline)
        if lint_baseline is not None
        else None
    )
    return AuditPlan(
        formatter=PlannedPass(Tool.PRETTIER, ".prettierrc"),
        formatter_baseline=".prettierrc",
        linter=linter,
    )


class LintPassTests(unittest.TestCase):
    """The plan-driven complementary markdownlint pass."""

    def test_runs_planned_linter_with_its_repo_config(self) -> None:
        cmd = (
            "markdownlint-cli2", "--config", "/repo/.markdownlint.json",
            "--", "/repo/README.md",
        )
        runner = FakeProcessRunner(
            paths={"markdownlint-cli2": "/x/mdl2"},
            results={cmd: ProcessResult(1, "README.md:1 MD040 no language\n", "")},
        )
        events, code = _lint_pass(
            _prettier_plan(lint_baseline=".markdownlint.json"),
            runner, "/repo", ("/repo/README.md",), quiet=False,
        )
        self.assertEqual(code, 1)
        selected = next(e for e in events if e.event == EventType.SELECTED)
        self.assertEqual(selected.tool, "markdownlint-cli2")
        self.assertEqual(selected.detail["baseline"], ".markdownlint.json")
        self.assertTrue(any(e.event == EventType.FINDING for e in events))

    def test_runs_bundled_rules_when_plan_carries_the_sentinel(self) -> None:
        cfg = bundled_config_for(Tool.MARKDOWNLINT_CLI2)
        cmd = ("markdownlint-cli2", "--config", cfg, "--", "/repo/README.md")
        runner = FakeProcessRunner(
            paths={"markdownlint-cli2": "/x/mdl2"},
            results={cmd: ProcessResult(0, "", "")},
        )
        events, code = _lint_pass(
            _prettier_plan(lint_baseline=UNIVERSAL_SUBSET),
            runner, "/repo", ("/repo/README.md",), quiet=False,
        )
        self.assertEqual(code, 0)
        self.assertTrue(any(e.event == EventType.CLEAN for e in events))

    def test_noop_when_plan_has_no_lint_pass(self) -> None:
        events, code = _lint_pass(
            _prettier_plan(lint_baseline=None),
            FakeProcessRunner(), "/repo", ("/repo/README.md",), quiet=False,
        )
        self.assertEqual((events, code), ([], 0))


class FrontmatterPassTests(unittest.TestCase):
    """The frontmatter pass folded into the composite audit."""

    def test_soft_skips_when_yamllint_absent(self) -> None:
        events, code = _frontmatter_pass(
            FakeProcessRunner(), _repo_fs(), "/repo", ("/repo/README.md",)
        )
        self.assertEqual((events, code), ([], 0))

    def test_uses_repo_yamllint_config_when_declared(self) -> None:
        fs = _repo_fs(".yamllint", readme="---\ntitle: x\n---\n# Title\n")
        cmd = ("yamllint", "-f", "parsable", "-s", "-c", "/repo/.yamllint", "-")
        runner = FakeProcessRunner(
            paths={"yamllint": "/x/yamllint"},
            results={cmd: ProcessResult(0, "", "")},
        )
        events, code = _frontmatter_pass(runner, fs, "/repo", ("/repo/README.md",))
        self.assertEqual(code, 0)
        selected = next(e for e in events if e.event == EventType.SELECTED)
        self.assertEqual(selected.detail["config_source"], "repo")


class CliEndToEndTests(unittest.TestCase):
    def _run(
        self,
        runner: FakeProcessRunner,
        argv: list[str],
        fs: FakeFileSystem | None = None,
    ) -> tuple[int, list[dict]]:
        buf = io.StringIO()
        with patch("docs_steward.cli.SubprocessRunner", return_value=runner), patch(
            "sys.stdout", buf
        ):
            if fs is not None:
                with patch("docs_steward.cli.OsFileSystem", return_value=fs):
                    code = main(argv)
            else:
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

    def test_audit_baseline_override_forces_the_formatter_owner(self) -> None:
        cmd = (
            "prettier", "--config", "/repo/.prettierrc",
            "--check", "--parser", "markdown", "--", "/repo/README.md",
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results=_repo_results({cmd: ProcessResult(0, "", "")}),
        )
        code, events = self._run(
            runner, ["md-audit", "--baseline", ".prettierrc"], fs=_repo_fs()
        )
        self.assertEqual(code, 0)
        selected = [e for e in events if e["event"] == "selected"][0]
        self.assertEqual(selected["detail"]["baseline"], ".prettierrc")
        self.assertEqual(selected["detail"]["files_scoped"], 1)

    def test_format_with_unwrap_propagates_flag_through_to_command(self) -> None:
        cmd = (
            "prettier",
            "--config",
            "/repo/.prettierrc",
            "--prose-wrap=never",
            "--write",
            "--parser",
            "markdown",
            "--",
            "/repo/README.md",
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results=_repo_results({cmd: ProcessResult(0, "foo.md 12ms\n", "")}),
        )
        code, events = self._run(
            runner, ["md-format", "--baseline", ".prettierrc", "--unwrap"],
            fs=_repo_fs(),
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
        cmd = (
            "prettier", "--config", "/repo/.prettierrc",
            "--check", "--parser", "markdown", "--", "/repo/README.md",
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results=_repo_results({
                cmd: ProcessResult(
                    1, "Linting: 3 file(s)\nSummary: 1 error(s)\nfoo.md:1 MD040\n", "",
                ),
            }),
        )
        code, events = self._run(
            runner, ["md-audit", "--baseline", ".prettierrc", "--quiet"],
            fs=_repo_fs(),
        )
        self.assertEqual(code, 1)
        findings = [e for e in events if e["event"] == "finding"]
        self.assertEqual(len(findings), 1)
        self.assertIn("MD040", findings[0]["detail"])

    def test_md_format_dry_run_emits_would_change(self) -> None:
        audit_cmd = (
            "prettier", "--config", "/repo/.prettierrc",
            "--check", "--parser", "markdown", "--", "/repo/README.md",
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results=_repo_results({audit_cmd: ProcessResult(1, "foo.md\n", "")}),
        )
        code, events = self._run(
            runner, ["md-format", "--baseline", ".prettierrc", "--dry-run"],
            fs=_repo_fs(),
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
        cmd = (
            "prettier", "--config", "/repo/.prettierrc",
            "--check", "--parser", "markdown", "--", "/repo/README.md",
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results=_repo_results({cmd: ProcessResult(0, "", "")}),
        )
        code, events = self._run(
            runner, ["md-audit", "--baseline", ".prettierrc"], fs=_repo_fs()
        )
        self.assertEqual(code, 0)
        self.assertEqual([e for e in events if e["event"] == "plugin-missing"], [])

    def test_md_fix_clean_yields_zero_delta(self) -> None:
        audit_cmd = (
            "prettier", "--config", "/repo/.prettierrc",
            "--check", "--parser", "markdown", "--", "/repo/README.md",
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results=_repo_results({audit_cmd: ProcessResult(0, "", "")}),
        )
        code, events = self._run(
            runner, ["md-fix", "--baseline", ".prettierrc"], fs=_repo_fs(),
        )
        self.assertEqual(code, 0)
        deltas = [e for e in events if e["event"] == "delta"]
        self.assertEqual(len(deltas), 1)
        self.assertEqual(
            deltas[0]["detail"], {"resolved": 0, "still_open": 0, "new": 0},
        )

    def test_md_fix_runs_complementary_markdownlint_pass(self) -> None:
        # Regression: md-fix must agree with md-audit on the same repo. With
        # prettier clean (zero delta) but a markdownlint-only violation
        # (MD040), md-fix used to exit 0 while md-audit exited 1. The
        # complementary lint pass now surfaces the MD### finding and drives
        # the exit code, while the delta stays prettier-only (zeros).
        prettier_audit = (
            "prettier", "--config", "/repo/.prettierrc",
            "--check", "--parser", "markdown", "--", "/repo/README.md",
        )
        mdl_cmd = (
            "markdownlint-cli2",
            "--config", bundled_config_for(Tool.MARKDOWNLINT_CLI2),
            "--", "/repo/README.md",
        )
        runner = FakeProcessRunner(
            paths={
                "prettier": "/x/prettier",
                "markdownlint-cli2": "/x/mdl2",
                "git": "/x/git",
            },
            results=_repo_results({
                prettier_audit: ProcessResult(0, "", ""),
                mdl_cmd: ProcessResult(1, "foo.md:1 MD040 no language\n", ""),
            }),
        )
        code, events = self._run(
            runner, ["md-fix", "--baseline", ".prettierrc"], fs=_repo_fs()
        )
        # Exit code matches md-audit on the same repo (markdownlint finding).
        self.assertEqual(code, 1)
        # Delta stays prettier-only — the format pass resolved nothing.
        deltas = [e for e in events if e["event"] == "delta"]
        self.assertEqual(len(deltas), 1)
        self.assertEqual(
            deltas[0]["detail"], {"resolved": 0, "still_open": 0, "new": 0},
        )
        # The markdownlint MD### finding surfaces in the stream.
        findings = [e for e in events if e["event"] == "finding"]
        self.assertTrue(any("MD040" in f["detail"] for f in findings))
        self.assertTrue(
            any(
                e["event"] == "selected" and e["tool"] == "markdownlint-cli2"
                for e in events
            )
        )

    def test_md_fix_skips_markdownlint_pass_when_formatter_is_markdownlint(self) -> None:
        # When the repo selects markdownlint as the formatter, the fix cycle
        # already covers the MD### rules; the complementary pass must no-op so
        # the run isn't double-linted.
        audit_cmd = (
            "markdownlint-cli2", "--config", "/repo/.markdownlint.json",
            "--", "/repo/README.md",
        )
        runner = FakeProcessRunner(
            paths={"markdownlint-cli2": "/x/mdl2", "git": "/x/git"},
            results=_repo_results({audit_cmd: ProcessResult(0, "", "")}),
        )
        code, events = self._run(
            runner, ["md-fix", "--baseline", ".markdownlint.json"], fs=_repo_fs()
        )
        self.assertEqual(code, 0)
        selected = [e for e in events if e["event"] == "selected"]
        # Exactly one tool selected (the fix-cycle's markdownlint), no second
        # complementary pass.
        self.assertTrue(all(e["tool"] == "markdownlint-cli2" for e in selected))


class CompositeAuditEndToEndTests(unittest.TestCase):
    """The composite audit plan, end to end: a repo declaring complementary
    formatter and linter configs gets every applicable check, each pass
    honoring its own family's config, aggregated into one verdict."""

    _PRETTIER_REPO_CMD = (
        "prettier", "--config", "/repo/.prettierrc",
        "--check", "--parser", "markdown", "--", "/repo/README.md",
    )
    _MDL_REPO_CMD = (
        "markdownlint-cli2", "--config", "/repo/.markdownlint.json",
        "--", "/repo/README.md",
    )

    def _run(
        self, runner: FakeProcessRunner, argv: list[str], fs: FakeFileSystem,
    ) -> tuple[int, list[dict]]:
        buf = io.StringIO()
        with patch("docs_steward.cli.SubprocessRunner", return_value=runner), patch(
            "docs_steward.cli.OsFileSystem", return_value=fs
        ), patch("sys.stdout", buf):
            code = main(argv)
        lines = [line for line in buf.getvalue().splitlines() if line.strip()]
        return code, [json.loads(line) for line in lines]

    def _both_tools(
        self, prettier: ProcessResult, mdl: ProcessResult,
    ) -> FakeProcessRunner:
        return FakeProcessRunner(
            paths={
                "prettier": "/x/prettier",
                "markdownlint-cli2": "/x/mdl2",
                "git": "/x/git",
            },
            results=_repo_results({
                self._PRETTIER_REPO_CMD: prettier,
                self._MDL_REPO_CMD: mdl,
            }),
        )

    def test_multi_config_repo_fails_when_only_the_formatter_fails(self) -> None:
        # The headline defect: a repo declaring both configs used to run
        # only the linter, so a document that passed lint but violated the
        # repo's own formatter config audited clean. Both passes now run
        # and the formatter failure drives the aggregate.
        runner = self._both_tools(
            prettier=ProcessResult(1, "README.md\n", ""),
            mdl=ProcessResult(0, "", ""),
        )
        code, events = self._run(
            runner, ["md-audit"], _repo_fs(".markdownlint.json", ".prettierrc")
        )
        self.assertEqual(code, 1)
        selected = {e["tool"]: e["detail"]["baseline"] for e in events if e["event"] == "selected"}
        self.assertEqual(
            selected,
            {"prettier": ".prettierrc", "markdownlint-cli2": ".markdownlint.json"},
        )

    def test_multi_config_repo_fails_when_only_the_linter_fails(self) -> None:
        runner = self._both_tools(
            prettier=ProcessResult(0, "", ""),
            mdl=ProcessResult(1, "README.md:1 MD040 no language\n", ""),
        )
        code, events = self._run(
            runner, ["md-audit"], _repo_fs(".markdownlint.json", ".prettierrc")
        )
        self.assertEqual(code, 1)
        findings = [e for e in events if e["event"] == "finding"]
        self.assertTrue(any("MD040" in f["detail"] for f in findings))

    def test_forced_formatter_lints_with_repo_config_not_bundled(self) -> None:
        # Forcing the formatter used to route the complementary lint pass
        # to the bundled markdownlint rules; the repo's own config must win.
        runner = self._both_tools(
            prettier=ProcessResult(0, "", ""),
            mdl=ProcessResult(0, "", ""),
        )
        code, events = self._run(
            runner,
            ["md-audit", "--baseline", ".prettierrc"],
            _repo_fs(".markdownlint.json"),
        )
        self.assertEqual(code, 0)
        lint_selected = next(
            e for e in events
            if e["event"] == "selected" and e["tool"] == "markdownlint-cli2"
        )
        self.assertEqual(lint_selected["detail"]["baseline"], ".markdownlint.json")
        self.assertIn("/repo/.markdownlint.json", lint_selected["detail"]["cmd"])

    def test_frontmatter_findings_contribute_to_the_aggregate(self) -> None:
        yamllint_cmd = (
            "yamllint", "-f", "parsable", "-s",
            "-c", bundled_config_for(Tool.YAMLLINT), "-",
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "yamllint": "/x/yamllint", "git": "/x/git"},
            results=_repo_results({
                self._PRETTIER_REPO_CMD: ProcessResult(0, "", ""),
                yamllint_cmd: ProcessResult(
                    1, "stdin:1:1: [error] too few spaces (commas)\n", "",
                ),
            }),
        )
        code, events = self._run(
            runner,
            ["md-audit", "--baseline", ".prettierrc"],
            _repo_fs(readme="---\ntitle: x\n---\n# Title\n"),
        )
        self.assertEqual(code, 1)
        findings = [e for e in events if e["event"] == "finding" and e["tool"] == "yamllint"]
        self.assertTrue(findings)

    def test_no_markdown_files_short_circuits_clean(self) -> None:
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier", "git": "/x/git"},
            results={
                _GIT_TOPLEVEL: ProcessResult(0, "/repo\n", ""),
                _GIT_LS_FILES: ProcessResult(0, "", ""),
            },
        )
        code, events = self._run(runner, ["md-audit"], FakeFileSystem())
        self.assertEqual(code, 0)
        self.assertEqual(
            events,
            [{"event": "clean", "tool": "all", "detail": "no markdown files discovered"}],
        )
        # No formatter/linter invocation happened — only the two git calls.
        self.assertEqual(len(runner.calls), 2)

    def test_no_usable_tool_still_exits_3_with_missing_event(self) -> None:
        runner = FakeProcessRunner(
            paths={"git": "/x/git"},
            results=_repo_results(),
        )
        code, events = self._run(runner, ["md-audit"], _repo_fs())
        self.assertEqual(code, 3)
        self.assertEqual(events[0]["event"], "missing")


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


class DiscoverRepoYamllintConfigTests(unittest.TestCase):
    """Auto-discovery of repo-root yamllint config (round 22). When the
    caller did not pass `--yamllint-config`, the CLI now probes the
    same filenames yamllint itself probes at the repo root, so a repo
    that ships `.yamllint` is honoured instead of buried by the bundled
    fallback. None means "fall back to the bundled config" — that
    contract is what `yaml_audit.audit_frontmatter` already documents."""

    def test_candidate_order_matches_yamllint(self) -> None:
        # Mirror yamllint's standalone lookup so reading our docs and
        # reading yamllint's docs land on the same answer.
        self.assertEqual(
            YAMLLINT_REPO_CANDIDATES,
            (".yamllint", ".yamllint.yaml", ".yamllint.yml"),
        )

    def test_no_config_returns_none(self) -> None:
        fs = FakeFileSystem(files={})
        self.assertIsNone(_discover_repo_yamllint_config(fs, "/repo"))

    def test_dotyamllint_wins(self) -> None:
        fs = FakeFileSystem(files={"/repo/.yamllint": "rules: {}\n"})
        self.assertEqual(
            _discover_repo_yamllint_config(fs, "/repo"), "/repo/.yamllint"
        )

    def test_dotyamllint_yaml_picked_up(self) -> None:
        fs = FakeFileSystem(files={"/repo/.yamllint.yaml": "rules: {}\n"})
        self.assertEqual(
            _discover_repo_yamllint_config(fs, "/repo"),
            "/repo/.yamllint.yaml",
        )

    def test_dotyamllint_yml_picked_up(self) -> None:
        fs = FakeFileSystem(files={"/repo/.yamllint.yml": "rules: {}\n"})
        self.assertEqual(
            _discover_repo_yamllint_config(fs, "/repo"), "/repo/.yamllint.yml"
        )

    def test_dotyamllint_outranks_yaml_and_yml(self) -> None:
        # Two siblings on disk: the one yamllint would pick first wins.
        fs = FakeFileSystem(
            files={
                "/repo/.yamllint": "a: 1\n",
                "/repo/.yamllint.yaml": "b: 2\n",
                "/repo/.yamllint.yml": "c: 3\n",
            }
        )
        self.assertEqual(
            _discover_repo_yamllint_config(fs, "/repo"), "/repo/.yamllint"
        )

    def test_uses_posix_join_under_root(self) -> None:
        # Round-8a path handling: the helper must build POSIX paths so
        # NDJSON output and downstream command lines never mix
        # separators on Windows. Forward slashes regardless of host.
        fs = FakeFileSystem(files={"C:/repo/.yamllint.yaml": "rules: {}\n"})
        self.assertEqual(
            _discover_repo_yamllint_config(fs, "C:/repo"),
            "C:/repo/.yamllint.yaml",
        )


class DispatchAuditFrontmatterTests(unittest.TestCase):
    """End-to-end: md-audit-frontmatter routes through cli.main and
    must honour the new precedence (explicit override > auto-discovery
    > bundled fallback). Patch `audit_frontmatter` and `repo_root` to
    capture which `config_path` the dispatcher actually forwards;
    `repo_root` is patched because the test repo is the project
    checkout, not a synthetic root, and we want to assert against a
    stable string."""

    def _run(
        self,
        argv: list[str],
        *,
        root: str = "/repo",
        files_on_disk: dict[str, str] | None = None,
    ) -> str | None:
        captured: dict[str, str | None] = {"config_path": "<unset>"}

        def fake_audit_frontmatter(runner, fs, files, config_path=None):
            captured["config_path"] = config_path
            return ([], 0)

        def fake_list_markdown_files(runner, root_arg):
            return ()

        def fake_os_filesystem():
            return FakeFileSystem(files=files_on_disk or {})

        with patch(
            "docs_steward.cli.SubprocessRunner",
            return_value=FakeProcessRunner(),
        ), patch(
            "docs_steward.cli.repo_root", return_value=root,
        ), patch(
            "docs_steward.cli.list_markdown_files",
            side_effect=fake_list_markdown_files,
        ), patch(
            "docs_steward.cli.OsFileSystem", side_effect=fake_os_filesystem,
        ), patch(
            "docs_steward.cli.audit_frontmatter",
            side_effect=fake_audit_frontmatter,
        ), patch("sys.stdout", io.StringIO()):
            main(argv)
        self.assertNotEqual(
            captured["config_path"], "<unset>",
            msg="audit_frontmatter was never called",
        )
        return captured["config_path"]

    def test_explicit_yamllint_config_wins_over_repo_config(self) -> None:
        with patch("docs_steward.cli.os.getcwd", return_value="/repo"):
            forwarded = self._run(
                ["md-audit-frontmatter", "--yamllint-config", "/etc/strict.yaml"],
                files_on_disk={"/repo/.yamllint": "rules: {}\n"},
            )
        self.assertEqual(forwarded, "/etc/strict.yaml")

    def test_repo_yamllint_discovered_when_no_override(self) -> None:
        forwarded = self._run(
            ["md-audit-frontmatter"],
            files_on_disk={"/repo/.yamllint.yaml": "rules: {}\n"},
        )
        self.assertEqual(forwarded, "/repo/.yamllint.yaml")

    def test_no_override_and_no_repo_config_routes_to_bundled(self) -> None:
        # None signals to yaml_audit.audit_frontmatter "use the bundled
        # fallback". Round-21a's contract: that None passthrough is the
        # only way the bundled config gets activated for frontmatter.
        forwarded = self._run(
            ["md-audit-frontmatter"], files_on_disk={},
        )
        self.assertIsNone(forwarded)


if __name__ == "__main__":
    unittest.main()
