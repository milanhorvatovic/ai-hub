"""emit.serialize — deterministic NDJSON shape."""

from __future__ import annotations

import json
import unittest

from docs_steward.emit import serialize
from docs_steward.events import Event, EventType


class SerializeTests(unittest.TestCase):
    def test_string_detail_round_trips(self) -> None:
        event = Event(EventType.MISSING, "all", "no formatter on PATH")
        decoded = json.loads(serialize(event))
        self.assertEqual(
            decoded,
            {"event": "missing", "tool": "all", "detail": "no formatter on PATH"},
        )

    def test_dict_detail_round_trips(self) -> None:
        detail = {"priority_rank": 1, "install_options": "npm install prettier"}
        event = Event(EventType.RECOMMEND, "prettier", detail)
        decoded = json.loads(serialize(event))
        self.assertEqual(decoded["event"], "recommend")
        self.assertEqual(decoded["tool"], "prettier")
        self.assertEqual(decoded["detail"], detail)

    def test_no_trailing_newline(self) -> None:
        event = Event(EventType.CLEAN, "prettier", "audit passed")
        self.assertFalse(serialize(event).endswith("\n"))

    def test_single_line_output(self) -> None:
        event = Event(EventType.FINDING, "markdownlint-cli2", "file.md:1 MD013")
        self.assertNotIn("\n", serialize(event))

    def test_unicode_preserved(self) -> None:
        event = Event(EventType.FINDING, "prettier", "résumé — done")
        decoded = json.loads(serialize(event))
        self.assertEqual(decoded["detail"], "résumé — done")


if __name__ == "__main__":
    unittest.main()
