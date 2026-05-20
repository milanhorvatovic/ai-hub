# testing-quality — scaffold templates

Test-runner and coverage configs for the `testing-quality` capability. Tailor to
the repo's framework; the CI step that runs them is scaffolded by ci-automation.

## Python — `pyproject.toml` (pytest + coverage)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"

[tool.coverage.run]
branch = true
source = ["<package>"]

[tool.coverage.report]
show_missing = true
# fail_under = 80   # uncomment to gate; pick a realistic threshold
```

Layout: put tests under `tests/`, named `test_*.py`.

## JS/TS — `vitest.config.ts`

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      // thresholds: { lines: 80 }   // uncomment to gate
    },
  },
});
```

Layout: co-locate `*.test.ts` next to source, or a `test/` tree.

## Coverage upload (optional) — `codecov.yml`

```yaml
coverage:
  status:
    project:
      default:
        target: auto
        threshold: 1%   # allow small dips, block large regressions
```
