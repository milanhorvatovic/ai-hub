"""Install-recommendation priority order.

Distinct from the tool-selection fallback in `selector.py`. Selection answers
"given multiple tools on PATH, which runs?"; priority answers "given nothing,
what should the user install first?". The two orderings diverge because they
optimize for different objectives — strict-linter-first when running, broadest
formatter ecosystem first when installing.
"""

from __future__ import annotations

from .tools import Tool

INSTALL_PRIORITY: tuple[Tool, ...] = (
    Tool.PRETTIER,            # widest ecosystem; --prose-wrap=never matches preference
    Tool.MDFORMAT,            # pure-Python alternative when Node is undesirable
    Tool.MARKDOWNLINT_CLI2,   # strict rule linter; complements a formatter
    Tool.DPRINT,              # fast native binary; plugin URL pinning is the trade-off
    Tool.REMARK,              # niche; needs an installed remark preset to be useful
    Tool.YAMLLINT,            # complementary — lints YAML frontmatter + fenced YAML blocks
)
