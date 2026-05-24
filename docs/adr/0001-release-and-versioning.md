# 1. Release and versioning

Date: 2026-05-24

## Status

Accepted

## Context

ai-hub is a library of AI-agnostic artifacts — today four skills under `skills/<name>/`, each a self-contained directory distributed via `npx skills` (and planned zip bundles). The skills evolve independently: a fix to `git-toolkit` is unrelated to a fix in `docs-steward`. We need a versioning and release process that (a) gives each skill its own predictable version, (b) provides a single place a human can read what changed across the catalog, and (c) is repeatable rather than hand-cut.

Several facts constrain the design:

- **The consumer tool ignores versions.** `npx skills add <owner>/<repo>/tree/main/skills/<name>` installs the skill at HEAD of the default branch. It reads `name`, `description`, and `metadata.internal`; it does not read a version field, and it has no pinning or ranges. So a per-skill version is a human/changelog signal and a tag a consumer can choose to check out — not a contract the installer enforces.
- **The version already lives in the skill.** Each `SKILL.md` carries `metadata.version` (SemVer), and a structural test asserts the shape. The release process should keep that field authoritative, not introduce a second source of truth.
- **Skill directories must stay clean.** PR A established that `skills/<name>/` ships as-is, so non-distributable files must not live there. Per-skill changelog files under each skill would either ship as noise or have to be filtered.
- **Bundles are built from tracked files.** Future zip bundles come from `git archive`, so `.gitattributes export-ignore` is effectively the shipping manifest.
- **No releases exist yet.** No tags, no GitHub Releases, no `CHANGELOG.md` — this is a clean bootstrap.

## Decision

### Two version namespaces

- **Per-skill SemVer** is the consumer-facing version of each skill, authored in `SKILL.md` `metadata.version` and surfaced as a per-skill git tag and GitHub Release (`<skill>-v<major.minor.patch>`, e.g. `git-toolkit-v1.2.0`). SemVer communicates the impact of a change to that skill's contract (its router/capability behavior); it is a documentation and release signal, not an installer-enforced contract (the consumer tool ignores it).
- **Repo CalVer release-train** (`vYYYY.MM.MICRO`, e.g. `v2026.05.0`) is a catalog snapshot — the set of skill versions as of a date. `MICRO` increments per train cut within a month and resets monthly. It is not SemVer and makes no API promise; it is a coordinate for "the catalog on this date" that the future marketplace can consume.

### One aggregated changelog

A single root `CHANGELOG.md` (Keep a Changelog format) is the human history surface, with entries attributed per skill. This deliberately departs from the common monorepo pattern of per-package changelogs (and from this repo's own `oss-repository-conventions` guidance that "a single root version under-covers"): at four skills with low release frequency, one file readers can scan beats four files they must stitch together, and per-skill files would either pollute the clean skill directories or need filtering from bundles. If the catalog grows enough that one file becomes unwieldy, revisit per-skill files plus a generated index.

### Tooling: release-please + thin glue

- **release-please (manifest/monorepo mode)** is the spine. One component per skill (`release-type: simple`, since a skill is markdown with no language manifest). It attributes each commit to a component by the **file paths** it touches under `skills/<name>/`, computes that skill's next SemVer from the commit **type** in its Conventional-Commit history, bumps `metadata.version` in `SKILL.md` via a generic updater, writes the aggregated root `CHANGELOG.md`, and on merge of its release PR cuts the per-skill tags and GitHub Releases. A contributor who needs to override the computed bump (a human SemVer judgment release-please can't infer) uses a `Release-As: x.y.z` commit footer.
- **The CalVer release-train tag is applied by hand** (a proposed `git tag` command) when a batch of per-skill releases lands. release-please has no CalVer release-type, and automating the umbrella tag + a CalVer-grouped changelog presentation is glue we defer until the cadence justifies it. Until then the train is a lightweight tag plus a dated heading in `CHANGELOG.md`.
- **Changesets was rejected**: it is npm/JS-native and expects a `package.json` per package. The skills are markdown plus stdlib Python with no package manifests; adopting Changesets would mean inventing manifest files purely to feed the tool, fighting the clean-skill-directory decision.

### Commit and change-intent convention

- **Conventional-Commit PR titles** become the rule. PRs are squash-merged, so the PR title is the commit subject release-please reads. The commit **type** (`feat`/`fix`/…) drives the bump and component membership is by **file path** (above); the **scope** names the skill so the changelog groups by it and the PR stays focused (`feat(git-toolkit): …`), enforced by the change-intent gate. Repo-wide changes use an area scope (`release`, `repo`, `deps`, `ci`) or none. Because a squash commit collapses the whole PR, a PR touching two skills bumps both with the same type — so keep one logical change (one skill) per PR.
- **A "change-intent declared" CI gate** validates the PR title against this convention (a stdlib check, no third-party action), failing PRs whose title release-please could not parse or whose scope names neither a skill nor a known area. The gate runs the validator from the **base branch**, not the PR head, so a PR cannot edit the script that judges it; a consequence is that a PR adding a new skill scopes its title `repo` until the skill is on the base branch. The bump itself is then either inferred by release-please from the title or forced with `Release-As:`.
- **Per-skill version-bump policy:** behavior-affecting changes bump per SemVer (breaking → major, additive → minor, fix → patch). Internal-only, behavior-preserving edits (refactors, comment/wording fixes, test-only changes) do **not** require a version bump — versions track the consumer-visible contract, not every edit. When unsure, prefer a patch bump.

### Bundling manifest

`.gitattributes export-ignore` marks repo machinery (`tests/`, `.github/`, dev dotfiles, top-level config) as non-shipping so `git archive` of the repo or a skill subtree excludes it, while documentation under `docs/` (the ADRs that shipped docs link to) stays exportable. This is the manifest the future zip-bundle work (PR C) builds on; the existing distribution-hygiene guard already keeps `skills/<name>/` itself clean.

## Consequences

- `SKILL.md` `metadata.version` lines carry an `# x-release-please-version` annotation so release-please can bump them. This is an innocuous YAML comment that travels into installed copies — accepted as the cost of keeping the version authoritative in one place.
- CONTRIBUTING and AGENTS change from "imperative subjects" to Conventional-Commit subjects with skill scopes. The `git-toolkit` skill already enforces Conventional Commits when a repo opts in, so contributors using it are covered.
- release-please opens a bot-authored release PR; a human merging it is the publish gate, consistent with the repo's "never auto-publish" stance. Releases that must trigger downstream workflows (e.g. bundle builds in PR C) will need a release identity (App/PAT) and OIDC for keyless publish — out of scope here, tracked for PR C.
- SemVer remains a signal, not an installer contract, until `npx skills` (or a successor) supports version selection. The aggregated changelog and per-skill Releases are where the version earns its keep today; the marketplace epic is the eventual consumer-facing history surface.
- The CalVer-grouped changelog presentation and the umbrella-tag automation are deferred; the root `CHANGELOG.md` initially carries release-please's per-skill sections under dated headings.

## Alternatives considered

- **release-please with per-package changelogs** (the default monorepo shape): rejected for the four-skill catalog because it scatters history and pressures the clean skill directories; revisit if the catalog grows.
- **A lightweight custom release script** (contributor-declared versions, custom CalVer tagger, custom changelog assembler): more flexible and fully CalVer/aggregation-native, but it reinvents bump computation, tagging, release creation, and changelog generation, and discards release-please's maintained tooling that this repo's own conventions skill already endorses. Folded in as the documented fallback if release-please's shared-changelog handling proves unworkable in practice.
- **Changesets:** rejected (JS/`package.json`-native; fights the clean-skill-directory decision), as above.
