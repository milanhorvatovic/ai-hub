"""plugins module — GFM-syntax sniffer + plugin probe + plugin-missing emit."""

from __future__ import annotations

import unittest

import os
import tempfile

from docs_steward.events import EventType
from docs_steward.plugins import (
    KNOWN_PLUGINS,
    _probe_via_interpreter,
    _resolve_mdformat_interpreter,
    detect_installed_plugin_labels,
    emit_plugin_missing,
    needs_gfm,
    probe_mdformat_plugins,
)
from docs_steward.process import ProcessResult

from .fakes import FakeProcessRunner


# ============================================================
# needs_gfm sniffer
# ============================================================

class NeedsGfmTests(unittest.TestCase):
    def test_plain_commonmark_no_gfm_needed(self) -> None:
        self.assertFalse(needs_gfm("# heading\n\nparagraph"))

    def test_pipe_table_triggers_gfm(self) -> None:
        text = "| col | col |\n|---|---|\n| a | b |\n"
        self.assertTrue(needs_gfm(text))

    def test_task_list_triggers_gfm(self) -> None:
        text = "- [ ] todo\n- [x] done\n"
        self.assertTrue(needs_gfm(text))

    def test_strikethrough_triggers_gfm(self) -> None:
        self.assertTrue(needs_gfm("This is ~~deleted~~ text."))

    def test_autolink_triggers_gfm(self) -> None:
        self.assertTrue(needs_gfm("Visit https://example.com for more."))

    def test_markdown_link_form_does_not_trigger_autolink(self) -> None:
        # `[text](https://example.com)` is plain CommonMark — should not fire.
        self.assertFalse(needs_gfm("[link](https://example.com)"))

    def test_inline_code_with_pipes_does_not_trigger_table(self) -> None:
        # The table regex anchors at `^\s*\|`, so pipes living inside inline
        # code that does not start the line are not mistaken for table
        # delimiters. The fixture must actually contain a `|` inside backticks
        # to exercise this case — without one the test passes trivially.
        self.assertFalse(needs_gfm("Run `cat | grep foo` to filter output."))


# ============================================================
# probe_mdformat_plugins
# ============================================================

class ProbeMdformatPluginsTests(unittest.TestCase):
    def test_no_pip_returns_empty(self) -> None:
        # No pip on PATH; probe returns empty list silently.
        self.assertEqual(probe_mdformat_plugins(FakeProcessRunner()), [])

    def test_detects_installed_plugin(self) -> None:
        runner = FakeProcessRunner(
            paths={"pip": "/usr/bin/pip"},
            results={
                ("/usr/bin/pip", "show", "mdformat-gfm"): ProcessResult(
                    0, "Name: mdformat-gfm\nVersion: 0.3.5\n", ""
                ),
                ("/usr/bin/pip", "show", "mdformat-tables"): ProcessResult(1, "", ""),
                ("/usr/bin/pip", "show", "mdformat-frontmatter"): ProcessResult(1, "", ""),
                ("/usr/bin/pip", "show", "mdformat-footnote"): ProcessResult(1, "", ""),
                ("/usr/bin/pip", "show", "mdformat-toc"): ProcessResult(1, "", ""),
            },
        )
        events = probe_mdformat_plugins(runner)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event, EventType.PLUGIN_AVAILABLE)
        self.assertEqual(events[0].tool, "mdformat")
        self.assertEqual(events[0].detail["plugin"], "gfm")  # type: ignore[index]
        self.assertEqual(events[0].detail["version"], "0.3.5")  # type: ignore[index]

    def test_detects_multiple_plugins(self) -> None:
        runner = FakeProcessRunner(
            paths={"pip": "/usr/bin/pip"},
            results={
                ("/usr/bin/pip", "show", pkg): ProcessResult(0, f"Version: 1.0.0\n", "")
                for pkg, _ in KNOWN_PLUGINS
            },
        )
        events = probe_mdformat_plugins(runner)
        self.assertEqual(len(events), len(KNOWN_PLUGINS))

    def test_pip3_fallback(self) -> None:
        # pip absent but pip3 present.
        runner = FakeProcessRunner(
            paths={"pip3": "/usr/bin/pip3"},
            results={
                ("/usr/bin/pip3", "show", pkg): ProcessResult(1, "", "")
                for pkg, _ in KNOWN_PLUGINS
            },
        )
        # Should run probes (returns empty events list since none found).
        self.assertEqual(probe_mdformat_plugins(runner), [])

    def test_prefers_mdformat_interpreter_over_pip(self) -> None:
        # When mdformat is on PATH and its shebang resolves to a real
        # interpreter, the probe MUST use that interpreter (not the
        # ambient pip — that's the whole bug fix).
        with tempfile.TemporaryDirectory() as tmp:
            mdformat_path = os.path.join(tmp, "mdformat")
            with open(mdformat_path, "w", encoding="utf-8") as fh:
                fh.write("#!/opt/pipx/venvs/mdformat/bin/python3\n# launcher\n")
            os.chmod(mdformat_path, 0o755)

            interpreter = "/opt/pipx/venvs/mdformat/bin/python3"
            # All KNOWN_PLUGINS probed via the interpreter; mdformat-gfm hits.
            results = {
                (
                    interpreter, "-c",
                    f"import importlib.metadata as m; print(m.version({pkg!r}))",
                ): ProcessResult(
                    0, "0.3.5\n" if pkg == "mdformat-gfm" else "", ""
                ) if pkg == "mdformat-gfm" else ProcessResult(1, "", "")
                for pkg, _ in KNOWN_PLUGINS
            }
            # NB: also provide a pip path that would emit DIFFERENT results so
            # we can prove the probe IGNORED pip when the shebang strategy worked.
            results[("/usr/bin/pip", "show", "mdformat-gfm")] = ProcessResult(
                1, "", ""
            )
            runner = FakeProcessRunner(
                paths={"mdformat": mdformat_path, "pip": "/usr/bin/pip"},
                results=results,
            )
            events = probe_mdformat_plugins(runner)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].detail["plugin"], "gfm")  # type: ignore[index]
            self.assertEqual(events[0].detail["version"], "0.3.5")  # type: ignore[index]

    def test_falls_back_to_pip_when_mdformat_shebang_missing(self) -> None:
        # mdformat is on PATH but the file is a compiled launcher with no
        # shebang (Windows .exe shim convention). Probe falls back to pip.
        with tempfile.TemporaryDirectory() as tmp:
            mdformat_path = os.path.join(tmp, "mdformat-launcher.bin")
            with open(mdformat_path, "wb") as fh:
                fh.write(b"\x7fELF\x02\x01\x01\x00")  # not a shebang
            runner = FakeProcessRunner(
                paths={"mdformat": mdformat_path, "pip": "/usr/bin/pip"},
                results={
                    ("/usr/bin/pip", "show", "mdformat-gfm"): ProcessResult(
                        0, "Version: 0.3.5\n", ""
                    ),
                    ("/usr/bin/pip", "show", "mdformat-tables"): ProcessResult(1, "", ""),
                    ("/usr/bin/pip", "show", "mdformat-frontmatter"): ProcessResult(1, "", ""),
                    ("/usr/bin/pip", "show", "mdformat-footnote"): ProcessResult(1, "", ""),
                    ("/usr/bin/pip", "show", "mdformat-toc"): ProcessResult(1, "", ""),
                },
            )
            events = probe_mdformat_plugins(runner)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].detail["plugin"], "gfm")  # type: ignore[index]


class ResolveMdformatInterpreterTests(unittest.TestCase):
    def test_returns_none_when_mdformat_absent(self) -> None:
        self.assertIsNone(_resolve_mdformat_interpreter(FakeProcessRunner()))

    def test_reads_direct_shebang(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "mdformat")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("#!/opt/foo/bin/python3.11\n# body\n")
            runner = FakeProcessRunner(paths={"mdformat": path})
            self.assertEqual(
                _resolve_mdformat_interpreter(runner), "/opt/foo/bin/python3.11"
            )

    def test_unwraps_env_shebang(self) -> None:
        # `/usr/bin/env python3` -> return "python3" so subprocess resolves via PATH.
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "mdformat")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("#!/usr/bin/env python3 -s\n")
            runner = FakeProcessRunner(paths={"mdformat": path})
            self.assertEqual(_resolve_mdformat_interpreter(runner), "python3")

    def test_unwraps_env_dash_S_shebang(self) -> None:
        # `/usr/bin/env -S python3 ...` — env's split-args flag. The first
        # non-flag token is the interpreter; the leading `-S` (and any
        # other flags between `env` and the interpreter name) must be
        # skipped, not returned as the executable.
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "mdformat")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("#!/usr/bin/env -S python3 -u\n")
            runner = FakeProcessRunner(paths={"mdformat": path})
            self.assertEqual(_resolve_mdformat_interpreter(runner), "python3")

    def test_env_shebang_with_only_flags_returns_none(self) -> None:
        # Pathological: `env -S` and nothing else. No interpreter to
        # extract; must fall through to the pip fallback rather than
        # try to exec `-S` as a binary.
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "mdformat")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("#!/usr/bin/env -S\n")
            runner = FakeProcessRunner(paths={"mdformat": path})
            self.assertIsNone(_resolve_mdformat_interpreter(runner))

    def test_endswith_env_false_positive_rejected(self) -> None:
        # Regression: head.endswith("env") used to match interpreters
        # whose final path component just happened to end with "env" —
        # `/opt/genv/bin/wrapper`, `~/.envs/myenv`, `/some/.env`. Those
        # shebangs were wrongly parsed as the /usr/bin/env <interp>
        # form. Now an exact basename match is required.
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "mdformat")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("#!/opt/genv/bin/wrapper\n")
            runner = FakeProcessRunner(paths={"mdformat": path})
            # The shebang is treated as a non-env interpreter. wrapper
            # is not recognized as Python, so the helper returns None
            # and the probe falls back to pip rather than executing
            # /opt/genv/bin/wrapper -c '...'.
            self.assertIsNone(_resolve_mdformat_interpreter(runner))

    def test_non_python_shebang_falls_back_to_pip(self) -> None:
        # mise / asdf / pyenv shims may have a bash shebang. Running
        # `bash -c 'import importlib.metadata; ...'` would exit non-zero,
        # the probe would report zero plugins, and emit_plugin_missing
        # would fire false events. Reject bash and other non-Python
        # interpreters so the caller falls back to the pip-based probe.
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "mdformat")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("#!/usr/bin/env bash\n")
            runner = FakeProcessRunner(paths={"mdformat": path})
            self.assertIsNone(_resolve_mdformat_interpreter(runner))

    def test_versioned_python_interpreter_recognized(self) -> None:
        # python3.12 etc. — version-suffixed forms should still match.
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "mdformat")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("#!/opt/pipx/venvs/mdformat/bin/python3.12\n")
            runner = FakeProcessRunner(paths={"mdformat": path})
            self.assertEqual(
                _resolve_mdformat_interpreter(runner),
                "/opt/pipx/venvs/mdformat/bin/python3.12",
            )

    def test_returns_none_for_non_shebang_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "mdformat")
            with open(path, "wb") as fh:
                fh.write(b"\x7fELF binary")
            runner = FakeProcessRunner(paths={"mdformat": path})
            self.assertIsNone(_resolve_mdformat_interpreter(runner))

    def test_returns_none_when_file_unreadable(self) -> None:
        # Path resolved by `which` but the file isn't on disk -> OSError -> None.
        runner = FakeProcessRunner(paths={"mdformat": "/no/such/path/mdformat"})
        self.assertIsNone(_resolve_mdformat_interpreter(runner))


class ProbeViaInterpreterTests(unittest.TestCase):
    def test_emits_event_per_installed_plugin(self) -> None:
        interpreter = "/opt/venv/bin/python3"
        results = {
            (
                interpreter, "-c",
                f"import importlib.metadata as m; print(m.version({pkg!r}))",
            ): ProcessResult(0, "1.2.3\n", "") if pkg == "mdformat-gfm"
            else ProcessResult(1, "", "")
            for pkg, _ in KNOWN_PLUGINS
        }
        runner = FakeProcessRunner(results=results)
        events = _probe_via_interpreter(runner, interpreter)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].detail["plugin"], "gfm")  # type: ignore[index]
        self.assertEqual(events[0].detail["version"], "1.2.3")  # type: ignore[index]
        self.assertEqual(events[0].detail["package"], "mdformat-gfm")  # type: ignore[index]

    def test_returns_empty_when_no_plugins_installed(self) -> None:
        interpreter = "/opt/venv/bin/python3"
        results = {
            (
                interpreter, "-c",
                f"import importlib.metadata as m; print(m.version({pkg!r}))",
            ): ProcessResult(1, "", "")
            for pkg, _ in KNOWN_PLUGINS
        }
        runner = FakeProcessRunner(results=results)
        self.assertEqual(_probe_via_interpreter(runner, interpreter), [])


# ============================================================
# detect_installed_plugin_labels
# ============================================================

class DetectInstalledPluginLabelsTests(unittest.TestCase):
    def test_returns_label_set(self) -> None:
        runner = FakeProcessRunner(
            paths={"pip": "/usr/bin/pip"},
            results={
                ("/usr/bin/pip", "show", "mdformat-gfm"): ProcessResult(
                    0, "Version: 0.3.5\n", ""
                ),
                ("/usr/bin/pip", "show", "mdformat-tables"): ProcessResult(
                    0, "Version: 1.0.0\n", ""
                ),
                ("/usr/bin/pip", "show", "mdformat-frontmatter"): ProcessResult(1, "", ""),
                ("/usr/bin/pip", "show", "mdformat-footnote"): ProcessResult(1, "", ""),
                ("/usr/bin/pip", "show", "mdformat-toc"): ProcessResult(1, "", ""),
            },
        )
        labels = detect_installed_plugin_labels(runner)
        self.assertEqual(labels, {"gfm", "tables"})

    def test_empty_when_none_installed(self) -> None:
        self.assertEqual(detect_installed_plugin_labels(FakeProcessRunner()), set())


# ============================================================
# emit_plugin_missing
# ============================================================

class EmitPluginMissingTests(unittest.TestCase):
    def test_no_event_when_gfm_installed(self) -> None:
        events = emit_plugin_missing(
            ["/repo/foo.md"],
            lambda _: "| col | col |\n|---|---|\n| a | b |\n",
            installed_labels={"gfm"},
        )
        self.assertEqual(events, [])

    def test_emits_when_file_needs_gfm_but_plugin_missing(self) -> None:
        events = emit_plugin_missing(
            ["/repo/foo.md"],
            lambda _: "| col | col |\n|---|---|\n| a | b |\n",
            installed_labels=set(),
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event, EventType.PLUGIN_MISSING)
        self.assertEqual(events[0].detail["plugin"], "gfm")  # type: ignore[index]
        self.assertEqual(events[0].detail["file"], "/repo/foo.md")  # type: ignore[index]

    def test_no_event_when_file_is_plain_commonmark(self) -> None:
        events = emit_plugin_missing(
            ["/repo/foo.md"],
            lambda _: "# heading\n\nparagraph\n",
            installed_labels=set(),
        )
        self.assertEqual(events, [])

    def test_unreadable_file_skipped_silently(self) -> None:
        def raise_oserror(_: str) -> str:
            raise OSError("permission denied")

        events = emit_plugin_missing(
            ["/repo/foo.md"], raise_oserror, installed_labels=set()
        )
        self.assertEqual(events, [])

    def test_non_utf8_file_skipped_silently(self) -> None:
        # The CLI preamble plugin check must NOT crash on a non-UTF-8
        # markdown file. UnicodeDecodeError is a ValueError subclass,
        # not OSError; widening the except clause covers both so the
        # entire md-audit / md-format invocation isn't aborted before
        # the formatter even runs.
        def raise_unicode_decode(_: str) -> str:
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid byte")

        events = emit_plugin_missing(
            ["/repo/badenc.md"], raise_unicode_decode, installed_labels=set()
        )
        self.assertEqual(events, [])

    def test_multiple_files_each_emit_independently(self) -> None:
        contents = {
            "/repo/a.md": "| t | t |\n|---|---|\n| 1 | 2 |\n",
            "/repo/b.md": "# plain\n",
            "/repo/c.md": "- [ ] task\n",
        }
        events = emit_plugin_missing(
            list(contents.keys()),
            lambda path: contents[path],
            installed_labels=set(),
        )
        self.assertEqual(len(events), 2)
        self.assertEqual({e.detail["file"] for e in events}, {"/repo/a.md", "/repo/c.md"})  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
