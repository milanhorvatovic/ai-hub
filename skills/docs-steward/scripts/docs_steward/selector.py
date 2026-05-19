"""Tool selection given a style baseline and PATH availability.

The baseline-preference table maps a baseline-name prefix to the ordered list
of tools that consume that config family. When the baseline matches a prefix,
the matching tools are tried in order; the first one on PATH wins. When no
prefix matches (or none of the preferred tools is available), `FALLBACK_ORDER`
is tried in order — favoring strict linters over loose formatters, so the
caller gets the noisiest signal when given a choice.

This selection order is intentionally different from `priority.INSTALL_PRIORITY`
which optimizes for "what should the user install first?" — see priority.py.
"""

from __future__ import annotations

import os.path

from .process import ProcessRunner
from .tools import Tool


_BASELINE_PREFERENCES: tuple[tuple[str, tuple[Tool, ...]], ...] = (
    (".markdownlint", (Tool.MARKDOWNLINT_CLI2, Tool.MARKDOWNLINT)),
    (".prettierrc", (Tool.PRETTIER,)),
    ("prettier.config.", (Tool.PRETTIER,)),
    (".remarkrc", (Tool.REMARK,)),
    (".mdformat.toml", (Tool.MDFORMAT,)),
    ("dprint.json", (Tool.DPRINT,)),
)


FALLBACK_ORDER: tuple[Tool, ...] = (
    Tool.MARKDOWNLINT_CLI2,
    Tool.MARKDOWNLINT,
    Tool.PRETTIER,
    Tool.MDFORMAT,
    Tool.DPRINT,
    Tool.REMARK,
)


def select_tool(baseline: str, runner: ProcessRunner) -> Tool | None:
    """Pick the tool to run for `baseline`. Returns None when no usable tool
    is on PATH for any preference + fallback path.

    Matching is done on the baseline's basename so an explicit
    `--baseline /repo/.prettierrc` (or `config/.prettierrc`) honours the
    same family preference as the auto-detected bare `.prettierrc`.
    Without the basename normalization, an absolute or subdirectory path
    fails the `startswith` check and silently falls through to
    `FALLBACK_ORDER`, picking whichever formatter happens to be on PATH
    first — frequently a different family than the user asked for.
    """
    basename = os.path.basename(baseline)
    for prefix, preferred in _BASELINE_PREFERENCES:
        if basename.startswith(prefix):
            for tool in preferred:
                if runner.which(tool.value):
                    return tool
            break  # baseline matched a prefix but none of its tools were available
    for tool in FALLBACK_ORDER:
        if runner.which(tool.value):
            return tool
    return None


def baseline_belongs_to_tool(baseline: str, tool: Tool) -> bool:
    """True when `baseline` is a config the given `tool` natively consumes.

    Routes through the same `_BASELINE_PREFERENCES` table as `select_tool`
    so the answer agrees with selection: e.g. `.prettierrc` belongs to
    Tool.PRETTIER, `.markdownlint.json` belongs to Tool.MARKDOWNLINT_CLI2
    and Tool.MARKDOWNLINT, `.editorconfig` and `universal-subset` belong
    to no tool (the prefix table doesn't include them).

    Used by `runner.run_tool` to decide whether an explicit baseline path
    should be forwarded as the tool's `--config` argument. Passing a
    non-family config (e.g. `.editorconfig` to markdownlint) would either
    error out the formatter or be silently ignored, so the runner only
    threads `--config` through for family-matching baselines.
    """
    basename = os.path.basename(baseline)
    for prefix, preferred in _BASELINE_PREFERENCES:
        if basename.startswith(prefix):
            return tool in preferred
    return False
