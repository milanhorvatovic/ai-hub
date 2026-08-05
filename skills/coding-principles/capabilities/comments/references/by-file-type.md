# Comments by file type

Per-format depth behind the quick rules in `../capability.md`. Every section applies the same value → content gates; what differs per format is which meanings tend to be load-bearing and which comment habits are noise. Sections carry a before/after sketch where the pattern benefits from one.

## Comment forms recognized

The rubric governs syntactic comments in every form the fleet of file types offers:

- Python — triple-quoted docstrings (`"""…"""` / `'''…'''`); runs of `#` lines.
- TypeScript / JavaScript / Rust / Go / C / C++ / Java / Kotlin / Swift / Scala / C# — `/* … */`; JSDoc / TSDoc / doc-comment `/** … */` and `///`.
- Ruby — `=begin … =end`; runs of `#`.
- HTML / Markdown / Vue templates — `<!-- … -->`.
- MDX — `{/* … */}`.
- RST — `..` directive-less indented blocks.
- AsciiDoc — `//` line comments; `////` delimited blocks.
- Shell / YAML / TOML / Dockerfile / Makefile — runs of `#`; consecutive `#` lines count as one block for the partial-failure rule.

## Source code

The rubric as stated in `../capability.md`: a comment earns its place by carrying an invariant, a surprise, a stated deviation, an anchored workaround, a security assumption, or profiled evidence. The habits that fail it most often:

- Restating the line (`i += 1  # increment i`).
- Narrating control flow a reader sees from structure (`# loop over users`).
- Section banners (`# ─── helpers ───`) — if a file needs signage to navigate, it needs splitting.
- Dead code held in comments — that is principle 20's territory, delete it.

Before:

```python
# Get the user from the database
user = repo.get(user_id)
# Check if the user is active
if user.suspended_at is None:
    ...
```

After (the only comment left is the one carrying a surprise):

```python
user = repo.get(user_id)
# suspended_at of None means never-suspended, not "suspension cleared" —
# cleared suspensions keep the timestamp (billing relies on it).
if user.suspended_at is None:
    ...
```

Docstrings follow the policy and detection table in `../capability.md`: convention first, value bar otherwise. When a convention demands docstrings everywhere, write them to carry contract — parameters whose interaction is non-obvious, preconditions, invariants, failure modes — and let the signature carry names and types.

## Configs — YAML, TOML, INI, .env, JSON5/JSONC

Config keys are named by their schema; annotating each one restates it. Comment the values that would surprise:

- Magic numbers and their units (`timeout: 4500  # ms — p99 upstream latency is 4s`).
- Deviations from the tool's default, with the reason.
- Values coupled to something external (`replicas: 3  # one per AZ; keep in sync with the subnet list`).
- Ordering or grouping constraints the format cannot express.

Before:

```yaml
# The port the server listens on
port: 8080
# Number of worker processes
workers: 4
# Enable debug mode
debug: false
```

After:

```yaml
port: 8080
workers: 4 # matches the container CPU limit; more just context-switch
debug: false
```

`.env` files earn comments for provenance of non-secret values ("issued from the staging tenant") — never for the secret itself or hints at its value. JSON5/JSONC exist to be commented; the same value bar applies. Pure `.json` has no comment syntax — N/A.

## Workflows — GitHub Actions, GitLab CI, and kin

Step and job names are the primary documentation surface; a well-named step needs no comment. Comment only:

- Non-obvious ordering constraints ("must run before the cache restore — the key derives from the lockfile this step rewrites").
- Workarounds with an anchor (runner image bugs, upstream action issues).
- Pinned-version rationale (`# v4 drops node16 support; we still build on node16`, or the SHA-pin's provenance).
- Deliberate security posture (`# default token stays read-only; release job gets its own`).

Before:

```yaml
# Checkout the repository
- uses: actions/checkout@v4
# Set up Python
- uses: actions/setup-python@v5
```

After (nothing — both steps say what they are), or when there is something to say:

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0 # commit-range lint diffs against the PR base
```

## Infra — Dockerfile, Terraform, Kubernetes, Compose

Infra files encode cross-resource relationships the syntax cannot state. That is what earns comments:

- Invariants spanning resources ("this CIDR must not overlap the peered VPC").
- Ordering constraints ("layer order matters: deps before source, or every commit busts the cache").
- Security assumptions ("runs as non-root; the entrypoint chowns the volume first").
- Workarounds anchored to provider/tool issues.

Not: what each directive does (`FROM python:3.12  # use python 3.12 base image`), restated resource names, or per-attribute narration in Terraform blocks.

## Shell

Shell rewards comments precisely where it is least readable:

- The non-obvious flag (`sort -z  # NUL-delimited; filenames may contain newlines`).
- Traps and signal handling rationale.
- Portability constraints ("BSD sed — no `-i` without suffix").
- The reason for an unusual construct (`: "${VAR:=default}"`).

Not: a narration line above each pipeline stage. If a pipeline needs prose to follow, split it into named functions or intermediate variables first (readability first) — then see whether any comment is still needed.

## Migrations

A migration is read twice: at review, and at 3 a.m. when it went wrong. Comment for the second reader:

- The irreversible step, called out as such ("drops the column; the down-migration cannot restore the data").
- The invariant the data must satisfy before/after ("assumes no NULLs remain — backfill ran in the previous migration").
- Locking/duration expectations on large tables, when known.

Not: narrated DDL (`-- add index` above `CREATE INDEX`). The statement says it.

## Tests

Test names carry intent (`test_returns_empty_when_input_is_none`); comments restating intent duplicate the name. In tests:

- No comment restating what the test does.
- No arrange/act/assert dividers (`# arrange`, `# act`, `# assert`) — block structure already communicates the phases.
- Mock-setup explanation only when the *shape* of the mock is non-obvious (a partial mock pretending a remote service is half-up).
- Fixture explanation only when the fixture composes multiple sources or simulates a rare state.
- Docstrings on tests: project convention first; otherwise only when they add what the name cannot.

This section governs comments in tests only; testing strategy lives in the parent skill's `testing.md` reference.

## Markdown — and MDX, RST, AsciiDoc

Two flavors of fenced code, two rule sets:

- **Documentary snippets** — code shown to teach (tutorials, READMEs, concept docs). Didactic comments are allowed and often *are* the point: the comment carries the why the surrounding prose is building. Still banned: AI-narration markers, comments restating the adjacent line, bare TODOs, and references to "this PR"/"this change".
- **Copy-paste executable snippets** — commands, config samples, install steps. Treat the snippet as a standalone file of its language; the full rubric applies, because readers paste these into real files.

Beyond fences:

- **HTML comments** (`<!-- … -->`) — earn their place carrying editorial state the rendered page must not show (a genuinely tracked TODO with an owner, a template marker consumed by tooling). Not for narrating document structure the headings already show.
- **Frontmatter remarks** — YAML frontmatter follows the config rules above.
- **MDX** `{/* … */}` and **RST** `..` blocks — same dual-flavor logic as HTML comments in markdown.

## Notebooks (`.ipynb`)

Per cell type: code cells follow their language's rules; markdown cells follow the markdown rules; raw cells follow whatever format they hold. Narrative markdown cells are the notebook's documentary voice — prefer moving explanation there over stacking `#` narration inside code cells.
