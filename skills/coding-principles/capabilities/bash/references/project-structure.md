# Bash — project structure & mechanics

Language-specific notes for the architecture concepts in `../../../references/architecture.md`. Short, because bash has almost no architecture above functions and sourced files — and the moment a script *needs* architecture, that is the signal to leave bash.

> **The tools named below were last checked 2026-08.** The mechanics do not decay; the tools do. How to read a stamped file is stated once under "Currency" in `../../../SKILL.md`.

## What bash has

- **Function** — the only unit of decomposition. `local` for scoping (capability.md).
- **Sourced file** — `source lib/foo.sh` (or `. lib/foo.sh`) pulls functions from another file. The closest thing to a module.
- No packages, no visibility modifiers, no interfaces, no dependency injection. Everything sourced shares one global namespace.

## Conventions for a multi-file script

When a script genuinely warrants splitting (still rare — see "when to leave bash" below):

```
tool/
├── tool.sh            # entry point: arg parsing, orchestration
├── lib/
│   ├── common.sh      # shared helpers (logging, error handling)
│   └── deploy.sh      # one concern per file
└── tests/
    └── deploy.bats    # bats-core tests
```

- **Entry point** does arg parsing (`getopts` — see examples.md) and orchestration; sources `lib/*.sh` for the work.
- **Namespace by prefix** — since everything shares globals, prefix related functions (`deploy_start`, `deploy_rollback`) to avoid collisions. This is bash's only "module boundary."
- **Resolve the script's own directory** to source siblings reliably:
  ```bash
  script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  source "$script_dir/lib/common.sh"
  ```
- **`readonly`** for constants; keep mutable globals to a minimum (hidden-state-is-debt — principle 14).

## When to leave bash

The architecture concepts (layering, ports/adapters, dependency direction) effectively don't apply to bash — there's no mechanism to express them. If a script has grown to the point where you *want* those — multiple modules, swappable backends, real boundaries — that is precisely the "leave bash" threshold (best-practices.md): rewrite in Python or Go, where `../../../references/architecture.md` actually has mechanics to apply.

Rule of thumb: past ~200 lines, multiple subcommands, or any need for structured boundaries, stop adding bash structure and switch languages.
