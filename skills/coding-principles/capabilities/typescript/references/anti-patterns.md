# TypeScript — anti-patterns

Language-specific anti-patterns and smells. Complements the language-agnostic `../../../references/smells.md`. The positive rules these anti-patterns negate live in `../capability.md`.

- **`enum`** — produces runtime objects, has odd reverse-mapping behavior. Prefer `as const` objects or string-literal unions.
- **`namespace`** — legacy, use modules.
- **`@ts-ignore` without a comment** — banned. `@ts-expect-error // reason: ...` is acceptable temporarily.
- **`Function` type** — too loose. Use a specific signature `(x: T) => U`.
- **`object` type** — almost never what you want; use `Record<string, unknown>` or a real shape.
- **`null | undefined` mixing** — pick one for "absent." Most modern TS picks `undefined`.
- **Returning `Promise<any>`** — defeats async typing. Annotate the resolved type.
- **`new Date()` in business logic** — inject a clock. Real dates make tests flaky.
