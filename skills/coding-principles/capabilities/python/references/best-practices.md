# Python — industry best practices

External standards (PEPs), modern toolchain consensus, language features by version, security and operational conventions. Complements the principle-anchored content in `../capability.md`.

> **Toolchain claims here were last checked 2026-08.** How to read a stamped file, and what the stamp does not cover, is stated once under "Currency" in `../../../SKILL.md`.

## External standards (PEPs)

- **[PEP 8](https://peps.python.org/pep-0008/)** — style. Ruff and Black enforce most of it automatically; the bits that aren't auto-enforced (naming, import order grouping, line-length tolerance) live in the team's `pyproject.toml`.
- **[PEP 257](https://peps.python.org/pep-0257/)** — docstring conventions. One-line summary, blank line, optional further detail. Most projects pick a style (Google / NumPy / Sphinx) — match the file.
- **[PEP 484](https://peps.python.org/pep-0484/)** + [PEP 585](https://peps.python.org/pep-0585/) + [PEP 604](https://peps.python.org/pep-0604/) — typing. Use `list[T]` not `List[T]` (3.9+), `X | None` not `Optional[X]` (3.10+).
- **[PEP 561](https://peps.python.org/pep-0561/)** — distributing type information. Ship a `py.typed` marker if your package exposes types.
- **[PEP 621](https://peps.python.org/pep-0621/)** — project metadata in `pyproject.toml`. Use `[project]` table; `setup.py` is legacy.
- **[PEP 668](https://peps.python.org/pep-0668/)** — externally-managed environments. Modern OS Python distros refuse global `pip install`; use venvs or `uv`/`pipx`.

## Modern features by version

- **3.10**: `match/case` (structural pattern matching), `X | Y` union syntax, parenthesized context managers, better error messages.
- **3.11**: `ExceptionGroup` + `except*` (true parallel exception handling), `asyncio.TaskGroup` (structured cancellation), `asyncio.timeout` (cleaner than `wait_for`), 10-60% faster interpreter.
- **3.12**: `type X = ...` syntax for type aliases, PEP 695 generic syntax (`def f[T](x: T) -> T`), per-interpreter GIL groundwork.
- **3.13**: free-threaded build (experimental no-GIL), JIT (experimental), `dbm.sqlite3`.
- **3.14**: free-threaded build officially supported (PEP 779), template strings (PEP 750), deferred annotation evaluation (PEP 649/749), `concurrent.interpreters` (PEP 734).

The list runs to the newest stable release at the stamp date; a version past that is one this file has not seen. Default new code to the minimum project Python, and do not down-shim modern syntax to satisfy an interpreter that is already end-of-life — check the release's EOL date rather than assuming a version is still supported because a machine somewhere still runs it.

## Toolchain consensus

- **Package + env manager**: `uv` (Astral) — fastest, replaces `pip` / `pip-tools` / `virtualenv` / much of `poetry`. `poetry` and `hatch` remain valid; `pipenv` is declining.
- **Lint + format**: `ruff` and `ruff format` — replaces `flake8`, `isort`, `pyupgrade`, `pydocstyle`, `eradicate`, mostly replaces `black`. Single tool; near-instant.
- **Type checker**: `mypy` (most common) or `pyright` (faster, used by VS Code's Pylance). Pick one per project.
- **Test runner**: `pytest`. `unittest` for stdlib-only contexts.
- **Property testing**: `hypothesis` — strong industry recommendation for input-heavy / pure-logic code.
- **Build backend**: `hatchling` or `uv` — the modern picks. `setuptools` works but is heavier.

## Logging

- **`logging.dictConfig`** for application setup — declarative, env-tunable. Do not call `logging.basicConfig` and `addHandler` ad-hoc across modules.
- **`contextvars`** for request-scoped fields (request ID, user ID, trace ID). `logging.LoggerAdapter` or `structlog` propagate them into every log record.
- **Structured logging**: `structlog` for new projects; `logging` with a JSON formatter (e.g., `python-json-logger`) for stdlib-only deployments. Log records should be machine-parseable when going to anything other than human eyes.
- **No `print` in libraries.** `print` is for scripts/CLI entry points only.

## Async

- **`asyncio.TaskGroup`** (3.11+) over `asyncio.gather` for fan-out — propagates cancellation correctly when one task fails.
- **`asyncio.timeout`** context manager (3.11+) over `asyncio.wait_for`.
- **Never block in async code** — no `time.sleep`, no synchronous `requests.get`, no `os.path.isfile` for big trees. Use `asyncio.sleep`, `httpx` / `aiohttp`, `aiofiles`, or run blocking calls via `asyncio.to_thread`.
- **Don't mix sync + async in the same module** without a clear boundary. Pick one paradigm per layer.

## Property-based testing

Use `hypothesis` for any function that takes structured input and has algebraic properties (parsing, normalization, encoding, math). It generates inputs you wouldn't think to write tests for and _shrinks_ failures to minimal repros.

```python
from hypothesis import given, strategies as st

@given(st.lists(st.integers()))
def test_sort_is_idempotent(xs):
    assert sorted(sorted(xs)) == sorted(xs)
```

Per-input randomness is reproducible (Hypothesis stores the seed); failing inputs are saved for regression.

## Security

- **Never `eval` / `exec` / `compile` on untrusted input.** If you think you need it, you need a config schema or a plugin system instead.
- **`yaml.safe_load`**, never `yaml.load` without a `SafeLoader`. The default loader can construct arbitrary Python objects.
- **`defusedxml`** for any XML from an untrusted source. The stdlib `xml.etree`, `xml.dom` are vulnerable to billion-laughs and external-entity attacks.
- **`pickle.load` only on trusted data** — pickle is a code-execution primitive, not a serialization format.
- **`secrets`** module for tokens/IDs that need cryptographic randomness; `random` is for simulations.
- **`hashlib`** with `pbkdf2_hmac` / `scrypt` / `bcrypt` (via `passlib`) for password hashing; never raw `sha256` of a password.
- **`subprocess` with `shell=False`** (the default) and a list-form argv; `shell=True` is a command injection waiting to happen.
- **`requests` with `verify=True`** (the default) and a `timeout=` always specified; un-timed requests leak threads on slow upstreams.
- **Supply chain**: `pip-audit` (or `safety`) in CI; pin transitive dependencies via `uv.lock` / `requirements.txt`.

## Packaging

- **`src/` layout** — package code under `src/yourpkg/`, not at the repo root. Prevents accidental imports of the in-tree package without an install.
- **`pyproject.toml`** — all metadata, build, lint, type-checker config in one file.
- **Single-source the version**: declare it in `pyproject.toml`, read it at runtime via `importlib.metadata.version("yourpkg")`.
- **Lockfile committed** — `uv.lock` or `poetry.lock`. Don't ship a package without a way to reproduce the dev environment.

## When to leave the stdlib

The stdlib is the right default. Reach for third-party libraries when:

- HTTP client: `httpx` (sync + async, modern); `requests` is fine for sync-only.
- Date/time arithmetic: `pendulum` or `whenever` (modern) over `datetime` when time zones / arithmetic get hairy.
- Settings: `pydantic-settings` over hand-rolled `os.environ` parsing.
- Data validation at boundaries: `pydantic` v2.
- CLI: `typer` or `click` over hand-rolled `argparse` for anything multi-subcommand.

## Documentation

- **Whether a docstring is warranted at all** is the comments capability's call — it owns the cross-language policy, including the pydocstyle / interrogate / ruff D-rule signals that say this project demands them. What follows is Python's _how_, once that policy says yes.
- **Docstring style** — the shape is PEP 257's (External standards, above); the choice among Google, NumPy, and Sphinx/reStructuredText is the repo's, applied consistently. Google style is the most readable for most projects.
- **Type hints are documentation** — a precise signature replaces a paragraph of prose. Prefer expressive types over describing types in the docstring.
- **Site generators**: `mkdocs` + `mkdocstrings` (Markdown, modern) or `Sphinx` + `autodoc` (reStructuredText, the classic). Generate from docstrings; don't hand-maintain a parallel doc tree.
