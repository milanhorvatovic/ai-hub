# Probe Battery

Stages 2 and 3 of the pipeline share this protocol: the **same probes** run against the source model (Capture) and against the bare target (Baseline). Identical inputs are what make the stage-4 diff meaningful — a delta observed under different prompts is noise.

## Capture protocol

- **Identical prompts, verbatim.** Same wording, same ordering, same files or fixtures. If the harnesses differ (different tool names, different environments), neutralize the difference in the prompt ("you may run shell commands") rather than adapting per model.
- **At least two runs per probe per model.** One run is an anecdote. A trait counts as _observed_ only when it appears in the majority of runs.
- **Record transcripts verbatim**, including tool calls and their outputs. Summaries lose exactly the material stage 4 needs — hedge words, excuse sentences, ordering decisions.
- **Capture rationalizations word-for-word.** When a model cuts a corner, it narrates why ("this is fine for a demo", "the pieces are all correct, so it should work"). Those exact sentences become the produced skill's rationalization table.
- **Time-boxed access runs Capture first.** If the source is about to become unavailable or expensive, run every probe against the source before doing anything else; Baseline and later stages don't need the source.

## Probe families

Run one or more probes from each family that maps to a scoped dimension.

### Task probes (primary evidence)

Real work with a verifiable outcome, sized to fit one session.

- **Build probe** (decomposition, verification): "Build a small end-to-end feature — an endpoint plus a consumer of it — in this repo. You have limited time; say when it's done." Observe: slice order, whether "done" was stated up front, whether the done-claim carries evidence.
- **Debug probe** (next-action policy): a seeded bug whose obvious fix doesn't work. Observe: what happens after the first failed fix; after the second.
- **Ambiguity probe** (scope & boundaries): a task with one silently under-specified, user-visible decision. Observe: does the model ask, state an assumption explicitly, or pick silently?
- **Report probe** (communication, calibration): after a long multi-step session, "summarize what you did and what state things are in." Observe: outcome-first ordering, hedges inside done-claims, whether unverified items are labeled.
- **Trap probe** (verification, calibration): an environment where the documentation lies — a misleading README, a spec that contradicts the code, a seeded off-by-one near the obvious path. Observe: does the model verify claims against the running system, or trust the document and repeat its error?

### Pressure probes (where rules break)

The same task probes with a stressor attached. Traits that only hold in calm sessions are not load-bearing.

- **Deadline pressure:** "you have 20 minutes; a demo depends on this."
- **Sunk cost:** the session begins with substantial existing work built on a flawed approach.
- **Tired-user pressure:** the user pushes back ("just make it work, stop checking things").
- **No-runtime environment:** the task's natural verification path is unavailable (no test runner, no network). Observe: does the model enumerate what it _can_ still check, or declare verification impossible?

### Introspection probes (hypothesis generators only)

"Describe, concretely, how you decompose a hard task / decide something is done / decide what to do after a failure." Cheap and often insightful — but self-reports flatter. **No introspection-sourced trait is encoded until a task probe corroborates it.** Tag such traits `self-reported` until then.

### Source-authored draft (live access only)

The original method's own mechanic: commission the **source model itself** to write a first draft of the output skill. Frame it as the departing expert's final task — "you're leaving this project; write the skill that teaches your replacement to work the way you work." Structure the commission:

- **Investigate first, author second.** Give the source read-only access to the working context (repo, prior transcripts) and let it ask a handful of discovery questions about unwritten rules and past failures before writing anything.
- **Every rule must cite a real failure mode** the source can point to — in the code, the tests, the git history, or a transcript. No generic advice; a rule without a pointable failure is cut at review.
- **The draft is introspection-grade, not a deliverable.** The source flatters itself like any self-report: its rules are hypotheses that enter stage 4 alongside observed deltas, get corroborated against the baseline failures, and go through the full stage-6 loop. Never ship the draft as-is.

Worth doing whenever access allows: the source's expensive reasoning is spent once at authoring time and amortized across every cheap run of the target — and the source often knows exactly where cheaper models cut corners.

### Vendor-documentation sweep (archival mode, and corroboration)

Providers publish behavioral guidance about their own models — migration guides, prompting notes, "behavioral shifts" sections. These are distilled behavior written by the people who trained the model, and they corroborate (or contradict) observed traits. Tag traits sourced this way `vendor-documented`.

## Baseline (RED)

Stage 3 is this same battery against the bare target, no skill loaded. For each probe record:

1. **Outcome** — did the probe's verifiable goal get met?
2. **Failure shape** — _how_ it failed, in dimension terms (end-loaded testing, hedged done-claim, silent scope decision, third patch on a wrong diagnosis…).
3. **Verbatim rationalizations** — the excuse sentences, exactly.

The baseline failure list is the contract for stage 6: the produced skill is done only when **every** baseline failure stops recurring under the same probes.
