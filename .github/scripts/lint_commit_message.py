#!/usr/bin/env python3
"""Lint a commit message (or PR body) against the repo's commit-style rules.

This repo squash-merges with the COMMIT_MESSAGES setting, so branch-commit bodies are
concatenated into the merge commit on main — commit text is permanent public history.
This script is the single source of truth behind every enforcement layer: the CI job in
change-intent.yml, the opt-in `.githooks/commit-msg` hook, and the unit tests. It checks
the deterministic subset of the conventions declared in AGENTS.md and CONTRIBUTING.md:

- **Subject** — a Conventional Commit with the PR-title vocabulary (reused from the
  sibling `validate_pr_title.py`, one vocabulary for both gates), <=72 chars, no
  trailing period. Git-generated `Revert "..."` / `Reapply "..."` subjects pass, and
  `fixup!` / `squash!` / `amend!` rebase prefixes are stripped before validation.
- **Trailers** — no attribution trailers (`Co-Authored-By`, `Signed-off-by`, ...);
  commits are author-only. `Release-As:` (a release-please control footer) and
  git-generated `(cherry picked from ...)` lines pass because they are not on the
  attribution denylist.
- **Body shape** — every blank-line-separated paragraph is exactly one source line
  (the Prettier `proseWrap: never` house rule applied to commit text); list lines
  (with their indented continuations), tab/4-space indented blocks, fenced blocks,
  and trailer/footer blocks are exempt.
- **Plan-ref hygiene** — no private planning paths or track codes; public text
  describes the change on its own terms. The denylist is deliberately narrow —
  widen it only when a real leak slips past, never preemptively.

Imperative mood and why-vs-what remain judgment calls for review — a gate that cries
wolf teaches everyone `--no-verify`, so only deterministic checks live here.

Git's auto-generated merge subjects skip the subject check — the hook must not block
`git merge` / `git pull` — while their bodies are still linted (empty or indented
conflict lists in practice, so real merges pass). CI additionally excludes true merge
commits by parent count via `--no-merges`.

The message is read from a file path or stdin (`-`), never from a shell-interpolated
argument, because commit text is attacker-controllable on fork PRs. `--strip-comments`
applies git's editor cleanup (drop `#` lines and the scissors block) and belongs only
to the commit-msg hook, which lints the pre-cleanup editor file; CI lints committed
text verbatim, where a `#`-prefixed line is real content. The bot skip (Dependabot
bodies are hard-wrapped by design) fires only when BOTH `--author-email` and
`--pr-author-login` look bot-authored — the email alone is forgeable, so omitting the
login fails closed and lints. Even then the skip is a formatting convenience, not a
security boundary.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def _load_sibling(name: str):
    """Load a sibling script by file path — `.github/scripts/` is not a package."""
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_title = _load_sibling("validate_pr_title")

# Attribution trailer keys (lowercase). Control footers like Release-As are allowed
# simply by not being listed here.
ATTRIBUTION_TRAILERS = {
    "co-authored-by",
    "co-developed-by",
    "signed-off-by",
    "reviewed-by",
    "acked-by",
    "tested-by",
    "reported-by",
    "suggested-by",
    "helped-by",
    "mentored-by",
}

# Private planning markers: archive paths, plus a word-boundary denylist of the actual
# track-code series (a broad [A-Z]\d+ would false-positive on ordinary vocabulary).
PLAN_REF_PATTERNS = [
    re.compile(r"docs/repo/tickets/"),
    re.compile(r"skills-audit-"),
    re.compile(r"ai-hub-planning"),
    re.compile(r"\b[RSGCOD]\d\b"),
]

# Bot author-email patterns, case-insensitive regexes vendored here so the gate stays
# self-contained (the fuller catalog lives in maintainer tooling, not repo machinery).
# `noreply@github.com` alone is the web editor — a real user — and is deliberately absent.
BOT_AUTHOR_EMAIL_PATTERNS = [
    r"\[bot\]@users\.noreply\.github\.com$",
    r"@bots\.noreply\.github\.com$",
    r"^bot@",
    r"-bot@",
    r"-ci@",
    r"^ci@",
]

BOT_LOGIN_PATTERNS = [
    r"\[bot\]$",
    r"-bot$",
]

FIXUP_PREFIX = re.compile(r"^(?:(?:fixup|squash|amend)! )+")
REVERT_SUBJECT = re.compile(r'^(?:Revert|Reapply) ".+"$')
# Git's auto-generated merge subjects only — a hand-written subject that merely
# starts with "Merge" still gets the Conventional-Commit check.
MERGE_SUBJECT = re.compile(r"^Merge (?:branch(?:es)? |remote-tracking branch |tag |commit |pull request #)")
TRAILER_KEY = re.compile(r"([A-Za-z][A-Za-z-]*)\s*:")
TRAILER_LINE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*:\s+\S")
CHERRY_PICK_LINE = re.compile(r"^\(cherry picked from commit [0-9a-fA-F]{7,40}\)$")
ISSUE_REF_LINE = re.compile(r"^(?:Close[sd]?|Fix(?:es|ed)?|Resolve[sd]?|Refs?) #\d+", re.IGNORECASE)
LIST_LINE = re.compile(r"^\s*(?:[-*+]|\d{1,3}[.)])\s+")
# Tab or 4-space indent — the markdown/git convention for preformatted blocks
# (code excerpts, conflict lists). A 1-3 space indent is NOT a block, so wrapped
# prose cannot slip past the one-line-per-paragraph rule by light indentation.
INDENTED_BLOCK_LINE = re.compile(r"^(?:\t| {4})")
FENCE_LINE = re.compile(r"^\s*(?:```|~~~)")
SCISSORS_LINE = re.compile(r"^# -+ >8 -+")


def strip_comments(text: str) -> str:
    """Drop `#` comment lines and everything below a scissors line, like git's cleanup."""
    lines = []
    for line in text.splitlines():
        if SCISSORS_LINE.match(line):
            break
        if line.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines).strip("\n")


def is_bot_author(email: str) -> bool:
    return any(re.search(pattern, email, re.IGNORECASE) for pattern in BOT_AUTHOR_EMAIL_PATTERNS)


def is_bot_login(login: str) -> bool:
    return any(re.search(pattern, login, re.IGNORECASE) for pattern in BOT_LOGIN_PATTERNS)


def _split_fenced(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    """Return (non-fenced lines, blank-line-separated paragraphs of them).

    Fenced blocks are exempt from the shape and trailer checks; a fence boundary also
    terminates the surrounding paragraph, so prose around a fence stays one-line-checked.
    """
    visible: list[str] = []
    paragraphs: list[list[str]] = []
    current: list[str] = []
    in_fence = False
    for line in lines:
        if FENCE_LINE.match(line):
            if current:
                paragraphs.append(current)
                current = []
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        visible.append(line)
        if line.strip():
            current.append(line)
        elif current:
            paragraphs.append(current)
            current = []
    if current:
        paragraphs.append(current)
    return visible, paragraphs


def _is_footer_block(paragraph: list[str]) -> bool:
    """A paragraph of trailers, issue refs, and cherry-pick lines.

    The first line must be one of those outright, and an indented line is accepted
    only directly under a trailer line, as its folded continuation (git's own
    semantics — issue refs and cherry-pick lines do not fold). Wrapped prose can
    therefore neither open a fake footer nor hide inside a real one.
    """
    first, *rest = paragraph
    if not (TRAILER_LINE.match(first) or CHERRY_PICK_LINE.match(first) or ISSUE_REF_LINE.match(first)):
        return False
    can_fold = TRAILER_LINE.match(first) is not None
    for line in rest:
        if TRAILER_LINE.match(line):
            can_fold = True
        elif CHERRY_PICK_LINE.match(line) or ISSUE_REF_LINE.match(line):
            can_fold = False
        elif not (can_fold and line[:1].isspace()):
            return False
    return True


def _subject_errors(subject: str, skills: set[str]) -> list[str]:
    subject = FIXUP_PREFIX.sub("", subject)
    if REVERT_SUBJECT.match(subject):
        return []
    return _title.validate(subject, skills, noun="subject")


def _body_shape_errors(paragraphs: list[list[str]]) -> list[str]:
    errors = []
    for paragraph in paragraphs:
        if _is_footer_block(paragraph):
            continue
        in_list = LIST_LINE.match(paragraph[0]) is not None
        for line in paragraph[1:]:
            if LIST_LINE.match(line):
                in_list = True
                continue
            # Indented continuations belong to list items only; outside a list an
            # indented line must be a real preformatted block (tab / 4 spaces), so
            # lightly indenting wrapped prose does not dodge the check.
            if in_list and line[:1].isspace():
                continue
            if INDENTED_BLOCK_LINE.match(line):
                continue
            errors.append(
                f"hard-wrapped paragraph: {line!r} continues the previous line — "
                "write each paragraph as one source line and let it wrap"
            )
            break
    return errors


def _attribution_errors(lines: list[str]) -> list[str]:
    errors = []
    for line in lines:
        match = TRAILER_KEY.match(line.strip())
        if match and match.group(1).lower() in ATTRIBUTION_TRAILERS:
            errors.append(
                f"attribution trailer {match.group(1)!r} — commits are author-only; drop it"
            )
    return errors


def _plan_ref_errors(text: str) -> list[str]:
    errors = []
    for pattern in PLAN_REF_PATTERNS:
        match = pattern.search(text)
        if match:
            errors.append(
                f"private planning reference {match.group(0)!r} — public commit/PR text "
                "must not cite internal planning codes or paths"
            )
    return errors


def lint(message: str, skills: set[str], *, pr_body: bool = False) -> list[str]:
    """Return a list of human-readable problems with `message`; empty means valid.

    `pr_body=True` applies only the trailer and plan-ref checks: the PR body never
    enters git history under squash COMMIT_MESSAGES but is still public text, and it
    is markdown, so the subject and one-line-paragraph rules do not apply.
    """
    text = message.strip("\n")
    lines = text.splitlines()

    if pr_body:
        visible, _ = _split_fenced(lines)
        return _attribution_errors(visible) + _plan_ref_errors(text)

    if not lines or not lines[0].strip():
        return ["message is empty"]

    # Git-generated merge subjects are exempt from the subject check so the hook
    # never blocks `git merge` / `git pull`; the body checks below still run, so a
    # crafted "Merge ..." subject cannot smuggle a trailer or plan ref past the gate
    # (CI additionally excludes true merge commits by parent count via --no-merges).
    errors = [] if MERGE_SUBJECT.match(lines[0]) else _subject_errors(lines[0], skills)
    rest = lines[1:]
    if rest and rest[0].strip():
        errors.append("second line must be blank — it separates the subject from the body")
    visible, paragraphs = _split_fenced(rest)
    errors += _body_shape_errors(paragraphs)
    errors += _attribution_errors(visible)
    errors += _plan_ref_errors(text)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("message_file", help="path to the message file, or '-' for stdin")
    parser.add_argument(
        "--pr-body",
        action="store_true",
        help="lint as a PR body: attribution and plan-ref checks only",
    )
    parser.add_argument(
        "--author-email",
        default="",
        help="commit author email; part of the bot skip, which requires "
        "--pr-author-login as well",
    )
    parser.add_argument(
        "--pr-author-login",
        default=None,
        help="PR author login; the bot skip fires only when BOTH this and "
        "--author-email look bot-authored — omitting either fails closed and lints",
    )
    parser.add_argument(
        "--strip-comments",
        action="store_true",
        help="drop # comment lines and the scissors block first (commit-msg hook "
        "input is the pre-cleanup editor file; committed text is linted verbatim)",
    )
    parser.add_argument(
        "--annotate",
        action="store_true",
        help="also emit GitHub Actions ::error:: workflow commands per finding",
    )
    parser.add_argument(
        "--label",
        default="commit message",
        help="name for this message in output, e.g. the commit sha",
    )
    args = parser.parse_args()

    if (
        args.author_email
        and args.pr_author_login is not None
        and is_bot_author(args.author_email)
        and is_bot_login(args.pr_author_login)
    ):
        print(f"{args.label}: skipped (bot author {args.author_email})")
        return 0

    if args.message_file == "-":
        message = sys.stdin.read()
    else:
        message = Path(args.message_file).read_text(encoding="utf-8", errors="replace")
    if args.strip_comments:
        message = strip_comments(message)

    repo_root = Path(__file__).resolve().parents[2]
    errors = lint(message, _title.skill_names(repo_root), pr_body=args.pr_body)
    if errors:
        print(f"{args.label} violates the commit-style rules:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        print(
            "The rules are declared in AGENTS.md Conventions and CONTRIBUTING.md.",
            file=sys.stderr,
        )
        if args.annotate:
            # Workflow-command escaping: the data is derived from untrusted commit
            # text, so %/CR/LF must be encoded to keep it one inert command.
            for error in errors:
                data = f"{args.label}: {error}"
                for char, escape in (("%", "%25"), ("\r", "%0D"), ("\n", "%0A")):
                    data = data.replace(char, escape)
                print(f"::error title=commit-style::{data}")
        return 1

    print(f"{args.label} OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
