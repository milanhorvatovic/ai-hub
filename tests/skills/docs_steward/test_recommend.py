"""recommend.recommend_installs — verdict gating + event ordering."""

from __future__ import annotations

import unittest

from docs_steward.events import EventType
from docs_steward.process import ProcessResult
from docs_steward.recommend import recommend_installs
from docs_steward.tools import Tool

from .fakes import FakeProcessRunner


def _runner_with_tools(*tools: Tool) -> FakeProcessRunner:
    paths = {t.value: f"/usr/bin/{t.value}" for t in tools}
    # Each installed tool also needs --version routed somewhere.
    results = {
        (t.value, "--version"): ProcessResult(0, f"{t.value} 1.0.0\n", "") for t in tools
    }
    return FakeProcessRunner(paths=paths, results=results)


class RecommendInstallsTests(unittest.TestCase):
    def test_nothing_installed_yields_6_recommendations_and_exit_1(self) -> None:
        events, code = recommend_installs(FakeProcessRunner())
        self.assertEqual(code, 1)
        recommends = [e for e in events if e.event == EventType.RECOMMEND]
        self.assertEqual(len(recommends), 6)
        # Verify rank monotonicity.
        ranks = [e.detail["priority_rank"] for e in recommends]  # type: ignore[index]
        self.assertEqual(ranks, [1, 2, 3, 4, 5, 6])

    def test_nothing_installed_verdict_is_none(self) -> None:
        events, _ = recommend_installs(FakeProcessRunner())
        verdict = events[-1]
        self.assertEqual(verdict.event, EventType.VERDICT)
        self.assertEqual(verdict.tool, "none")

    def test_top_priority_installed_yields_exit_0(self) -> None:
        runner = _runner_with_tools(Tool.PRETTIER)
        events, code = recommend_installs(runner)
        self.assertEqual(code, 0)
        # Recommends are emitted for every missing priority tool, even when the
        # top tool is installed — alternatives stay discoverable.
        recommends = [e for e in events if e.event == EventType.RECOMMEND]
        self.assertEqual(len(recommends), 5)
        self.assertNotIn(
            Tool.PRETTIER.value, [r.tool for r in recommends]
        )
        verdict = events[-1]
        self.assertEqual(verdict.event, EventType.VERDICT)
        self.assertEqual(verdict.tool, Tool.PRETTIER.value)

    def test_fallback_installed_recommends_top_and_exit_1(self) -> None:
        # mdformat (rank 2) installed; prettier (rank 1) missing.
        runner = _runner_with_tools(Tool.MDFORMAT)
        events, code = recommend_installs(runner)
        self.assertEqual(code, 1)
        verdict = events[-1]
        self.assertEqual(verdict.event, EventType.VERDICT)
        self.assertEqual(verdict.tool, Tool.MDFORMAT.value)
        self.assertIn("prettier", verdict.detail)  # type: ignore[operator]

    def test_installed_events_precede_recommend_events(self) -> None:
        runner = _runner_with_tools(Tool.MDFORMAT)
        events, _ = recommend_installs(runner)
        types = [e.event for e in events]
        last_installed = max(i for i, t in enumerate(types) if t == EventType.INSTALLED)
        first_recommend = min(i for i, t in enumerate(types) if t == EventType.RECOMMEND)
        self.assertLess(last_installed, first_recommend)


if __name__ == "__main__":
    unittest.main()
