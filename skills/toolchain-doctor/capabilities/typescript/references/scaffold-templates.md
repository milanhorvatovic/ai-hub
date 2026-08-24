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

**Route B — `eslint` for lint, `prettier` for format.** Best fit for a project with an existing `eslint` rule set worth keeping.

```typescript
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import prettier from "eslint-config-prettier";

export default tseslint.config(
  js.configs.recommended,
  tseslint.configs.recommended,
  prettier,
);
```

The TypeScript config is not optional decoration here. `@eslint/js` alone brings no TypeScript parser, so `eslint .` walks the JavaScript it can parse and leaves the `.ts` and `.tsx` sources the project is actually written in unlinted — a scaffold that satisfies the lint floor on paper while checking almost none of the code. Add `typescript-eslint` as a devDependency alongside `eslint` when taking this route; a JavaScript-only repository is the one case that can drop it, and it should say so rather than inherit the omission.

`eslint-config-prettier` goes last. It exists to disable every rule that would fight the formatter, and a config that lists it before the rule sets it is meant to neutralize has it backwards — the later entry wins, so the stylistic rules come back on.

## The CI steps

The scripts come first, and CI calls them — not because it is tidier, but because a CI step invoking a tool directly runs a different thing from what contributors run, and one of the two will drift without anyone noticing.

```json
{
  "devDependencies": {
    "typescript": "<pinned>",
    "@biomejs/biome": "<pinned>"
  },
  "scripts": {
    "typecheck": "tsc --noEmit",
    "lint": "biome check ."
  }
}
```

```yaml
check:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@<40-char-sha> # <the version this sha is>
    - uses: actions/setup-node@<40-char-sha> # <the version this sha is>
      with:
        node-version: "<the project's version>"
        cache: "<npm, pnpm, or yarn>"
    - run: <the project's install command, resolving the tracked lock file>
    - run: npm run typecheck
    - run: npm run lint
```

The tools are devDependencies rather than `npx` invocations, and that is the whole difference between a pinned toolchain and a floating one. `npx eslint` in a CI step resolves whatever is current when nothing in the tree declares the package, so a rule added upstream arrives as a red build on an unrelated change — and it does it quietly, because the same command locally finds the installed copy and behaves. A declared dependency plus a tracked lock file is what fixes which version runs.

`typecheck` is its own script for a reason worth stating in the pull request that adds it: the build already compiles this code, and compiling is not checking. A bundler that strips types will build a project whose types have never once been verified, and the failure surfaces at runtime in a shape that looks nothing like a type error.

Keep the script names honest about what they invoke. A `lint` script that runs the formatter, or a `format` script that also lints, is the naming defect this audit reports on the next run — and with `biome` covering both jobs, one `lint` script is the accurate shape rather than two names for the same call.
