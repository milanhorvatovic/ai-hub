---
name: python
description: >
  Examines a Python project's tooling and prescribes what is missing — reads
  pyproject.toml, setup.cfg, tox.ini, and the standalone config files for ruff,
  mypy, and pyright; establishes whether CI actually runs them; grades the
  distance to the python floor (ruff for lint and format, mypy or pyright for
  types, a managed environment, a declared interpreter version); and scaffolds
  minimal pinned configs and CI steps on confirmation. Never installs anything.
  Triggers on "set up ruff", "do we have a type checker", "is mypy running in
  CI", "what should my pyproject declare", "pin our python version", or a
  Python repository with no lint configuration at all.
allowed-tools: Bash Read Grep Glob Write
---

# python capability

Audits a Python project's toolchain configuration. Modes and their contracts come from `../../references/modes.md`; the bar is the python section of `../../references/tooling-floors.md`; grades are `../../references/diagnosis-grading.md`.

## Where the declarations live

**Each tool's own discovery order, not one shared ranking.** The column below is ordered as the tool itself searches, and the tools disagree — a standalone file wins for `ruff` and `pyright`, while `mypy` prefers its `.ini` and reaches `pyproject.toml` only after. Reporting the first file a human would look in, rather than the first the tool would load, is how a scan cites a config that nothing reads. Where a tool has settings in more than one of its own locations, report both and name which one loses. It is a `drift` finding when the two disagree, because then the effective rule is not what the losing file says and someone edited it expecting otherwise; where they agree the lower-precedence copy is redundant rather than contradictory, and grading redundancy as a contradiction is a finding with no fix behind it.

| Tool | Config locations, highest precedence first |
| --- | --- |
| `ruff` | `.ruff.toml`, `ruff.toml`, `pyproject.toml` `[tool.ruff]` |
| `mypy` | `mypy.ini`, `.mypy.ini`, `pyproject.toml` `[tool.mypy]`, `setup.cfg` `[mypy]` — with `tox.ini` `[mypy]` read only when passed explicitly |
| `pyright` | `pyrightconfig.json`, `pyproject.toml` `[tool.pyright]` |
| interpreter version | no single owner — `pyproject.toml` `requires-python` is the project's declaration, `.python-version` and `mise.toml` bind local shells, a CI matrix binds CI, and `[tool.ruff] target-version` binds one linter's syntax rules. They are peers, and disagreement between them is the finding |
| environment | `uv.lock`, `poetry.lock`, `requirements*.txt` with a `pip-compile` header, `[tool.hatch.envs]`, `Pipfile.lock` — a project uses one, and two is the finding |

`setup.py` may carry `python_requires` as a keyword argument. Read it as a declaration when it is a literal; when it is computed, grade the version row `unknown` rather than parsing Python by eye.

## What the scan reports

Per `../../references/modes.md`, configuration and execution are separate columns. For this language the rows worth carrying are:

1. **`ruff`** — declared, and whether both jobs are configured. `ruff` linting without `ruff format` (or with a separate formatter alongside) is the shape to notice; the tool does two jobs and projects routinely adopt one.
2. **Type checker** — `mypy` or `pyright`, and what it is pointed at, resolved from the config **and** the invocation together. Neither half decides alone: a config with no `files` or `packages` is normal when CI runs `mypy src/`, and a config that names a package is still checking nothing if the CI step passes a different path. The finding is a checker whose resolved scope is empty on both halves — it passes CI having checked an empty set, and reads as coverage that does not exist.
3. **Interpreter version** — declared where, and whether the declarations agree. The CI matrix and `requires-python` disagreeing is common and quietly means the tested versions are not the supported ones.
4. **Environment management** — which tool, and whether a lock file is tracked. An untracked lock leaves dependency resolution unfixed, so it takes the grade that already means exactly that: `floating`, on the environment rather than on any one tool. Naming the registered grade is the point — an instruction to report something "gently" asks the capability to invent a severity in a skill whose grades are a closed set.
5. **Warnings-as-errors** — whether CI treats tool output as fatal. `ruff check` exits non-zero on findings by default, so this row is usually about what CI does with the exit status, not about the config.

## Audit specifics

Beyond the floor rows, three checks are worth running for this language because they produce green pipelines that check less than they appear to:

- **A type checker whose scope is empty.** Resolve the config together with the invocation, per scan row 2 — a config naming nothing is the ordinary shape when the command supplies the target. Only when both resolve to no files is this a `wiring` finding rather than a satisfied row, and the prescription names the package to point it at.
- **`ruff` rule selection that excludes the reason it was adopted.** A config selecting only `E` and `F` is `ruff` acting as `pyflakes`; that is a legitimate choice and worth surfacing as a `decision` when it looks deliberate, and as an observation when the config reads like a default nobody revisited.
- **A second formatter alongside `ruff format`.** `black` and `ruff format` in one repository is a `conflict` — they agree on most files and disagree on enough to produce a formatting war in review.
- **A CI job that installs past the environment manager.** Where the project declares one — `uv`, `poetry`, `pip-tools`, `hatch` — and CI reaches for a bare `pip install` of the tools instead, the two disagree about what the project's environment is, which is a `conflict`. It has a practical edge as well as a tidiness one: that job never installs the project or its dependencies, so a type checker hits the first third-party import and reports the environment rather than the code, and the report reads like a codebase problem.
- **Tools installed without a constraint.** A CI step reading `pip install ruff` is a `floating` finding: the linter that runs is whichever released most recently, so a new rule arrives as a red build on a pull request that did not cause it. An **exact** version constraint, a dev-dependency group resolved through a tracked lock file, or a pinned tool-installer action all fix it — any one of them is enough, and the audit says which the repository already has rather than prescribing a new mechanism. A range does not: `ruff>=0.5` resolves whichever release is current at install time, which is the same floating behaviour spelled more carefully.

The version row deserves a note on tone. A project pinned to an interpreter that no longer receives security fixes is a real fact with real consequences, and it is still graded `decision` when the pin is deliberate and cited. The report states what the pin costs; it does not escalate. Where no version is declared anywhere, that is a `gap`: nothing holds contributors to a common interpreter, and the failure shows up as a bug reproducible on one machine.

## Scaffold

Templates: `references/scaffold-templates.md` in this directory. Each is filled against what the scan found — the project's declared interpreter version, its existing rule selection, its CI shape — and written one file per confirmation per `../../references/modes.md`.

Never raise `requires-python` as a side effect of scaffolding a tool config. When a floor tool's own minimum exceeds the project's declared interpreter, say so and let the user choose; a config that silently drops support for an interpreter the project promises is a breaking change wearing a linter's clothes.
