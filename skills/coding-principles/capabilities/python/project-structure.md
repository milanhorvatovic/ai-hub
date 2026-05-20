# Python — project structure & mechanics

Language-specific *mechanics* for the architecture concepts in `../../references/architecture.md` (dependency-points-inward, hexagonal, package-by-feature). That file is the *why*; this is the Python *how*. Load when structuring or restructuring a Python project.

## Unit of modularity

- **Module** = a `.py` file. **Package** = a directory with `__init__.py` (or a namespace package without one).
- Group by **feature/domain** (`orders/`, `billing/`), not by layer (`services/`, `repositories/`) — see the concept file. Layer *within* each feature package.
- One concept per module; split when a file exports several unrelated things.

## Visibility / boundary enforcement

Python has no enforced `private` — it's convention + tooling:

- **`_leading_underscore`** marks module-internal names. Linters and humans treat them as private.
- **`__all__`** in `__init__.py` declares the package's public surface (minimum public surface — modular-by-composition mantra). What's not in `__all__` is internal.
- **Don't re-export everything** from `__init__.py` — export the package's intended API, keep internals unimported.
- Tools: `ruff` can flag imports of private names across package boundaries; import-linter enforces layer/dependency rules in CI.

## Ports & adapters

- A **port** is a `typing.Protocol` (structural — preferred, no inheritance coupling) or an `abc.ABC` (nominal). Define it in the domain/application layer.
- An **adapter** implements the protocol in the infrastructure layer.

```python
# application layer — defines the port it needs
class UserRepository(Protocol):
    def get(self, user_id: UserId) -> User | None: ...

# infrastructure layer — adapter
class PostgresUserRepository:
    def get(self, user_id: UserId) -> User | None: ...   # structurally satisfies the Protocol
```

The domain depends on `UserRepository` (the port), never on `PostgresUserRepository` (the adapter). `Protocol` is the idiomatic choice — duck typing means the adapter doesn't even import the port.

## Dependency injection

- **Constructor / function injection** is idiomatic — pass dependencies in. `def __init__(self, repo: UserRepository)` or `def handle(req, *, repo: UserRepository)`.
- The composition root is the entry point (`main`, the FastAPI/Django app factory) — wire concrete adapters there (imperative shell — principle 16).
- DI *frameworks* (`dependency-injector`, `wired`) exist but are usually unnecessary — explicit wiring at the edge is clearer (explicit-over-implicit mantra). Reach for a framework only when manual wiring genuinely hurts.

## Layout (src layout)

```
project/
├── pyproject.toml
├── src/
│   └── mypkg/
│       ├── __init__.py        # public API surface (__all__)
│       ├── orders/            # feature package
│       │   ├── domain.py      # entities + rules (pure)
│       │   ├── service.py     # use cases; defines ports
│       │   └── repository.py  # adapter (infra)
│       └── billing/
└── tests/
    ├── unit/
    └── integration/
```

- **`src/` layout** prevents accidental imports of the in-tree package without an install (best-practices.md).
- **Tests**: unit tests can sit next to source or in a mirrored `tests/` tree — match the repo. Integration tests in a separate `tests/integration/`.
- **Entry point**: `__init__.py` declares the public API; a `__main__.py` or a `[project.scripts]` console-script for executables.

## When not to structure

A script or a single-purpose tool is one module with a few functions — no packages, no ports, no layers (principle 4 / when-NOT-to-layer in the concept file).
