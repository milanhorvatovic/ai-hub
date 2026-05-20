# Bash — dependency management

Bash has no package manager. "Dependencies" are the external commands a script invokes (`jq`, `curl`, `git`, GNU vs BSD coreutils — see `platform-matrix.md`) and any sourced libraries. Load when a script depends on external tools.

## Pinning stance — declare and check, pin where you control the environment

The user's pin-explicit preference manifests differently here — there's no version range to pin, but the same intent (deterministic, reproducible) applies:

- **Declare required tools and minimum versions** in the script header and/or README, and **check them at startup** (fail fast — principle / fail-fast mantra):
  ```bash
  require() { command -v "$1" >/dev/null 2>&1 || { echo "missing required tool: $1" >&2; exit 69; }; }   # EX_UNAVAILABLE
  require jq
  require curl

  # version check when a minimum matters
  jq_ver=$(jq --version | sed 's/jq-//')
  [[ "$(printf '%s\n1.6\n' "$jq_ver" | sort -V | head -1)" == "1.6" ]] || { echo "jq >= 1.6 required" >&2; exit 69; }
  ```
- **Pin the environment, not the command** — when reproducibility genuinely matters, pin the *whole toolchain* with a container image (exact base image tag, not `latest`) or Nix. That's how bash "pins versions": fix the environment the script runs in.
- **Vendoring** — for small sourced libraries, vendor a copy at a known version into `lib/` rather than fetching at runtime; a runtime `curl | bash` is both a supply-chain risk and a non-reproducible dependency.

## Sourced libraries

- `source lib/foo.sh` for in-repo helpers (see `project-structure.md`).
- Vendor third-party shell libraries (e.g. a `bats` helper) at a pinned commit; don't fetch at runtime.

## Supply chain

- **Never `curl ... | bash`** from an unpinned URL — you're executing whatever the server returns today. If you must fetch-and-run, pin to a commit hash and verify a checksum.
- Tools installed via a package manager (apt/brew) should be pinned in the *container/image* layer for reproducible runs.

## When this is a "leave bash" signal

If a script's external-tool dependencies are numerous or version-sensitive enough that you're writing elaborate version checks, that complexity is a signal to move to a language with real dependency management (see `best-practices.md` "when to leave bash").

## Principle alignment

- **Fail fast, fail loud** mantra — check required tools at startup with a clear message + a meaningful exit code, not a cryptic failure deep in the script.
- **Reproducibility** — pin the environment (container tag / Nix) since the commands themselves can't be pinned (the user's preference, applied at the environment level).
- **Security** (principle 13) — no unpinned `curl | bash`; vendor + checksum.
