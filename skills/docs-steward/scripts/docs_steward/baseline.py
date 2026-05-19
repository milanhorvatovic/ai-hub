"""Style-baseline detection.

`detect_baseline(fs, root, override=None)` walks the candidate list in
declaration order and returns the first existing config filename, or
`UNIVERSAL_SUBSET` when none match. `override` short-circuits detection;
it is passed through verbatim so the caller can force any path.

The candidate list mirrors SKILL.md section 3 step ordering — markdownlint
configs first, then prettier, then remark, mdformat, dprint, editorconfig.
`dprint.json` ranks above `.editorconfig` (round 8e) so a repo that
declares both is matched against the formatter-specific config (routes
to Tool.DPRINT) rather than the cross-tool style hint that has no
preferred-tool entry. Adding a candidate is a one-line edit here;
downstream modules iterate this list.
"""

from __future__ import annotations

import os.path

from .fs import FileSystem


UNIVERSAL_SUBSET = "universal-subset"
"""Sentinel returned when no baseline config is detected. Downstream code
checks for equality with this constant; do not parse it as a path."""


BASELINE_CANDIDATES: tuple[str, ...] = (
    ".markdownlint.json",
    ".markdownlint.jsonc",
    ".markdownlint.yaml",
    ".markdownlint.yml",
    ".markdownlint-cli2.jsonc",
    ".markdownlint-cli2.yaml",
    ".prettierrc",
    ".prettierrc.json",
    ".prettierrc.yaml",
    ".prettierrc.yml",
    ".prettierrc.js",
    ".prettierrc.cjs",
    ".prettierrc.mjs",
    ".prettierrc.toml",
    "prettier.config.js",
    "prettier.config.cjs",
    "prettier.config.mjs",
    ".remarkrc",
    ".remarkrc.json",
    ".remarkrc.yaml",
    ".remarkrc.yml",
    ".remarkrc.js",
    ".remarkrc.cjs",
    ".remarkrc.mjs",
    ".mdformat.toml",
    # `dprint.json` ranks ABOVE `.editorconfig` so a repo that declares
    # both is matched against the formatter-specific config the user
    # explicitly wrote rather than the cross-tool style hint that has
    # no selector preference. `.editorconfig` left below means: if it's
    # the ONLY config a repo declares, selection falls through to
    # FALLBACK_ORDER (which is fine — the user gets whatever formatter
    # is on PATH and editorconfig itself is consumed by tools that
    # support it via their own mechanism, not via --config forwarding).
    "dprint.json",
    ".editorconfig",
)


def detect_baseline(
    fs: FileSystem, root: str, override: str | None = None
) -> str:
    """Return the chosen style-baseline filename relative to `root`, or
    `UNIVERSAL_SUBSET` when nothing matches. When `override` is provided,
    return it verbatim without checking existence — the caller asked for it."""
    if override:
        return override
    for candidate in BASELINE_CANDIDATES:
        if fs.exists(os.path.join(root, candidate)):
            return candidate
    return UNIVERSAL_SUBSET
