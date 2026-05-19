"""Install recommendations — installed inventory + missing-tool ranking + verdict.

Three event passes followed by a verdict. Exit code 0 when the top-priority
tool is installed; 1 when at least one priority tool is missing.

`install_options` is a JSON array, not a delimited string — install commands
contain shell metacharacters (`|`, `&&`, `;`) and a delimiter-based encoding
would corrupt them. Consumers consume the array directly.
"""

from __future__ import annotations

from .events import Event, EventType
from .hints import install_hints
from .priority import INSTALL_PRIORITY
from .probe import capture_version
from .process import ProcessRunner
from .tools import REGISTRY, SUPPORTED_TOOLS, Tool


def _first_installed_from_priority(runner: ProcessRunner) -> Tool | None:
    """Return the first priority tool that's actually a markdown formatter
    (in `REGISTRY`) AND present on PATH. yamllint is part of INSTALL_PRIORITY
    so the recommender surfaces install commands for it, but it is NOT a
    markdown formatter — finding only yamllint on PATH must not satisfy
    the "fallback tool present" VERDICT, or the message would imply a
    usable markdown formatter exists when probe correctly reports none."""
    formatter_tools = set(REGISTRY.keys())
    for tool in INSTALL_PRIORITY:
        if tool in formatter_tools and runner.which(tool.value):
            return tool
    return None


def recommend_installs(runner: ProcessRunner) -> tuple[list[Event], int]:
    events: list[Event] = []

    # 1. Inventory pass — every supported binary on PATH.
    for tool in SUPPORTED_TOOLS:
        if runner.which(tool.value):
            events.append(
                Event(EventType.INSTALLED, tool.value, capture_version(runner, tool))
            )

    # 2. Recommendation pass — every missing priority tool.
    for rank, tool in enumerate(INSTALL_PRIORITY, start=1):
        if runner.which(tool.value):
            continue
        events.append(
            Event(
                EventType.RECOMMEND,
                tool.value,
                {
                    "priority_rank": rank,
                    "install_options": list(install_hints(tool)),
                },
            )
        )

    # 3. Verdict pass — single summary event tied to exit code.
    top = INSTALL_PRIORITY[0]
    if runner.which(top.value):
        events.append(
            Event(EventType.VERDICT, top.value, "top-priority tool present; no install needed")
        )
        return events, 0

    fallback = _first_installed_from_priority(runner)
    if fallback is not None:
        events.append(
            Event(
                EventType.VERDICT,
                fallback.value,
                f"fallback tool ({fallback.value}) present; consider installing "
                f"{top.value} for the preferred unwrap-friendly experience",
            )
        )
    else:
        events.append(
            Event(
                EventType.VERDICT,
                "none",
                f"no formatter on PATH; install {top.value} (top priority) "
                "or any tool from the recommend events above",
            )
        )
    return events, 1
