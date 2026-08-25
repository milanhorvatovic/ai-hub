---
name: typescript
description: >
  Examines a TypeScript or JavaScript project's tooling and prescribes what is
  missing — reads tsconfig.json for strictness, package.json scripts, and the
  config files for biome, eslint, and prettier; establishes whether CI actually
  typechecks and lints; grades the distance to the typescript floor (strict
  tsc, one linter, one formatter); and scaffolds minimal configs and CI steps on
  confirmation. Flags the overlap this ecosystem produces most — two tools
  claiming one job. Never installs anything. Triggers on "is our tsconfig
  strict", "biome or eslint", "prettier and eslint are fighting", "add a
  typecheck step", or a TypeScript repository whose CI never runs tsc.
allowed-tools: Bash Read Grep Glob Write
---

# typescript capability

Audits a TypeScript or JavaScript project's toolchain configuration. Modes and their contracts come from `../../references/modes.md`; the bar is the typescript section of `../../references/tooling-floors.md`; grades are `../../references/diagnosis-grading.md`.

## Where the declarations live

| Tool | Config locations |
| --- | --- |
| `tsc` | `tsconfig.json`, `tsconfig.*.json`, and whatever they `extends` — including a package such as `@tsconfig/strictest` |
| `eslint` | `eslint.config.*` (flat config) always; `.eslintrc*` and `package.json` `eslintConfig` **only on a major that still reads them** — resolve the pinned version first, because the legacy format was made opt-in and then removed, so on a current major a repository carrying only `.eslintrc` is not configured, it is broken, and reporting it as configured hides the reason `eslint` refuses to start |
| `biome` | `biome.json`, `biome.jsonc` |
| `prettier` | `.prettierrc*`, `prettier.config.*`, `package.json` `prettier` |
| scripts | `package.json` `scripts` — the entry points CI and contributors actually call |
| module system | `package.json` `type`, `exports`, and `tsconfig`'s `module` / `moduleResolution` |

Read the declared `eslint` version alongside the config file rather than treating the file's presence as the answer; where the version cannot be resolved, that is `unknown` on the linter row rather than a satisfied one.

**An explicit selector outranks discovery here too**, and the table above lists only what discovery finds. `tsc --project`, `eslint --config`, `biome --config-path`, and `prettier --config` each name a config the tool will use whatever the conventional filenames say, so `eslint --config config/lint.mjs` is a configured, running linter that a discovery-only scan reports as undeclared — or, worse, as broken. Resolve each invocation's selector first, per call site, and fall through to the table only where none is given.

`extends` chains matter here more than in any other language: a `tsconfig.json` whose visible body sets nothing can still be strict through a base config, and a config that sets `"strict": true` can have it undone by a later `"strictNullChecks": false`. Resolve the chain before grading, and when a base config lives in a package the scan cannot read, grade the strictness row `unknown` with that reason rather than reading the visible file alone.

## What the scan reports

1. **Strictness** — the effective value of `strict` after the `extends` chain resolves, plus which of the three recommended extras are on. The effective value is the fact; the file it came from is the citation.
2. **Typecheck execution** — whether anything type-checks, which is a question about the resolved configuration rather than about a command's spelling. The compiler checks by default: `tsc --noEmit`, a bare `tsc` that also emits, and `tsc -b` over project references are all type checks, and only an explicit opt-out — `noCheck`, or a transpile-only pipeline — turns that off. So resolve the effective config for whatever the step invokes and look for the opt-out, rather than looking for `--noEmit` and calling everything else a gap.

   Bundlers need the same treatment and get assumed away more often. Most strip types without checking them, which is how a project builds cleanly every day with types nothing has verified — but a build configured with a type-checking plugin is a real check, and grading it a `gap` on the grounds that it is a bundler would be a false finding against a correctly wired project. Read the plugin configuration; where it cannot be resolved, that is `unknown`.

3. **Linter** — which one, one or several.
4. **Formatter** — which one, one or several, and whether the linter also carries formatting rules.
5. **Scripts** — what `package.json` exposes. A repository whose CI calls `npm run lint` is answered by reading that script, and a script named `lint` that runs a formatter is worth reporting as what it does rather than what it is called.

## Audit specifics

This ecosystem produces overlap more than absence, so the checks that pay off here are contradiction checks:

- **Two formatters over the same files.** `prettier` alongside `biome` is a `conflict` only once both are actually formatting, and overlapping on something. `biome` splits its roles — `linter.enabled` and `formatter.enabled` are separate switches — so a repository running `biome` as its linter and `prettier` as its formatter has made a coherent choice, and flagging it would be a false finding against a setup that works. Resolve the enabled roles first, then the file scopes: two formatters with disjoint `include` patterns are a division of labour, not a disagreement. What earns the grade is two tools whose enabled formatter roles both claim the same paths, because then the result depends on which ran last.
- **A linter carrying rules the formatter will undo.** `eslint` beside `prettier` is a `conflict` only for rules whose required output the formatter rewrites — quote style, spacing, semicolons — which produces the specific misery of a lint error the formatter reintroduces on save. Plenty of rules called stylistic are not in that set: import ordering, file length, naming, and anything else `prettier` does not format can coexist with it indefinitely. Resolve the enabled rules against what the formatter actually touches and grade only the overlap; the prescription is then to disable those rules, not the rule set they sit in.
- **`strict` defeated downstream.** A config that enables `strict` and then disables one of its constituent flags is not strict, and grading it from the `strict` line alone reports a project as satisfying the floor when it does not.
- **A build that is not a typecheck.** Where the only type-adjacent CI step is a bundler invocation, the typecheck row is a `gap` even though the project's types compile every day — nothing has ever checked them. Resolve first, per the scan row above: a step that reaches the compiler in any checking form satisfies this row, and only a step that never does is the gap.
- **A tool invoked without being declared, or declared without being fixed.** These are two steps and both must pass. `npx eslint` resolves the project's own installed binary when `eslint` is a declared dependency — that is the resolution order — so the command's spelling proves nothing either way, and a rule that reads `npx` as floating is wrong about every repository that declares its tools. But a declaration is not a pin: `"eslint": "^9"` with no tracked lock resolves a different version on the next clean install, so declaring the package fixes which tool runs and not which version of it. Judge fixity per `../../references/modes.md` — an exact constraint or a tracked lock — and grade `floating` when neither holds, whether the invocation says `npx` or not. Where the package is declared, `npx --no-install` is worth naming as a recommendation: it restricts resolution to the local copy and fails loudly when dependencies have not been installed rather than silently reaching past them.

## Scaffold

Templates: `references/scaffold-templates.md` in this directory.

Three rules specific to this language. First, a scaffolded linter must parse the language the project is written in — an eslint config carrying no TypeScript parser lints the JavaScript it can read and skips the `.ts` sources entirely, which satisfies the lint floor on paper while checking almost none of the code. Second, never scaffold a second tool into a job that already has one: the fix for a missing formatter in an `eslint`-only repo is to add `prettier` or migrate to `biome`, and the fix for a repo with both is to remove one — the audit says which, and the user picks. Third, respect the module system. A scaffolded config that assumes ESM in a CommonJS-locked project produces a config file the project's own loader cannot read, which is a worse first impression than the gap it closed.
