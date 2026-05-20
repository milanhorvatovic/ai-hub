# repo-infrastructure — scaffold templates

Baseline plumbing files for the `repo-infrastructure` capability. The `.gitignore` itself is fetched per-stack (`gh api /gitignore/templates/{name}`) rather than templated here. Tailor these to the languages present before writing.

## `.gitattributes`

```gitattributes
# Normalize line endings on checkin; check out native
* text=auto

# Force LF for scripts and configs
*.sh   text eol=lf
*.yml  text eol=lf
*.yaml text eol=lf

# Mark generated / vendored paths so they don't skew language stats or diffs
dist/**     linguist-generated=true
vendor/**   linguist-vendored=true

# Treat common binaries as binary
*.png binary
*.jpg binary
*.pdf binary
```

## `.editorconfig`

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
indent_style = space
indent_size = 2

[*.py]
indent_size = 4

[*.md]
trim_trailing_whitespace = false

[Makefile]
indent_style = tab
```

## `.mailmap` (optional)

Normalizes contributor names/emails in `git shortlog` and `git log`.

```text
Proper Name <proper@email> <old@email>
Proper Name <proper@email> Old Name <old@email>
```
