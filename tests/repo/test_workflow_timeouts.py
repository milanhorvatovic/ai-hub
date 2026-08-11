"""Structural contract: every workflow job declares an explicit timeout.

A job without `timeout-minutes` inherits GitHub's six-hour default, so a hung
step — a network stall, a wait loop that never terminates — holds a runner for
that whole window and delays everything queued behind it. Each cap is chosen
per job, just above its typical runtime; this guard only pins that the choice
was made, so a new job cannot silently ship with the six-hour default.
"""

from pathlib import Path

import yaml

_WORKFLOW_DIR = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def _jobs(workflow: Path) -> dict:
    parsed = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict), f"{workflow.name}: not a mapping at the top level"
    jobs = parsed.get("jobs") or {}
    assert isinstance(jobs, dict) and jobs, f"{workflow.name}: no jobs found"
    return jobs


def test_every_job_declares_a_timeout() -> None:
    workflows = sorted(_WORKFLOW_DIR.glob("*.y*ml"))
    assert workflows, "no workflow files found"

    missing = [
        f"{workflow.name}:{name}"
        for workflow in workflows
        for name, job in _jobs(workflow).items()
        # A reusable-workflow call cannot declare timeout-minutes; the caps
        # live on the jobs inside the called workflow.
        if "uses" not in (job or {}) and (job or {}).get("timeout-minutes") is None
    ]

    assert not missing, (
        f"jobs without an explicit timeout-minutes: {', '.join(missing)} — an "
        "undeclared job inherits GitHub's six-hour default, so a hung step holds "
        "a runner for six hours before failing"
    )
