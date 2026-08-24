# python — scaffold templates

Shapes to fill in from what the scan found, not files to copy verbatim. Every placeholder in angle brackets is a value the scan already established; a template written out with a placeholder still in it is a defect, not a to-do left for the user.

## `ruff` in `pyproject.toml`

The floor wants both jobs configured. Rule selection starts conservative because a first `ruff` adoption that reports four hundred findings gets reverted.

```toml
[tool.ruff]
target-version = "<py3XX matching requires-python>"
line-length = <the project's existing width, or 100>

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]   # errors, pyflakes, imports, pyupgrade, bugbear

[tool.ruff.format]
docstring-code-format = true
```

`I` earns its place on adoption day: import sorting is the change most likely to conflict with an existing tool, so its presence here is what surfaces a leftover `isort` config as a `conflict` on the next audit rather than a merge conflict later.

## `mypy` in `pyproject.toml`

```toml
[tool.mypy]
python_version = "<3.XX matching requires-python>"
files = ["<the package directory>"]
strict = true
```

`files` is the row that matters, and not because omitting it produces a green check of nothing — `mypy` with no target in the config and none on the command line exits with an error, so that failure is loud rather than silent. It matters because it fixes the scope in one place: without it, what gets checked is whatever each call site passes, so CI and a contributor's local run can cover different sets and neither notices. Naming the package here makes the scope a property of the project instead of a property of the invocation.

`strict = true` is the destination, not necessarily the starting point. For an existing codebase adopting types, propose it with the escape hatch alongside — a per-module override block that relaxes the modules not yet annotated — so the first run is actionable rather than a wall:

```toml
[[tool.mypy.overrides]]
module = ["<legacy.module.one>", "<legacy.module.two>"]
disallow_untyped_defs = false
```

## `pyright` in `pyrightconfig.json`

The alternative to `mypy`, not an addition to it. Scaffold this only when the project already leans on it or asks for it.

```json
{
  "include": ["<the package directory>"],
  "pythonVersion": "<3.XX>",
  "typeCheckingMode": "standard"
}
```

## The CI step

Two things separate a real lint job from a decorative one: it runs on pull requests, and its failure fails the job. Both are visible in the shape below.

```yaml
lint:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@<40-char-sha> # <the version this sha is>
    - uses: actions/setup-python@<40-char-sha> # <the version this sha is>
      with:
        python-version: "<3.XX>"
    - run: <the project's locked dev-environment install — uv sync, poetry install, pip-sync, hatch env create>
    - run: <the project's runner prefix> ruff check .
    - run: <the project's runner prefix> ruff format --check .
    - run: <the project's runner prefix> <the project's type-checker command>
```

The install step is the project's environment manager, not a bare `pip install` of the two tools. The floor already asks for a managed environment with a tracked lock, and a CI job that sidesteps it installs unpinned tools into whatever interpreter the runner provides and — the part that actually breaks — never installs the project or its dependencies, so a type checker reaches the first third-party import and reports errors about the environment rather than the code. Declare the tools in the project's own dev-dependency group, install through the lock, and let the runner prefix (`uv run`, `poetry run`, or nothing where the environment is already active) be whatever the repository uses elsewhere.

The type-checker rows are placeholders because the floor admits two tools and the repository has already picked one. Filling them with `mypy` regardless is how a `pyright` project asking for a missing CI step gets handed a second type checker instead — two tools disagreeing about the same code, which is a `conflict` finding on the next audit and a worse position than the wiring gap it was meant to close. Read the choice off the scan: `mypy` for a repository that declares it, `pyright` for one that declares that, and only where neither exists does the audit's alternatives line get to recommend either.

Pin the tool versions. An unpinned linter turns every upstream release into a surprise red build on an unrelated pull request, which is the fastest route to a team adding `continue-on-error` and never removing it.

Where the repository already routes CI through a task runner, add the commands to that runner and call it from the workflow instead of duplicating them — a lint job that bypasses the repository's own entry point drifts from what contributors run locally.

## Declaring the interpreter version

One home, referenced by the rest. When the project has none, `requires-python` is the one to add first, because it is the declaration packaging tools and installers already read.

```toml
[project]
requires-python = ">=<3.XX>"
```

Then make the CI matrix and any `.python-version` agree with it rather than restating it independently — the disagreement between them is a `drift` finding on the next audit, and scaffolding one without checking the others is how it gets introduced.
