# Language capabilities — when to add one

The Capabilities section invites expansion — _propose a new capability if the language recurs_ — and this file is what "recurs" means and what saying yes costs. Load it when an uncovered language keeps turning up, or when you are about to write a capability for one. It governs promotion only; how an uncovered language is handled in the meantime is the last section here.

## When a language earns one

**Three distinct tasks in the same uncovered language, across different sessions or different people.** One task is a visit, two is a coincidence, three is a language this skill is being asked to have an opinion about. What never counts toward it: one-off scripts, generated or vendored code, a file opened only to delete it, and a single task that touches forty files of one language — the signal is repeated demand, not volume.

The count is of _live_ demand: if the first two sightings are a year stale the language did not recur, it appeared twice and stopped, and the count starts over.

Nothing tracks this automatically, so the threshold is a judgment made at the third sighting and the thing that makes it real is a proposal naming the three tasks. That proposal is a ticket rather than a pull request, because the bill below is worth agreeing before anyone pays it.

## What a new capability ships

A language capability is not one file, and most of what follows is asserted by a test in the repo that hosts this skill — a capability missing a required file fails on its first run rather than shipping incomplete and being noticed a release later. Where an item rests on convention rather than on a check, it says so, because a list mixing what is enforced with what is hoped for is worth less than the same list marking which is which.

Some of it also reaches outside the skill directory: a repo packaging several skills may keep a manifest naming their capabilities, and the activation corpus behind the description is a repo-level artifact too. The contracts that enforce the items below can carry their own declaration as well — a list of the languages they cover, kept beside the tests rather than in the skill, which a new language joins or the contracts never enroll it and pass without checking anything. Its contributor docs own that list, so read them rather than assuming the skill directory is the whole job.

- **A row in the Capabilities table, and a place in the frontmatter description.** The row is what makes the capability exist at all: a directory nobody routes fails, and so does a row pointing at a directory that is not there. That the description then names the new language is **convention rather than a check** — nothing fails if it is missed, and the skill goes on advertising one language fewer than it ships. Editing it is the expensive half regardless: a repo that scores its descriptions against an activation corpus holds the new wording to it, so budget re-reviewing that corpus as part of adding the language rather than meeting it at review time.
- **`capability.md`**, the entry point that routes to the references and summarizes them. It carries no currency stamp of its own; it inherits what the references state, and a second date could only drift from the first.
- **The same seven reference files every other language carries** — `anti-patterns.md`, `examples.md`, `best-practices.md`, `concurrency.md`, `dependencies.md`, `performance.md`, `project-structure.md`. Parity is enforced, so six files is a failing test rather than a gap.
- **A pointer line for every example it ships.** Those lines live in `principles.md`, in the `> **Code examples**` blockquote under each principle, so a new language edits a shared reference on its first day — that part is neither optional nor judgment. The contract runs both ways: a language named on principle N's line must carry a matching `## Principle N` heading in its own `examples.md`, and a heading nobody points at fails just as loudly, because an example nothing routes to is invisible drift. The grammar is language-neutral by design, so this is filling in a shape rather than inventing one.
- **A currency stamp on the five that decay** — the seven above minus `anti-patterns.md`, which is language semantics, and `examples.md`, which is code — per the Currency rule the router states. Five files to re-verify is the standing cost of a language, and weighing it belongs at the threshold rather than at the first sweep that finds them stale.
- **Threading into the concern references wherever the language genuinely differs, and nowhere else — the judgment call, and the one item here no check could settle even in principle.** The description rule above is merely unchecked, and a test could take it tomorrow; this one is uncheckable, because "genuinely differs" is the whole question. The pointer lines are the enforced half of touching shared material; this is the other half, and it covers the concern files the router lists rather than `principles.md`. What is enforced even here is the direction: a shared reference names the language in prose where its mechanics diverge and never points into the capability, per the router's reference-direction rule. Where the threading belongs is left to whoever adds the language, so a new language is not a licence to sprinkle its name through files that were language-agnostic before it arrived.
- **A fence syntax check when — and only when — the language parses with a toolchain the host repo's CI already installs for another reason.** Otherwise the language ships unchecked, deliberately: a compiler pulled in for a few dozen samples is a slow job and a dependency to keep alive, and checking fragments needs a heuristic that wraps each snippet into something compilable, whose false failures cost more trust than the gap costs. Deciding it by that rule settles every future language at once; the host repo states which side each language currently falls on, and that statement is the one place the answer lives.

## Candidates

Go, Java, Swift, Ruby, and C/C++ — the languages the Capabilities section names as uncovered.

This is a list of names and deliberately not a scoreboard. Where each one stands against the threshold is a running count, and a shipped file is a poor ledger for one: every sighting would edit the skill, consumers would install somebody else's tally, and the number would rot between edits with nothing to catch it. Status lives in the host repo's issue tracker instead, one proposal per language.

## Until a language has one

An uncovered language runs on the core — the mantras, the numbered principles, and the repo's own declared conventions, on the precedence the router already states for the two. A capability adds language mechanics; it never adds a second rulebook, which is why not having one costs less than the gap looks like it should. Where the distinction matters to a review, say which language is uncovered and review against the core.
