---
name: pr-autonomy
description: >
  Scans, audits, and scaffolds how autonomously pull requests move to merge — the
  rung on the autonomy ladder (manual → assisted → auto-approve → auto-merge →
  full autonomous flow) and the guardrails that must scale with it (eligibility
  gate, hard stops, scoped bot identity, required-checks gate, reconciler,
  escape hatch). It owns the cross-cutting autonomy model; per-domain
  instantiations (e.g. the autonomous Dependabot flow) live in their pillar and
  reference this ladder. Governs merge-autonomy configuration and policy, not the
  review of any one PR's content. Triggers on "set up auto-merge", "auto-approve
  bot PRs", "make this fully autonomous", "how autonomous is my repo", "raise/
  lower the autonomy level", or a full-repo audit.
allowed-tools: Bash Read Grep Glob Write
---

# pr-autonomy capability

Governs how far a pull request travels toward merge without a human, and whether the guardrails for that level are in place. Reads and judges by default; writes autonomy automation only on confirmation, and _proposes_ (never applies) the settings it depends on.

## Modes

- **scan** — determine the repo's current autonomy rung and which guardrails exist.
- **audit** — judge whether the rung is appropriate to the repo's risk and fully guarded.
- **scaffold** — move up or down a rung with the matching guardrails, at the maintainer's chosen approach.

## The autonomy ladder

The full model — rungs, guardrails, and per-rung implementation approaches — lives in `references/autonomy-levels.md`. In brief:

| Level | Automated | Human role |
| --- | --- | --- |
| L0 manual | nothing | opens, reviews, merges |
| L1 assisted | bots open PRs; CI gates | reviews + merges each |
| L2 auto-approve | automation approves eligible PRs | merges / oversees |
| L3 auto-merge | eligible PRs self-merge once checks pass | sets policy, handles exceptions |
| L4 full autonomous | open → approve → merge → reconcile end-to-end | only gated exceptions |

## Guardrails (must scale with the rung)

Higher autonomy without these is reckless, not advanced:

- **Eligibility gate** — only a defined subset qualifies (bot author, patch/minor, path allowlist, size cap); never the whole PR population.
- **Hard stops** — major bumps, security-flagged PRs, breaking changes, and _human-authored_ edits to CI/release/secret paths always require a human. A dependency bot's bump of an action is a weaker case, but not because it "changes no logic" — a new SHA is new code, and the pin makes the revision immutable, not vetted. What bounds the risk is the action's **trust boundary**: an action that runs only in a read-only job with no secrets in scope can do little with a compromised revision, so its bump may be eligible at the repo's tolerance; an action that runs in a secret-bearing or write-scoped job is always a hard stop for bot updates, and the actions the policy job itself executes are barred entirely (they run from the PR head before any gate). The audit scores whether a **privileged-context** action update can reach merge without a human — not whether every workflow-file touch does.
- **Scoped identity** — least-privilege. The default `GITHUB_TOKEN` is the floor and is enough when the flow only needs a plain approval (Actions-can-approve setting on, `pull-requests: write`) and no bot event has to cascade. Move up to a **GitHub App** token when an authored event must trigger a downstream required check or for truthful bot attribution; a fine-grained PAT is the fallback, never a classic PAT. Code-owner review is a _separate_ remedy — no App can satisfy it, so it resolves to a code-owner PAT or a reshaped ruleset. Choose per `../../references/automation-identity.md`.
- **Required checks are the gate** — autonomy only ever lands a _green_ PR; branch protection enforces it. For high-traffic repos a **merge queue** (`branch-protection.md`) re-tests each PR against the latest base, removing the BEHIND-then-`update-branch` reconciliation the recipe otherwise needs.
- **Concurrency control** — serialize per-PR so an automation can't race itself (`concurrency:` with `group: …-pr-${{ github.event.pull_request.number }}`), and run the reconciler as a singleton (`cancel-in-progress: false`). Without it, overlapping `synchronize`/`labeled` events double-merge or strand PRs. Mechanism in the ci-automation capability.
- **Reconciler + observability** — a scheduled/event-driven catch-up for dropped events, _and_ failures that surface: an unrecoverable autonomous action must fail the run **red** (`exit 1` + `::error::`), not warn-and-pass, and ideally notify or open-an-issue-on-failure so a broken reconciler isn't silent. Silent failure is the failure mode autonomy is most prone to.
- **Failure postures, asymmetric by direction** — named by what the failure does to authorization, not by the ambiguous "fail open/closed" (which inverts between reliability and security usage). A step that would **grant** autonomy must _deny on failure_: an approve/arm step that can't run warns and stops, leaving the PR for a human — never grant on error. A step that **revokes** autonomy must _block on failure, loudly_: a disarm that can't confirm auto-merge is off exits red **and** the merge gate must actually hold — because a red run alone is only observable, the veto/disarm job must post an always-reporting **required** status context (and/or dismiss the approval, as the recipe does), or the PR still lands once unrelated required checks go green. Getting the direction backwards turns every transient error into either a stall (deny that should have granted) or a bypass (grant that should have blocked).
- **Held means armed, never approved** — the cleanest hard-stop mechanic: enable auto-merge on the held PR but withhold the automation's approval, so the one missing ingredient is a human's review and the merge completes itself the moment it arrives. The hold **is** the branch rules' required-approving-review — it exists only where that rule does. Where branch protection requires no review, arming is merging: leave held PRs unarmed there. The rule must also **dismiss stale approvals on push** (or require approval of the latest push) — otherwise a human approves the held PR, Dependabot rebases it, and the old approval still satisfies the rule when automation re-arms the new commit.
- **Escape hatch** — one switch to disable (a gating repo variable) that **fails safe**: unset or missing reads as _disabled_, and the automation logs the resolved switch state every run so a deliberately-off switch is distinguishable from a variable that isn't resolving. Plus reactive auto-disable: a hard-stop label applied _after_ auto-merge was armed must trigger a disarm (with the fail-closed posture above), not just block re-arming. And because a variable change fires no event, the stop procedure pairs the flip with an immediate reconciler dispatch that disarms in-flight PRs — until that pass runs, already-armed PRs still merge on green.

## Inputs & guards

- Not a git repo → stop.
- This is merge-autonomy _configuration and policy_ — not reviewing a specific PR's content (that's the change-narration domain).
- L2+ needs `gh` and a bot/App token; L3+ needs branch protection with required checks. Detect these; if absent, scaffold them as prerequisites (settings are proposed, not applied). The full provisioning surface each rung adds — bot identity, the Actions/Dependabot secret stores, gating labels, the auto-merge repo settings, and the code-owner approval identity — is catalogued in `../../references/automation-prerequisites.md` (its rung table mirrors this ladder); whether it's all in place is the cross-cutting `automation-prereqs-provisioned` check owned by the automation-baseline capability, not re-scored here.
- Never raise the rung past what the guardrails support — gate the recommendation on the prerequisites being present.

## Scan

Determine the current rung and guardrails, citing sources:

1. Auto-merge: repo `allow_auto_merge` setting (`gh api repos/{owner}/{repo} --jq .allow_auto_merge`); workflows calling `gh pr merge --auto`; third-party mergers (Mergify `.mergify.yml`, Kodiak `.kodiak.toml`).
2. Auto-approve: workflows running `gh pr review --approve` or an approval action, and the identity they use (App token vs `GITHUB_TOKEN`).
3. Gates: branch-protection required checks/reviews (`gh api .../branches/{default}/protection`); eligibility/hard-stop logic in the automation; `dependabot/fetch-metadata` update-type gating.
4. Resilience: a reconciler/scheduled catch-up; any disable/escape mechanism.

Map the findings to a rung (the highest level fully supported by its guardrails).

## Audit

Checks follow the schema in `../../references/oss-health-rubric.md` (`id` — **severity** [· scorecard: Name]. criterion. why):

- `autonomy-level-appropriate` — **could**. Pass when the rung fits the repo's risk and PR volume (a flooded repo stuck at L1 is toil; a high-blast-radius repo at L4 without gates is risk). Match autonomy to context.
- `autonomy-guardrails-complete` — **should** (when above L1). Fail when the current rung lacks a guardrail it requires (e.g. auto-merge with no required checks). Ungated autonomy merges unreviewed or red changes. (Auto-approve via the default token is not itself a gap — see `autonomy-scoped-identity`.)
- `autonomy-hard-stops` — **should** (when above L1). Fail when major/security/breaking changes, or human-authored CI/release/secret edits, can complete without a human's approval, or when a hard-stop label applied after arming can't disarm an already-armed auto-merge. (A bot's bump of an action that runs in no secret-bearing or write-scoped job is a repo risk call, not an automatic hard stop; one that runs in a privileged job always is — see the guardrail above.) Armed-but-never-approved is a compliant hold — the automation may arm these, so long as only a human review can complete them, including late.
- `autonomy-scoped-identity` — **should** (when above L1). Fail when approval/merge runs as an over-scoped PAT, or as the default token **where the flow needs what the default token can't do** — a bot action whose event must cascade to a downstream required check, or code-owner review. A minimally-scoped default token approving to satisfy a _plain_ review count (Actions-can-approve setting on, `pull-requests: write`) with no required cascade is itself the least-privilege choice and scores clean. The App is preferred for cascade and truthful attribution; **code-owner review is not an App remedy** — no App can satisfy it, so that resolves to a code-owner PAT or a reshaped ruleset (`../../references/automation-identity.md`).
- `autonomy-escape-hatch` — **could** (when above L2). Pass when there's a one-switch disable that fails safe (unset reads as off, resolved state logged), whose stop procedure also disarms in-flight PRs (a variable flip fires no event, so it must dispatch reconciliation — blocking only new arming isn't a stop), plus auto-disable on security review. Operators need a fast stop that can't be on by accident and that catches what's already armed.

## Scaffold

Per-rung snippets live in `references/scaffold-templates.md` (native auto-merge, App-token approve, eligibility gate, reconciler, escape hatch); the out-of-band prerequisites each rung needs first (identity, secret stores, labels, repo settings) are in `../../references/automation-prerequisites.md`; the ordered end-to-end flow (flow 5) is in `../../references/automation-playbooks.md`. Move **one rung at a time**, after confirmation, installing that rung's guardrails and prerequisites first:

- **→ L2 auto-approve** — mint an App token; approve only eligibility-gated PRs.
- **→ L3 auto-merge** — require branch protection + required checks (propose the settings), then enable native `gh pr merge --auto` or a third-party merger; gate by update-type/path.
- **→ L4 full autonomous** — add the reconciler, observability, and escape hatch on top of L3.

Name the **approaches** at each rung (native vs Mergify/Kodiak; bot-action vs App-token review) and let the maintainer choose; don't prescribe one. For the dependency-specific full flow, defer to the autonomous recipe in the dependency-supply-chain capability — it instantiates L3/L4 for Dependabot.

## Output

Report per `../../references/output-format.md`: scan emits the current rung + guardrail map; audit emits severity-tagged findings, the recommended target rung, and a `scaffold` offer to move (with the prerequisites it would set up first).

## Edge cases

- **Solo repo** — L3/L4 can be reasonable even solo (less toil), but keep hard stops; note the single-operator risk.
- **High-blast-radius repo** (infra, security-critical) — cap the recommended rung lower, or restrict autonomy to a narrow eligibility set.
- **`gh` / token unavailable** — report the current rung from files; mark settings-derived checks `unknown`; don't scaffold L2+ without the token.
- **Third-party merger already in use** (Mergify/Kodiak) — audit _its_ config for the same guardrails rather than proposing a parallel mechanism.

## Anti-patterns

- Don't raise the rung past what the guardrails support — prerequisites first.
- Don't auto-approve/merge with the default `GITHUB_TOKEN` or an over-scoped PAT.
- Don't auto-merge major, security-flagged, or breaking changes — hard-stop them.
- Don't apply branch protection or repo settings automatically — propose the commands.
- Don't review or merge a specific PR's content here — that's the change-narration domain.
