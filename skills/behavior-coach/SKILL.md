---
name: behavior-coach
description: >
  Distills the observable working behavior of a stronger source model into a
  portable, Agent Skills-compliant skill that almost any target model can load —
  process transfers (decomposition habits, verification discipline, next-action
  policy, reporting style); raw capability does not. Runs a six-stage pipeline:
  scope the behavioral dimensions, capture source behavior with a probe battery,
  baseline the bare target, extract load-bearing deltas, author the skill under
  portability rules, and pressure-test it RED/GREEN/REFACTOR until every baseline
  failure stops recurring. Prompt-level behavior transfer only — no fine-tuning,
  no training-data generation, no system-prompt extraction. Triggers when the
  user asks to distill / clone / capture / preserve a model's behavior or
  reasoning style, "make model B work like model A", "write a skill that teaches
  a smaller model how this one works", "port this model's process before access
  changes", or via /behavior-coach.
allowed-tools: Read Write Edit Bash
metadata:
  version: "1.0.0" # x-release-please-version
---

# behavior-coach

## Purpose

A repeatable method for turning _how a strong model works_ into a skill file that survives the model. The output is a standalone, spec-compliant skill (a `SKILL.md`, optionally with references) that encodes the source model's load-bearing process — how it decomposes, verifies, decides what's next, and reports — in rules a weaker or different target model can actually follow.

The founding insight, stated by the method's earliest practitioners and confirmed under test: **a skill file does not transfer raw capability; it transfers process.** The target won't suddenly reason at the source's level, but it keeps the decomposition habits, the self-checks, and the answer structure that made the source's output sharper.

## What this skill is

A pipeline the agent executes when asked to distill one model's behavior for use in another. It produces a new skill directory as its artifact. It is delta-driven: the output encodes only what the target model _doesn't already do_ — a rule that re-teaches baseline behavior is dead weight that dilutes the rules that matter.

## Design principles

1. **Deltas, not portraits.** Never write down everything the source does. Diff the source against the bare target and encode only the differences that changed outcomes. The target model is already smart; only add process it doesn't have.
2. **Observation over self-report.** What the source model _says_ about its own process is a hypothesis; what it _does_ in a transcript is evidence. Introspection probes are allowed as cheap hypothesis generators, but no trait is encoded until a task probe corroborates it.
3. **Rules must be checkable.** "Be rigorous" transfers nothing. "Paste the command output under every works-claim, or reclassify the claim as unverified" transfers, because compliance is observable from the transcript alone.
4. **Pressure-tested before shipped.** A rule that holds in a calm session and folds under deadline pressure is not a rule. Every produced skill goes through the RED/GREEN/REFACTOR loop before it is delivered.

## The pipeline

Execute the stages in order. Each stage's reference file carries the full procedure; load it when the stage begins, not before.

| Stage | Action | Reference |
| --- | --- | --- |
| 1. Scope | Pick the source model, target model(s), and 2–4 behavioral dimensions to distill | `references/behavioral-dimensions.md` |
| 2. Capture | Run the probe battery against the source; collect verbatim transcripts | `references/probe-battery.md` |
| 3. Baseline | Run the same probes on the bare target (no skill); record failures and verbatim rationalizations — this is RED | `references/probe-battery.md` |
| 4. Extract | Diff source vs baseline per dimension; classify each delta portable / partial / non-portable | `references/delta-extraction.md` |
| 5. Author | Write the output skill from portable deltas only, under the portability rules | `references/portability-rules.md` |
| 6. Pressure-test | Re-run the baseline probes with the skill loaded (GREEN), then attack the text with three critics (REFACTOR); iterate to convergence | `references/pressure-testing.md` |

A worked end-to-end pass — distilling Claude Fable 5's execution behavior into an Opus-class target — is in `references/worked-example.md`.

## What transfers, what doesn't

| Transfers (encode it) | Does not transfer (never encode it) |
| --- | --- |
| Decomposition policy — what the source does _first_ and what it refuses to defer | Raw reasoning depth; the source solving a problem the target can't |
| Verification discipline — what counts as evidence, how claims are classified | Latent knowledge the target wasn't trained on |
| Next-action policy — how failures, surprises, and completed goals change the plan | Context-window length and long-horizon coherence |
| Output structure — how results, failures, and uncertainty are reported | Instruction-following depth itself (the skill _rides on_ the target's existing depth) |
| Scope and boundary habits — when to proceed, when to stop, when to ask | Speed, cost profile, or harness-specific tool access |

Every produced skill must carry a short **honest-limits note** naming what was _not_ transferred, so downstream users don't mistake process transfer for capability transfer.

## Operating modes

- **Live source access** (preferred): the source model is still reachable — run the full probe battery against it, and also commission a **source-authored draft** of the output skill (the probe battery describes the commission). The source's expensive reasoning is spent once at capture time and amortized across every cheap run of the target. When access is time-boxed (pricing change, deprecation, preview ending), run Capture first and completely; every other stage can happen after access ends.
- **Archival**: the source is gone or unaffordable. Substitute existing transcripts, the vendor's published behavioral and migration guidance, and community observations. Mark every trait's provenance (`observed` / `vendor-documented` / `community-reported`) in the extraction table; traits with only community provenance need corroboration from a second source before encoding.

## Output contract

The produced skill directory must contain, at minimum:

- Valid frontmatter — `name` matching its directory (lowercase + hyphens), a trigger-bearing `description` ≤ 1024 chars, body ≤ 500 lines.
- **Rules as observables** — every rule checkable from the transcript alone.
- **A rationalization table** — the baseline's verbatim excuses on the left, the counter on the right. This is the highest-leverage section: the target model will produce those exact sentences under pressure, and a rule that names the excuse defuses it.
- **A red-flags list** — self-check signals the target can pattern-match against its own draft output.
- **The honest-limits note** — what this skill does not transfer.

## Anti-patterns (in applying this skill)

- **Portrait mode.** Encoding everything admirable about the source. The output balloons, the target skims, nothing sticks. Encode deltas only.
- **Trusting introspection.** Asking the source "how do you reason?" and shipping the answer. Self-reports flatter; transcripts don't.
- **Vibes rules.** "Think deeply before acting" survives no pressure scenario. If compliance can't be judged from the transcript, rewrite or drop the rule.
- **Skipping RED.** Authoring from source transcripts without baselining the target first. You cannot know which rules are load-bearing without knowing what the target already does.
- **One skill per model pair.** The output should be model-agnostic on the target side — written against _any_ capable instruction-following model, tested on at least one. Never hardcode vendor tool names or harness specifics into the output.
- **Encoding the non-portable.** A rule like "reason for longer before answering" asks the target for capability it doesn't have; it produces stalling, not depth. Non-portable deltas go in the honest-limits note, nowhere else.

## Scope boundaries

- **Prompt-level transfer only.** This skill produces instruction files. It does not fine-tune, does not generate training datasets from a source model's outputs, and must not be used to do so — most providers' terms (including Anthropic's) prohibit using model outputs to train competing models. Behavioral emulation via loaded instructions is a different, permitted mechanism: the target model's weights never change.
- **No system-prompt extraction.** Distilling observable working behavior is not extracting a vendor's hidden system prompt or safety scaffolding, and probes attempting that are out of scope.
- **Not benchmark gaming.** The goal is transferable working process, not making a target model impersonate the source on evaluations.
- **Maintenance is out of scope.** The produced skill is versioned and maintained like any other skill by its owners; this pipeline ends at delivery of a pressure-tested v1.

## Output behavior

When invoked with a distillation request, confirm source, target(s), and dimensions (stage 1), then execute the pipeline. When invoked bare via `/behavior-coach`, respond with: _"Loaded. Which model's behavior are we distilling, and into what?"_ — nothing more.
