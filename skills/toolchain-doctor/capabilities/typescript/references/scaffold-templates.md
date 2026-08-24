# typescript — scaffold templates

Shapes to fill in from what the scan found. Placeholders in angle brackets are values the scan already established.

## Strictness in `tsconfig.json`

The floor is `strict`. The extras below it are worth enabling once a project is healthy enough to absorb them, and they are proposed as their own patch — turning them all on at once in an existing codebase produces a diff nobody can review.

```json
{
  "compilerOptions": {
    "strict": true,
    "module": "<the project's existing module setting>",
    "moduleResolution": "<the project's existing resolution setting>"
  },
  "include": ["<the source directory>"]
}
```

The three extras go in a **second** patch, offered after the first lands:

```json
{
  "compilerOptions": {
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noFallthroughCasesInSwitch": true
  }
}
```

Separating them is the whole point rather than tidiness: each of the three produces its own class of error across an existing codebase, and a single scaffold enabling all four at once yields exactly the unreviewable diff this section warns against. A template that bundled them would be advising one thing and doing another.

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

The dependency and script blocks come from whichever route the audit picked, not from a default. The `typescript` dependency and the `typecheck` script below belong to a project that has TypeScript in it: where the lane ran on a JavaScript-only repository and marked the compiler rows `N/A`, they come out, because scaffolding a compiler into a project that has no TypeScript adds a tool nothing asked for and a script that checks nothing. Route A:

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

Route B, where the format check is a separate script because the two tools are separate:

```json
{
  "devDependencies": {
    "typescript": "<pinned>",
    "eslint": "<pinned>",
    "typescript-eslint": "<pinned>",
    "prettier": "<pinned>",
    "eslint-config-prettier": "<pinned>"
  },
  "scripts": {
    "typecheck": "tsc --noEmit",
    "lint": "eslint .",
    "format:check": "prettier --check ."
  }
}
```

Taking Route A's block into a Route B repository is the mistake this split exists to prevent: it adds the second linter the capability forbids and drops the format check entirely, so the scaffold would both create a `conflict` and leave a floor row unmet.

The JavaScript-only variant is either block with the compiler removed — no `typescript` dependency, no `typecheck` script, no `tsc` step — and, on Route B, no `typescript-eslint` either. What remains is the lint and format rows, which are the only ones that applied to that repository in the first place.

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
    - run: npm run format:check # Route B only; Route A's lint script covers both
```

What fixes the version is an exact constraint or the tracked lock file, not the shape of the invocation and not the declaration on its own. `npx eslint` resolves the project's own installed copy whenever `eslint` is a declared dependency, so the command is not the problem; a caret range with no committed lock is, because the next clean install can resolve a different version with nothing in the repository having changed. Pin the devDependencies and commit the lock, then reach them however the project prefers. Where a repository does use `npx`, `npx --no-install` is the form worth recommending: it restricts resolution to the local copy and fails loudly when dependencies have not been installed, instead of quietly falling back to whatever is on `PATH`.

`typecheck` is its own script for a reason worth stating in the pull request that adds it: the build already compiles this code, and compiling is not checking. A bundler that strips types will build a project whose types have never once been verified, and the failure surfaces at runtime in a shape that looks nothing like a type error.

Keep the script names honest about what they invoke. A `lint` script that runs the formatter, or a `format` script that also lints, is the naming defect this audit reports on the next run — and with `biome` covering both jobs, one `lint` script is the accurate shape rather than two names for the same call.
