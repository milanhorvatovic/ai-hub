# Diagnosis grading

Every audit finding carries a grade. The vocabulary is small on purpose, and all of it is advisory.

## The grades

| Grade | Means | Example |
| --- | --- | --- |
| `gap` | A floor row nothing satisfies | No linter configured for a language the repo contains |
| `wiring` | Declared but not running — the config exists and nothing executes it | `ruff` configured in `pyproject.toml`, no CI job calls it |
| `conflict` | Two declarations that cannot both be honored | `prettier` and `biome` both formatting the same files |
| `drift` | The same fact declared twice, differently | Language version pinned in CI and floated in the manifest |
| `unknown` | Detection could not reach the answer | CI calls a task runner whose config the scan could not read |
| `decision` | A floor row the repo has deliberately declined | An explicit lower language pin, with the pin cited |

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
