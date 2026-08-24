# typescript — scaffold templates

Shapes to fill in from what the scan found. Placeholders in angle brackets are values the scan already established.

## Strictness in `tsconfig.json`

The floor is `strict`. The extras below it are the ones worth enabling once a project is healthy enough to absorb them — propose them separately from `strict` itself, because turning them all on at once in an existing codebase produces a diff nobody can review.

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noFallthroughCasesInSwitch": true,
    "module": "<the project's existing module setting>",
    "moduleResolution": "<the project's existing resolution setting>"
  },
  "include": ["<the source directory>"]
}
```

Where the project already extends a shared base, add the options to the project's own config rather than editing the base — a base config is usually shared with packages this audit never looked at.

## One linter and one formatter

Two routes, and the audit picks between them from what the repository already has rather than from preference.

**Route A — `biome`, one tool for both jobs.** Best fit for a project adopting tooling fresh, or one already carrying `biome` for part of the work.

```json
{
  "linter": { "enabled": true, "rules": { "recommended": true } },
  "formatter": {
    "enabled": true,
    "indentStyle": "<space or tab, matching the project>",
    "indentWidth": <the project's width>
  }
}
```

**Route B — `eslint` for lint, `prettier` for format.** Best fit for a project with an existing `eslint` rule set worth keeping. The load-bearing piece is turning off `eslint`'s stylistic rules so the two tools stop disagreeing:

```typescript
import js from "@eslint/js";
import prettier from "eslint-config-prettier";

export default [js.configs.recommended, prettier];
```

`eslint-config-prettier` goes last. It exists to disable every rule that would fight the formatter, and a config that lists it before the rule sets it is meant to neutralize has it backwards — the later entry wins, so the stylistic rules come back on.

## The CI steps

```yaml
check:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@<40-char-sha> # v5
    - uses: actions/setup-node@<40-char-sha> # v6
      with:
        node-version: "<the project's version>"
        cache: "<npm, pnpm, or yarn>"
    - run: <the project's install command>
    - run: npx tsc --noEmit
    - run: <npx biome check . | npx eslint . && npx prettier --check .>
```

`tsc --noEmit` is its own step for a reason worth stating in the pull request that adds it: the build already compiles this code, and compiling is not checking. A bundler that strips types will build a project whose types have never once been verified, and the failure surfaces at runtime in a shape that looks nothing like a type error.

Where the repository routes through `package.json` scripts, add the commands there and have CI call the scripts, so contributors and CI run the same thing:

```json
{
  "scripts": {
    "typecheck": "tsc --noEmit",
    "lint": "biome check .",
    "format:check": "biome check ."
  }
}
```

A `lint` script that runs the formatter, or a `format` script that also lints, is the naming defect this audit reports on the next run — keep the script names honest about what they invoke.
