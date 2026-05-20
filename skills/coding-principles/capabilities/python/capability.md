---
name: coding-principles-python
description: >
  Python-specific capability of the coding-principles skill. Loaded when the
  task touches *.py files or sits in a pyproject.toml context. Covers the
  tooling floor (ruff + mypy/pyright, version pinning, env management),
  idioms (type hints, f-strings, pathlib, dataclasses), error and logging
  discipline, async-only-for-I/O rules, anti-patterns (mutable default args,
  bare except, eval, global), test conventions, and before/after code
  examples anchored to numbered principles 4, 5, 13, 15, 17, and 19 of the
  parent skill.
allowed-tools: Read Grep
---

# Python capability

Language-specific rules layered on top of the parent `coding-principles` skill. Apply when editing `*.py` files.

> **Industry best practices** — PEP anchors (8, 257, 484, 561, 621, 668), modern toolchain consensus (ruff, uv, mypy/pyright, pytest, hypothesis), version-by-version language features (3.10 match/case, 3.11 TaskGroup/ExceptionGroup, 3.12 type syntax), logging discipline (dictConfig, contextvars, structlog), async patterns, security (safe_load, defusedxml, no eval), and packaging conventions live in `best-practices.md` in this directory. Load it alongside this file when the task warrants justifying choices against industry standards.

## Floor

- Python 3.10+ unless the project pins lower (check `pyproject.toml` / `setup.cfg` / `python_requires`).
- Type hints on public surface (module-level functions, class methods, dataclass fields). Internal helpers may skip them if obvious.
- `ruff` for lint + format; `mypy` or `pyright` for types. Treat warnings as errors in CI.
- Manage env with the project's tool (`uv`, `poetry`, `pip-tools`, `hatch`). Never `pip install` into a global interpreter.

## Idiom and style

- f-strings for interpolation. Not `%` formatting, not `.format`, not string concatenation.
- `pathlib.Path` over `os.path`. `Path("a") / "b"` reads, `os.path.join` does not.
- `dataclass` / `pydantic.BaseModel` over dict-shaped-like-an-object. Once a dict has a fixed schema, model it.
- `with` for resources (files, locks, DB sessions). Never call `.close()` manually unless there's a reason `with` cannot apply.
- Generators / comprehensions over `map`+`filter` chains. Comprehensions over `for`-append loops.
- `enumerate` over `range(len(...))`. `zip` over parallel indexing.

## Errors

- Raise specific exception types (`ValueError`, `KeyError`, custom `class XError(Exception)`). Never `raise Exception(...)`.
- Catch specific exceptions. Never bare `except:`. Never `except Exception:` unless re-raising or logging at a top-level boundary.
- Don't use exceptions for control flow on the happy path — they're for exceptional conditions.
- Don't return `None` as a sentinel when the caller might forget to check; raise or return an explicit `Optional[X]` with type-narrowing on the caller side.

## Async

- `async` only when there is actual I/O concurrency to exploit (network, subprocess, disk). Wrapping CPU work in `async def` does not make it concurrent — it makes it confusing.
- Don't mix sync and async APIs in the same module without a clear boundary. Pick one and offer adapters at the edge.
- `asyncio.gather` for fan-out; `asyncio.TaskGroup` (3.11+) when you need structured cancellation.

## Logging and I/O

- `logging` in libraries — never `print`. Use a module-level `logger = logging.getLogger(__name__)`.
- `print` is fine in scripts and CLI entry points. Send progress to stderr, results to stdout.
- Use `argparse` (or `click` / `typer` if the project already does) for CLIs; don't parse `sys.argv` by hand.

## Anti-patterns

Language-specific anti-patterns live in `anti-patterns.md` (sibling). Load it for review-mode scans or pre-commit smell checks; the language-agnostic catalog is in `../../references/smells.md`.

## Tests

- `pytest`, not unittest, unless the project is already on unittest.
- Test names describe behavior: `test_returns_empty_list_when_input_is_none`, not `test_1`.
- One assertion per test in most cases. Multiple OK when they verify one behavior together.
- `pytest.fixture` for setup; avoid module-level state.
- `pytest.mark.parametrize` over loop-based test generation.

## Verification

- `ruff check . && ruff format --check .`
- `mypy <pkg>` (or `pyright`)
- `pytest -x` on the affected modules at least.

## Examples by principle

Concrete before/after code for high-leverage principles (4, 5, 8, 13, 15, 17, 19) lives in `examples.md` (sibling). Load it when matching patterns at write-time or validating suggested fixes at review-time.

## Performance

Performance idioms (and the "measure first" discipline) live in `performance.md` (sibling). Load it when working on a hot path or large-data code — not for routine changes.

## Concurrency

Concurrency model, decision matrix, and correctness traps live in `concurrency.md` (sibling). Load it when the task involves parallelism, async, or shared state.

## Project structure

Language-specific structure mechanics (modularity unit, visibility/boundary enforcement, ports & adapters, dependency injection, layout) live in `project-structure.md` (sibling). It is the *how* for this language; `../../references/architecture.md` is the cross-language *why*. Load when structuring or restructuring a project.

## Dependencies

Dependency-management mechanics (version pinning, lockfiles, audit tools, update cadence, minimal footprint) live in `dependencies.md` (sibling). Default stance: **pin explicit exact versions** for applications/binaries (reproducibility); ranges only for published libraries. Load when adding, updating, or auditing dependencies.

## Cross-cutting references

Concern-specific, language-agnostic references live in `../../references/` — `api-design.md`, `persistence.md`, `observability.md`, `platform-matrix.md`, `resilience.md`, `data-handling.md`, `architecture.md`, `configuration.md`. Load the one matching the concern the code touches (see the table in the root `SKILL.md`). They apply across all language capabilities.
