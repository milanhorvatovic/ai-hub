# Automation prerequisites

The out-of-band wiring an automation needs before its workflows can run at all. Workflow YAML is necessary but not sufficient: a committed auto-merge workflow silently no-ops when `allow_auto_merge` is off, a required "exactly one release label" check fails every PR when the labels don't exist, and a Dependabot-triggered flow can't read its own token when the secret lives only in the Actions store. This file is the single home for that provisioning surface — the automation capabilities (automation-baseline, ci-automation, dependency-supply-chain, release-versioning, pr-autonomy) link here instead of restating it. Everything here is **proposed as a command, never applied** (the router's "never auto-publish repo settings" principle).

`automation-identity.md` decides _which_ identity an automation acts as; this file is _how_ you stand that identity — and the rest of the wiring — up.

## The surfaces

| # | Surface | Detect | Silent failure if missing |
| --- | --- | --- | --- |
| 1 | Bot identity (App / PAT) | `gh api repos/{o}/{r}/installation` | approve / merge / push steps 403 or no-op |
| 2 | Secret & variable stores (Actions **and** Dependabot) | `gh secret list`, `gh variable list` | token unreadable in the triggering context |
| 3 | Environment-scoped secrets | `gh api repos/{o}/{r}/environments` | secret out of scope, or a per-leg approval stall |
| 4 | Gating labels the automation reads | `gh label list` | required label-check fails; hard stops can't be set |
| 5 | Repo settings (auto-merge, merge methods, default token) | `gh api repos/{o}/{r}` | `gh pr merge --auto` fails; over-privileged token |
| 6 | Code-owner approval identity | `gh api .../branches/{def}/protection` + `CODEOWNERS` | approval posts but `reviewDecision` stays `REVIEW_REQUIRED` |

## 1. Bot identity

`automation-identity.md` covers the choice (App preferred over a fine-grained PAT; never a classic PAT). To provision the chosen App: create a GitHub App with the **minimum** fine-grained permissions for its task (e.g. `contents: write` to push an artifact, `pull-requests: write` to approve/merge), install it on the repo, store its **client ID as a variable** and its **private key as a secret** (ids aren't sensitive; keys are), and mint a short-lived token **per job** with `actions/create-github-app-token` rather than storing a long-lived token. Use the App's **client ID** (`create-github-app-token`'s `client-id` input), and keep the same `AUTOMATION_CLIENT_ID` / `AUTOMATION_PRIVATE_KEY` names the scaffold snippets consume so a copy/paste setup wires up cleanly.

```bash
gh variable set AUTOMATION_CLIENT_ID --body "<client-id>"
gh secret   set AUTOMATION_PRIVATE_KEY < private-key.pem
```

**Two-App split (blast radius).** When automations span risk tiers, give each tier its own App — e.g. a lower-risk automation identity (labels, artifact pushes, branch updates) kept separate from a higher-risk release identity (tags, releases, moving the major tag) — so leaking the lower-risk key doesn't force rotating the release key. One App is fine to start; split when a single identity would otherwise hold both routine-write and release authority.

## 2. Secret & variable stores

- **Secret vs variable:** keys, tokens, and private keys are **secrets** (masked, write-only); non-sensitive ids and tuning knobs are **variables** (readable, shown in logs).
- **Actions and Dependabot are separate stores.** A workflow **triggered by Dependabot** reads only the *Dependabot* secret store; a workflow triggered by `push` / `pull_request` / `schedule` / `workflow_run` / `workflow_dispatch` reads only the *Actions* store. A secret consumed from **both** contexts must be set in **both** stores under the same name — this is the single most common reason an autonomous-Dependabot flow only half-works.

| Workflow triggered by | Reads secrets from |
| --- | --- |
| `dependabot` events | Dependabot store |
| `push` / `pull_request` / `schedule` / `workflow_run` / `workflow_dispatch` | Actions store |

```bash
gh secret set CODEOWNER_APPROVER_TOKEN                   # Actions store
gh secret set CODEOWNER_APPROVER_TOKEN --app dependabot  # Dependabot store (mirror)
```

## 3. Environment-scoped secrets

Scope a high-value credential (a model API key, a publish token) to a deployment **environment** so only jobs that declare `environment:` can read it — narrower than a repo-wide secret. Environment protection rules are covered in `branch-protection.md`.

- **Gotcha:** don't put **required reviewers** on an environment a **matrix** job enters — GitHub raises one approval prompt **per matrix leg**. Scope the secret with the environment; gate approvals elsewhere.

## 4. Gating labels

Automation that reads labels needs those labels to **exist first**, or it jams:

- **Release-level labels** (one per PR) that drive release classification and any "exactly one release label" required check.
- **Hard-stop labels** (e.g. a security-review / trust-boundary marker) that an eligibility gate keys on to force a human onto the change (the autonomy ladder's hard stops, owned by pr-autonomy).

The community-health capability owns the repo's general triage-label taxonomy; these are the automation-gating subset of it. Create the labels the workflows reference:

```bash
gh label create "release: patch" --color 0E8A16
gh label create "security-review-required" --color B60205
```

## 5. Repo settings

| Setting | Why | Propose |
| --- | --- | --- |
| `allow_auto_merge` on | `gh pr merge --auto` fails outright when off | `gh repo edit --enable-auto-merge` |
| Squash-only + delete-branch-on-merge | linear history; tidy branches | `gh repo edit --enable-squash-merge --enable-merge-commit=false --delete-branch-on-merge` |
| Default workflow token **read-only** | least privilege; elevate per job | Settings → Actions → Workflow permissions, or `gh api -X PUT repos/{o}/{r}/actions/permissions/workflow` |
| Dependabot alerts + security updates on | CVEs surface and auto-open PRs | `gh api -X PUT repos/{o}/{r}/vulnerability-alerts` |

The repo-infrastructure capability owns merge-policy / settings depth; these are the automation-relevant ones. Propose; never apply.

## 6. Code-owner approval identity

When the branch ruleset requires **code-owner review** (`branch-protection.md`, against the `CODEOWNERS` file the governance capability owns), the approving automation identity must **itself be a code-owner**. Otherwise `gh pr review --approve` exits 0 but the authoritative `reviewDecision` stays `REVIEW_REQUIRED` and nothing merges. The default `GITHUB_TOKEN` cannot approve at all, and a bot cannot approve its own PR — so an autonomous flow under code-owner rules needs a separate PAT (or App) whose identity is listed in `CODEOWNERS`.

## Prerequisites by autonomy rung

Pairs with the autonomy ladder (the pr-autonomy capability); install a rung's prerequisites before its automation.

| Rung | Adds these prerequisites |
| --- | --- |
| L1 assisted | CI on `pull_request` (no identity / secrets yet) |
| L2 auto-approve | bot identity (§1); gating labels for eligibility (§4); code-owner identity if the ruleset requires it (§6) |
| L3 auto-merge | `allow_auto_merge` + required checks (§5); the Dependabot-store mirror when the flow is Dependabot-triggered (§2) |
| L4 full autonomous | reconciler / escape-hatch wiring — a gating **variable** to disable the flow, plus any reconciler token (§1–2) |

## Checking & proposing

Read state with `gh secret list`, `gh variable list`, `gh label list`, `gh api repos/{o}/{r}/environments`, `gh api repos/{o}/{r} --jq '{auto_merge: .allow_auto_merge, squash: .allow_squash_merge}'`, and `gh api repos/{o}/{r}/installation` for the App. Mark any surface **`unknown`** when `gh` is unavailable rather than assuming it's absent. Propose every fix as a command; never apply (router principle).
