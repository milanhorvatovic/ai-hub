# 1. Release and versioning

Date: 2026-05-24

## Status

Accepted

## Context

ai-hub is a library of AI-agnostic artifacts — today four skills under `skills/<name>/`, each a self-contained directory distributed via `npx skills` (and planned zip bundles). The skills evolve independently: a fix to `git-toolkit` is unrelated to a fix in `docs-steward`. We need a versioning and release process that (a) gives each skill its own predictable version, (b) provides a single place a human can read what changed across the catalog, and (c) is repeatable rather than hand-cut.

Several facts constrain the design:

- **The consumer tool ignores versions.** `npx skills add <owner>/<repo>/tree/main/skills/<name>` installs the skill at HEAD of the default branch. It reads `name`, `description`, and `metadata.internal`; it does not read a version field, and it has no pinning or ranges. So a per-skill version is a human/changelog signal and a tag a consumer can choose to check out — not a contract the installer enforces.
- **The version already lives in the skill.** Each `SKILL.md` carries `metadata.version` (SemVer), and a structural test asserts the shape. The release process should keep that field authoritative, not introduce a second source of truth.
- **Skill directories must stay clean.** `skills/<name>/` ships as-is, so non-distributable files (tests, tool configs) must not live there at all — they belong at the repo root, and the distribution-hygiene guard fails if any is tracked under the skill subtree.
- **Bundles are built from tracked files.** Future zip bundles come from `git archive`, so `.gitattributes export-ignore` is effectively the shipping manifest.
- **No releases exist yet.** No tags and no GitHub Releases — this is a clean bootstrap (the root `CHANGELOG.md` holds only a hand-written baseline).

## Decision

### Two version namespaces

- **Per-skill SemVer** is the consumer-facing version of each skill, authored in `SKILL.md` `metadata.version` and surfaced as a per-skill git tag and GitHub Release (`<skill>-v<major.minor.patch>`, e.g. `git-toolkit-v1.2.0`). SemVer communicates the impact of a change to that skill's contract (its router/capability behavior); it is a documentation and release signal, not an installer-enforced contract (the consumer tool ignores it).
- **Repo CalVer release-train** (`vYYYY.MM.MICRO`, e.g. `v2026.05.0`) is a catalog snapshot — the set of skill versions as of a date. `MICRO` increments per train cut within a month and resets monthly. It is not SemVer and makes no API promise; it is a coordinate for "the catalog on this date" that the future marketplace can consume.

### Per-skill changelogs

Each skill owns its `skills/<name>/CHANGELOG.md` (Keep a Changelog format), written by release-please — the standard monorepo layout. A single shared root changelog is not achievable alongside per-skill versioning: release-please resolves each package's `changelog-path` relative to that package's directory and rejects `..` traversal, so a package cannot write up to a repo-root file. Per-skill packages (which per-skill SemVer requires) and one aggregated root file are mutually exclusive through this mechanism; keeping both would need custom aggregation glue that reinvents what release-please already does.

The per-skill file ships with its skill by design. A single-skill `npx skills add …/skills/<name>` installs only that directory, so a per-skill changelog gives that consumer the skill's own history — which a repo-root file never reached. The distribution-hygiene guard permits `CHANGELOG.md` as distributable content, and a guard test pins the allowance so it is not mistaken for dev cruft.

The root `CHANGELOG.md` is the frozen pre-automation baseline (the `v2026.05.0` initial-catalog record), no longer a release-please target. The catalog-wide view is the CalVer release-train (`vYYYY.MM.MICRO`) in GitHub Releases; a generated index over the per-skill files is the natural home for a single scannable surface if the cadence later warrants it. At four skills this trades the one-file scan the catalog began with for a layout that both works and travels with each skill.

### Tooling: release-please + thin glue

- **release-please (manifest/monorepo mode)** is the spine. One component per skill (`release-type: simple`, since a skill is markdown with no language manifest). It attributes each commit to a component by the **file paths** it touches under `skills/<name>/`, computes that skill's next SemVer from the commit **type** in its Conventional-Commit history, bumps `metadata.version` in `SKILL.md` via a generic updater, writes each skill's own `skills/<name>/CHANGELOG.md`, and on merge of its release PR cuts the per-skill tags and GitHub Releases. A contributor who needs to override the computed bump (a human SemVer judgment release-please can't infer) uses a `Release-As: x.y.z` commit footer.
- **The CalVer release-train tag is applied by hand** (a proposed `git tag` command) when a batch of per-skill releases lands. release-please has no CalVer release-type, and automating the umbrella tag + a CalVer-grouped changelog presentation is glue we defer until the cadence justifies it. Until then the train is a lightweight tag, with the catalog-wide view presented in GitHub Releases.
- **Changesets was rejected**: it is npm/JS-native and expects a `package.json` per package. The skills are markdown plus stdlib Python with no package manifests; adopting Changesets would mean inventing manifest files purely to feed the tool, fighting the clean-skill-directory decision.

### Commit and change-intent convention

- **Conventional-Commit PR titles** become the rule. PRs are squash-merged, so the PR title is the commit subject release-please reads. The commit **type** (`feat`/`fix`/…) drives the bump and component membership is by **file path** (above); the **scope** names the skill so the changelog groups by it and the PR stays focused (`feat(git-toolkit): …`), enforced by the change-intent gate. Repo-wide changes use an area scope (`release`, `repo`, `deps`, `ci`) or none. Because a squash commit collapses the whole PR, a PR touching two skills bumps both with the same type — so keep one logical change (one skill) per PR.
- **A "change-intent declared" CI gate** validates the PR title against this convention (a stdlib check, no third-party action), failing PRs whose title release-please could not parse or whose scope names neither a skill nor a known area. The gate runs the validator from the **base branch**, not the PR head, so a PR cannot edit the script that judges it; a consequence is that a PR adding a new skill scopes its title `repo` until the skill is on the base branch. The bump itself is then either inferred by release-please from the title or forced with `Release-As:`.
- **Per-skill version-bump policy:** behavior-affecting changes bump per SemVer (breaking → major, additive → minor, fix → patch). Internal-only, behavior-preserving edits (refactors, comment/wording fixes, test-only changes) do **not** require a version bump — versions track the consumer-visible contract, not every edit. When unsure, prefer a patch bump.

### Bundling manifest

`.gitattributes export-ignore` marks repo machinery (`tests/`, `.github/`, dev dotfiles, top-level config) as non-shipping so `git archive` of the repo or a skill subtree excludes it, while documentation under `docs/` (the ADRs that shipped docs link to) stays exportable. This is the manifest the zip-bundle build relies on; the distribution-hygiene guard keeps `skills/<name>/` itself clean.

## Consequences

- `SKILL.md` `metadata.version` lines carry an `# x-release-please-version` annotation so release-please can bump them. This is an innocuous YAML comment that travels into installed copies — accepted as the cost of keeping the version authoritative in one place.
- CONTRIBUTING and AGENTS change from "imperative subjects" to Conventional-Commit subjects with skill scopes. The `git-toolkit` skill already enforces Conventional Commits when a repo opts in, so contributors using it are covered.
- release-please opens a bot-authored release PR; a human merging it is the publish gate, consistent with the repo's "never auto-publish" stance. Merging the release PR runs the release path, which bundles each released skill, signs it with OIDC keyless (sigstore) signing, and attaches the zip with a build-provenance attestation.
- SemVer remains a signal, not an installer contract, until `npx skills` (or a successor) supports version selection. Each skill's changelog and its GitHub Releases are where the version earns its keep today; the marketplace epic is the eventual consumer-facing history surface.
- The CalVer-grouped changelog presentation and the umbrella-tag automation are deferred; each skill's `CHANGELOG.md` carries its own release-please sections, and the root `CHANGELOG.md` is the frozen pre-automation baseline.

## Alternatives considered

- **A single aggregated root changelog** (one `CHANGELOG.md` for the whole catalog): attractive for a four-skill catalog — one file to scan rather than four to stitch — but not writable from per-skill release-please packages (they cannot escape their own directory to a repo-root file), so it is incompatible with per-skill versioning without custom aggregation glue.
- **A lightweight custom release script** (contributor-declared versions, custom CalVer tagger, custom changelog assembler): more flexible and fully CalVer/aggregation-native, but it reinvents bump computation, tagging, release creation, and changelog generation, and discards release-please's maintained tooling that this repo's own conventions skill already endorses.
- **Changesets:** rejected (JS/`package.json`-native; fights the clean-skill-directory decision), as above.
