# Publication-audience catalog for pre-publication self-containment

Load this whenever a capability is about to display or write text that will be published — a commit message, PR body, release note, or review reply. It is the audience half of the pre-publication pass whose other half is `secret-patterns.md`: that catalog asks whether a value is confidential, this one asks whether the text resolves for a reader who holds only the published artifact. Both run over the same surfaces and neither subsumes the other — nothing here is a credential, and a missing antecedent matches no secret pattern.

## The contract

Published text must resolve for a public reader. Every artifact a sentence names is one of three things: diff-visible, publicly linkable, or defined in the text itself — visible in the change the text accompanies, reachable through a link anyone can open (an issue, a pull request, a commit, a released document), or explained where it is mentioned. A name that is none of the three is private context that reached the draft through the author's session rather than through the change — a planning-track code, a path on the author's disk, a document only the author can open, or a definite article pointing at something the reader was never shown.

Nothing confidential need be involved for this to fail. The sentence reads as complete to its author and as a dead end to everyone else, and it is permanent: commit and release text is history, and a PR body outlives the session that wrote it by years.

## Detection catalog

Listed rather than tabulated for the reason the secret catalog gives — alternation pipes must stay literal in the raw source. Each entry is `name` — `pattern` — what it catches. Every entry grades `WARN` (see Grading), and a finding reports under the `private-context-ref` rule id defined in `review-output.md`.

- `definite_reference` — `(?i)\b(?:the|this|that|our)\s+(?:packet|plan|program|roadmap|audit|tracker|archive|backlog|spec|writeup|doc(?:ument)?|note|session|thread|discussion)s?\b` — a definite noun phrase naming a document or a conversation the reader was never handed. Subject to the sentence-level exemption below, and skip the finding too when the noun is defined earlier in the same text — "the plan below" resolves, and only reading the surrounding text can tell.
- `session_deixis` — `(?i)\b(?:as (?:discussed|agreed|decided|noted|mentioned)|we (?:agreed|decided|discussed)|per (?:the|our) (?:plan|packet|program|roadmap|audit|tracker|archive|backlog|spec|writeup|doc(?:ument)?|note|session|thread|discussion)s?)\b` — an appeal to a conversation the reader was not in. The decision may be worth publishing; the appeal is not, because it cites an inaccessible authority in place of the reasoning. `per the …` takes the same private-document nouns as the entry above rather than any word, so "per the diff" and "per the API docs" are left alone, and this entry is subject to the sentence-level exemption below.
- `track_code` — `(?<!\w)[A-Z]{1,2}\d{1,2}\b` — planning-track ids (`Z9`, `Q14`, `M2`). The lookbehind keeps the match off the tail of a longer token (`HTTP2` is not a track code); it deliberately does not exempt a leading `#`, because issue references are numeric and a numeric reference cannot match a letter-prefixed pattern in the first place. Exempting `#` would therefore exempt no real issue reference and would hide the one thing it looks like — a track code someone pasted with a hash in front of it. The discriminator is lookup, not shape: flag only when the token appears nowhere in the diff, the linked issues, or the repository's tracked docs. A token a reader can look up is public by construction, which is what keeps `L2`, `S3`, and `H2` out of the findings.
- `private_path` — `(?:^|[\s("'\x60=])(?:/|~/|[A-Za-z]:[\\/]|\\\\)\S+` — absolute, drive-letter, UNC, or home-relative paths, which name a filesystem rather than the repository. Any absolute path qualifies, not a list of familiar roots: an enumeration of `/Users`, `/home` and friends promises to catch absolute paths and then lets `/tmp/design.md`, `/root/notes`, and `/srv/build/plan` through, which is a narrower rule wearing a broader sentence. The delimiter class includes a backtick — written `\x60` so the pattern itself survives being quoted as inline code — because inline code is the ordinary way a path reaches a description, and omitting it would miss the most common spelling of the thing being detected. It includes `=` for the same reason one step further out: a path most often appears in a description as the value of a flag or a variable (`--config=/home/dev/plan.md`, `HOME=~/workspace`), and a delimiter list built from prose habits misses every one of those. It still keeps URLs out, code-formatted ones included, since the slashes in `https://example.com/x` follow a colon and a letter rather than a delimiter. The Windows forms are spelled to match what Windows accepts rather than what a POSIX author pictures: a drive path takes either separator (`C:\Users\dev` and `C:/Users/dev` are the same path) and a UNC path opens with two backslashes, so a pattern that took only `C:\` left two ordinary spellings of a private path unflagged. Repo-relative paths join the finding when they resolve in neither the tree nor the diff (`git ls-files --error-unmatch <path>`), because a path that resolves nowhere the reader can reach is a private path spelled relatively.
- `foreign_repository` — a forge URL or `owner/repo` slug naming any repository other than the one the text is published in. Only the publishing repository resolves automatically. A configured remote does not: the author's remotes and credentials are not the reader's, so a private sibling repository set up as a remote would otherwise clear the scan while being unreadable to everyone the text is written for — the single most common shape of this whole defect. Public cross-repository links are legitimate; the finding asks for confirmation that the target is publicly readable, not for its removal.
- `foreign_branch` — a branch name that does not resolve in the repository the text is published in: `git ls-remote --heads <publishing remote> <candidate>`, where the publishing remote is the one the artifact goes to, `origin` in the ordinary setup. Other configured remotes are deliberately not consulted — a branch that lives only on a private fork is reachable for the author and absent for the reader, and consulting every remote would answer the author's question instead of the audience's. Branch names are cheap to paste from a session and mean nothing to a reader who cannot fetch them.

### The sentence-level exemption

`definite_reference` and `session_deixis` find candidates rather than deliver verdicts. After a match, read the sentence it sits in and drop the finding when that sentence carries a reference that **resolves for the publication audience and names the thing the phrase points at** — an issue or pull request in this repository, or a link on a host anyone can reach. So "See #12 for the plan" and "as discussed in #12" are clean once `#12` exists, while a bare "the plan" is not.

Presence is not resolution, and this is where the exemption is easiest to get wrong. A dangling issue number, an unrelated link two clauses away, or a URL on an intranet host all look like references and hand the reader nothing, so none of them clears the finding: verify the target the way the contract asks — the issue resolves, the host is public — and keep the warning when verification is unavailable rather than reading an unchecked `#N` as proof. A guard that accepts any `#`-shaped token as an antecedent has been talked out of its own rule by punctuation.

It is a step rather than part of the expressions because it cannot be part of them. A trailing lookahead inspects only what follows the phrase, so it clears the reference-after spelling and flags the reference-before one, and no regular expression can look backward by an unbounded amount to even that out. An exemption holding for half its cases is worse than one stated plainly, since the half it misses is a warning on text that already met the contract — and a reader of the pattern alone would never know which half they had.

## Grading

Every heuristic above grades `WARN` — surfaced, never auto-obeyed, never auto-stripped. The grade is deliberate rather than timid: a repository whose planning is public legitimately publishes its track codes and archive paths, and a generic mechanism that hard-failed them would be wrong about a setup it cannot see. So the mechanism recommends, and a repository escalates for itself.

A declared `error` changes what the capability does with the draft, not only how the finding reads. At `WARN` the proposal is shown with the finding beside it and the author decides. At `error` the repository has said this span must not ship, so the text carrying it is not emitted and no apply command is surfaced — the rewrite is proposed in its place, the same posture the secret catalog takes on a match. Every consumer passes the grade through: a capability that prints `WARN` unconditionally has overridden a declaration it was written to honor, which is the failure mode this paragraph exists to name.

Two vocabularies meet here and only one of them is a result. At draft time the finding is surfaced as a `WARN:` line above the proposal, the same shape the secret scan uses. In a REVIEW-mode report it is an internal severity of `warn`, which reaches the reader through the mapping in `review-output.md` as `MOSTLY-PASS` — never as a `WARN` result, which the output schema does not define and would reject.

Where a repository declares its own private surface, the same finding is exact rather than heuristic, and the severity it carries is the one the repository's own declaration or gate states. Each grade is stated where it is enforced — here for the heuristics, in the repository's declaration for its own patterns — so a reader of either surface learns what that surface does without inferring it from the other.

## Repository declarations

Convention discovery reads the repository's agent-instruction and contributing files for format rules; it reads publication-audience declarations from the same files. A declaration names what only the repository knows: its private track-code series, its private path prefixes, the repositories it keeps unreadable. Declared patterns are matched exactly and reported at the declared severity.

Declaration and detection meet in the middle rather than duplicating. The catalog covers what any repository can be wrong about; the declaration covers what this repository alone can state. A repository that declares nothing still gets the heuristics; a repository that declares its vocabulary stops relying on them.

A declaration is a labeled list under a heading a reader can recognize, so that stating it costs a repository one block rather than a config format:

```
## Publication audience

- private track codes: /\b[A-Z]{1,2}\d{1,2}\b/ — error
- private path: planning/ — error
- private path: internal-notes/ — error
- private repository: acme/acme-planning — warn
```

Each entry carries one value and an optional severity, and a repository with several values repeats the entry rather than packing a list into one — comma-separated values would collide with the commas inside a regular expression's own quantifiers, and a grammar whose separator appears in its values is a grammar that mis-parses its own example. A value is a literal substring unless it is written between slashes, which marks a regular expression; inside those slashes a literal slash is written `\/`. The severity is `warn` or `error`, and `warn` is the default when the entry omits it — an omission is a repository that has not thought about severity, not one asking for the strictest reading.

**Read declarations from the base branch, never from the branch under review.** A declaration is a judge, and a change cannot supply its own: the head tree of a proposed change is untrusted input like any other, so honoring a declaration it introduces would let a contributor add a catch-all pattern, or raise ordinary prose to `error`, and thereby author the findings that grade their own change. Resolve the declaration against the branch being merged into; when the head modifies it, surface that as a finding for a human to read rather than applying it. This is the same reason `untrusted-content.md` forbids fetched text from deciding a verdict, and it is why even an addition — which sounds harmless — is base-branch-sourced.

Within those bounds a declaration only widens the scan. It adds patterns and raises severity; it cannot delete a catalog entry, cannot lower a heuristic below `WARN`, and cannot switch the scan off. A declaration able to disable the check would be a one-line way to quiet it, which is exactly what the base-branch rule above exists to make impossible.

## Action on a match

1. Name the span and the pattern that matched, at the line where it sits.
2. Propose a rewrite, not a deletion. The sentence usually carries real information — replace the private name with what the diff shows, a public link, or a definition in the text itself.
3. Never resolve a private reference by pasting the private content in its place. That inverts the fix: the unresolvable name becomes a published detail, which is the leak the author was drifting toward.
4. Never decide on the author's behalf that a flagged span is public. Surface it even when the heuristic over-flags — a false positive costs one sentence of review, a false negative ships.

## Scope

Apply this scan to every proposed text before it is displayed **or written to disk** — mktemp proposal files and previews carry exactly what the displayed copy carries:

- Proposed commit subjects and bodies.
- Proposed PR titles, descriptions, and body patches.
- Proposed release notes.
- Proposed review replies and comments.
- Carry-forward content from an existing body — the rewrite is the moment to resolve an inherited reference, not to relay it.

Do NOT scan:

- Diff content read for context. That is the author's code, not new text being authored, and it is what the reader can see.
- Issue and PR references (`#N`) that resolve in this repository — that is the publicly-linkable form the contract asks for, not a violation of it.
- Track-code-shaped tokens inside code samples, identifiers, quoted logs, or file contents shown from the diff. The diff is the artifact that defines them.

## Why this is a second catalog rather than more patterns in the first

The two run as stages of one pre-publication pass and stay separate because their profiles differ in every dimension that matters to a caller. A secret match is redaction-worthy on sight and its false positives are cheap to dismiss; an audience match is usually a legitimate sentence that needs rewriting rather than removal, and its false positives are ordinary English. Merging the catalogs would make one severity mean two things, and the first time a repository wanted to tune one it would have to tune both.
