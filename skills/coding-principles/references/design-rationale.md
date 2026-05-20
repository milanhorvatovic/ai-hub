# Design rationale

Why coding-principles is shaped the way it is. Loaded on demand; the operational rules this rationale implies (severity-governs-triage, tier precedence, YAGNI-as-check) live in `../SKILL.md` and the mantra/principle references.

This skill is built for *AI agents authoring code*, not for human teams iterating toward done. The distinction shapes every choice:

- **Optimize for first-pass correctness, not iteration speed.** An AI agent with the right rules can produce correct, modular, observable code in one pass. The classic human-velocity sequencing — "make it work, then right, then fast" — is deliberately *rejected* here because it would license shipping the works-but-ugly version. Each draft is expected to be right *and* simple *and* tested.
- **Severity (must / should / could) governs triage.** When several violations exist at once, fix musts first, recommend shoulds, apply coulds silently.
- **Mantra tier (Goals > Design > Pruning) governs design conflicts.** When two principles fight, the higher tier wins. Inside a tier, siblings are case-by-case — they answer different questions and rarely conflict head-on.
- **YAGNI is a check, not a veto.** Modular shape (small functions, narrow interfaces, isolated I/O, typed boundaries) is free at write-time and earned by the current feature. Infrastructure (one-impl interfaces, plugin points, factories, configuration layers) requires evidence of need and is deferred.
- **The skill is read-only.** It shapes the Edit/Write calls that follow; it does not run linters, formatters, or refactor tools, and it leaves post-edit cleanup and repo-local style to separate passes (see "Scope boundaries" in `../SKILL.md`).

When in doubt about how a rule applies: prefer the interpretation that produces simpler, more typed, more testable, more observable code in *this* draft — not the one that anticipates future flexibility.
