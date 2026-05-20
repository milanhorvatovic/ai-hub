---
name: coding-principles-review
description: >
  Review-mode capability of the coding-principles skill. Loaded when the
  task is to review an existing diff, PR, branch, or specific change
  rather than author new code. Frames the parent skill as a
  find-violations lens (instead of avoid-violations): scan the diff, tag each
  finding with a principle number and severity (must / should / could),
  triage by severity, phrase findings as observations + suggestions, and
  emit a structured report. Covers what to flag, what to skip
  (formatter-handled style nits, file-local-consistency conflicts,
  generated code), output format, and review-specific anti-patterns
  (lecturing, stacking coulds, inventing findings).
allowed-tools: Read Grep
---

# Review capability

How to apply the parent `coding-principles` skill to a diff or PR — *finding* violations, not *avoiding* them. Load this capability when the task is to review existing code rather than write new code.

> **Industry best practices** — Conventional Comments format with labeled prefixes (`praise:` / `nitpick:` / `suggestion:` / `question:` / `issue:` / `thought:` / `todo:` / `chore:`) and `(blocking)` / `(non-blocking)` decorators, approve-vs-request-changes decision rule, severity → label map, reviewer load discipline (~400 LOC limit per session), constructive phrasing, and review-specific anti-patterns live in `references/best-practices.md` in this directory. Load it alongside this file when phrasing review findings or judging merge gates.

## When to use this lens

- User asks to review a PR, diff, branch, or specific file change ("review this", "what do you think of these changes", "find issues in this diff").
- User invokes a review-oriented skill (`/review`, `parallel-pr-review`, etc.) and this skill is loaded alongside.
- User asks "is this ready to merge?" / "what would you change?"

Do not use this lens for:

- Writing new code (use the rest of the skill in its default write-mode).
- Asking the question of the diff yourself proactively when the user only asked for a code change. Reviewing your own diff inline is part of the write-mode checklist; this file is for reviewing *someone else's* diff on request.

## Workflow

1. **Read the diff.** Not the whole repo — the diff plus enough surrounding context (caller sites, sibling files) to judge each change. If the change is large, ask the user to focus the review or split it.
2. **Tag each finding** with a principle number and a severity (**must** / **should** / **could**) — using the severities in `../../references/principles.md`. If you spotted the smell but can't immediately name the principle, look it up in `../../references/smells.md` (catalog of observable symptoms → anchoring principle). A finding without a principle anchor is taste, not a rule; either find the anchor or drop the finding.
3. **Triage** before responding:
   - **must** findings — block merge; lead with these.
   - **should** findings — recommend; the author can push back with a reason.
   - **could** findings — mention briefly or silently skip when the surrounding code already deviates. Do not pile on coulds; that is nit-noise.
4. **Phrase findings as observations + suggestions, not commands.** "This appears to violate principle 5 — `items` is already typed `list[Item]`, so the `None` check is unreachable. Consider removing." beats "DELETE THIS."
5. **Group by file / by principle**, whichever is shorter. Do not interleave findings from ten files in flat list form.

## What to flag

Apply the full skill — every mantra and every principle is a potential finding source. The most common review-mode catches:

- **must** — secrets in logs (13), missing reproducing test for a bug fix (2), half-implementations (8), destructive ops without a guard (11), inputs not parsed at boundary when security-relevant (19), no verification ran (10).
- **should** — defensive code for impossible states (5), abstraction with one implementation (4), mock-at-internals instead of boundaries (15), `Date.now()` / `Math.random()` in business logic (16), bag-of-optionals where a sum type would work (mantras: illegal-states-unrepresentable), mutable bindings that could be `const` (mantras: immutability), silent `try/except` (mantras: fail-fast-fail-loud).
- **could** — comment restating the code (7), abbreviated names (17), commented-out blocks (20), missing structured log context (mantras: observability).

## What to skip

- **Style nits the formatter handles.** Indentation, quote style, trailing commas, line length under 120. If the project runs Prettier / Black / rustfmt, do not comment on what the formatter would fix.
- **Personal-preference renames** when the existing name is clear (see principle 9: file-local consistency wins).
- **"While I'm here…" cleanups** suggested in review — those belong in a follow-up PR, not as blocking review comments on someone else's change.
- **Principle violations that match the surrounding file's conventions.** Local consistency wins over absolute purity (principle 9). Flag the conflict at file/module level instead, not on each instance.
- **Generated code, vendored code, migrations** — out of scope; the principles apply to the generator, not its output (edge case in SKILL.md).

## Output format

For a diff review, structure the response as:

```
## Summary
One sentence: ship it / blockers exist / cleanup needed.

## Must fix (N)
- [file:line] **principle N** — what is wrong; what to do instead.

## Should fix (N)
- [file:line] **principle N** — what is wrong; what to do instead.

## Could fix (N, optional)
- [file:line] **principle N** — short.

## Observations
Anything that is not a finding — context, questions for the author, follow-up suggestions.
```

If there are zero **must** findings and the author asked "is this ready?", say yes and list the **should**s as recommendations the author can accept or push back on. Do not artificially inflate review depth — empty sections are a sign of correctness, not laziness.

## Phrasing

- **Cite the principle by number**: "principle 5 — trust internal code." This makes the recommendation auditable and lets the author look up the full prose.
- **Describe the violation in observable terms**, not in principle-jargon. Bad: "violates principle 16." Good: "`Date.now()` is called inside `createSession` — pass a clock instead so tests don't need patching."
- **Suggest a concrete change**, not just "fix this." If the suggestion is non-trivial, write the two-line code sketch.
- **One paragraph per finding**, max. Reviewers reading ten findings should not have to scroll through prose.

## Anti-patterns specific to review mode

- **Lecturing.** Cite the principle, give the fix, move on. Do not explain *why* the principle exists unless the author asks.
- **Stacking coulds.** Five trivial nits drown out one real blocker. Pick the top one or two coulds per file; drop the rest.
- **Inventing findings.** If you cannot find a principle that anchors the concern, the concern is taste. Either find the anchor or do not mention it.
- **Reviewing the whole codebase instead of the diff.** The diff is the unit. Findings about code that did not change in this PR are out of scope unless the diff introduces a *new* caller of the problem code.
- **Treating diffs from junior authors more harshly.** Severity comes from the principle, not the author. (And reviewers do not know who the author is when this skill runs.)
- **Refusing to approve over a single could.** Coulds are preferences; an author may reasonably decline them.

## Relationship to the write-mode checklist

The write-mode "while editing" checklist in SKILL.md is the same set of concerns from the author's side. Review mode is its mirror: the author asks *"am I about to violate X?"*; the reviewer asks *"did the author violate X?"*. Same rules; opposite vantage.
