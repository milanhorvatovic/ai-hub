---
name: dependency-supply-chain
description: >
  Scans, audits, and scaffolds a repository's dependency and supply-chain
  hygiene — automated dependency updates (Dependabot/Renovate), committed
  lockfiles, dependency pinning/constraints, vulnerability monitoring, and SBOM
  generation. Audit flags no update automation, unmonitored vulnerable deps, and
  wildcard versions; scaffold writes a Dependabot config (house style) or a
  Renovate config. Workflow action-pinning lives in the ci-automation capability.
  Triggers on "set up Dependabot/Renovate", "are my deps up to date", "add an
  SBOM", "monitor vulnerable dependencies", or a full-repo audit.
allowed-tools: Bash Read Grep Glob Write
---

# dependency-supply-chain capability

Governs the trustworthiness of what the project depends on: are updates automated, is the dependency graph pinned and reproducible, are known vulnerabilities surfaced, and can consumers see a bill of materials. Reads and judges by default; writes dependency config only on confirmation.

## Modes

- **scan** — report the update automation, lockfiles, and supply-chain tooling present.
- **audit** — judge hygiene against `../../references/oss-health-rubric.md` and OpenSSF Scorecard.
- **scaffold** — write a Dependabot or Renovate config after confirmation.

## Inputs & guards

- Not a git repo → stop.
- Workflow action-pinning (`uses:` SHAs) is the ci-automation capability; here, cover package dependencies and update bots (don't double-report action pinning).
- Detect package ecosystems first (npm, pip/uv, cargo, go, bundler, …) so config targets the right manifests.
- Don't run dependency updates or installs — propose config and commands.

## Languages

Detect per `../../references/language-support.md`. Bound by Dependabot's `package-ecosystem` set:

- **First-class (Dependabot):** `npm`, `pip`, `uv`, `cargo`, `gomod`, `bundler`, `composer`, `gradle`, `maven`, `nuget`, `mix`, `pub`, `swift`, `docker`, `github-actions`, `terraform`, `gitsubmodule`.
- **Recognized:** ecosystems Dependabot lacks but Renovate covers — propose Renovate instead.
- **Unknown:** no update-bot config; flag dependencies as manually maintained. Never invent a `package-ecosystem` value.
- **Hash-pinning mechanism (per ecosystem):** pip `--require-hashes` / `uv.lock` / `poetry.lock`; `package-lock.json` + `npm ci`; `Cargo.lock`; `go.sum` (hashes built in); `Gemfile.lock` — name the right mechanism for the detected ecosystem rather than a generic one.

## Scan

Sources (catalog: `../../references/convention-files.md`, CI/CD + Security sections), citing each:

1. Update automation: `.github/dependabot.yml` / `.yaml`, `renovate.json` / `.renovaterc*` / `renovate` key in `package.json`.
2. Lockfiles: `package-lock.json` / `pnpm-lock.yaml` / `yarn.lock`, `poetry.lock` / `uv.lock`, `Cargo.lock`, `go.sum`, `Gemfile.lock`.
3. Version constraints: scan manifests for wildcard / unconstrained versions (`*`, `latest`).
4. Vulnerability monitoring: Dependabot alerts (`gh api repos/{owner}/{repo}/vulnerability-alerts` returns 204 when enabled), secret/dependency scanning settings.
5. SBOM/provenance: CycloneDX / Syft / `actions/dependency-review-action` steps in workflows.
6. Update autonomy: workflows that auto-label, auto-approve, and auto-merge Dependabot PRs (`dependabot/fetch-metadata`, `gh pr merge --auto`) and any reconcile/scheduled catch-up job.

## Audit

Checks follow the schema in `../../references/oss-health-rubric.md` (`id` — **severity** [· scorecard: Name]. criterion. why):

- `updates-automated` — **should** · scorecard: Dependency-Update-Tool. Fail when no Dependabot/Renovate config exists. Without it, dependencies rot and CVE fixes are missed.
- `updates-autonomous` — **could** (→ **should** for repos drowning in update PRs). Pass when safe update-types (patch/minor) are auto-approved and auto-merged once required checks pass, with a reconcile/scheduled catch-up. Open-only automation still buries maintainers in manual merges.
- `vulnerabilities-monitored` — **should** · scorecard: Vulnerabilities. Fail when Dependabot alerts / dependency scanning are off. Known-vulnerable deps go unnoticed.
- `lockfile-committed` — **should** (apps; nuanced for libraries). Fail when an application has no committed lockfile. Without it, installs and CI aren't reproducible.
- `deps-pinned` — **could**. Pass when dependencies are constrained (no `*` / `latest`). Wildcards make builds non-deterministic and widen the attack surface.
- `deps-hash-pinned` — **could** (→ **should** for apps that ship a lockfile). Pass when dependencies are pinned by **hash**, not only version (pip `--require-hashes`, a committed lockfile with integrity hashes, `npm ci` against `package-lock.json`). Hash-pinning blocks a tampered-but-same-version package — the S2C2F consumption baseline (see below).
- `sbom-published` — **could** (→ **should** for distributed artifacts). Pass when an SBOM is generated/attached to releases. Lets consumers audit the supply chain.

Consumption maturity is framed by the **S2C2F** (Secure Supply Chain Consumption Framework): ingest dependencies through a controlled source, pin by hash, scan for vulnerabilities and malware, and be able to rebuild from a known-good cache. The checks above (`updates-automated`, `vulnerabilities-monitored`, `lockfile-committed`, `deps-hash-pinned`) are its baseline practices; deeper S2C2F levels (private mirror/proxy, provenance verification on ingest) are `could` and noted, not scaffolded.

## Scaffold

Templates live in `references/scaffold-templates.md` (Dependabot config, Renovate config, a dependency-review CI step). Write after confirmation, targeting the detected ecosystems. House style uses **Dependabot** at `.github/dependabot.yaml` with a weekly cadence and grouped updates; offer Renovate if the maintainer prefers it. Enabling Dependabot alerts is a repo _setting_ — propose the command, don't apply it.

For hands-off updates, scaffold the **autonomous Dependabot recipe** in the same file (release-label → auto-merge → reconciler), distilled from a proven setup. The recipe classifies every bot PR into one of three tiers — **eligible** (patch/minor of an unprivileged dependency: approve + arm auto-merge, hands-off), **held** (major, or a privileged dependency: arm but never approve, so one human review completes the merge), and **veto** (a hard-stop label: untouched, disarmed if already armed, and any pre-veto bot approval dismissed) — with the pr-autonomy failure postures (a step that grants autonomy denies on failure; a step that revokes it blocks on failure, loudly, behind a required context). One class is excluded _earlier_ than any tier can act: the actions the policy job itself runs (the metadata and token-minting actions) execute from the PR head's workflow definition **before** the tier decision, credentials in scope — so their pins are barred from bot updates in the update-bot config and arrive as human PRs (the ci-automation `fork-pr-safe` check states the general rule). It requires:

- a **GitHub App token or bot PAT** — the default `GITHUB_TOKEN`'s own events don't cascade to the downstream required checks (only explicit dispatch does) and it approves only behind an off-by-default setting; pick per `../../references/automation-identity.md` (App token preferred);
- **branch protection with required status checks** so `gh pr merge --auto` lands a PR only when it's green, **plus at least one required approving review with stale-review dismissal on push** — the held tier's arm-but-never-approve hold exists only where a review is required (without it a major or privileged update merges unattended; leave held updates unarmed there), and only where a post-approval rebase re-invalidates the approval, or the bot's update merges an unreviewed commit on it;
- an **update-type gate** (`dependabot/fetch-metadata`) that auto-merges patch/minor but holds major and security-flagged PRs for a human;
- for **built artifacts** (e.g. a bundled action's `dist/`), an auto-merge step that rebuilds and commits the artifact **as the App** (via `createCommitOnBranch`, so the commit is Verified and the resulting `synchronize` re-triggers required checks — a `GITHUB_TOKEN` push lands Unverified and is anti-loop-suppressed, leaving the PR stranded on stale checks), backstopped by a `built-artifact-verified` CI gate (ci-automation) so a missed rebuild fails loudly;
- a **reconciler** (scheduled + event-driven) that catches dropped events and re-drives stuck PRs.

Stand up the identity, secret stores, gating labels, and repo settings these depend on per `../../references/automation-prerequisites.md` — for a Dependabot-triggered flow the usual missing piece is **mirroring the bot/approver secret into the Dependabot secret store**, which those workflows read instead of the Actions store. Don't re-score the prerequisites here; that's the cross-cutting `automation-prereqs-provisioned` check owned by the automation-baseline capability.

On **Renovate** the equivalent is its native auto-merge — `automerge: true` with `platformAutomerge: true`, scoped by `packageRules` to patch/minor — which needs no separate approve/merge/reconcile workflows (Renovate runs its own loop), but still depends on the same prerequisites (branch protection with required checks; a bot identity if your ruleset requires a non-default approver).

This recipe instantiates the autonomy ladder at L3/L4 for Dependabot; the pr-autonomy capability owns the general ladder, the guardrail spine, and the other rungs/approaches — apply its guardrails here rather than re-deriving them. For the ordered end-to-end setup — assisted updates (flow 2) and the full autonomous flow (flow 6) — follow `../../references/automation-playbooks.md`.

## Output

Report per `../../references/output-format.md`: scan emits the dependency/supply-chain inventory with sources; audit emits severity-tagged (Scorecard-aligned) findings, the domain score, and a `scaffold` offer or the exact command for each unmet check.

## Edge cases

- **Library vs application** — a library may intentionally not commit a lockfile (it tests a range); treat `lockfile-committed` as nuanced, not an automatic fail.
- **Monorepo / multiple ecosystems** — Dependabot needs one `package-ecosystem` entry per manifest directory; a single entry under-covers.
- **Vendored dependencies** — note that vendored trees bypass the update bot; flag if they're stale.
- **`gh` unavailable** — alert/scanning settings are `unknown`; still audit on-disk config and lockfiles.

## Anti-patterns

- Don't run installs or dependency upgrades — propose config and commands.
- Don't duplicate workflow action-pinning here — that's ci-automation.
- Don't auto-merge major version bumps or security-flagged PRs unattended — gate those for human review.
- Don't treat a missing library lockfile as an automatic failure.
- Don't overwrite an existing Dependabot/Renovate config without a diff.
