# Contributing to ai-hub

Thanks for your interest! ai-hub is an incubator for AI-agnostic artifacts — skills, docs, and related content. This guide covers setup, the change process, and what we expect in a pull request.

## Getting started

1. Fork and clone the repository.
2. Create a virtualenv and install the test dependencies:

   ```sh
   python -m venv venv
   ./venv/bin/pip install -r requirements-test.txt
   ```

3. Install the pinned markdown toolchain — needed to format locally and by the opt-in pre-commit hook; CI installs its own copy from the same lockfile:

   ```sh
   npm ci
   ```

4. Run the test suite to confirm a clean baseline:

   ```sh
   ./venv/bin/pytest -q
   ```

## Repository layout

- `skills/<name>/` — one skill per directory: `SKILL.md` (the always-loaded router), optional `capabilities/<name>/capability.md`, and shared `references/`.
- `tests/skills/` — stdlib-only pytest suite: `test_structure_all.py` validates every skill's structure generically (frontmatter, spec limits, annotated semver, capability routing, link resolution, pointer direction); `tests/skills/<snake_name>/` (the skill name snake_cased) holds the content contracts unique to one skill.
- `tests/skills/context-cost-baseline.json` — the recorded discovery / router / load bytes of every skill. The suite fails when the record no longer describes the tree, so a change in what a skill costs to load lands as a reviewable diff; refresh with `./venv/bin/python -m tests.support.context_cost`. The size itself is not gated — only the record going stale is.
- `tests/skill-corpus/<name>/skill.json` — description-activation corpora: positive prompts that should route to the skill, negatives drawn from sibling domains. The `description-eval` workflow scores them against the live descriptions with the pinned skill-system-foundry evaluator — precision/recall is advisory, but a stale `description_sha256` blocks.

## Making a change

- Create a topic branch from `main`.
- Keep changes focused; one logical change per pull request.
- The generic structural suite (`tests/skills/test_structure_all.py`) validates every skill automatically — a new skill needs no test directory to be covered. Add tests under `tests/skills/<snake_name>/` only for contracts unique to that skill.
- Adding or removing a skill's reference files changes what it costs to load, so refresh `tests/skills/context-cost-baseline.json` with `./venv/bin/python -m tests.support.context_cost` and commit the diff — the suite blocks on a stale record, and every pull request gets the per-skill deltas in its job summary.
- Editing a skill's frontmatter `description` means reviewing its corpus: adjust `tests/skill-corpus/<name>/skill.json` if the routing boundary moved, then refresh the recorded hash with the evaluator from [skill-system-foundry](https://github.com/milanhorvatovic/skill-system-foundry) (`evaluate_descriptions.py tests/skill-corpus --skill-set skills --backfill-hash`) — the `description-eval` workflow blocks on a stale hash.
- Code samples in markdown are parsed by the suite: every `python`, `bash`/`sh`, and `typescript` fence in the tracked tree must be syntactically valid — the skills' samples and the commands these contributor docs tell you to run, because a sample that does not run teaches the wrong thing more convincingly than prose does. It is a syntax check and not a typecheck — fragments naming helpers and types that exist nowhere are the right shape for an illustration and pass. Where a fence is a shape to fill in rather than a command to run, mark it in the info string (` ```bash template `) and the parser skips it; the marker is checked in both directions, so a marked fence that parses cleanly fails until the marker comes off. `rust` fences are deliberately unparsed: a fence check joins a language's baseline when CI already installs that toolchain for another reason, and rust would mean adding one for eighteen samples plus a guess at how to wrap each fragment.
- Skill content that decays — toolchain versions, tool recommendations, ecosystem defaults — carries a "last checked" stamp in the file that states it. Refreshing one is its own change: re-verify the claims, move the stamp, and title it `fix(<skill>)`. Keep it separate from PRs that change what a skill _says_, so a currency sweep stays reviewable as a currency sweep and a rule change is not waved through inside one. This governs refreshes; the change that first places a stamp on a file necessarily rides along with whatever work introduces it.
- Run `./venv/bin/pytest -q` before pushing. Markdown is formatted with Prettier (`proseWrap: never`) per `.prettierrc.json` — author prose as one line per paragraph and let it wrap. **This is enforced:** the `lint` workflow runs `npm run format:check` on each pull request, and a hard-wrapped paragraph fails it. Run `npm ci` once to install the pinned Prettier, then `npm run format` to fix formatting locally. That same install also provides the pinned TypeScript compiler, which one test uses to parse every `typescript` sample the skills ship: without it that lane skips and the suite still reports green, so a machine that has never run `npm ci` checks less than CI does — the `code-samples` job installs the compiler and treats a skip as a failure. The check globs every `.md` in the working tree except what `.gitignore` and `.prettierignore` exclude — in CI that is exactly the tracked set, and locally it also sees files you have not committed yet, so a new document is checked before it is ever staged. Generated files stay out via `.prettierignore` — today that is release-please's per-skill changelogs, which are rewritten on every release.
- Optional but recommended: `git config core.hooksPath .githooks` turns on a `commit-msg` hook that checks each commit message as you write it — the same linter CI runs on every PR (see [Commit messages](#commit-messages)). If you use the repo's opt-in [pre-commit](.pre-commit-config.yaml) hooks, note that `core.hooksPath` takes over hook dispatch: the bundled `.githooks/pre-commit` delegates to `pre-commit` automatically, so skip `pre-commit install`.

## Adding a skill

New skills follow the runbook at [docs/adding-a-skill.md](docs/adding-a-skill.md): the skill directory's required shape, the activation corpus, the fleet manifest, the release wiring, and the README entry — with the test that backs each step. The short version: the structural suite validates the skill's shape from its first `pytest` run; staging the skill engages the wiring guards (fleet manifest, release-please config and manifest); the only unguarded step is the README's Skills list. Title the introducing PR with the `repo` scope (see [Pull requests](#pull-requests)) and keep it to one skill.

## Commit messages

Branch commits are concatenated into the squash commit on `main` (the `COMMIT_MESSAGES` setting), so commit text is permanent public history. A CI job in the `change-intent` workflow lints every branch commit, and the `commit-msg` hook above gives you the same feedback locally at commit time:

- **Subject:** a [Conventional Commit](https://www.conventionalcommits.org/) with the same type/scope vocabulary as PR titles, imperative, ≤72 characters, no trailing period.
- **Body:** flowing paragraphs that explain **why** — each blank-line-separated paragraph is a single source line, never hard-wrapped (the repo's `proseWrap: never` rule applied to commit text). Bullet lists, fenced and tab/4-space-indented blocks, and the trailer block are exempt.
- **Trailers:** author-only — no attribution trailers (`Co-Authored-By`, `Signed-off-by`, `Reviewed-by`, …). The scan skips fenced code blocks, so quoting a trailer in an example is fine. `Release-As: x.y.z` (a release-please control footer) and git-generated `(cherry picked from …)` lines are fine.
- **No private references:** don't cite internal planning documents, ticket codes, or audit paths — public text describes the change on its own terms. This check applies everywhere, fenced blocks included.

Bot-authored commits (Dependabot and friends) are exempt in CI, and git-generated text passes everywhere as-is: merge commits, `Revert "…"` subjects, `fixup!` prefixes, and `(cherry picked from …)` lines. Imperative mood and why-over-what are review judgment, not lint rules.

## Versioning

Each skill is versioned independently with [Semantic Versioning](https://semver.org/) in its `SKILL.md` `metadata.version`. Bump it as part of a behavior-affecting change to that skill:

- **major** — a breaking change to the skill's contract (router behavior, capability removal/rename).
- **minor** — a backward-compatible addition (new capability, new trigger).
- **patch** — a backward-compatible fix.

Internal-only, behavior-preserving edits (refactors, comment/wording fixes, test-only changes) do not require a bump. When in doubt, prefer a patch. Releases are cut by [release-please](https://github.com/googleapis/release-please) from merged PR titles. To force a specific version, add a `Release-As: x.y.z` footer to a branch commit: this repo squashes with the `COMMIT_MESSAGES` setting, so branch commit messages are concatenated into the merge commit on `main`, where release-please reads the footer (you can also add it when editing the squash message at merge time). This is a release-please control footer, not an attribution trailer. The repository's release model is recorded in [docs/adr/0001-release-and-versioning.md](docs/adr/0001-release-and-versioning.md).

## Releasing

Per-skill releases are automated; the CalVer catalog snapshot is a deliberate manual step.

**Per-skill releases (automated).** On merge to `main`, release-please opens or updates a release PR that bumps each touched skill's `metadata.version` and writes that skill's own `skills/<name>/CHANGELOG.md` (which ships with the skill). Merging that PR cuts the per-skill `<skill>-v<x.y.z>` tags and GitHub Releases; a `bundle` job then builds the reproducible zip for each skill that released, attaches it together with a `SHA256SUMS` file, and signs build provenance. No manual step is required.

Which identity each workflow acts as — and why the release path is moving off the default `GITHUB_TOKEN`, whose pushes trigger no workflows and so leave the release PR with nothing reported — is recorded in [docs/adr/0002-automation-identity.md](docs/adr/0002-automation-identity.md), along with how to get a real CI run onto that PR meanwhile. Read it before giving any workflow write access or adding a secret.

**Catalog snapshots (manual).** A CalVer `vYYYY.MM.MICRO` catalog snapshot — the set of skill versions as of a date — is cut by hand:

1. Confirm the per-skill Releases you are snapshotting already exist: the catalog's `index.json` points at their assets, so cut it after them.
2. Create the CalVer Release by hand, choosing `vYYYY.MM.MICRO` (`MICRO` increments per cut within the month and resets monthly):

   ```sh
   gh release create v2026.05.0 --title v2026.05.0 --notes "<catalog snapshot notes>"
   ```

3. Run the **release-please** workflow via **Run workflow**, with `ref` set to the snapshot commit-ish (a release tag or `main`) and `catalog_tag` set to the CalVer tag. The run builds the catalog, attests `index.json`, and uploads it to that Release.
4. Verify the published manifest after downloading it from the Release:

   ```sh
   gh attestation verify index.json --repo milanhorvatovic/ai-hub
   ```

Leaving `catalog_tag` empty makes the same dispatch a dry run that publishes the catalog as a workflow artifact, without touching any Release.

## Pull requests

- Fill in the PR template; describe what changed and why, and which skill it touches. The PR body is public text too: the trailer and private-reference checks from [Commit messages](#commit-messages) apply to it (the one-line-paragraph rule does not — PR bodies are markdown).
- PRs are squash-merged, so the **PR title becomes the commit subject** — write it as a [Conventional Commit](https://www.conventionalcommits.org/) with the **skill name as the scope** (e.g. `fix(git-toolkit): handle an empty diff`). Repo-wide changes use an area scope (`release`, `repo`, `deps`, `ci`) or none. A CI gate validates the title; bot-authored titles (Dependabot and friends) waive the length cap only — their grouped-update suffix can exceed it — but must still parse as a Conventional Commit with a valid type and scope. release-please then bumps each skill whose files the PR touched, using the commit **type** (`feat` → minor, `fix` → patch); the scope keeps the changelog grouped by skill. Keep one skill per PR so the squashed commit doesn't bump several skills at once. The gate runs from the base branch (so a PR can't edit the validator that judges it); a PR that introduces a brand-new skill therefore scopes its title `repo` until the skill exists on the base branch.

## Dependency updates

Dependabot groups patch and minor updates by ecosystem and leaves major updates as standalone PRs. Actions that execute with repository write credentials or attestations (`actions/attest-build-provenance` and `googleapis/release-please-action`) are also excluded from the group so they remain standalone. The pinned `dependabot/fetch-metadata` action executes inside the approval workflow itself, so Dependabot ignores it and a maintainer updates that pin through a human-reviewed PR. `.github/workflows/dependabot-auto-merge.yaml` applies a three-tier policy: ordinary patch/minor updates are approved and armed for squash auto-merge; major and privileged-action updates are armed but wait for a code-owner approval; and PRs labeled `trust-boundary` or `security-review-required` remain fully manual. GitHub's branch rules and required checks are the merge safety boundary.

`.github/workflows/dependabot-reconciler.yaml` runs after the policy workflow, after pushes to `main`, every 30 minutes, and on manual dispatch. It updates behind branches and re-arms approved PRs when an event or GitHub's auto-merge worker was missed. It deliberately leaves an unapproved and unarmed PR for manual triage because a scheduled workflow cannot safely reconstruct Dependabot's update type.

`DEPENDABOT_AUTOMERGE_ENABLED` is an operational kill switch. Only the exact value `true` permits approval, auto-merge, and reconciliation; an unset variable or any other value leaves PRs manual. `CODEOWNER_APPROVER_TOKEN` must be a fine-grained PAT owned by a code owner, limited to this repository, with Contents and Pull requests read/write permissions. Store the same token in both the Actions and Dependabot secret stores because Dependabot-triggered workflows cannot read Actions secrets, while scheduled and maintainer-triggered runs cannot read Dependabot secrets.

Provision the prerequisites after the workflows merge, then enable the kill switch last:

```sh
gh repo edit --enable-auto-merge
gh label create trust-boundary --color B60205 --description "Requires manual review because the update crosses a trust boundary"
gh label create security-review-required --color D93F0B --description "Requires explicit security review before merge"
gh secret set --app actions CODEOWNER_APPROVER_TOKEN
gh secret set --app dependabot CODEOWNER_APPROVER_TOKEN
gh variable set DEPENDABOT_AUTOMERGE_ENABLED --body true
```

To stop autonomous dependency updates without removing the workflows, set the variable to `false`. Applying either security-review label to an armed Dependabot PR also disables auto-merge immediately.

## Contribution basis

By contributing you agree your work is licensed under the project's [MIT License](LICENSE). No CLA or sign-off is required.

## Code of conduct

This project follows its [Code of Conduct](CODE_OF_CONDUCT.md). By participating you agree to uphold it.
