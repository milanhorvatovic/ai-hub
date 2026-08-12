# Automation identity

Which identity an automation acts as — the most consequential choice for any CI / bot / autonomy flow. It governs least privilege, whether the action can **trigger downstream workflows**, whether it can **approve PRs**, how it rotates, how it's audited, and whether its commits show as **verified**.

## The options

| Identity | Scope | Triggers downstream workflows? | Can approve PRs? | Rotation | Audited as |
| --- | --- | --- | --- | --- | --- |
| **Default `GITHUB_TOKEN`** | the workflow's repo, per-job `permissions:` | No (anti-recursion) | Only if the Actions-can-approve setting is on; never code-owner | auto, per-run | `github-actions[bot]` |
| **Fine-grained PAT** | selectable repos + scoped permissions | Yes | Yes | manual expiry | the user who created it |
| **Classic PAT** | broad (every repo the user can access) | Yes | Yes | manual | the user |
| **Custom GitHub App** | installed repos, fine-grained perms, short-lived (~1h) installation token | Yes | Yes | auto | the App's own identity |
| **Deploy key** | one repo, git read/write only | n/a (git, not API) | No | manual | the key |

## Choosing

- **Default `GITHUB_TOKEN` first** — least privilege, no secret to manage. Only reach past it for its two hard limits: it **can't approve PRs** unless the repo's "Allow GitHub Actions to create and approve pull requests" setting is on (off by default — and even on, never code-owner review), and its pushes/events **don't trigger** other workflows (a bot commit won't kick CI).
- **To trigger downstream workflows or approve PRs** (the autonomy ladder's L2+): a **GitHub App** installation token (preferred) or a tightly-scoped **fine-grained PAT**. Never a classic PAT.
- **For git-only push** (e.g. pushing built artifacts): a **deploy key** beats a PAT — no API surface.
- **Verified commits:** a GitHub App or the GitHub API (`createCommitOnBranch`) produces **verified** commits without managing signing keys; a PAT pushing over HTTPS does not (see `commit-signing.md`).

- **Attribution is part of the choice.** A review or commit is a claim about who acted. An App's actions read as the bot they are (`some-bot[bot]`), so an auditor can distinguish "a human looked at this" from "policy acted"; a PAT's actions read as the human who minted it, even when no human was in the loop. Prefer the identity whose audit trail tells the truth.

## Code-owner review and automation

When the branch rules require **code-owner review**, automation meets a hard platform edge: `CODEOWNERS` resolves to users and teams, and a GitHub App is neither — it has no user form and cannot be a team member — so **no App approval can ever satisfy the rule, in any repository**. (An organization can place a dedicated machine-user account in an owning team; a personal account has no team to even try.) A bot also can't approve its own PR. Two honest ways through, and which fits is the maintainer's call:

- **A code-owner PAT** — a fine-grained PAT belonging to a listed code owner, used by the automation to post the approval. Works everywhere; costs a standing human-shaped credential (expiry-driven rotation, leaves with its owner) and approvals that read as a human review no human performed.
- **Reshape the rule** — before paying that cost, check what the rule binds _for this repo_. With a sole maintainer, any qualifying human approval is the code owner's anyway, and maintainer PRs often merge through an admin bypass — the rule's whole binding surface can turn out to be bot PRs, where the tier gates (pr-autonomy) are the real protection. Then dropping `require_code_owner_review` while keeping the plain review count loses nothing today, and it returns cleanly when a second human gets write access: a **second ruleset** holding only the code-owner rule, with the automation App as its bypass actor — humans face it, automation doesn't, and no credential impersonates anyone. (Native auto-merge won't exercise a bypass, so an automation relying on it merges via a direct API call under this shape.)

Worked example of the second path, end to end: [ai-hub's ADR 0002](https://github.com/milanhorvatovic/ai-hub/blob/main/docs/adr/0002-automation-identity.md). Neither path is "the" answer — audit scores the _risk_ (an unrotated broad credential, an unaudited approval surface), not the choice.

## Guardrails

- Store tokens/keys as repo/org **secrets**, never in files; mint App tokens **per-job** (`actions/create-github-app-token`) so they're short-lived.
- Grant the **minimum** permissions for the task — an over-scoped automation identity is the blast radius when a workflow or dependency is compromised.
- This file is the rationale behind the autonomy ladder's `autonomy-scoped-identity` guardrail (`pr-autonomy`): approval/merge running as the default token or an over-scoped PAT fails it.
