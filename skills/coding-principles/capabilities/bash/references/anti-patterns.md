# Bash — anti-patterns

Language-specific anti-patterns and smells. Complements the language-agnostic `../../../references/smells.md`. The positive rules these anti-patterns negate live in `../capability.md`.

- **`cat file | grep x`** — useless cat. `grep x file` or `< file grep x`.
- **`eval` on user input** — command injection waiting to happen. Reach for it only with a clearly documented invariant.
- **Backticks `` `cmd` ``** — use `$(cmd)`, nestable and clearer.
- **Long `if`/`elif` ladders on strings** — use `case` instead.
- **Parsing JSON with `grep`/`sed`** — call `jq`. If `jq` is not available, the script is in the wrong language.
- **Calling `python -c '...'` from bash to do one thing** — rewrite the whole script in Python.
