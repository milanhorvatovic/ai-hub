# Pressure Testing

Stage 6: prove the produced skill against the same probes that defined the problem, then attack its text. The method is skill-TDD — the stage-3 baseline failures are the failing tests; the skill is done when they all pass and nothing in the text is dead weight.

## GREEN — re-run the baseline

Load the produced skill into the target and re-run **every** stage-3 probe, identically (same prompts, same fixtures, same pressure). For each probe, judge with a fresh-context evaluator — a separate session that sees only the transcript and the probe's expected observables, never the skill's authoring history. Self-grading by the authoring session is not a judgment.

Per-probe verdict:

- **PASS** — the baseline failure shape did not recur, and the probe's verifiable goal was met.
- **FAIL** — the failure recurred, or a new failure appeared. Record the transcript excerpt showing it.

A FAIL loops back: usually to stage 5 (the rule was negotiable — tighten it), sometimes to stage 4 (the delta was misclassified — a PARTIAL without a real mechanical trigger), rarely to stage 2 (the probe under-specified the pressure).

## REFACTOR — three critics

Once all probes pass, three adversarial passes over the skill _text_. Run each as a separate fresh-context session with a single mandate:

1. **Loophole hunter.** Role-plays a pressured, corner-cutting agent that has read the skill and wants to comply in letter while defecting in spirit. Mandate: find wording a motivated reader can negotiate with ("I'll weaken the checkpoint since it keeps failing", "self-review counts as an observation"). Every found loophole gets the wording tightened, then GREEN re-runs.
2. **Dead-weight critic.** Mandate: for each rule, ask whether the stage-3 baseline _already_ exhibited the behavior. Any rule not anchored to a recorded baseline failure is provisionally deleted; GREEN re-runs without it. No regression → the deletion stands. This is empirical, not editorial — the arbiter is the probe outcome, not taste.
3. **Format reviewer.** Mandate: spec compliance (frontmatter validity, name/directory match, description length and trigger quality, body ≤ 500 lines), the output-contract sections present (rationalization table, red flags, honest-limits note), and no vendor/harness-specific wording per the portability rules.

## Convergence

The skill ships when, in a single iteration:

- every probe passes on **two consecutive** GREEN runs (guards against single-run luck), and
- the loophole hunter finds nothing new, and
- the dead-weight critic's deletions all stand or all reverted with a probe-anchored justification, and
- the format reviewer is clean.

If the loop hasn't converged after roughly three full iterations, the usual cause is upstream: too many dimensions in scope (split the distillation) or PARTIAL deltas encoded without real mechanical triggers (reclassify them as non-portable and move them to the honest-limits note).

## Portability spot-check

Before delivery, run at least one GREEN probe on a **second target model** if any is available. The rules were written model-agnostic (portability rules #6); this is the cheap empirical check that they read that way. A pass is not certification for all models — note in the colophon which targets were actually tested.
