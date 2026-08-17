# Worked Example — Distilling Claude Fable 5

The pass that motivated this skill: in July 2026, Claude Fable 5 left standard Claude plans for pay-per-use credits ($10/$50 per MTok — double Opus 4.8), giving users a hard deadline to capture its working behavior while access was still flat-rate. The community response — "write a SKILL.md that teaches a smaller model to work the way Fable works" — is this pipeline in action. This file replays it stage by stage as the canonical illustration: a historical pass whose record ends before the full convergence contract, with stages 5–6 marking where.

## Stage 1 — Scope

```text
SOURCE:     Claude Fable 5 (live, time-boxed — flat-rate access ends 2026-07-07)
TARGET(S):  Opus-class models (developed against Claude Opus 4.8)
DIMENSIONS: decomposition, verification, next-action policy
DOMAIN:     general execution (multi-step engineering tasks)
DEADLINE:   Capture must complete before the pricing cutoff
```

Communication and scope-and-boundaries were observed as strong Fable dimensions too, but were cut from this pass — three dimensions was already the top of the budget. That cut is recorded so the honest-limits note can say so.

## Stage 2 — Capture (what Fable observably does)

Task and pressure probes against Fable, corroborated by the vendor's own published guidance — Anthropic's Fable 5 migration and prompting documentation describes several of these traits explicitly, strong provenance in archival mode; the passage-level citations the provenance gate requires live in that pass's distillation notes, which are not shipped with this file. The recurring observations:

- **Decomposition:** states what "done" looks like as a checkable observation before starting; builds the thinnest end-to-end slice through the riskiest integration path first rather than completing layers in isolation; surfaces user-visible choices as explicit decision lines instead of picking silently; runs a cheap spike before building on an unproven architecture.
- **Verification:** separates what has been _observed_ from what is merely _believed_; pastes the output that could have falsified a claim before making it; treats hedges ("should work", "once X is done") as automatic downgrades out of the verified pile; grounds progress reports in tool results from the session — vendor-documented almost verbatim ("before reporting progress, audit each claim against a tool result").
- **Next-action policy:** never proceeds past a failed check; treats a second failed fix on the same symptom as evidence the _diagnosis_ is wrong, not the patch; re-derives the remaining plan whenever an observation contradicts a plan assumption; stops when the goal's observation is verified instead of continuing into adjacent improvements.

## Stage 3 — Baseline (RED)

Six pressure scenarios against the bare Opus-class target — deadline pressure, sunk cost, tired-user pushback, no-runtime environments. The recorded failure shapes, with verbatim rationalizations:

| Failure shape | Verbatim rationalization |
| --- | --- |
| End-loaded plans — all real testing in a final phase that the deadline eats | "I'll test everything at the end, in one block" |
| Done-claims with no observation behind them | "It should work — the pieces are all correct" |
| Corner-cutting justified by the demo framing | "Fine for a demo / just get something working" |
| Verification declared impossible when the obvious path is missing | "I can't verify anything from here" |
| Building on an unproven dependency without a spike | "The rewrite costs nothing — the dependency already exists" |
| Silent selection of one of two user-visible semantics | "It's the obvious default, no need to mention it" |

## Stage 4 — Extract

Sample classified rows (the full table had ~12 portable rows):

- PORTABLE — "done" stated as an observation the user would accept, before work starts. Checkable: the plan either contains the sentence or it doesn't.
- PORTABLE — evidence-classified reporting: claims sort into _verified_ (observation pasted, produced after the last edit), _believed_, _not checked_; a hedge inside a done-claim reclassifies it automatically.
- PARTIAL → mechanical trigger found — "notices when it's chasing a wrong diagnosis" became: _count fix attempts per failing check; at two, the diagnosis is wrong — revert masking changes and re-derive from a captured failure_.
- PARTIAL → mechanical trigger found — "notices surprises" became: _a surprise is checkpoint output differing from the expectation written in the plan; any surprise forces a plan re-derivation before the next action_.
- NON-PORTABLE — many-minute single-turn coherence, always-on deep reasoning, 1M-token working context. Honest-limits note, not rules.

## Stages 5–6 — Author and pressure-test

The authored skill encoded the portable rows as decision-point rules (a plan contract, three-bucket reporting, an after-every-checkpoint procedure) sequenced into an explicit decision loop — decompose, execute the subtask that retires the most risk per minute, run the checkpoint, branch on pass and surprise, verify — with a done-observation gate at the exit, quoted the six rationalizations back in a two-column table, and closed with red flags ("a hedge inside a done/works claim", "a Verified line with nothing pasted under it"). GREEN re-ran the six scenarios with the skill loaded: all baseline failures stopped recurring. REFACTOR ran the three critics — the loophole hunter forced one tightening (weakening a checkpoint after it fails is itself a red checkpoint, reportable as a plan change); the dead-weight critic deleted every rule that merely re-taught what the bare target already did. The record stops there: the surviving artifacts document one GREEN pass and the critics' edits, not the second consecutive GREEN run, the format reviewer's outcome, or the field trial — so read stages 5–6 as an illustration of the loop rather than evidence of its completion, and hold a new pass to the full convergence contract in the pressure-testing reference, which this pass predates.

A public MIT-licensed artifact of this exact pass exists — a gerund-named execution skill carrying the pressure scenarios, rationalization table, and red flags described above, produced against Opus-class targets with model-agnostic rules.

## The honest-limits note it shipped with

> This skill transfers Fable 5's execution process — decomposition contracts, evidence-classified verification, and failure-driven re-planning — as observed in July 2026. It does not transfer reasoning depth, long-horizon coherence, or context capacity; the target will follow the same process at its own level of capability. Communication style and autonomy boundaries were out of scope for this pass.

## Independent replications

The same July-2026 window produced several independent passes of this method, and their results corroborate the pipeline's load-bearing choices:

- A six-skill pass (plan gating, adversarial verification, live-state truth, scope fencing, editing discipline, memory hygiene) validated with **blind paired grading and planted traps** — seeded off-by-one bugs, contradictory specs, misleading READMEs; each probe ran twice on the bare and skill-loaded target, judged by graders who didn't know which was which. Final score 12 wins / 0 losses / 2 ties — but only after two skills that initially tested as **pure overhead** were rewritten, and with a measured cost of roughly **7% added tokens per loaded skill**. Empirical confirmation of the dead-weight critic and the size budget.
- A **source-authored** pass framing Fable as the departing principal architect: read-only repo, discovery questions first, 10–16 skills each anchored to a real failure mode visible in the code, tests, or git history ("no generic advice"), then a three-reviewer validation (factual, doctrinal, usability). Its cost analysis is the amortization argument: one expensive authoring session on the source pays for itself across hundreds of cheap target runs.
- A nine-discipline library derived primarily from **Anthropic's own published guidance** on the behavioral differences between Fable and Opus — confirmation that the vendor-documentation sweep alone can seed a usable extraction table, with the author's honest caveat that capability gaps ("getting hard problems right on the first try") don't transfer.

The artifact above and all three passes are community-maintained work outside this repository, deliberately described without names or links: this file ships with the skill, and the decoupling rule keeps distributed text free of pointers to separately maintained artifacts. Their numbers are `community-reported` under this skill's own provenance gates — corroboration to weigh against your own pass, never verified benchmarks.
