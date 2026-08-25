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

**An explicit selector outranks discovery, and discovery is per tool.** Before reading any of the tables below, look at how the tool is actually invoked: `ruff --config`, `mypy --config-file`, and `pyright --project` all override discovery, and a scan that skipped that step would cite and grade a config the run never opens. Resolve per call site — CI and a hook can pass different ones — and fall through to discovery only where no selector is given.

Read what the selector's value **is** before treating it as a path. `ruff --config` takes either a file or an inline TOML fragment such as `lint.select=["F"]`, which sets an option and leaves discovery to supply the rest; `pyright --project` takes a file or a directory to search. A scan that assumed every value is a filename would report a working invocation as pointing at a config that does not exist, which reads as a broken repository and is a broken reading.

**Then each tool's own discovery order, not one shared ranking.** The column below is ordered as the tool itself searches, and the tools disagree — a standalone file wins for `ruff` and `pyright`, while `mypy` prefers its `.ini` and reaches `pyproject.toml` only after. Reporting the first file a human would look in, rather than the first the tool would load, is how a scan cites a config that nothing reads. The same reading applies to the environment row: a monorepo whose packages use different managers has made a choice per package, not a contradiction, and flattening the repository into one environment would invent a conflict out of its structure. A nested config in a monorepo is therefore scoping, not duplication — grading a package's own `ruff.toml` as a losing copy of the root's would report the wrong effective settings and invent a contradiction out of deliberate structure. Compare only configs competing for the same scope. Where a tool has settings in more than one location competing for one scope, report both and name which one loses. It is a `drift` finding when the two disagree, because then the effective rule is not what the losing file says and someone edited it expecting otherwise; where they agree the lower-precedence copy is redundant rather than contradictory, and grading redundancy as a contradiction is a finding with no fix behind it.

| Tool | Config locations, highest precedence first |
| --- | --- |
| `ruff` | resolved per source file, not per repository: the closest config in an ancestor directory wins, and `.ruff.toml`, `ruff.toml`, `pyproject.toml` `[tool.ruff]` rank against each other only when they sit in the **same** directory |
| `mypy` | `mypy.ini`, `.mypy.ini`, `pyproject.toml` `[tool.mypy]`, `setup.cfg` `[mypy]` — with `tox.ini` `[mypy]` read only when passed explicitly |
| `pyright` | `pyrightconfig.json`, `pyproject.toml` `[tool.pyright]` |
| interpreter version | no single owner — `pyproject.toml` `requires-python` is the project's declaration, `.python-version` and `mise.toml` bind local shells, a CI matrix binds CI, and `[tool.ruff] target-version` binds one linter's syntax rules. They are peers, and disagreement between them is the finding |
| environment | `uv.lock`, `poetry.lock`, `requirements*.txt` with a `pip-compile` header, `[tool.hatch.envs]`, `Pipfile.lock` — resolved per project root, like `ruff`'s config above: one manager per environment, and two competing for the **same** environment is the finding |

`setup.py` may carry `python_requires` as a keyword argument. Read it as a declaration when it is a literal; when it is computed, grade the version row `unknown` rather than parsing Python by eye.

## What the scan reports

Per `../../references/modes.md`, configuration and execution are separate columns. For this language the rows worth carrying are:

1. **`ruff`** — declared, and separately, which of its two jobs anything runs. The declaration does not carry that: the formatter needs no `[tool.ruff.format]` section, so an absent one means defaults rather than an unadopted formatter, and reading it as a gap would report a perfectly ordinary config — including the one this skill scaffolds — as half-configured. Adoption is a wiring question, answered by whether `ruff format --check` is invoked anywhere. Linting wired without formatting, or with a separate formatter alongside, is the shape to notice; the tool does two jobs and projects routinely adopt one.
2. **Type checker** — `mypy` or `pyright`, and the scope it resolves to, read from the config **and** the invocation together with the checker's own defaults applied. Neither half decides alone, and neither tool has the failure this row was first written against: `mypy` with no target in either place exits with an error rather than passing, and `pyright` with no `include` defaults to the project directory rather than to nothing. So the report is the effective scope, and the finding is scope **narrower than the code it appears to cover** — a checker pointed at one package in a repository holding six, which passes honestly while six-sevenths of the codebase has never been typed. Name what is outside it.

   **What this row grades is checker coverage, and it says so rather than implying more.** The floor's sentence asks for type hints on the public surface — module-level functions, class methods, dataclass fields — and that is a property of the source, which this skill does not read. A row claiming to have established it would be claiming something no scan here can see, and a row left `unknown` until an enforcement setting appears is a row the minimal scaffold can never close, which breaks the promise that a scaffolded repository re-audits clean. Both were tried on this branch; both were wrong in opposite directions.

   So the row is coverage: a checker whose effective scope reaches the code the repository ships satisfies it, and the report names the scope it verified. Whether the checker also **insists** on annotations is reported beside the row as a separate, always-advisory fact — `disallow_untyped_defs` for `mypy`, the missing-parameter and missing-return diagnostics for `pyright`, present and enabled or not — with the note that none of those is scoped to the public surface alone, so adopting one reaches every internal helper the floor explicitly leaves alone. That is a recommendation with a stated cost, offered and written on request, never a gate the audit applies on the user's behalf.

   The distinction is worth holding because it is the difference between a report that says what it checked and one that says what it wishes were true.

3. **Interpreter version** — declared where, and whether the declarations agree. The CI matrix and `requires-python` disagreeing is common and quietly means the tested versions are not the supported ones.
4. **Environment management** — which tool, and whether a lock file is tracked. An untracked lock leaves dependency resolution unfixed, so it takes the grade that already means exactly that: `floating`, on the environment rather than on any one tool. Naming the registered grade is the point — an instruction to report something "gently" asks the capability to invent a severity in a skill whose grades are a closed set.
5. **Warnings-as-errors** — whether CI treats tool output as fatal. `ruff check` exits non-zero on findings by default, so this row is usually about what CI does with the exit status, not about the config.

## Audit specifics

Beyond the floor rows, three checks are worth running for this language because they produce green pipelines that check less than they appear to:

- **A type checker covering less than it appears to.** Resolve the effective scope per scan row 2, then compare it against the package layout: a `wiring` finding is one whose scope omits source the repository ships, and the prescription names the omitted packages. What is _not_ a finding is a config that names no target while the invocation supplies one — the ordinary shape — nor a `pyright` config without `include`, which already means the whole project.
- **`ruff` rule selection that excludes the reason it was adopted.** A config selecting only `E` and `F` is running pycodestyle's error family beside Pyflakes — roughly what Flake8 gives without plugins, rather than Pyflakes alone; that is a legitimate choice and worth surfacing as a `decision` when it looks deliberate, and as an observation when the config reads like a default nobody revisited.
- **A second formatter alongside `ruff format`.** `black` and `ruff format` are a `conflict` when both are enabled **and their file scopes overlap** — then they agree on most files, disagree on enough, and the result depends on which ran last. Two formatters with disjoint includes, or a monorepo running one per package, are a division of labour that both declarations honour; grading their coexistence would invent a contradiction out of the same structure the environment and config rows above already read per project root. Resolve the scopes first, exactly as the typescript lane does for its own pair.
- **A CI job that installs past the environment manager.** Compare the job against the manager for the **same** project root: in a monorepo, one package's deliberate pip-based job says nothing about another package that uses Poetry, and grading them together would manufacture a conflict from two environments that never meet. Where a project declares a manager — `uv`, `poetry`, `pip-tools`, `hatch`, `pipenv` — and the job covering that project reaches for a bare `pip install` of the tools instead, the two disagree about what its environment is, which is a `conflict`. It has a practical edge as well as a tidiness one: that job never installs the project or its dependencies, so a type checker hits the first third-party import and reports the environment rather than the code, and the report reads like a codebase problem.
- **Tools installed without a constraint.** A CI step reading `pip install ruff` is a `floating` finding: the linter that runs is whichever released most recently, so a new rule arrives as a red build on a pull request that did not cause it. An **exact** version constraint, a dev-dependency group resolved through a tracked lock file, or a tool-installer action pinned **and given an exact tool version** all fix it — any one of them is enough, and the audit says which the repository already has rather than prescribing a new mechanism. Pinning the action alone does not: that fixes the installer's own code, and an installer whose version input defaults to "latest" goes on fetching a different tool every week from behind a SHA that never changes. A range does not: `ruff>=0.5` resolves whichever release is current at install time, which is the same floating behaviour spelled more carefully.

The version row deserves a note on tone. A project pinned to an interpreter that no longer receives security fixes is a real fact with real consequences, and it is still graded `decision` when the pin is deliberate and cited. The report states what the pin costs; it does not escalate. Where no version is declared anywhere, that is a `gap`: nothing holds contributors to a common interpreter, and the failure shows up as a bug reproducible on one machine.

## Scaffold

Templates: `references/scaffold-templates.md` in this directory. Each is filled against what the scan found — the project's declared interpreter version, its existing rule selection, its CI shape — and written one file per confirmation per `../../references/modes.md`.

Never raise `requires-python` as a side effect of scaffolding a tool config. When a floor tool's own minimum exceeds the project's declared interpreter, say so and let the user choose; a config that silently drops support for an interpreter the project promises is a breaking change wearing a linter's clothes.
