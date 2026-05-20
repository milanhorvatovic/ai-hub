# PR autonomy ladder

The model behind the `pr-autonomy` capability. Each rung adds capability *and* a
matching set of guardrails. Move one rung at a time; never adopt a rung whose
guardrails aren't in place.

## Rungs

### L0 — Manual
A human opens, reviews, and merges every PR. No automation.
- **Prerequisites:** none.
- **When:** tiny/experimental repos; highest-trust changes.

### L1 — Assisted
Bots/tools *open* PRs (Dependabot, release-please); CI runs on every PR. A human
still reviews and merges each one.
- **Prerequisites:** CI on `pull_request`.
- **Guardrails:** required checks visible (even if not enforced yet).
- **When:** the baseline for any active repo.

### L2 — Auto-approve
Automation *approves* eligible PRs so they satisfy required review; a human (or
L3) still merges.
- **Prerequisites:** a least-privilege **App token** (the default `GITHUB_TOKEN`
  cannot approve PRs); an **eligibility gate**.
- **Guardrails:** eligibility gate, hard stops, scoped identity.
- **Approaches:** App-token `gh pr review --approve`; a dedicated approval Action.
- **Risk:** approval without merge gating can normalize rubber-stamping — pair
  with required checks so approval alone never lands a change.

### L3 — Auto-merge
Eligible PRs *merge themselves* once required checks pass.
- **Prerequisites:** **branch protection** with **required status checks**;
  auto-merge enabled on the repo; an update-type/path gate.
- **Guardrails:** all of L2 + required-checks-are-the-gate.
- **Approaches:** native `gh pr merge --auto` (+ branch protection); third-party
  mergers (**Mergify** `.mergify.yml`, **Kodiak** `.kodiak.toml`) that queue and
  merge on green.
- **Risk:** a too-broad eligibility gate merges things no one looked at — keep it
  narrow (e.g. patch/minor deps, docs-only).

### L4 — Full autonomous flow
End-to-end with no human on the safe path: open → label → approve → merge →
reconcile, and optionally → release. Humans handle only gated exceptions.
- **Prerequisites:** all of L3 + a **reconciler**, **observability**, and an
  **escape hatch**.
- **Guardrails:** the full spine below.
- **Approaches:** the autonomous Dependabot flow (see the dependency-supply-chain
  capability) for deps; release-please/semantic-release for autonomous releases.
- **Risk:** silent failure — without a reconciler and alerting, dropped events
  leave PRs stuck or, worse, an unsafe change slips a weak gate.

## Guardrail spine (scale these with the rung)

| Guardrail | L2 | L3 | L4 |
|---|---|---|---|
| Eligibility gate (who qualifies) | ✅ | ✅ | ✅ |
| Hard stops (major / security / breaking / CI-touching → human) | ✅ | ✅ | ✅ |
| Scoped App-token identity (least privilege) | ✅ | ✅ | ✅ |
| Required checks are the merge gate | — | ✅ | ✅ |
| Reconciler / scheduled catch-up | — | optional | ✅ |
| Observability / alerting on autonomous actions | — | optional | ✅ |
| Escape hatch (one-switch disable, auto-disable on security review) | optional | ✅ | ✅ |

## Choosing a target rung

- Match autonomy to **risk × volume**: high PR volume + low blast radius (deps,
  docs) → push toward L3/L4; security-critical or infra repos → cap lower or
  restrict the eligibility set.
- Solo repos can run L3/L4 to cut toil, but keep the hard stops — there's no
  second reviewer.
- It's legitimate to run **different rungs for different PR classes** in one repo
  (e.g. L4 for patch deps, L1 for everything else).
