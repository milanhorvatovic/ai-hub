# licensing — scaffold snippets

Small reusable pieces for the `licensing` capability's scaffold mode. The full `LICENSE` text itself is fetched canonically (`gh api /licenses/{spdx} --jq .body`) rather than templated here — only fill the `[year]` / `[fullname]` placeholders.

## Per-file SPDX header

Prepend to source files when the repo opts into per-file headers (REUSE-style). Use the comment syntax of the file's language; keep it as the first lines.

```text
SPDX-FileCopyrightText: <year> <holder>
SPDX-License-Identifier: <SPDX-id>
```

Language comment forms:

- C / C++ / Go / Rust / Java / TS / JS: `// SPDX-License-Identifier: <id>`
- Python / Ruby / Shell / YAML: `# SPDX-License-Identifier: <id>`
- HTML / XML / Markdown: `<!-- SPDX-License-Identifier: <id> -->`

## Dual-license "at your option" notice

Add to `README` when the repo ships `LICENSE-MIT` + `LICENSE-APACHE`:

```markdown
## License

Licensed under either of

- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE))
- MIT license ([LICENSE-MIT](LICENSE-MIT))

at your option. Unless you explicitly state otherwise, any contribution
intentionally submitted for inclusion in this work shall be dual licensed as
above, without any additional terms or conditions.
```
