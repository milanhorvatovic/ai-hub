# documentation — scaffold templates

Documentation skeletons for the `documentation` capability. Fill headings from
the repo's reality; leave prose placeholders for the maintainer. Don't invent
feature claims.

## `README.md`

```markdown
# <project>

<One sentence: what it is and who it's for.>

[badges: build · version · license]

## Install

```sh
<install command>
```

## Usage

```sh
<minimal runnable example>
```

## Configuration

<Key options / environment variables, if any.>

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

<SPDX id> — see [LICENSE](LICENSE).
```

## `AGENTS.md` (house-style canonical agent instructions)

```markdown
# Agent instructions

## Project
<One-paragraph orientation: what this repo is and its layout.>

## Setup & tests
- Setup: `<setup command>`
- Test: `<test command>`
- Lint: `<lint command>`

## Conventions
- <Commit / PR / branch conventions, or a pointer to CONTRIBUTING.>
- <Anything an agent must not do.>
```

> Point `CLAUDE.md` and `.github/copilot-instructions.md` at this file rather
> than duplicating it, e.g. "See [AGENTS.md](AGENTS.md)."

## ADR — `docs/adr/0001-record-architecture-decisions.md`

```markdown
# 1. Record architecture decisions

Date: YYYY-MM-DD

## Status
Accepted

## Context
<What forces are at play, why a decision is needed.>

## Decision
<The decision made.>

## Consequences
<Trade-offs and follow-on effects.>
```
