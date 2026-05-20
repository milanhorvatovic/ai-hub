# Rust — anti-patterns

Language-specific anti-patterns and smells. Complements the language-agnostic `../../references/smells.md`. The positive rules these anti-patterns negate live in `capability.md` (sibling).

- **`unwrap()` in library code** — panic from a library is almost never the right contract.
- **`Box<dyn Error>` in library APIs** — opaque to callers. Use a specific error enum.
- **`String::from` / `.to_string()` on `&str` parameters you immediately use as `&str`** — drop the conversion.
- **`Vec<String>` when `&[&str]` would do** for read-only access.
- **Premature `Rc<RefCell<_>>`** — usually a sign the data structure should be redesigned. Acceptable in single-threaded graphs and AST manipulation.
- **`#[allow(...)]` without a comment** — banned. State why the lint is wrong here.
- **`#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]` on everything** — derive only what's needed; over-derivation locks API surface.
- **Re-exporting third-party types from a public API** — couples your version to theirs. Wrap or re-define.
