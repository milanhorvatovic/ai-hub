# Diagnosis grading

Every audit finding carries a grade. The vocabulary is small on purpose, and all of it is advisory.

## The grades

| Grade | Means | Example |
| --- | --- | --- |
| `gap` | A floor row nothing satisfies | No linter configured for a language the repo contains |
| `wiring` | Declared, and the execution does not cover what it claims to — nothing runs it, or what runs cannot fail, or it reaches only part of the code | `ruff` configured in `pyproject.toml` with no CI job calling it; `clippy` run over a workspace whose members it does not reach |
| `conflict` | Two declarations that cannot both be honored | `prettier` and `biome` both formatting the same files |
| `drift` | The same fact declared twice, differently | Language version pinned in CI and floated in the manifest |
| `floating` | Running, at whatever version resolved today | `pip install ruff` in CI with no version constraint |
| `unknown` | Detection could not reach the answer | CI calls a task runner whose config the scan could not read |
| `decision` | A floor row the repo has deliberately declined | An explicit lower language pin, with the pin cited |

`wiring` covers absence and partial reach alike, which is deliberate: a linter nothing calls and a linter called over half the repository are the same defect from a reader's side — the report says the tool is set up, and the code it was set up for goes unchecked. The finding always names which part is uncovered, so the two are not confusable in a report even though they share a grade.

`floating` is separate from `gap` because the tool is there and working: the floor row is satisfied, and what is unfixed is which version satisfies it. The cost lands somewhere else entirely — on an unrelated pull request, on the morning the linter releases a new rule, as a red build nobody's change caused. That is the failure that teaches a team to reach for `continue-on-error`, and a check that cannot fail is worth less than the one they started with.

A repository that floats deliberately, to catch upstream changes early, has chosen the trade rather than missed it — and it still grades `floating`, because a grade describes the repository's state and not the intent behind it. The version is unfixed either way and the red build on an unrelated pull request arrives either way; what the choice changes is the prescription, which for a deliberate float is to say the lever exists rather than to recommend pulling it. Record the choice and its citation beside the finding.

`decision` can look like that same judgement applied to a different row, and the difference is where the intent lives. A declined floor row carries its own evidence — a pin written down, a tool named instead of the floor's — so the grade points at a declaration rather than at an inference about what someone meant, and it exists at all because a declined row would otherwise vanish from a report that lists only what it found. Version fixity has neither half of that: no declaration to point at, and no floor row to vanish from, since `modes.md` grades it on its own axis against no table this file carries. An unfixed version is `floating` and the choice is a note.

**`decision` requires a declined floor row, not merely a deliberate choice.** The two are easy to conflate and the difference decides whether a finding exists at all: a repository that pins an older interpreter has declined a row and earns the grade, while one that selects a narrower lint rule set, documents a suppression, or declares the minimum version the floor asked it to declare has satisfied its rows and earns nothing. Grading the second kind fills a report with entries for a repository that did what was asked, which is how a reader learns to skim the section. Where a choice is worth mentioning and no row was declined, it belongs in the scan's facts rather than the audit's findings.

`decision` is a grade rather than a silence so the report stays complete: a maintainer reading it should see every floor row accounted for, including the ones they themselves opted out of, because a row that simply vanishes reads as a row nobody checked.

`unknown` is a grade rather than an absence for the sharper version of the same reason. A tool the scan could not reach and a tool the repository does not have look identical in a report that only lists what it found, and the two call for opposite responses.

## Everything here is advisory

No grade in this vocabulary blocks, fails, or gates. A missing linter is a gap in a repository's setup, not an unmitigated risk to anyone, and this skill does not have the standing to decide that a project must adopt a tool. What it has is a floor worth arguing for, evidence about where a repository sits relative to it, and a concrete next step.

That posture has a cost worth stating plainly rather than hiding: when a finding _is_ serious — a repository shipping shell scripts nothing has ever linted, a type checker configured and silently skipped for a year — the report says so in the same register as everything else. The compensation is the prescription and the evidence, not an escalated severity. A reader who can see the exact file, the exact missing step, and the exact command that would prove it is better served than one handed a red label.

The one thing the audit states in stronger terms is a contradiction: `conflict` and `drift` findings describe a repository disagreeing with itself, and the fix is not adoption of anything new but resolution of something already chosen twice. Those are worth leading a report with, because they cost a team time today rather than in principle.

## Finding shape

Each finding names, in this order: the grade, the floor row or contradiction it concerns, the evidence with its file citation, and the prescription.

```text
gap · python types — no type checker declared
  Evidence: pyproject.toml declares [tool.ruff] and no [tool.mypy]; no mypy.ini, no pyrightconfig.json.
  Prescription: add mypy to pyproject.toml and a CI step that runs it over the package.
  Alternatives: pyright satisfies this row equally; pick whichever the team already reads output from.
```

The alternatives line appears whenever the floor row genuinely admits more than one tool, and is omitted when it does not — offering a choice where none exists is as unhelpful as withholding one where it does. Where the repository already uses one of the alternatives elsewhere, name that as the recommendation and say why: consistency inside a repository beats the doctor's preference between two equivalent tools.

## What is never a finding

- A tool above the floor that the repository has chosen not to adopt.
- A rule the repository has disabled with an explanation.
- A style choice the floor does not speak to — line length, quote style, import ordering.
- The code the tools would complain about. This skill audits whether tooling is set up, not what it would find.
