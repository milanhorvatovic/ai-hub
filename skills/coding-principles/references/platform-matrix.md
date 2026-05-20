# Platform / OS matrix

Language-agnostic operating-system differences that bite cross-platform code. Load when the code under change touches the filesystem, processes, shells, signals, paths, or anything that behaves differently across Linux / macOS / Windows. Applies across all language capabilities — each language's *handling* of these concerns is noted at the bottom.

The rule: **don't assume the developer's OS is the deployment OS.** Code written on macOS often runs on Linux in production and is edited on Windows by a teammate.

## The matrix

| Concern | Linux | macOS | Windows | Cross-platform rule |
| ------- | ----- | ----- | ------- | ------------------- |
| **Path separator** | `/` | `/` | `\` (and `/` mostly works) | Never hardcode `/` or `\` — use the language's path API |
| **Path list separator** (PATH) | `:` | `:` | `;` | Use the language's constant (`os.pathsep`, `path.delimiter`) |
| **Line endings** | LF (`\n`) | LF (`\n`) | CRLF (`\r\n`) | Open text mode aware; normalize on read; `.gitattributes` for the repo |
| **Filesystem case** | case-sensitive (ext4) | case-**insensitive** (APFS default, but preserving) | case-insensitive (NTFS default) | Don't rely on case to distinguish files; `Foo.txt` and `foo.txt` may collide |
| **Max path length** | ~4096 | ~1024 | 260 (legacy; opt-in long paths) | Keep paths short; don't assume deep nesting works on Windows |
| **Symlinks** | yes | yes | yes (needs privilege/dev mode) | Don't assume symlink creation succeeds on Windows |
| **Default shell** | `bash` / `dash` (`sh`) | `zsh` (interactive), `bash` 3.2 at `/bin/bash` | `cmd` / PowerShell; no POSIX shell by default | Don't shell out to `bash` and assume it exists; see bash capability |
| **Home dir env** | `$HOME` | `$HOME` | `%USERPROFILE%` (`$HOME` in some shells) | Use the language's home-dir API, not `$HOME` directly |
| **Temp dir** | `/tmp`, `$TMPDIR` | `$TMPDIR` (per-user, long path) | `%TEMP%` | Use the language's tempfile API; never hardcode `/tmp` |
| **Signals** | full POSIX (`SIGTERM`, `SIGKILL`, `SIGHUP`, ...) | full POSIX | limited; `SIGTERM`/`SIGKILL` emulated, no `SIGHUP`/`SIGUSR*` | Don't rely on POSIX-only signals for cross-platform services |
| **Process model** | `fork` + `exec` | `fork` + `exec` | `CreateProcess` (no `fork`) | `fork`-based code (some multiprocessing) behaves differently on Windows |
| **Executable bit** | yes (`chmod +x`) | yes | no (extension-based: `.exe`, `.bat`) | Don't rely on the executable bit to mark scripts on Windows |
| **Coreutils flavor** | GNU | BSD (different flags!) | neither (or Git-Bash GNU) | The #1 bash portability trap — see below |
| **`/dev/null`** | `/dev/null` | `/dev/null` | `NUL` | Use the language's null-device API |
| **Arch** | x86_64, aarch64 | aarch64 (Apple Silicon), x86_64 | x86_64, aarch64 | Don't assume x86; native deps need per-arch builds |

## GNU vs BSD coreutils (the macOS/Linux trap)

macOS ships **BSD** versions of `sed`, `awk`, `date`, `find`, `xargs`, `readlink`, `stat`, `cp`; Linux ships **GNU** versions. Common divergences:

| Command | GNU (Linux) | BSD (macOS) |
| ------- | ----------- | ----------- |
| `sed -i` | `sed -i 's/a/b/' f` | `sed -i '' 's/a/b/' f` (needs the empty backup arg) |
| `date` | `date -d '1 day ago'` | `date -v-1d` |
| `readlink -f` | works | not available (use `realpath`, or `grealpath`) |
| `stat` | `stat -c '%s' f` | `stat -f '%z' f` |
| `find -printf` | works | not available |
| `xargs -r` | works | no `-r` (BSD doesn't run on empty input anyway) |
| `cp --reflink` | works | not available |

Strategies:
- **Write POSIX-only** when portability matters — avoid the divergent flags entirely.
- **Detect and branch**: `if sed --version >/dev/null 2>&1; then GNU; else BSD; fi`.
- **Require GNU coreutils** explicitly (install via `brew install coreutils`, use `gsed`/`gdate`/`grealpath`), and document it.
- **Don't write a portable shim** that tip-toes around both — past a couple of divergences, move to Python (whose stdlib is OS-normalized).

## Testing across OS

- **CI matrix** — run the test suite on `ubuntu-latest`, `macos-latest`, and `windows-latest` (GitHub Actions matrix, or equivalent) for any code that ships cross-platform. A green test on one OS proves nothing about the others.
- **The CRLF trap in CI** — set `.gitattributes` (`* text=auto`, `*.sh text eol=lf`) so checkout doesn't rewrite line endings and break shell scripts / snapshot tests on Windows.
- **Path assertions in tests** — don't assert on hardcoded `/`-joined paths; build expected paths with the same path API the code uses.

## Per-language handling

How each capability normalizes these concerns (load the language capability for detail):

- **Bash** (`../capabilities/bash/`) — most exposed to OS differences. GNU vs BSD coreutils, `#!/usr/bin/env bash` (not `/bin/bash` — macOS bash is 3.2), `mktemp` syntax differs. When portability gets hard, the bash capability's "when to leave bash" rule points at Python.
- **Python** (`../capabilities/python/`) — `pathlib.Path` normalizes separators; `os.sep` / `os.pathsep` / `os.linesep` for raw access; `sys.platform` / `platform.system()` for branching; `tempfile` for temp dirs; `subprocess` with list-form argv (not `shell=True`) avoids shell-availability issues.
- **TypeScript/Node** (`../capabilities/typescript/`) — `node:path` (`path.sep`, `path.join`, `path.delimiter`); `os.EOL` for line endings; `process.platform` (`'linux'` / `'darwin'` / `'win32'`) for branching; `os.tmpdir()`; `os.homedir()`.
- **Rust** (`../capabilities/rust/`) — `std::path::{Path, PathBuf}` (separator-agnostic, use `.join()` not string concat); `std::env::consts::OS` and `cfg!(target_os = "...")` / `#[cfg(...)]` for conditional compilation; `std::env::temp_dir()`; `MAIN_SEPARATOR`.

## Principle alignment

OS branching is a **boundary** concern (principle 19 / pure-impure separation): detect the platform once at the edge (the imperative shell), pass the resolved behavior inward; don't sprinkle `if platform == ...` through business logic. Where the language's path/temp/env API already normalizes a difference, use it — that's the "trust the framework" stance (principle 5), not reinventing normalization.
