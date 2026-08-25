# typescript — scaffold templates

Shapes to fill in from what the scan found. Placeholders in angle brackets are values the scan already established.

## Strictness in `tsconfig.json`

The floor is `strict`. The extras below it are worth enabling once a project is healthy enough to absorb them, and they are proposed as their own patch — turning them all on at once in an existing codebase produces a diff nobody can review.

```json
{
  "compilerOptions": {
    "strict": true
  },
  "include": ["<the source directory>"]
}
```

The three extras are **not** scaffolded. They are recommendations, no floor row asks for them, and no finding produces them — so writing them, even as a follow-up patch, is the scaffold choosing a policy the audit never called for. Name them in the report as options; write them only when the user asks for them by name, and then as their own patch:

```json
{
  "compilerOptions": {
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noFallthroughCasesInSwitch": true
  }
}
```

Keeping them separate is the whole point rather than tidiness: each produces its own class of error across an existing codebase, and enabling all four at once yields a diff nobody can review.

Module settings are deliberately absent. The common case for this template is a project with no `tsconfig.json` at all, where there is no existing `module` or `moduleResolution` to carry over and the rule against inventing policy forbids picking one — a placeholder nobody can fill is worse than an omission, because it ships to the user as a blank to guess at. Where the project has a config already, its settings stay untouched; where it has none, ask which module system the project targets rather than assuming.

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

**Route B — `eslint` for lint, `prettier` for format.** Best fit for a project with an existing `eslint` rule set worth keeping. Write it as **`eslint.config.mjs`**: the config below uses ESM imports, and scaffolded as the conventional `eslint.config.js` into a package that has not declared `"type": "module"`, Node parses it as CommonJS and ESLint fails before it lints anything. The `.mjs` extension settles that without touching the package's module type, which is the module-system failure this capability tells the audit to look for and would otherwise have created.

```typescript
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import prettier from "eslint-config-prettier";

export default tseslint.config(
  js.configs.recommended,
  tseslint.configs.recommended,
  {
    files: ["**/*.{js,cjs,mjs,jsx,ts,cts,mts,tsx}"],
    languageOptions: { parserOptions: { ecmaFeatures: { jsx: true } } },
  },
  prettier,
);
```

The `files` entry is not optional here for the same reason it is not on the JavaScript route: this lane accepts `*.jsx` and `*.tsx` at stage 0, and flat config's default matching covers only `.js`, `.cjs`, and `.mjs` with JSX parsing off. The `typescript-eslint` presets add the `.ts` and `.tsx` extensions but not `.jsx`, so a mixed TypeScript-and-JSX project scaffolded without this block would have its `.jsx` sources walked past while the job reported success — the same unlinted-source failure the TypeScript parser was added to prevent, arriving through the one extension the presets do not claim.

Every package the config imports is declared, `@eslint/js` included. Relying on it arriving transitively through `eslint` works under a flat `node_modules` and fails under a strict package manager, where a config cannot resolve what the project does not declare — so the scaffold that lints cleanly on one machine is unloadable on another.

The TypeScript config is not optional decoration here. `@eslint/js` alone brings no TypeScript parser, so `eslint .` walks the JavaScript it can parse and leaves the `.ts` and `.tsx` sources the project is actually written in unlinted — a scaffold that satisfies the lint floor on paper while checking almost none of the code. Add `typescript-eslint` as a devDependency alongside `eslint` when taking this route; a JavaScript-only repository is the one case that can drop it, and it should say so rather than inherit the omission.

`eslint-config-prettier` goes last. It exists to disable every rule that would fight the formatter, and a config that lists it before the rule sets it is meant to neutralize has it backwards — the later entry wins, so the stylistic rules come back on.

## The CI steps

The scripts come first, and CI calls them — not because it is tidier, but because a CI step invoking a tool directly runs a different thing from what contributors run, and one of the two will drift without anyone noticing.

**Corepack is not the mechanism to reach for in that slot**, which is worth saying because it is the obvious one. `corepack enable` installs shims beside whichever Node is current when it runs, so a later `setup-node` selecting a different Node hides them — and moving it after `setup-node` does not work either, because the cache input needs the manager to exist by then. Recent Node has also stopped bundling Corepack, so the step's availability depends on the runtime version the job has not selected yet. A pinned setup action for the manager avoids the whole ordering question: it provides the manager itself, before and independently of Node. Where a project genuinely wants Corepack, it belongs in a sequence built around that constraint rather than dropped into this one.

`actions/setup-node` supplies Node and `npm` and nothing further. Its `cache` input names a manager's store to restore; it does not install that manager, so a scaffold adapted to pnpm or a modern yarn relies on whatever happens to be global on the runner, and one adapted to bun has no path through `setup-node` at all. Bootstrap first, then cache — that order is the constraint, because the cache step resolves a store the manager has to be present to describe.

The script runner is the project's own, for the same reason the install command is: a template that discovers the package manager for setup and then hardcodes `npm run` contradicts itself, and breaks outright on a setup like Yarn Plug'n'Play that requires its own runner to resolve anything.

The dependency and script blocks come from whichever route the audit picked, not from a default. The `typescript` dependency and the `typecheck` script below belong to a project that has TypeScript in it: where the lane ran on a JavaScript-only repository and marked the compiler rows `N/A`, they come out, because scaffolding a compiler into a project that has no TypeScript adds a tool nothing asked for and a script that checks nothing. Route A:

```json
{
  "devDependencies": {
    "typescript": "<pinned>",
    "@biomejs/biome": "<pinned>"
  },
  "scripts": {
    "typecheck": "tsc --noEmit",
    "check": "biome check ."
  }
}
```

Route B, where the format check is a separate script because the two tools are separate:

```json
{
  "devDependencies": {
    "typescript": "<pinned>",
    "eslint": "<pinned>",
    "@eslint/js": "<pinned>",
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

The JavaScript-only variant is either block with the compiler removed — no `typescript` dependency, no `typecheck` script, no `tsc` step. What remains is the lint and format rows, which are the only ones that applied to that repository in the first place.

The `files` entry is there because this lane accepts `*.jsx` at stage 0 and the linter does not: eslint's default matching covers `.js`, `.cjs`, and `.mjs`, and JSX parsing is off unless something turns it on — so a JSX project scaffolded without it would have its actual sources skipped while the job reported success, which is the same unlinted-source failure the TypeScript route was corrected for.

On Route B the config file changes with it, and dropping the dependency alone is not enough: the flat config above imports `typescript-eslint` and calls `tseslint.config(...)`, so removing the package while leaving those lines produces a config that cannot load. The JavaScript form is the plain array:

```typescript
import js from "@eslint/js";
import prettier from "eslint-config-prettier";

export default [
  js.configs.recommended,
  {
    files: ["**/*.{js,cjs,mjs,jsx}"],
    languageOptions: { parserOptions: { ecmaFeatures: { jsx: true } } },
  },
  prettier,
];
```

```yaml
on:
  pull_request:
  push:
    branches: [<the default branch>]

permissions:
  contents: read

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<40-char-sha> # <the version this sha is>
      # Bootstrap the package manager BEFORE setup-node: the cache input below
      # resolves the manager's store and needs the manager to already exist.
      # npm needs nothing here. pnpm and yarn use their own pinned setup action,
      # which installs the manager independently of whichever Node follows.
      # bun uses its own setup action and does not use setup-node at all.
      - name: bootstrap <the project's package manager>
        uses: <that manager's pinned setup action>@<40-char-sha> # <the version this sha is>
      - uses: actions/setup-node@<40-char-sha> # <the version this sha is>
        with:
          node-version: "<the project's version>"
          cache: "<npm, pnpm, or yarn>"
      - run: <the project's install command, resolving the tracked lock file>
      - run: <the project's script runner> typecheck
      # Route A: one script covers both jobs.
      - run: <the project's script runner> check
      # Route B replaces the step above with these two.
      - run: <the project's script runner> lint
      - run: <the project's script runner> format:check
```

The trigger and the permission floor are part of the scaffold, not context around it. A bare job fragment dropped into a push-only workflow still grades `wiring` on the next audit — it runs, and not where review happens — so a scaffold that omitted `on: pull_request` would not close the finding it was written for. And a job that runs repository code inherits whatever token permissions the repository defaults to, which on an older repository is write; `contents: read` is the floor, raised only for a scope the job demonstrably needs.

What fixes the version is an exact constraint or the tracked lock file that a completed install has consumed — not the shape of the invocation, and not the declaration on its own. `npx eslint` resolves the project's own installed copy only once that dependency is installed; a declaration without `node_modules` present does not pin anything, because `npx` fetches a temporary copy rather than failing. So the command is not the problem; a caret range with no committed lock is, and so is a committed lock the workflow never installs from. Pin the devDependencies, commit the lock, install from it, then reach the binaries however the project prefers. Where a repository does use `npx`, `npx --no-install` is the form worth recommending: it restricts resolution to the local copy and fails loudly when dependencies have not been installed, instead of quietly falling back to whatever is on `PATH`.

`typecheck` is its own script for a reason worth stating in the pull request that adds it: the build already compiles this code, and compiling is not checking. A bundler that strips types will build a project whose types have never once been verified, and the failure surfaces at runtime in a shape that looks nothing like a type error.

Route B needs two steps and not one with two names after it: a package manager reads `run lint format:check` as the `lint` script called with an argument, so the format gate would never fire and the job would stay green without it. One step per script.

Keep the script names honest about what they invoke, which is why Route A's script is `check` and not `lint`. `biome check` lints and formats, so calling it `lint` is precisely the naming defect this audit reports on the next run — the scaffold would have created the finding it exists to close. Route B keeps `lint` and `format:check` separate because there the two jobs really are two tools.
