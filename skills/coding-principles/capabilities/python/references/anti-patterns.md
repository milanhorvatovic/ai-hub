# Python — anti-patterns

Language-specific anti-patterns and smells. Complements the language-agnostic `../../../references/smells.md`. The positive rules these anti-patterns negate live in `../capability.md`.

- **Mutable default args** — `def f(x=[]):` is a bug factory. Default to `None` and assign inside.
- **`from x import *`** — pollutes the namespace, breaks tooling.
- **`eval` / `exec` on dynamic input** — say no. If you think you need it, you need a config file or a plugin system instead.
- **Monkey-patching third-party modules at import time** — fragile, untestable. Wrap or subclass.
- **`global` keyword** — almost always means the design is wrong. Pass state explicitly or use a class.
- **`hasattr` + getattr for optional attributes** — model the union properly with a type.
- **Catch-and-log-and-continue without re-raising** — silent failures pile up. Either handle or propagate.
- **Tests that import `time.sleep`** — use fakes or freeze the clock; sleeps make CI flaky.
