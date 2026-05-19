"""runner.run_tool + run_fix_cycle — orchestration + exit-code contract."""

from __future__ import annotations

import unittest

from docs_steward.baseline import UNIVERSAL_SUBSET
from docs_steward.events import EventType
from docs_steward.modes import Mode
from docs_steward.process import ProcessResult
from docs_steward.runner import _normalize_finding_key, run_fix_cycle, run_tool
from docs_steward.tools import Tool

from .fakes import FakeProcessRunner


ROOT = "/repo"


class RunToolTests(unittest.TestCase):
    def test_no_usable_tool_returns_exit_3(self) -> None:
        events, code = run_tool(Mode.AUDIT, UNIVERSAL_SUBSET, False, FakeProcessRunner(), ROOT)
        self.assertEqual(code, 3)
        self.assertEqual(events[0].event, EventType.MISSING)

    def test_clean_audit_returns_exit_0(self) -> None:
        cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(0, "", "")},
        )
        events, code = run_tool(Mode.AUDIT, ".prettierrc", False, runner, ROOT)
        self.assertEqual(code, 0)
        kinds = [e.event for e in events]
        self.assertIn(EventType.SELECTED, kinds)
        self.assertIn(EventType.CLEAN, kinds)

    def test_audit_clean_with_preamble_stdout_returns_exit_0(self) -> None:
        # Regression: markdownlint-cli2 prints version + file count + "Summary: 0 error(s)"
        # on stdout even when clean. Trust returncode in AUDIT mode; do not emit the
        # preamble lines as `finding` events nor flip the exit code to 1.
        cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        preamble = "prettier v3.8.3\nLinting: 3 file(s)\nSummary: 0 error(s)\n"
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(0, preamble, "")},
        )
        events, code = run_tool(Mode.AUDIT, ".prettierrc", False, runner, ROOT)
        self.assertEqual(code, 0)
        findings = [e for e in events if e.event == EventType.FINDING]
        self.assertEqual(findings, [])
        self.assertIn(EventType.CLEAN, [e.event for e in events])

    def test_findings_emit_finding_events_exit_1(self) -> None:
        cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(1, "Code style issues found in foo.md\n", "")},
        )
        events, code = run_tool(Mode.AUDIT, ".prettierrc", False, runner, ROOT)
        self.assertEqual(code, 1)
        findings = [e for e in events if e.event == EventType.FINDING]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].detail, "Code style issues found in foo.md")

    def test_signal_killed_negative_returncode_emits_error_event_and_exit_2(self) -> None:
        # Regression: returncode < 0 means subprocess.Popen surfaced a
        # signal-killed child (Python convention: -SIGTERM, -SIGKILL).
        # The old `if result.returncode >= 2` branch missed it, so any
        # stray stdout/stderr bytes from the killed child rendered as
        # FINDING events and the cycle returned exit 1 instead of exit 2.
        cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(-15, "foo.md\n", "killed")},
        )
        events, code = run_tool(Mode.AUDIT, ".prettierrc", False, runner, ROOT)
        self.assertEqual(code, 2)
        errors = [e for e in events if e.event == EventType.ERROR]
        self.assertEqual(len(errors), 1)
        # ERROR detail carries the returncode and the stderr text from
        # the killed child so consumers see what the formatter said
        # before exit. Round 9 attached stderr to the failure path.
        self.assertEqual(errors[0].detail, {"exit": -15, "stderr": "killed"})

    def test_tool_error_exit_geq_2_emits_error_event_and_exit_2(self) -> None:
        cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(2, "", "config error")},
        )
        events, code = run_tool(Mode.AUDIT, ".prettierrc", False, runner, ROOT)
        self.assertEqual(code, 2)
        errors = [e for e in events if e.event == EventType.ERROR]
        self.assertEqual(len(errors), 1)
        # ERROR detail surfaces stderr so the consumer sees the actual
        # diagnostic ('config error') and not just `{exit: 2}`.
        self.assertEqual(errors[0].detail, {"exit": 2, "stderr": "config error"})

    def test_tool_error_path_surfaces_stdout_as_findings(self) -> None:
        # Round 21a — round 10 had short-circuited the error path to
        # ERROR-only emission, but tools that write diagnostics to
        # STDOUT (rather than stderr) lost actionable signal. The
        # current ordering parses stdout as FINDING / CHANGED events
        # FIRST, then emits ERROR with stderr (not stdout) in detail.
        # No duplication because stderr is intentionally NOT folded
        # back into the FINDING stream on the error path.
        cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={
                cmd: ProcessResult(
                    2,
                    "stdout-diagnostic.md:1 MD040 missing-language\n",
                    "Error: Invalid configuration\n",
                ),
            },
        )
        events, code = run_tool(Mode.AUDIT, ".prettierrc", False, runner, ROOT)
        self.assertEqual(code, 2)
        findings = [e for e in events if e.event == EventType.FINDING]
        # stdout diagnostic surfaced as a FINDING:
        self.assertEqual(len(findings), 1)
        self.assertIn("stdout-diagnostic.md", findings[0].detail)  # type: ignore[operator]
        # ERROR still carries stderr in detail; no FINDING for the
        # stderr line (otherwise consumers see the diagnostic twice).
        errors = [e for e in events if e.event == EventType.ERROR]
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid configuration", errors[0].detail["stderr"])  # type: ignore[index]
        self.assertFalse(
            any("Invalid configuration" in (f.detail or "") for f in findings),  # type: ignore[operator]
        )

    def test_tool_error_path_does_not_duplicate_stderr_as_findings(self) -> None:
        # Regression: the failure path used to parse stdout+stderr into
        # FINDING events FIRST, then emit ERROR with the same stderr in
        # detail. AUDIT-mode consumers saw the diagnostic twice — once
        # per finding-line in the FINDING events, once in the ERROR
        # detail. The order is now error-check → ERROR-only (skipping
        # _emit_output_lines on failure); the FINDING/CHANGED parse
        # only runs on the returncode-1 path.
        cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={
                cmd: ProcessResult(
                    2,
                    "",
                    "Error: Invalid configuration: unknown option 'tabWdith'\nTrace: ...\n",
                ),
            },
        )
        events, code = run_tool(Mode.AUDIT, ".prettierrc", False, runner, ROOT)
        self.assertEqual(code, 2)
        # No FINDING events derived from the stderr — that's exactly the
        # duplication we're guarding against.
        self.assertEqual([e for e in events if e.event == EventType.FINDING], [])
        # The ERROR event still carries stderr in its detail.
        errors = [e for e in events if e.event == EventType.ERROR]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].detail["exit"], 2)  # type: ignore[index]
        self.assertIn("Invalid configuration", errors[0].detail["stderr"])  # type: ignore[index]

    def test_tool_error_with_empty_stderr_omits_stderr_field(self) -> None:
        # When the failing run produced no stderr, the ERROR detail
        # stays compact — no `stderr: ""` noise. Consumers branching
        # on `'stderr' in detail` see only the meaningful case.
        cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(2, "", "")},
        )
        events, code = run_tool(Mode.AUDIT, ".prettierrc", False, runner, ROOT)
        self.assertEqual(code, 2)
        errors = [e for e in events if e.event == EventType.ERROR]
        self.assertEqual(errors[0].detail, {"exit": 2})

    def test_format_mode_stderr_noise_does_not_suppress_clean(self) -> None:
        # Regression: FORMAT mode's CLEAN decision used to consult
        # combined stdout+stderr. A deprecation warning on stderr from
        # a successful format pass suppressed the CLEAN event and
        # emitted the warning as a spurious CHANGED event. Stderr is
        # banner / warning territory in FORMAT mode; only stdout decides
        # whether anything was rewritten.
        cmd = ("prettier", "--config", "/repo/.prettierrc", "--write", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={
                cmd: ProcessResult(
                    0,
                    "",
                    "Deprecation: --parser is going away in v4.\n",
                ),
            },
        )
        events, code = run_tool(Mode.FORMAT, ".prettierrc", False, runner, ROOT)
        self.assertEqual(code, 0)
        kinds = [e.event for e in events]
        self.assertIn(EventType.CLEAN, kinds)
        # No spurious CHANGED event derived from the stderr warning.
        self.assertEqual([e for e in events if e.event == EventType.CHANGED], [])

    def test_format_mode_emits_changed_not_finding(self) -> None:
        cmd = ("prettier", "--config", "/repo/.prettierrc", "--write", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(0, "foo.md 12ms\n", "")},
        )
        events, code = run_tool(Mode.FORMAT, ".prettierrc", False, runner, ROOT)
        self.assertEqual(code, 1)
        self.assertEqual(
            [e for e in events if e.event == EventType.CHANGED][0].detail,
            "foo.md 12ms",
        )

    def test_universal_subset_with_bundled_config_emits_bundled_event(self) -> None:
        # Selector with no baseline preference + only prettier on PATH falls
        # back to prettier; bundled config applies.
        from docs_steward.bundled_config import bundled_config_for
        cfg = bundled_config_for(Tool.PRETTIER)
        assert cfg is not None
        cmd = (
            "prettier",
            "--config",
            cfg,
            "--check",
            "--parser",
            "markdown",
            "**/*.md",
            "**/*.markdown",
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(0, "", "")},
        )
        events, code = run_tool(Mode.AUDIT, UNIVERSAL_SUBSET, False, runner, ROOT)
        self.assertEqual(code, 0)
        bundled = [e for e in events if e.event == EventType.BUNDLED_CONFIG]
        self.assertEqual(len(bundled), 1)
        self.assertEqual(bundled[0].detail, cfg)
        selected = [e for e in events if e.event == EventType.SELECTED][0]
        self.assertEqual(selected.detail["config_source"], "bundled")  # type: ignore[index]
        # Event ordering: SELECTED comes BEFORE BUNDLED_CONFIG so streaming
        # consumers see the run parameters first. Matches the ordering
        # yaml_audit.audit_frontmatter has always used.
        selected_idx = next(
            i for i, e in enumerate(events) if e.event == EventType.SELECTED
        )
        bundled_idx = next(
            i for i, e in enumerate(events) if e.event == EventType.BUNDLED_CONFIG
        )
        self.assertLess(selected_idx, bundled_idx)

    def test_universal_subset_unsupported_tool_uses_tool_default(self) -> None:
        # Force selection of mdformat (no bundled config) via universal-subset
        # with only mdformat on PATH.
        cmd = ("mdformat", "--check", ".")
        runner = FakeProcessRunner(
            paths={"mdformat": "/x/mdformat"},
            results={cmd: ProcessResult(0, "", "")},
        )
        events, code = run_tool(Mode.AUDIT, UNIVERSAL_SUBSET, False, runner, ROOT)
        self.assertEqual(code, 0)
        bundled = [e for e in events if e.event == EventType.BUNDLED_CONFIG]
        self.assertEqual(len(bundled), 0)
        selected = [e for e in events if e.event == EventType.SELECTED][0]
        self.assertEqual(selected.detail["config_source"], "tool-default")  # type: ignore[index]

    def test_unwrap_flag_propagates_to_command(self) -> None:
        cmd = (
            "prettier",
            "--config",
            "/repo/.prettierrc",
            "--prose-wrap=never",
            "--check",
            "--parser",
            "markdown",
            "**/*.md",
            "**/*.markdown",
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(0, "", "")},
        )
        _, code = run_tool(Mode.AUDIT, ".prettierrc", True, runner, ROOT)
        self.assertEqual(code, 0)

    def test_explicit_absolute_baseline_path_forwarded_as_config(self) -> None:
        # SKILL.md guarantees the baseline is "passed verbatim to the chosen
        # formatter". When the baseline is an explicit absolute path outside
        # repo root (e.g. --baseline /etc/.prettierrc), run_tool must
        # forward it as the tool's --config argument; relying on the tool's
        # cwd-based discovery would silently miss configs outside cwd.
        cmd = (
            "prettier", "--config", "/etc/.prettierrc",
            "--check", "--parser", "markdown",
            "**/*.md", "**/*.markdown",
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(0, "", "")},
        )
        events, code = run_tool(
            Mode.AUDIT, "/etc/.prettierrc", False, runner, ROOT,
        )
        self.assertEqual(code, 0)
        selected = [e for e in events if e.event == EventType.SELECTED][0]
        self.assertEqual(selected.detail["config_source"], "repo")  # type: ignore[index]
        self.assertIn("--config /etc/.prettierrc", selected.detail["cmd"])  # type: ignore[index]

    def test_relative_baseline_resolved_against_root(self) -> None:
        # --baseline config/.prettierrc with root=/repo => --config
        # /repo/config/.prettierrc. Forward-slash join regardless of host
        # so Windows CI lands on the same command line as POSIX.
        cmd = (
            "prettier", "--config", "/repo/config/.prettierrc",
            "--check", "--parser", "markdown",
            "**/*.md", "**/*.markdown",
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(0, "", "")},
        )
        events, code = run_tool(
            Mode.AUDIT, "config/.prettierrc", False, runner, ROOT,
        )
        self.assertEqual(code, 0)

    def test_cross_family_baseline_not_passed_as_config(self) -> None:
        # Baseline matches markdownlint family but only Prettier is on PATH.
        # selector falls back to Prettier — the baseline does NOT belong to
        # Prettier, so the --config arg must NOT be threaded through (would
        # confuse Prettier with a markdownlint config file).
        cmd = (
            "prettier", "--check", "--parser", "markdown",
            "**/*.md", "**/*.markdown",
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(0, "", "")},
        )
        events, code = run_tool(
            Mode.AUDIT, ".markdownlint.json", False, runner, ROOT,
        )
        self.assertEqual(code, 0)
        selected = [e for e in events if e.event == EventType.SELECTED][0]
        # The --config flag is absent in the rendered command.
        self.assertNotIn("--config", selected.detail["cmd"])  # type: ignore[index]

    def test_cr_lines_are_stripped(self) -> None:
        cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(1, "foo.md\r\nbar.md\r\n", "")},
        )
        events, _ = run_tool(Mode.AUDIT, ".prettierrc", False, runner, ROOT)
        findings = [e.detail for e in events if e.event == EventType.FINDING]
        self.assertEqual(findings, ["foo.md", "bar.md"])


# ============================================================
# Per-file targeting (#1)
# ============================================================

class PerFileTargetingTests(unittest.TestCase):
    def test_explicit_files_replace_glob_in_cmd(self) -> None:
        # When files= is passed, the glob "**/*.md" + #node_modules etc. are
        # dropped, a POSIX `--` separator is appended, and the explicit list
        # follows so paths starting with `-` aren't parsed as flags.
        cmd = (
            "prettier", "--config", "/repo/.prettierrc",
            "--check", "--parser", "markdown",
            "--", "docs/intro.md", "README.md",
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(0, "", "")},
        )
        events, code = run_tool(
            Mode.AUDIT, ".prettierrc", False, runner, ROOT,
            files=["docs/intro.md", "README.md"],
        )
        self.assertEqual(code, 0)
        selected = [e for e in events if e.event == EventType.SELECTED][0]
        self.assertEqual(selected.detail["files_scoped"], 2)  # type: ignore[index]
        # The -- separator must be in the rendered command string.
        self.assertIn(" -- ", selected.detail["cmd"])  # type: ignore[index]

    def test_scope_command_preserves_value_of_preceding_config_flag(self) -> None:
        # Regression: _scope_command's glob-arg heuristic dropped any token
        # ending in `.md` / `.markdown`. A `--config notes.md` value pair
        # would lose its value half, leaving the formatter to consume the
        # next flag as the config path. The dropper now skips tokens that
        # follow a value-bearing flag (`--config`, `-c`, `--ignore-path`).
        # Use a hypothetical baseline that yields a .md config path:
        # --baseline /repo/notes.md doesn't normally route through the
        # family table, so we trigger the value-half scenario by faking
        # the build_command output via baseline_belongs_to_tool match —
        # use the existing _scope_command directly with a synthesized cmd.
        from docs_steward.runner import _scope_command
        cmd = [
            "markdownlint",
            "--config", "/repo/special.markdown",
            "--ignore-path", "tooling/.gitignore.md",
            "**/*.md",
            "**/*.markdown",
        ]
        scoped = _scope_command(cmd, ["/repo/docs/intro.md"])
        # Value halves survive even though both end in .markdown / .md:
        self.assertIn("/repo/special.markdown", scoped)
        self.assertIn("tooling/.gitignore.md", scoped)
        # The glob args after the value pairs are still dropped:
        self.assertNotIn("**/*.md", scoped)
        self.assertNotIn("**/*.markdown", scoped)
        # And the explicit file is appended after `--`:
        self.assertEqual(scoped[-2:], ["--", "/repo/docs/intro.md"])

    def test_dash_prefixed_filename_passes_after_separator(self) -> None:
        # Regression: a file called --draft.md must be sent as a positional
        # arg, not parsed as an (unknown) flag by the formatter. The --
        # separator inserted by _scope_command makes this safe.
        cmd = (
            "prettier", "--config", "/repo/.prettierrc",
            "--check", "--parser", "markdown",
            "--", "--draft.md",
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(0, "", "")},
        )
        events, code = run_tool(
            Mode.AUDIT, ".prettierrc", False, runner, ROOT,
            files=["--draft.md"],
        )
        self.assertEqual(code, 0)
        selected = [e for e in events if e.event == EventType.SELECTED][0]
        self.assertIn("-- --draft.md", selected.detail["cmd"])  # type: ignore[index]

    def test_no_files_keeps_default_glob(self) -> None:
        cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(0, "", "")},
        )
        events, code = run_tool(Mode.AUDIT, ".prettierrc", False, runner, ROOT)
        self.assertEqual(code, 0)
        selected = [e for e in events if e.event == EventType.SELECTED][0]
        self.assertIsNone(selected.detail["files_scoped"])  # type: ignore[index]

    def test_markdownlint_cli2_drops_negative_globs_when_scoped(self) -> None:
        # markdownlint-cli2 default cmd includes #node_modules etc. — should
        # all be dropped when explicit files are provided. baseline is the
        # repo's .markdownlint.json so no bundled --config is added.
        cmd = ("markdownlint-cli2", "--config", "/repo/.markdownlint.json", "--", "/repo/foo.md")
        runner = FakeProcessRunner(
            paths={"markdownlint-cli2": "/x/markdownlint-cli2"},
            results={cmd: ProcessResult(0, "", "")},
        )
        events, code = run_tool(
            Mode.AUDIT, ".markdownlint.json", False, runner, ROOT,
            files=["/repo/foo.md"],
        )
        self.assertEqual(code, 0)
        selected = [e for e in events if e.event == EventType.SELECTED][0]
        self.assertIn("/repo/foo.md", selected.detail["cmd"])  # type: ignore[index]
        # Negative-glob tokens must be absent under scoping.
        self.assertNotIn("#node_modules", selected.detail["cmd"])  # type: ignore[index]
        self.assertNotIn("**/*.md", selected.detail["cmd"])  # type: ignore[index]


# ============================================================
# --quiet flag (#6)
# ============================================================

class QuietFlagTests(unittest.TestCase):
    def test_quiet_drops_markdownlint_cli2_preamble(self) -> None:
        cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        # Mixed preamble + real findings; quiet should drop preamble only.
        output = (
            "Finding: **/*.md\n"
            "Linting: 3 file(s)\n"
            "Summary: 2 error(s)\n"
            "foo.md:1 MD040 fenced-code-language\n"
            "bar.md:7 MD009 trailing-whitespace\n"
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(1, output, "")},
        )
        events, code = run_tool(
            Mode.AUDIT, ".prettierrc", False, runner, ROOT, quiet=True,
        )
        self.assertEqual(code, 1)
        findings = [e.detail for e in events if e.event == EventType.FINDING]
        # 2 real findings; the 3 preamble lines filtered out.
        self.assertEqual(len(findings), 2)
        self.assertTrue(all("MD0" in f for f in findings))

    def test_not_quiet_keeps_everything(self) -> None:
        cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        output = "Linting: 3 file(s)\nfoo.md:1 MD040 issue\n"
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(1, output, "")},
        )
        events, _ = run_tool(
            Mode.AUDIT, ".prettierrc", False, runner, ROOT, quiet=False,
        )
        findings = [e for e in events if e.event == EventType.FINDING]
        self.assertEqual(len(findings), 2)  # preamble + finding both kept

    def test_quiet_drops_warn_prefixed_prettier_summary(self) -> None:
        # Regression: some prettier builds emit the summary with the
        # `[warn] ` prefix (`[warn] Code style issues found in N files.
        # Run Prettier with --write to fix.`). The preamble pattern now
        # accepts the optional prefix so --quiet drops both forms.
        cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        output = (
            "[warn] foo.md\n"
            "[warn] bar.md\n"
            "[warn] Code style issues found in 2 files. Run Prettier with --write to fix.\n"
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(1, output, "")},
        )
        events, _ = run_tool(
            Mode.AUDIT, ".prettierrc", False, runner, ROOT, quiet=True,
        )
        findings = [e.detail for e in events if e.event == EventType.FINDING]
        # Two [warn] <path> lines survive; the [warn] summary is filtered.
        self.assertEqual(len(findings), 2)
        self.assertTrue(all("[warn]" in f for f in findings))
        self.assertFalse(
            any("Code style issues" in f for f in findings),
        )

    def test_quiet_drops_prettier_summary_line(self) -> None:
        # Regression: --quiet must drop Prettier's trailing summary
        # ("Code style issues found in N files. Run Prettier with
        # --write to fix.") in addition to the leading banner. Before
        # the round-10 preamble update, the summary leaked through as
        # an extra FINDING event.
        cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        output = (
            "Checking formatting...\n"
            "[warn] foo.md\n"
            "[warn] bar.md\n"
            "Code style issues found in 2 files. Run Prettier with --write to fix.\n"
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(1, output, "")},
        )
        events, _ = run_tool(
            Mode.AUDIT, ".prettierrc", False, runner, ROOT, quiet=True,
        )
        findings = [e.detail for e in events if e.event == EventType.FINDING]
        self.assertEqual(len(findings), 2)
        self.assertTrue(all("[warn]" in f for f in findings))

    def test_quiet_does_not_drop_finding_with_tool_name_path(self) -> None:
        # Regression: an over-broad preamble regex (^<tool>[\s\-v]) used
        # to false-positive on a finding line whose file path happened
        # to start with `prettier-v` or `remark-v` (e.g. someone named a
        # markdown file `prettier-v3.md`). The tightened regex requires
        # `^<tool>\s+v?\d` — whitespace separator + digit — so a tool-
        # name-as-path-prefix can't be mistaken for a version banner.
        cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        output = (
            "prettier 3.2.5\n"
            "prettier-v3.md:1 MD040 fenced-code-language\n"
            "remark-v1.md:5 MD040 fenced-code-language\n"
            "yamllint-v2.md:9 MD009 trailing-whitespace\n"
        )
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={cmd: ProcessResult(1, output, "")},
        )
        events, _ = run_tool(
            Mode.AUDIT, ".prettierrc", False, runner, ROOT, quiet=True,
        )
        findings = [e.detail for e in events if e.event == EventType.FINDING]
        # The version banner is dropped; the three findings whose paths
        # start with `<tool>-v<digit>.md` are kept.
        self.assertEqual(len(findings), 3)
        self.assertTrue(all("MD0" in f for f in findings))


# ============================================================
# --dry-run for md-format (#8)
# ============================================================

class DryRunTests(unittest.TestCase):
    def test_dry_run_format_emits_would_change_events(self) -> None:
        # Dry-run swaps to the AUDIT-mode invocation (--check), but emits
        # WOULD_CHANGE events instead of FINDING events.
        audit_cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={audit_cmd: ProcessResult(1, "foo.md\nbar.md\n", "")},
        )
        events, code = run_tool(
            Mode.FORMAT, ".prettierrc", False, runner, ROOT, dry_run=True,
        )
        self.assertEqual(code, 1)
        would = [e for e in events if e.event == EventType.WOULD_CHANGE]
        self.assertEqual(len(would), 2)
        # No CHANGED events should fire.
        self.assertEqual([e for e in events if e.event == EventType.CHANGED], [])
        # SELECTED event should record dry_run=True.
        selected = [e for e in events if e.event == EventType.SELECTED][0]
        self.assertTrue(selected.detail["dry_run"])  # type: ignore[index]

    def test_dry_run_format_clean_yields_no_would_change(self) -> None:
        audit_cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={audit_cmd: ProcessResult(0, "", "")},
        )
        events, code = run_tool(
            Mode.FORMAT, ".prettierrc", False, runner, ROOT, dry_run=True,
        )
        self.assertEqual(code, 0)
        self.assertEqual([e for e in events if e.event == EventType.WOULD_CHANGE], [])
        self.assertIn(EventType.CLEAN, [e.event for e in events])


# ============================================================
# run_fix_cycle (#4)
# ============================================================

class RunFixCycleTests(unittest.TestCase):
    def test_clean_pre_audit_skips_format_emits_zero_delta(self) -> None:
        audit_cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={audit_cmd: ProcessResult(0, "", "")},
        )
        events, code = run_fix_cycle(runner, ROOT, ".prettierrc", False)
        self.assertEqual(code, 0)
        deltas = [e for e in events if e.event == EventType.DELTA]
        self.assertEqual(len(deltas), 1)
        self.assertEqual(
            deltas[0].detail,
            {"resolved": 0, "still_open": 0, "new": 0},
        )

    def test_findings_then_format_then_re_audit_clean_emits_resolved(self) -> None:
        audit_cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        fmt_cmd = ("prettier", "--config", "/repo/.prettierrc", "--write", "--parser", "markdown", "**/*.md", "**/*.markdown")
        # Pre-audit finds 2 issues; format succeeds; post-audit is clean.
        results = {
            audit_cmd: ProcessResult(1, "foo.md:1 MD040\nbar.md:5 MD009\n", ""),
            fmt_cmd: ProcessResult(0, "foo.md 12ms\nbar.md 8ms\n", ""),
        }
        # First and third calls to audit_cmd return findings, clean respectively.
        # FakeProcessRunner returns the same result for the same key. Need a
        # stateful runner. Build it inline.
        call_count = {"audit": 0}

        original_run = FakeProcessRunner(paths={"prettier": "/x/prettier"}, results=results).run

        class StatefulRunner(FakeProcessRunner):
            def run(self, args, cwd=None, stdin=None):  # type: ignore[override]
                key = tuple(args)
                if key == audit_cmd:
                    call_count["audit"] += 1
                    if call_count["audit"] == 2:
                        return ProcessResult(0, "", "")
                return original_run(args, cwd, stdin)

        runner = StatefulRunner(paths={"prettier": "/x/prettier"}, results=results)
        events, code = run_fix_cycle(runner, ROOT, ".prettierrc", False)
        self.assertEqual(code, 0)
        deltas = [e for e in events if e.event == EventType.DELTA]
        self.assertEqual(len(deltas), 1)
        self.assertEqual(deltas[0].detail["resolved"], 2)  # type: ignore[index]
        self.assertEqual(deltas[0].detail["still_open"], 0)  # type: ignore[index]
        self.assertEqual(deltas[0].detail["new"], 0)  # type: ignore[index]

    def test_pre_exit_1_with_unparseable_output_propagates_exit_1(self) -> None:
        # Regression: a formatter that exits 1 but emits output the line
        # parser turns into zero FINDING events (custom shape / parser
        # gap) would previously collapse to DELTA 0,0,0 + exit 0 because
        # the "already clean" branch fired purely on `not pre_findings`.
        # Now the clean branch additionally requires `pre_exit == 0`, so
        # the failure signal survives.
        audit_cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={
                # exit 1 with stdout that the preamble filter eats whole
                # (a banner-shaped line that _emit_output_lines drops);
                # _finding_keys -> empty set, but pre_exit is 1.
                audit_cmd: ProcessResult(1, "Checking formatting...\n", ""),
            },
        )
        events, code = run_fix_cycle(runner, ROOT, ".prettierrc", False, quiet=True)
        self.assertEqual(code, 1)
        # No DELTA event since we did NOT enter the "clean" branch.
        self.assertEqual([e for e in events if e.event == EventType.DELTA], [])

    def test_post_audit_error_short_circuits_without_delta(self) -> None:
        # Regression: if the POST-format audit errored (exit >= 2),
        # post_findings was an empty set so pre - empty turned every
        # pre-finding into a "resolved" entry in the DELTA — falsely
        # claiming the format pass fixed everything when the audit just
        # crashed. Now the post_exit >= 2 branch short-circuits before
        # the DELTA event is built, so consumers see exit 2 and no DELTA.
        audit_cmd = (
            "prettier", "--config", "/repo/.prettierrc",
            "--check", "--parser", "markdown",
            "**/*.md", "**/*.markdown",
        )
        fmt_cmd = (
            "prettier", "--config", "/repo/.prettierrc",
            "--write", "--parser", "markdown",
            "**/*.md", "**/*.markdown",
        )

        call_count = {"audit": 0}

        class StatefulRunner(FakeProcessRunner):
            def run(self, args, cwd=None, stdin=None):  # type: ignore[override]
                key = tuple(args)
                if key == audit_cmd:
                    call_count["audit"] += 1
                    if call_count["audit"] == 1:
                        return ProcessResult(1, "foo.md\n", "")
                    # Post-audit fails (e.g. config error introduced by
                    # format pass; or a sibling tool crashed).
                    return ProcessResult(2, "", "prettier internal error")
                if key == fmt_cmd:
                    return ProcessResult(0, "foo.md 7ms\n", "")
                return ProcessResult(0, "", "")

        runner = StatefulRunner(paths={"prettier": "/x/prettier"})
        events, code = run_fix_cycle(runner, ROOT, ".prettierrc", False)
        self.assertEqual(code, 2)
        # No DELTA event emitted on post-audit error.
        self.assertEqual([e for e in events if e.event == EventType.DELTA], [])
        # The post-audit ERROR event is still surfaced for the caller.
        post_errors = [e for e in events if e.event == EventType.ERROR]
        self.assertTrue(post_errors)

    def test_audit_error_short_circuits(self) -> None:
        audit_cmd = ("prettier", "--config", "/repo/.prettierrc", "--check", "--parser", "markdown", "**/*.md", "**/*.markdown")
        runner = FakeProcessRunner(
            paths={"prettier": "/x/prettier"},
            results={audit_cmd: ProcessResult(2, "", "prettier config error")},
        )
        events, code = run_fix_cycle(runner, ROOT, ".prettierrc", False)
        self.assertEqual(code, 2)
        # No DELTA event since we bailed early.
        self.assertEqual([e for e in events if e.event == EventType.DELTA], [])

    def test_delta_counts_unfixed_finding_as_still_open_after_line_shift(self) -> None:
        # Regression: when format pass shifts line numbers, an unfixed
        # finding's raw output line changes (e.g. README.md:42:3 MD040 ...
        # becomes README.md:38:3 MD040 ...). Before normalization,
        # set-difference treated these as two different findings — one
        # resolved + one new — instead of one still_open. The delta must
        # use line-agnostic keys so unfixed findings count as still_open.
        audit_cmd = ("markdownlint-cli2", "--config", "/repo/.markdownlint.json",
                     "**/*.md", "**/*.markdown",
                     "#node_modules", "#.git",
                     "#dist", "#build", "#.venv", "#venv", "#target")
        fmt_cmd = ("markdownlint-cli2", "--config", "/repo/.markdownlint.json", "--fix",
                   "**/*.md", "**/*.markdown",
                   "#node_modules", "#.git",
                   "#dist", "#build", "#.venv", "#venv", "#target")
        pre_out = 'README.md:42:3 MD040 fenced-code-language-required "```"\n'
        post_out = 'README.md:38:3 MD040 fenced-code-language-required "```"\n'

        call_count = {"audit": 0}

        class StatefulRunner(FakeProcessRunner):
            def run(self, args, cwd=None, stdin=None):  # type: ignore[override]
                key = tuple(args)
                if key == audit_cmd:
                    call_count["audit"] += 1
                    if call_count["audit"] == 1:
                        return ProcessResult(1, pre_out, "")
                    return ProcessResult(1, post_out, "")
                if key == fmt_cmd:
                    return ProcessResult(0, "README.md 7ms\n", "")
                return ProcessResult(0, "", "")

        runner = StatefulRunner(paths={"markdownlint-cli2": "/x/mdl2"})
        events, code = run_fix_cycle(runner, ROOT, ".markdownlint.json", False)
        # post-audit still has a finding -> exit 1
        self.assertEqual(code, 1)
        deltas = [e for e in events if e.event == EventType.DELTA]
        self.assertEqual(len(deltas), 1)
        self.assertEqual(deltas[0].detail["resolved"], 0)  # type: ignore[index]
        self.assertEqual(deltas[0].detail["still_open"], 1)  # type: ignore[index]
        self.assertEqual(deltas[0].detail["new"], 0)  # type: ignore[index]


class NormalizeFindingKeyTests(unittest.TestCase):
    def test_strips_line_and_col_from_markdownlint_shape(self) -> None:
        self.assertEqual(
            _normalize_finding_key('README.md:42:3 MD040 fenced-code-language "```"'),
            "README.md MD040 fenced-code-language",
        )

    def test_strips_line_only_form(self) -> None:
        self.assertEqual(
            _normalize_finding_key("foo.md:42 MD009 trailing-whitespace"),
            "foo.md MD009 trailing-whitespace",
        )

    def test_strips_remark_range_form(self) -> None:
        self.assertEqual(
            _normalize_finding_key(
                "foo.md:42:3-42:10 warning Missing newline final-newline remark-lint"
            ),
            "foo.md warning Missing newline final-newline remark-lint",
        )

    def test_filename_only_passes_through(self) -> None:
        # Prettier / mdformat / dprint emit just a filename — already stable.
        self.assertEqual(_normalize_finding_key("foo.md"), "foo.md")

    def test_strips_trailing_quoted_fragment(self) -> None:
        self.assertEqual(
            _normalize_finding_key('foo.md MD040 fenced-code-language "```diff"'),
            "foo.md MD040 fenced-code-language",
        )

    def test_idempotent_for_already_normalized_keys(self) -> None:
        key = "foo.md MD040 fenced-code-language"
        self.assertEqual(_normalize_finding_key(key), key)

    def test_preserves_embedded_url_with_port(self) -> None:
        # Regression: an earlier unanchored pattern stripped `:8080` from a
        # URL embedded in finding text (e.g. a remark message referencing
        # https://host:8080/path). The anchored pattern leaves embedded
        # URLs alone and only touches the leading path:LINE:COL prefix.
        original = "foo.md:42 warning Visit https://host:8080/help final-newline remark-lint"
        self.assertEqual(
            _normalize_finding_key(original),
            "foo.md warning Visit https://host:8080/help final-newline remark-lint",
        )

    def test_path_with_spaces_is_normalized(self) -> None:
        # Regression: paths containing spaces (`my docs/guide.md:42:3 ...`)
        # were missed by the \\S+? path class so the same finding at two
        # different lines counted as one resolved + one new rather than
        # one still_open. The pattern now uses .+? to admit spaces while
        # still single-line-bounded.
        self.assertEqual(
            _normalize_finding_key(
                'my docs/guide.md:42:3 MD040 fenced-code-language "```"'
            ),
            "my docs/guide.md MD040 fenced-code-language",
        )
        # Two findings of the same rule at different lines must produce
        # the same normalized key.
        self.assertEqual(
            _normalize_finding_key(
                'my docs/guide.md:42:3 MD040 fenced-code-language "```"'
            ),
            _normalize_finding_key(
                'my docs/guide.md:7:1 MD040 fenced-code-language "```"'
            ),
        )

    def test_does_not_strip_colons_from_path_with_no_extension(self) -> None:
        # A line whose leading path doesn't end with .md/.markdown should not
        # be matched at all — the pattern requires the markdown extension to
        # avoid touching unrelated colon-bearing identifiers (URLs, time
        # stamps, package coordinates).
        self.assertEqual(
            _normalize_finding_key("https://host:8080/foo bar baz"),
            "https://host:8080/foo bar baz",
        )


if __name__ == "__main__":
    unittest.main()
