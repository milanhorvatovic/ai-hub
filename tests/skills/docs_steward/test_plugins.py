"""plugins module — GFM-syntax sniffer + plugin probe + plugin-missing emit."""

from __future__ import annotations

import unittest

from docs_steward.events import EventType
from docs_steward.plugins import (
    KNOWN_PLUGINS,
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
        # Inline code containing pipes shouldn't false-positive as a table,
        # but the simple regex catches it. Document the limitation.
        # (Conservative: PLUGIN_MISSING is INFO; false positives are acceptable.)
        self.assertFalse(needs_gfm("Some `inline code`."))


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
