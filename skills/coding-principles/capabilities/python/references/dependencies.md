# Python — dependency management

Language-specific dependency mechanics. The cross-language principles (semver, lockfile discipline, audit, minimal footprint) are thin; the mechanics differ per ecosystem. Load when adding, updating, or auditing Python dependencies.

> **The tools named below were last checked 2026-08.** The mechanics do not decay; the tools do. How to read a stamped file is stated once under "Currency" in `../../../SKILL.md`.

## Pinning stance — pin explicit exact versions (default)

**Default: pin exact versions.** Reproducibility over auto-upgrade convenience — the installed version should be exactly the declared version, not whatever a range resolves to today.

- **Applications / services**: pin exact in the manifest *and* commit the lockfile.
  ```toml
  # pyproject.toml — exact pins
  dependencies = [
    "requests==2.32.3",
    "pydantic==2.9.2",
  ]
  ```
  `requests>=2.32` invites silent drift; `requests==2.32.3` does not.
- **Lockfile is mandatory** — `uv.lock` / `poetry.lock` / `pip-tools`-compiled `requirements.txt`. It pins the full transitive tree. Commit it.
- **Hashes** for supply-chain integrity — `uv` records them; with pip-tools use `--generate-hashes` and install `--require-hashes`.

**Exception (ecosystem constraint, not style): published libraries.** A library on PyPI must use compatible ranges (`>=2,<3` / `~=2.32`), never `==` — exact pins force every downstream consumer to that version and cause unresolvable conflicts. Pin hard for what you deploy; range for what you publish. Surface this if the project is a library.

## Toolchain

- **`uv`** (modern default) — fast resolver, lockfile + hashes, `uv add requests==2.32.3`, `uv lock`, `uv sync`.
- `poetry` / `pip-tools` remain valid; same pin-exact + lockfile discipline.
- **`pip-audit`** (or `safety`) in CI — checks the pinned tree against advisories.

## Version syntax (PEP 440)

- `==2.32.3` — exact (the preferred default here).
- `~=2.32.3` — compatible release (`>=2.32.3,<2.33`). For libraries only.
- `>=2,<3` — explicit range. For libraries only.
- `==2.32.*` — prefix match. Avoid for apps (still floats the patch).

## Update cadence

- Automate detection (Renovate / Dependabot) but **review every bump** — an automated PR that changes a pin is a code change, not a rubber stamp. Run tests; read the changelog for majors.
- Update deliberately and in batches you can test, not continuously.

## Minimal footprint

- Prefer the stdlib (see `best-practices.md` "when to leave the stdlib"). Every dependency is a supply-chain surface, a version to track, and a potential CVE.
- Before adding: is it maintained, widely used, and worth the transitive tree it drags in? `uv tree` / `pipdeptree` to see the cost.
- Periodically prune unused deps (`deptry`).

## Principle alignment

- **Reproducibility** — exact pins + committed lockfile make builds deterministic (this skill's default).
- **No dead code** (principle 20) — prune unused dependencies like dead code.
- **Security** (principle 13) — audit pinned deps; hashes prevent tampered packages.
