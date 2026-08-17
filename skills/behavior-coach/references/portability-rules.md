# Portability Rules

Stage 5: author the output skill from the stage-4 delta table — rules from the table and from nothing else, framing sections from the recorded pipeline metadata (the stage-1 scope block for the honest-limits note, the source model and probe dates for the colophon), and no behavioral material that never passed classification. These rules exist so the produced skill runs on _almost any_ capable instruction-following model, not just the pair it was developed on.

## Structure of the produced skill

A standalone skill directory conforming to the Agent Skills spec:

- `SKILL.md` with valid frontmatter: `name` matches the directory (lowercase + hyphens, ≤ 64 chars) — prefer a gerund activity name that says what the target will be _doing_ (`shipping-verified-work`, not `verification-rules`); `description` ≤ 1024 chars, third-person, written around the **moments the rules fire at** ("use when about to report completion, when picking the next action after a failure or surprise…"), not around topics; body inside the spec's progressive-disclosure guidance — under 500 lines and roughly 5,000 tokens, longer material moved to references.
- Body sections, in rough order: a one-paragraph core principle; the rules grouped by dimension; the rationalization table; the red-flags list; the honest-limits note.
- When the deltas form a cycle (plan → act → check → report), present them as an **explicit decision loop** — numbered stations with pass/fail and surprise gates, loop-backs, and a done-observation gate at the exit — rather than a flat rule list. For multi-step workflows, a copyable progress checklist the target ticks off beats prose.
- References only if a section genuinely exceeds router budget — a distilled behavior skill should usually be a single file.

## Writing rules that transfer

1. **One rule per delta, stated as an observable.** The compliance question must be answerable by reading the transcript. "Verify your work" fails the test; "a claim counts as verified only when the observation that could have falsified it is pasted inline — secrets redacted — produced after the last edit" passes. Every rule must also name the recorded failure it counters — no generic advice; a rule without a pointable failure is dead-weight-critic bait.
2. **Put the decision procedure at the decision point.** Rules fire at moments — after a checkpoint, before a done-claim, on a surprise. Structure the skill around those moments ("after every checkpoint: …", "before reporting done: …") rather than around virtues.
3. **Mechanical triggers for every PARTIAL delta.** Counts, comparisons against written expectations, and pasted-evidence requirements substitute for the judgment the target lacks. If the trigger can be negotiated with ("I basically checked it"), tighten it until it can't.
4. **Counter the recorded rationalizations by name.** A two-column table — the baseline's verbatim excuse, the reality — is the cheapest defense that works: under pressure the target produces those exact sentences, and a skill that quotes them back breaks the pattern.
5. **Red flags as pattern-matchable text.** Give the target signals it can grep its own draft for: a hedge word inside a done-claim, a "Verified" line with nothing pasted under it, a plan whose testing is all in the final phase.
6. **Model-agnostic and harness-agnostic wording.** No vendor names, no harness-specific tool names in rules — "run a command and paste its redacted output", not "use the Bash tool". The produced skill must read the same loaded into any agent harness.
7. **Match freedom to fragility.** Fragile moments (claiming done, destructive actions) get low-freedom, exact-procedure rules. Flexible moments (how to explore, what to read first) stay high-freedom or unmentioned — over-constraining them makes the skill brittle on tasks unlike the probes. Pair each low-freedom rule with its reason — the reason is what lets the target generalize to situations the probes never covered; a bare imperative covers only the cases it names.
8. **Behavior, not vocabulary.** Instruct the produced skill's user-facing output to stay in plain engineering language — the target must not announce skill compliance or leak the skill's internal vocabulary into replies. Inside the skill itself, keep terminology consistent: one term per concept throughout — synonyms read as distinctions.
9. **The honest-limits note is mandatory.** Two or three sentences, from the NON-PORTABLE rows: what this skill does not transfer (e.g. reasoning depth, long-horizon coherence, domain knowledge), so users calibrate expectations. Include the stage-1 scope block's dimension list — what was in scope, therefore what wasn't.

## Size discipline

The produced skill competes for the target's attention with the task itself, and the cost is measurable — independent replications of this method observed roughly 7% added token cost per loaded skill. Budget: **the rules a pressured model will actually re-read** — in practice well under the 500-line spec ceiling; the strongest observed exemplars run 60–90 lines. Every line that re-teaches baseline behavior costs compliance with the lines that don't (the dead-weight critic in stage 6 enforces this empirically).

## Licensing and attribution

The produced skill must be an original instruction text authored from observations, and originality is an authoring rule, not an automatic property — the pipeline holds verbatim source transcripts and possibly a source-authored draft, so write every surviving rule in your own words and copy no sentence from either into the deliverable. (The rationalization table's verbatim quotes are the target's baseline excuses, not source output.) The result carries no source-model weights, outputs, or proprietary prompt text. Note the source model, probe date, and provenance tags in a short colophon (commented frontmatter or a trailing section) so future maintainers know what it was distilled from and when it may have gone stale.
