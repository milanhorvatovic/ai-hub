# Refactoring — industry conventions

Language-agnostic practices for *safely moving existing code* toward the structure the rest of this skill describes. The skill says what good code looks like; this file is how you get bad code there without breaking it. Load when the task is to restructure, clean up, or modernize existing code. Fowler's *Refactoring* is the canon.

Definition: **refactoring changes structure, not behavior.** If behavior changes, it's not a refactor — it's a feature or a fix, and it needs its own tests and review.

## The safety net comes first

- **Refactor only under green tests.** Tests are what let you change structure confidently. No tests = no safety net = you're not refactoring, you're rewriting and hoping.
- **Legacy code with no tests** → write **characterization tests** first: tests that pin the *current* behavior (even if it's weird), so you'll notice if your refactor changes it. Don't "fix" the weird behavior in the same step — characterize, refactor, *then* decide whether to change behavior (separately).
- **Tests stay green between every step.** If they go red, the last step broke something — revert it, take a smaller step.

## Small reversible steps

- Refactor in **small steps**, running tests after each. A big-bang restructure that's red for an hour is a debugging session, not a refactor.
- **Commit frequently** — each green step is a safe point to return to.
- Use **automated refactorings** (IDE rename, extract function/variable, inline, move) where available — they're mechanically correct in ways manual edits aren't.

## Two hats (Beck)

You're either **refactoring** (changing structure, tests stay green, no behavior change) or **adding behavior** (new tests, new functionality). Never both in the same commit — it makes review impossible and bisection useless (principle 1: match scope to the request; mantra readability first: a mixed commit hides the behavior change in the noise of the restructure).

> "Make the change easy, then make the easy change." — first refactor so the new feature *fits*, commit that, then add the feature.

## Patterns for change at scale

- **Parallel change / expand-contract** (you have this for DB migrations in `persistence.md` — it generalizes to APIs, function signatures, schemas, config):
  1. **Expand** — add the new form alongside the old (new param with a default, new field, new function).
  2. **Migrate** — move callers/consumers to the new form, incrementally.
  3. **Contract** — remove the old form once nothing uses it.
  This keeps every intermediate state working — essential when consumers deploy independently or you can't change all callers at once.
- **Branch by abstraction** — introduce an abstraction over the thing you're replacing, move callers to the abstraction, swap the implementation behind it, remove the abstraction if it was only scaffolding. For replacing a library/subsystem without a long-lived branch.
- **Strangler fig** — for replacing a large system: wrap the old, route a slice of traffic/functionality to the new implementation, grow the new until the old is dead, then delete the old. Incremental, reversible, never a risky cutover.

## When to refactor

- **Before adding a feature** that's awkward in the current structure (make the change easy).
- **When you touch confusing code** and understand it — leave it clearer (bounded — see below).
- **When duplication reaches the threshold** (DRY mantra: the third occurrence, not the second).
- **When tests are hard to write** — that's the design telling you the structure is wrong (testability mantra).

## When NOT to refactor

- **No tests and no time to add characterization tests** — refactoring blind is how you ship regressions. Add the safety net or don't touch it.
- **Speculatively** — don't refactor toward a flexibility nobody needs yet (principle 4 / YAGNI). Refactor for the change in front of you.
- **Mixed into a feature/fix PR** — scope creep (principle 1). The "while I'm here" refactor balloons the diff and hides the real change. Separate PR.
- **Pure churn** — renaming things to your preference when the existing name is fine and consistent (principle 9: file-local consistency wins).

## Refactor vs rewrite

- **Refactor** (incremental, under tests, always-working) is the default and far lower-risk.
- **Rewrite** (throw away, rebuild) loses accumulated bug fixes and domain knowledge, and the new thing is usually late and buggy. Reserve for genuinely dead-end designs, and even then prefer **strangler fig** (incremental rewrite) over big-bang.

## Principle alignment

- **Principle 1** (match scope) — refactoring and behavior change are separate scopes; don't mix.
- **Principle 2** (root cause) — characterization tests pin behavior before you change structure.
- **Principle 4 / YAGNI** — refactor for the present need, not speculative flexibility.
- **Principle 9** — match file-local conventions; don't refactor for personal taste.
- **Testability + pure/impure mantras** — "hard to test" is the signal to refactor; the target is a pure core with I/O at the edges.
- **Scalability mantra** — expand-contract and strangler-fig are how you *add/replace* without a risky rewrite.
- Pairs with a separate post-edit cleanup pass and this skill's **review** capability (which flags refactor-worthy smells via `smells.md`).
