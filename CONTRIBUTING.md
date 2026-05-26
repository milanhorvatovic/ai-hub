# Contributing to ai-hub

Thanks for your interest! ai-hub is an incubator for AI-agnostic artifacts — skills, docs, and related content. This guide covers setup, the change process, and what we expect in a pull request.

## Getting started

1. Fork and clone the repository.
2. Create a virtualenv and install the test dependencies:

   ```sh
   python -m venv venv
   ./venv/bin/pip install -r requirements-test.txt
   ```

3. Run the test suite to confirm a clean baseline:

   ```sh
   ./venv/bin/pytest -q
   ```

## Repository layout

- `skills/<name>/` — one skill per directory: `SKILL.md` (the always-loaded router), optional `capabilities/<name>/capability.md`, and shared `references/`.
- `tests/skills/<name>/` — stdlib-only pytest structural self-tests for each skill (frontmatter, semver, capability/reference resolution).

## Making a change

- Create a topic branch from `main`.
- Keep changes focused; one logical change per pull request.
- Add or update a skill's structural tests for any change to its shape.
- Run `./venv/bin/pytest -q` before pushing. Markdown is formatted with Prettier (`proseWrap: never`) per `.prettierrc.json` — author prose as one line per paragraph and let it wrap.

## Versioning

Each skill is versioned independently with [Semantic Versioning](https://semver.org/) in its `SKILL.md` `metadata.version`. Bump it as part of a behavior-affecting change to that skill:

- **major** — a breaking change to the skill's contract (router behavior, capability removal/rename).
- **minor** — a backward-compatible addition (new capability, new trigger).
- **patch** — a backward-compatible fix.

Internal-only, behavior-preserving edits (refactors, comment/wording fixes, test-only changes) do not require a bump. When in doubt, prefer a patch. Releases are cut by [release-please](https://github.com/googleapis/release-please) from merged PR titles. To force a specific version, add a `Release-As: x.y.z` footer to a branch commit: this repo squashes with the `COMMIT_MESSAGES` setting, so branch commit messages are concatenated into the merge commit on `main`, where release-please reads the footer (you can also add it when editing the squash message at merge time). This is a release-please control footer, not an attribution trailer. The repository's release model is recorded in [docs/adr/0001-release-and-versioning.md](docs/adr/0001-release-and-versioning.md).

## Releasing

Per-skill releases are automated; the CalVer catalog snapshot is a deliberate manual step.

**Per-skill releases (automated).** On merge to `main`, release-please opens or updates a release PR that bumps each touched skill's `metadata.version`. Merging that PR cuts the per-skill `<skill>-v<x.y.z>` tags and GitHub Releases; a `bundle` job then builds the reproducible zip for each skill that released, attaches it together with a `SHA256SUMS` file, and signs build provenance. The aggregated root `CHANGELOG.md` is **not** maintained here — it is regenerated at the catalog snapshot below. No manual step is required for the per-skill release itself.

**Catalog snapshots (manual).** A CalVer `vYYYY.MM.MICRO` catalog snapshot — the set of skill versions as of a date — is cut by hand:

1. Confirm the per-skill Releases you are snapshotting already exist: the catalog's `index.json` points at their assets, so cut it after them.
2. Create the CalVer Release by hand, choosing `vYYYY.MM.MICRO` (`MICRO` increments per cut within the month and resets monthly):

   ```sh
   gh release create v2026.05.0 --title v2026.05.0 --notes "<catalog snapshot notes>"
   ```

3. Run the **release-please** workflow via **Run workflow**, with `ref` set to the snapshot commit-ish (a release tag or `main`) and `catalog_tag` set to the CalVer tag. The run builds the catalog, attests `index.json`, regenerates the aggregated root `CHANGELOG.md` for this snapshot, and uploads both to that Release.
4. Verify the published manifest after downloading it from the Release:

   ```sh
   gh attestation verify index.json --repo milanhorvatovic/ai-hub
   ```

5. Land the regenerated `CHANGELOG.md` on `main` via a PR. `main` is PR-only, so the workflow can't write it directly — download the attached file and open a small PR replacing the root `CHANGELOG.md`:

   ```sh
   gh release download v2026.05.0 -p CHANGELOG.md
   # review the diff, then open a PR with the updated CHANGELOG.md
   ```

Leaving `catalog_tag` empty makes the same dispatch a dry run that publishes the catalog (without the `CHANGELOG.md` regeneration) as a workflow artifact, without touching any Release.

## Pull requests

- Fill in the PR template; describe what changed and why, and which skill it touches.
- PRs are squash-merged, so the **PR title becomes the commit subject** — write it as a [Conventional Commit](https://www.conventionalcommits.org/) with the **skill name as the scope** (e.g. `fix(git-toolkit): handle an empty diff`). Repo-wide changes use an area scope (`release`, `repo`, `deps`, `ci`) or none. A CI gate validates the title. release-please then bumps each skill whose files the PR touched, using the commit **type** (`feat` → minor, `fix` → patch); the scope keeps the changelog grouped by skill. Keep one skill per PR so the squashed commit doesn't bump several skills at once. The gate runs from the base branch (so a PR can't edit the validator that judges it); a PR that introduces a brand-new skill therefore scopes its title `repo` until the skill exists on the base branch.

## Contribution basis

By contributing you agree your work is licensed under the project's [MIT License](LICENSE). No CLA or sign-off is required.

## Code of conduct

This project follows its [Code of Conduct](CODE_OF_CONDUCT.md). By participating you agree to uphold it.
