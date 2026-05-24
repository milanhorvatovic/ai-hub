"""Resolve the path to the skill's bundled fallback config for a tool.

`bundled_config_for(tool)` returns the absolute path to the shipped config
under `assets/configs/` when the tool supports a path-passable config, else
None. The skill ships configs for markdownlint(-cli2), prettier, and the
complementary yamllint used by `audit-frontmatter`; mdformat / dprint /
remark are intentionally excluded — see `assets/configs/README.md` for the
rationale.

The path resolution uses `__file__` so the lookup works regardless of cwd.
"""

from __future__ import annotations

import os.path

from .tools import Tool

_HERE = os.path.dirname(os.path.abspath(__file__))
_CONFIGS_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "assets", "configs"))


_BUNDLED: dict[Tool, str] = {
    Tool.MARKDOWNLINT_CLI2: os.path.join(_CONFIGS_DIR, "markdownlint.json"),
    Tool.MARKDOWNLINT: os.path.join(_CONFIGS_DIR, "markdownlint.json"),
    Tool.PRETTIER: os.path.join(_CONFIGS_DIR, "prettierrc.json"),
    Tool.YAMLLINT: os.path.join(_CONFIGS_DIR, "yamllint.yaml"),
}


def bundled_config_for(tool: Tool) -> str | None:
    """Absolute path to the bundled fallback config, or None when this tool
    has no shipped config (use the tool's own defaults instead)."""
    return _BUNDLED.get(tool)
