# Behavioral Dimensions

Stage 1 of the pipeline: decide _what_ to distill before touching a probe. A dimension is a facet of working behavior that can be observed in transcripts, diffed between models, and encoded as rules. Pick **2–4 dimensions per distillation pass** — each dimension needs its own probe → baseline → extract cycle, and a skill that tries to encode all of them at once becomes a lecture the target model skims.

## The dimension catalog

| Dimension | What it covers | Example observable |
| --- | --- | --- |
| **Decomposition** | How a multi-step task is split, ordered, and scoped before work starts | Does the plan state what "done" looks like as a checkable observation? Is the first build target an end-to-end slice or an isolated layer? |
| **Verification** | What counts as evidence for a claim; how done/works claims are classified and backed | Are command outputs pasted under claims? Do hedges ("should work") appear inside done-claims? |
| **Next-action policy** | How results, failures, and surprises change the plan | After a failed check: debug now, or proceed anyway? After two failed fixes: re-derive the diagnosis, or patch a third time? |
| **Communication** | How outcomes, failures, and uncertainty are reported to the user | Does the summary lead with the outcome? Are failures stated plainly or buried? Is the final message readable without having watched the work? |
| **Scope & boundaries** | When to proceed autonomously, when to stop, when to ask | Are reversible in-scope actions taken without permission-asking? Are destructive or scope-changing actions gated? Does a "what do you think about X?" question get an assessment or an unrequested edit? |
| **Calibration** | How confidence is expressed and adjusted against evidence | Are uncertain claims labeled as such? Does stated confidence move when evidence contradicts it? |
| **Delegation & memory** | How work is split across helpers/sub-processes and how learnings persist | Is independent work parallelized? Are corrections written somewhere durable, in a consistent format? |

Domain-specific distillations (e.g. "how the source reviews code" or "how the source writes analyses") reuse the same catalog scoped to that domain — the dimensions are facets of _any_ working session, not of a task type. The narrowest and often highest-yield scope is **project-scoped**: distill how the source works _on one repository_, anchoring every rule to that repo's observable failure modes (its code, tests, and git history); the produced skill then travels with the project rather than with a model.

## Choosing dimensions

1. **Ask what made the source's output feel sharper.** The user usually knows: "it never claimed things worked when they didn't" → verification; "its plans didn't collapse mid-task" → decomposition + next-action policy.
2. **Prefer dimensions where the target visibly fails today.** A dimension where the target is already adequate produces empty deltas in stage 4 — cheap to confirm, wasteful to probe deeply.
3. **Pair naturally coupled dimensions.** Decomposition without next-action policy produces plans nobody re-derives; verification without communication produces evidence nobody reports.

## Recording the scope decision

Write the scope down before capturing anything, so later stages can't silently drift:

```text
SOURCE:     <model, access mode: live | archival>
TARGET(S):  <model(s) the output skill must work on>
ACCESS:     <per model: direct invocation (subagent / API) | manual handoff (operator runs the probe packet)>
DIMENSIONS: <2–4 from the catalog>
DOMAIN:     <general execution | domain-scoped, e.g. code review | project-scoped, one repo>
DEADLINE:   <if source access is time-boxed, the cutoff — Capture runs first>
```

The scope block travels with the distillation artifacts and is quoted in the produced skill's honest-limits note (what was in scope, therefore what wasn't).
