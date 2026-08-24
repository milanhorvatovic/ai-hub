# python — scaffold templates

Shapes to fill in from what the scan found, not files to copy verbatim. Every placeholder in angle brackets is a value the scan already established; a template written out with a placeholder still in it is a defect, not a to-do left for the user.

## `ruff` in `pyproject.toml`

The floor wants both jobs configured, and that is all this writes. Everything else `ruff` can express — line length, which rule families are selected, formatter preferences — is style the floor does not speak to and the grading reference lists as never a finding, so choosing it here would hand a repository whose only finding was "no linter configured" a set of decisions it never asked anyone to make.

```toml
[tool.ruff]
target-version = "<py3XX matching requires-python>"
```

Carry over any `line-length`, `select`, or formatter settings the scan found in a tool being replaced — a leftover `isort` section, a `flake8` config — because preserving an existing choice is not inventing one. Where the repository has expressed nothing, leave the keys out: `ruff`'s defaults are a considered set, and a scaffold that adopts them silently is smaller to review than one that restates them as though they were decisions.

Rule families beyond the default set are worth naming in the report as options — import sorting in particular, since adopting it is what surfaces a leftover `isort` config — and worth writing only when asked for.

## `mypy` in `pyproject.toml`

```toml
[tool.mypy]
python_version = "<3.XX matching requires-python>"
files = ["<the package directory>"]
```

`files` is the row that matters, and not because omitting it produces a green check of nothing — `mypy` with no target in the config and none on the command line exits with an error, so that failure is loud rather than silent. It matters because it fixes the scope in one place: without it, what gets checked is whatever each call site passes, so CI and a contributor's local run can cover different sets and neither notices. Naming the package here makes the scope a property of the project instead of a property of the invocation.

No enforcement setting is scaffolded, and the reason is a gap in what the tools can express. The floor asks for annotations on the **public** surface and explicitly lets obvious internal helpers go untyped; `mypy` has no setting scoped that way. `disallow_untyped_defs` is the nearest lever and it reaches every definition in the package, so scaffolding it to close a public-surface finding would gate legacy internals the floor never asked about — trading an under-enforcing default for an over-enforcing one.

So the audit reads the enforcement settings the repository declares, and the report names `disallow_untyped_defs` as the available lever together with what it costs. Write it when the user accepts that scope.

`strict = true` is deliberately not here. The floor asks that a checker cover the public surface, not that it run at maximum strictness, and defaulting to strict turns a scaffold meant to close "no type checker configured" into a CI job failing across an existing codebase for policies the audit never reported. Name it in the report as the destination; write it when the user asks.

When they do, an existing codebase wants the escape hatch alongside it — a per-module override block relaxing the modules not yet annotated — so the first run is actionable rather than a wall:

```toml
[[tool.mypy.overrides]]
module = ["<legacy.module.one>", "<legacy.module.two>"]
disallow_untyped_defs = false
```

## `pyright` in `pyrightconfig.json`

The alternative to `mypy`, not an addition to it. Scaffold this only when the project already leans on it or asks for it. `reportMissingParameterType` and `reportMissingReturnType` are this route's equivalent of `disallow_untyped_defs`, and they are left out for the same reason: both report on internal functions as readily as on the public surface, so enabling them by default gates more than the floor requires. Name them in the report with their scope stated; write them on request.

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
on:
  pull_request:
  push:
    branches: [<the default branch>]

permissions:
  contents: read

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<40-char-sha> # <the version this sha is>
      - uses: actions/setup-python@<40-char-sha> # <the version this sha is>
        with:
          python-version: "<3.XX>"
      - name: bootstrap <the project's environment manager>
        uses: <that manager's pinned setup action>@<40-char-sha> # <the version this sha is>
      - run: <the project's locked dev-environment install — uv sync, poetry install, pipenv sync --dev, pip-sync, hatch env create>
      - run: <the project's runner prefix> ruff check .
      - run: <the project's runner prefix> ruff format --check .
      - run: <the project's runner prefix> <the project's type-checker command>
```

The trigger and the permission floor are part of the scaffold, not context around it. A bare job fragment dropped into a push-only workflow still grades `wiring` on the next audit — it runs, and not where review happens — so a scaffold that omitted `on: pull_request` would not close the finding it was written for. And a job that runs repository code inherits whatever token permissions the repository defaults to, which on an older repository is write; `contents: read` is the floor, raised only for a scope the job demonstrably needs.

The bootstrap step is not optional scenery. `actions/setup-python` provides an interpreter and `pip`, and nothing else: `uv`, `poetry`, `pipenv`, `pip-sync`, and `hatch` are all absent from a fresh runner, so a job that jumps straight to the locked install fails with a command not found before any check runs — a scaffold that closes a wiring finding on paper and cannot execute. Use the manager's own pinned setup action where it has one, and a pinned installer step where it does not.

The install step is the project's environment manager, not a bare `pip install` of the two tools. The floor already asks for a managed environment with a tracked lock, and a CI job that sidesteps it installs unpinned tools into whatever interpreter the runner provides and — the part that actually breaks — never installs the project or its dependencies, so a type checker reaches the first third-party import and reports errors about the environment rather than the code. Declare the tools in the project's own dev-dependency group, install through the lock, and let the runner prefix (`uv run`, `poetry run`, `pipenv run`, or nothing where the environment is already active) be whatever the repository uses elsewhere.

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
