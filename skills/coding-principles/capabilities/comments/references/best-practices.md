# Comments — industry best practices

External standards and published thinking behind the comment-value rubric. Complements the operational rules in `../capability.md`; load when a choice needs justifying against industry consensus rather than house rules.

> **The docstring-detection tools named below were last checked 2026-08.** The rules do not decay; the tools do. How to read a stamped file is stated once under "Currency" in `../../../SKILL.md`.

## External standards

- **[John Ousterhout, *A Philosophy of Software Design*](https://web.stanford.edu/~ouster/cgi-bin/book.php)** — the strongest published case *for* comments: they should describe what is not obvious from the code, at a different level of abstraction than the code itself (higher: intent and invariants; or lower: units, boundary conditions, ownership). His comment categories — interface, data-structure member, implementation, cross-module — map directly onto the rubric's meaning categories.
- **[Jeff Atwood, "Code Tells You How, Comments Tell You Why"](https://blog.codinghorror.com/code-tells-you-how-comments-tell-you-why/)** — the canonical statement of the content gate (principle 7): the code carries the *how*; a comment earns its keep carrying the *why*.
- **[PEP 257](https://peps.python.org/pep-0257/)** and the **[Google Python Style Guide §3.8](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)** — docstring scope conventions: document the public surface's contract (args whose interaction is non-obvious, returns, raises), not restated signatures. The detection table in `../capability.md` decides when a project has opted into them.
- **[rustdoc — how to write documentation](https://doc.rust-lang.org/rustdoc/how-to-write-documentation.html)** — doc comments as consumed API documentation: first line is a summary, examples are compiled and tested. When comments feed a doc pipeline, they are interface, not commentary — the schema-doc edge case generalized.
- **Microsoft [XML documentation comments](https://learn.microsoft.com/dotnet/csharp/language-reference/xmldoc/)** — same contract stance for .NET: `<summary>` carries what the signature cannot, and tooling (`SA1600`, `GenerateDocumentationFile`) makes the convention detectable.

## Where the industry converges

Three points of agreement across the sources above, restated as this capability applies them:

1. **The code is the primary document.** Naming, structure, and types carry the *what*; a comment duplicating them is maintenance debt (Atwood; Kernighan's "don't comment bad code — rewrite it").
2. **Good comments are not optional decoration.** Ousterhout's counterpoint disciplines the deletion reflex: invariants, units, ownership, and cross-module constraints *cannot* be expressed in code, and omitting them loses design information permanently. The rubric's revise-before-remove stance is his position operationalized.
3. **Docstrings are a project-level contract, not a per-author taste.** Every ecosystem expresses "we document our public surface" through detectable tooling (pydocstyle, jsdoc lints, `missing_docs`, checkstyle) — so detection, not preference, decides.

## The agent-authoring addendum

AI coding agents systematically over-comment relative to every standard above — narrating edits, restating code, and leaving authorship markers. Agent-harness system prompts (Claude Code among them) converge on the same correction this capability encodes: default to few comments, make each one carry information the code cannot, and keep authorship narration in the commit message. The AI-narration marker policy in `../capability.md` is that convergence stated as a rule with its override clause.
