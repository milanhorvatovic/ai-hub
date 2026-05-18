"""Per-tool command builder.

Pure transformation: `(tool, mode, unwrap, config_path) -> list[str]`. Looks up
the `CommandTemplate` from `tools.REGISTRY`, picks the audit-vs-format base,
and inserts the optional config + unwrap flags immediately after the
executable name. Returns an `argv`-style list suitable for direct
`subprocess.run(args, shell=False, ...)`.

The config flag is appended as separate argv elements (e.g. `--config`,
`/path/to/file.json`) rather than the combined `--config=PATH` form, because
markdownlint-cli2 treats `--config=PATH` as a file glob and silently drops
the config. The separate-args form works for every supported tool.

Inserting flags at position 1 (just after the executable) is the canonical
spot for every formatter the registry supports; both prettier and markdownlint
treat trailing globs as positional inputs and need flags before them.
"""

from __future__ import annotations

from .modes import Mode
from .tools import REGISTRY, Tool


def build_command(
    tool: Tool,
    mode: Mode,
    unwrap: bool = False,
    config_path: str | None = None,
) -> list[str]:
    """Return the argv list for invoking `tool` in `mode` with optional
    `--config` and unwrap flags. Unknown `tool` raises KeyError, signaling
    a registry / caller mismatch (programmer error, not user input)."""
    template = REGISTRY[tool]
    base = template.audit if mode == Mode.AUDIT else template.fmt

    extras: list[str] = []
    if config_path and template.config_flag:
        extras.extend(template.config_flag)
        extras.append(config_path)
    if unwrap and template.unwrap_flag:
        extras.append(template.unwrap_flag)

    if not extras:
        return list(base)
    # Flags go after the executable (base[0]) but before positional inputs.
    return [base[0], *extras, *base[1:]]
