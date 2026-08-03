"""Style-baseline detection.

`detect_baselines(fs, root)` walks the candidate list in declaration order
and returns every config filename that exists at the repo root — the raw
material `selector.build_audit_plan` partitions into a formatter owner and
complementary lint passes. An empty result means the repo declares nothing;
the plan builder then applies `UNIVERSAL_SUBSET` per tool family.

The candidate list mirrors SKILL.md section 3 step ordering — markdownlint
configs first, then prettier, then remark, mdformat, dprint, editorconfig.
Declaration order doubles as the precedence policy when a repo declares two
configs of the same kind (e.g. `.prettierrc` and `dprint.json`): the earlier
candidate owns its concern. Adding a candidate is a one-line edit here;
downstream modules iterate this list.
"""

from __future__ import annotations

from .fs import FileSystem
from .paths import posix_join

UNIVERSAL_SUBSET = "universal-subset"
"""Sentinel used when no baseline config governs a concern. Downstream code
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
    # no selector preference. `.editorconfig` belongs to no tool family,
    # so its presence never claims a concern — a repo declaring only
    # `.editorconfig` gets the bundled fallback for both the formatter
    # and lint concerns, exactly like a repo that declares nothing.
    "dprint.json",
    ".editorconfig",
)


def detect_baselines(fs: FileSystem, root: str) -> tuple[str, ...]:
    """Return every baseline candidate present at `root`, in declaration
    order. Empty tuple when the repo declares none — the caller applies
    `UNIVERSAL_SUBSET` per concern.

    Probes with forward-slash joins (like the rest of the package feeds
    the FileSystem port) so the checked path is identical on every host."""
    return tuple(
        candidate
        for candidate in BASELINE_CANDIDATES
        if fs.exists(posix_join(root, candidate))
    )
