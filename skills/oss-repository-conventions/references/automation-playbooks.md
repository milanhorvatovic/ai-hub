# Automation setup playbooks

End-to-end, ordered flows for standing up each kind of repository automation — the guided path that chains the **prerequisites** (`automation-prerequisites.md`), the **artifact templates** each owning capability carries, and the **enable + verify** steps into one sequence. scaffold mode follows the relevant playbook when the request is "set up <automation>" rather than a single file; this adds no new mode — every step is still a proposed command or a file written one-confirmation-at-a-time (the router's never-auto-publish rule).

Each playbook is the same spine: **detect → prerequisites → artifacts → enable → verify → rollback**. Cite the capability that owns each artifact; don't restate its template here.

## Flow-dependency map

Later flows assume the earlier ones are in place — walk this top-down.

| Flow | Builds on | Adds |
| --- | --- | --- |
| 1. CI baseline | — | composable CI + code scanning; the gate everything else trusts |
| 2. Dependency updates (assisted) | 1 | Dependabot/Renovate opening PRs; a human merges (L1) |
| 3. CI hardening | 1 | least-privilege tokens, SHA-pins, OIDC, Scorecard |
| 4. Release automation | 1 | versioning + changelog + release artifacts |
| 5. PR autonomy | 1, 3 | auto-approve → auto-merge for an eligible PR class (L2–L3) |
| 6. Autonomous dependency updates | 1, 2, 3, 5 | the full Dependabot L3/L4 flow: label → approve → merge → reconcile |

## 1. CI baseline

Goal: every PR is built, linted, tested, and code-scanned, from composable blocks.

1. **Detect** — stack/languages (`language-support.md`); is there already a workflow on `pull_request`? If a monolith exists, propose decomposing it, don't rewrite wholesale.
2. **Prerequisites** — none beyond a git repo with Actions enabled; set the default workflow token read-only (`automation-prerequisites.md` §5).
3. **Artifacts** (automation-baseline building blocks, one confirmation each): the `setup` composite action → the thin `ci.yml` caller (`static` / `test` / `coverage` jobs) → the CodeQL workflow (skip for languages CodeQL doesn't cover).
4. **Enable** — nothing to flip; the workflows run once the files land.
5. **Verify** — push a branch / open a draft PR and confirm the jobs run and pass; for compiled languages confirm CodeQL gets a real build, not just `autobuild`.
6. **Rollback** — delete the workflow files; no settings were changed.

## 2. Dependency updates — assisted (L1)

Goal: a bot opens dependency-update PRs on a cadence; a human reviews and merges each.

1. **Detect** — package ecosystems (one entry per manifest directory); any existing `dependabot.yml` / Renovate config.
2. **Prerequisites** — Dependabot alerts + security updates on (`automation-prerequisites.md` §5); no bot identity yet (still L1).
3. **Artifacts** (dependency-supply-chain): the Dependabot config (house style — `.github/dependabot.yaml`, weekly, grouped) or a Renovate config; optionally a dependency-review CI step.
4. **Enable** — the alerts / security-updates settings (proposed `gh` commands).
5. **Verify** — confirm the first batch of update PRs opens and that CI (flow 1) runs on them.
6. **Rollback** — remove the config; PRs stop on the next cycle.

## 3. CI hardening

Goal: workflows run least-privilege, pin third-party actions, use OIDC, and report a Scorecard.

1. **Detect** — current `permissions:` blocks, `uses:` pins (moving tag vs full SHA), deploy/publish auth.
2. **Prerequisites** — for OIDC publish, a cloud/registry trust relationship configured out of band; no secrets to store.
3. **Artifacts** (ci-automation hardening patterns): default `permissions: contents: read` + per-job elevation → SHA-pin every third-party action with a `# vX.Y.Z` comment → the fork-PR safety guard (refuse fork PRs for any secret-bearing / write job; never run the PR head under `pull_request_target`) → OIDC for deploy/publish → concurrency + job timeouts → an artifact/invariant verification gate (rebuild a committed `dist/` and fail on drift) → the optional Scorecard workflow.
4. **Enable** — nothing beyond the file edits.
5. **Verify** — re-run CI; confirm jobs still pass under reduced permissions and that Scorecard uploads results.
6. **Rollback** — revert the workflow edits.

## 4. Release automation

Goal: versioning, changelog, and release artifacts are generated, not hand-maintained.

1. **Detect** — version source (manifest / tags), existing changelog and its shape, the current release process, the commit convention (release-please prefers Conventional Commits).
2. **Prerequisites** — a release identity for tagging/publishing (`automation-prerequisites.md` §1; prefer a separate, higher-risk App per the two-App split); tag protection (`branch-protection.md`); OIDC for keyless publish (§5); the code-owner approval identity if a release PR auto-merges (§6).
3. **Artifacts** (release-versioning): a Keep-a-Changelog `CHANGELOG.md` → a release-please (or semantic-release) workflow → the house `RELEASE_NOTES_TEMPLATE.md`.
4. **Enable** — store the release identity (id → variable, key → secret); set tag protection (proposed).
5. **Verify** — merge a Conventional-Commit change and confirm the version bump + changelog entry + GitHub Release + attached artifacts appear.
6. **Rollback** — disable the release workflow; leave already-published tags/releases in place (don't delete published releases).

## 5. PR autonomy — auto-approve → auto-merge (L2–L3)

Goal: an eligible PR class self-approves and merges on green, with no human on the safe path.

1. **Detect** — current rung (`pr-autonomy` scan); branch protection + required checks; the auto-merge setting; the eligible class (bot author? patch/minor? path allowlist? size cap?).
2. **Prerequisites** (in order): a scoped App identity (`automation-prerequisites.md` §1) → gating labels for eligibility + hard stops (§4) → `allow_auto_merge` on + required checks via branch protection (§5, `branch-protection.md`) → the code-owner approval identity if the ruleset requires it (§6).
3. **Artifacts** (pr-autonomy snippets): the eligibility gate + hard stops → the L2 auto-approve step (App-token `gh pr review`) → the L3 auto-merge step (`gh pr merge --auto`) → per-PR concurrency control so the flow can't race itself. For high-traffic repos consider a merge queue instead of immediate squash (`branch-protection.md`).
4. **Enable** — the settings from step 2; one rung at a time, guardrails before the rung.
5. **Verify** — open an eligible PR and confirm it's approved and auto-merges on green; open a hard-stop PR (major / security / CI-touching) and confirm it's held for a human; confirm an unrecoverable automation state fails the run **red** (not warn-and-pass) so failures surface.
6. **Rollback** — the escape hatch: flip the gating variable off; `gh pr merge --disable-auto` on open PRs.

## 6. Autonomous dependency updates — Dependabot (L3/L4)

Goal: patch/minor dependency PRs flow label → approve → merge → reconcile with no human; majors and security-flagged PRs stop for review.

1. **Detect** — flows 1, 2, 3, 5 in place; the existing Dependabot config; branch protection with required checks.
2. **Prerequisites** (the failure-prone part — `automation-prerequisites.md`): App identity (§1) → **the bot/approver secret mirrored into BOTH the Actions and Dependabot stores** (§2 — it's unreadable in Dependabot-triggered runs otherwise; this is the usual missing piece) → release + hard-stop labels (§4) → `allow_auto_merge` + required checks (§5) → the code-owner approval identity (§6).
3. **Artifacts** (dependency-supply-chain autonomous recipe): the release-label mapping → the `fetch-metadata` update-type gate (auto-merge patch/minor, hold major/security) → auto-approve + auto-merge → for built artifacts, a rebuild-and-commit-**as-App** step (`createCommitOnBranch` → Verified + re-triggers checks; a `GITHUB_TOKEN` push lands Unverified and is anti-loop-suppressed) backstopped by a `built-artifact-verified` CI gate → per-PR concurrency + a singleton reconciler (failures fail red) → an escape hatch. **On Renovate**, this whole recipe collapses to native config (`automerge: true` + `platformAutomerge: true` scoped to patch/minor) — no workflows to maintain.
4. **Enable** — all the settings plus the dual-store secrets from step 2.
5. **Verify** — let a patch PR run end to end (approved, merged, branch deleted); confirm a major/security PR is held; drop an event mid-flight and confirm the reconciler re-drives the PR; confirm a rebuilt-artifact commit lands Verified and re-runs checks.
6. **Rollback** — escape-hatch variable off; `gh pr merge --disable-auto` on open PRs; the Dependabot/Renovate config can stay (the repo drops back to L1).

## Using a playbook

- Run the **audit** first (`automation-baseline` plus the owning pillar) so the playbook starts from real gaps, not assumptions.
- Walk the steps in order; **prerequisites before artifacts** — a workflow committed before its secret / label / setting exists silently no-ops (the `automation-prereqs-provisioned` check).
- Every settings / secret / label step is a **proposed `gh` command**; every file is written one-at-a-time on confirmation. The skill never applies them for you.
- Stop at the rung/flow the repo's risk warrants — high-blast-radius repos cap lower (`pr-autonomy` edge cases).
