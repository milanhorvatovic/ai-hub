# TypeScript / Node — dependency management

Language-specific dependency mechanics. The cross-language principles (semver, lockfile discipline, audit, minimal footprint) are thin; the mechanics differ per ecosystem. Load when adding, updating, or auditing npm dependencies.

> **The tools named below were last checked 2026-08.** The mechanics do not decay; the tools do. How to read a stamped file is stated once under "Currency" in `../../../SKILL.md`.

## Pinning stance — pin explicit exact versions (default)

**Default: pin exact versions.** npm's `^` (caret) and `~` (tilde) float the version — `"react": "^18.3.1"` installs any `18.x` at install time. Pin exact for reproducibility.

- **Applications / services**: pin exact in `package.json` *and* commit the lockfile.
  ```json
  // package.json — exact, no ^ or ~
  "dependencies": {
    "react": "18.3.1",
    "zod": "4.1.11"
  }
  ```
- **Default new installs to exact** — set `.npmrc` `save-exact=true` (npm) or `save-exact=true` in `.npmrc` for pnpm, so `pnpm add x` writes `1.2.3` not `^1.2.3`.
- **Lockfile is mandatory** — `pnpm-lock.yaml` / `package-lock.json`. It pins the full transitive tree with integrity hashes. Commit it.
- **`overrides`** (`package.json`) to pin a transitive dependency exactly (e.g. to dodge a CVE before the parent updates).

**Exception (ecosystem constraint, not style): published packages.** A library on npm should use ranges (`^`) for its dependencies and `peerDependencies` — exact pins force resolution and break consumers' dedup. Pin hard for apps; range for published packages.

## Toolchain

- **`pnpm`** (preferred — strict, fast, monorepo-native). `npm` acceptable. Same pin-exact + commit-lockfile discipline.
- **`pnpm audit` / `npm audit`** in CI against the pinned tree.
- **`npm-check-updates` (`ncu`)** to *surface* available updates — but apply deliberately, with review and tests, not blindly.

## Version syntax (semver ranges)

- `1.2.3` — exact (the preferred default here).
- `^1.2.3` — compatible (`>=1.2.3 <2.0.0`). For published libraries only.
- `~1.2.3` — patch-level (`>=1.2.3 <1.3.0`). For published libraries only.
- `*` / `latest` — never.

## Update cadence

- Renovate / Dependabot to detect; **review every bump** (it's a code change). Run tests, read changelogs for majors.
- Batch and test updates; don't continuously float.

## Minimal footprint

- The npm tree gets huge fast. Before adding: check bundle-size impact (`bundlephobia`, `source-map-explorer`), maintenance, and the transitive count. A date library should not be 70KB (see `best-practices.md` / `performance.md`).
- Prefer built-ins (Node `fetch`, `node:` modules) over dependencies.
- Prune unused (`depcheck`, `knip`).

## Principle alignment

- **Reproducibility** — exact pins + committed lockfile = deterministic installs (this skill's default).
- **No dead code** (principle 20) — prune unused dependencies.
- **Security** (principle 13) — audit; lockfile integrity hashes; `overrides` for fast CVE pins.
