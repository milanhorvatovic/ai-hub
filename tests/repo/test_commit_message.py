"""Unit tests for the commit-style linter (`.github/scripts/lint_commit_message.py`).

Stdlib-only, in the same spirit as the PR-title validator tests: the module lives
outside the importable package tree (under `.github/scripts/`), so it is loaded
from its file path.
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / ".github" / "scripts" / "lint_commit_message.py"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "change-intent.yml"


def _load_module():
    spec = importlib.util.spec_from_file_location("lint_commit_message", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


linter = _load_module()

SKILLS = {"coding-principles", "docs-steward", "git-toolkit", "oss-repository-conventions"}


def lint(message: str, **kwargs) -> list:
    return linter.lint(message, SKILLS, **kwargs)


# --- whole messages that must pass -------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "fix(git-toolkit): handle an empty diff",
        (
            "feat(docs-steward): add a yaml frontmatter pass\n"
            "\n"
            "Frontmatter was skipped because the markdown formatters treat it as opaque, so broken keys shipped silently. Run yamllint over the block first and fold its findings into the stream.\n"
        ),
        # Multiple one-line paragraphs.
        (
            "refactor: simplify the router table\n"
            "\n"
            "The table grew a column per capability and most rows repeated the same defaults.\n"
            "\n"
            "Collapse the defaults into one row and keep per-capability overrides only where they differ.\n"
        ),
        # Bullet and numbered lists are exempt from the one-line rule.
        (
            "feat(git-toolkit): add a release-notes capability\n"
            "\n"
            "Covered flows:\n"
            "- draft from merged PRs\n"
            "- refresh after a late merge\n"
            "1. collect\n"
            "2) render\n"
        ),
        # Fenced blocks are exempt, even with hard-wrapped content and blank lines.
        (
            "docs(coding-principles): show the failing example\n"
            "\n"
            "The example below is quoted verbatim from a session\n"
            "```\n"
            "some output\n"
            "wrapped across lines\n"
            "\n"
            "Co-Authored-By: Example <e@example.com>\n"
            "```\n"
            "and the fence content is exempt from the shape and trailer checks.\n"
        ),
        # Release-As is a control footer, not an attribution trailer.
        (
            "fix(git-toolkit): rework the trailer scan\n"
            "\n"
            "The scan missed folded trailers.\n"
            "\n"
            "Release-As: 2.0.0\n"
        ),
        # Multi-line footer block: trailers plus issue refs are exempt from body shape.
        (
            "fix(docs-steward): keep findings ordered\n"
            "\n"
            "Ordering was lost when two formatters reported the same line.\n"
            "\n"
            "Closes #12\n"
            "Release-As: 1.3.0\n"
        ),
        # Git-generated cherry-pick line.
        (
            "fix(git-toolkit): handle an empty diff\n"
            "\n"
            "The parser assumed at least one hunk.\n"
            "\n"
            "(cherry picked from commit 1234567890abcdef1234567890abcdef12345678)\n"
        ),
        # Git-generated revert / reapply auto-text.
        (
            'Revert "feat(git-toolkit): add a release-notes capability"\n'
            "\n"
            "This reverts commit 1234567890abcdef1234567890abcdef12345678.\n"
        ),
        'Reapply "fix(docs-steward): keep findings ordered"',
        # Rebase directives wrap an already-valid subject.
        "fixup! fix(git-toolkit): handle an empty diff",
        "squash! refactor: simplify the router table",
        # Git's auto-generated merge subjects are exempt from the subject check —
        # the hook must not block `git merge` / `git pull`.
        "Merge branch 'main' into feature-branch",
        "Merge pull request #12 from someone/topic",
        # Old-style conflicts list: indented continuations, so body shape passes.
        (
            "Merge remote-tracking branch 'origin/main'\n"
            "\n"
            "Conflicts:\n"
            "\tskills/git-toolkit/SKILL.md\n"
        ),
    ],
)
def test_valid_messages(message: str) -> None:
    assert lint(message) == []


def test_merge_subject_exemption_is_subject_only() -> None:
    # CI skips true merge commits by parent count; the subject-based exemption here
    # must not let a crafted "Merge ..." subject smuggle body violations through.
    message = (
        "Merge branch 'main' into feature-branch\n"
        "\n"
        "Co-Authored-By: Sneaky <s@example.com>\n"
    )
    errors = lint(message)
    assert any("attribution trailer" in error for error in errors)


def test_hand_written_merge_subject_is_still_linted() -> None:
    # Only git's auto-formats are exempt — an imperative subject that happens to
    # start with "Merge" still needs the Conventional-Commit shape.
    assert lint("Merge duplicate helpers into one module") != []


def test_strip_comments_matches_hook_input() -> None:
    # The hook lints the pre-cleanup editor file: comment lines and everything
    # below the scissors are removed first, like git's own cleanup.
    message = (
        "fix(git-toolkit): handle an empty diff\n"
        "\n"
        "# Please enter the commit message for your changes.\n"
        "One real paragraph.\n"
        "# ------------------------ >8 ------------------------\n"
        "diff --git a/x b/x\n"
        "hard\nwrapped\ndiff text\n"
    )
    assert lint(linter.strip_comments(message)) == []


def test_committed_text_is_linted_verbatim() -> None:
    # In CI the message comes from `git log --format=%B` — committed text, where a
    # #-prefixed line is real content, not an editor comment. Stripping it there
    # would let a private reference hide behind a leading #.
    message = "fix(git-toolkit): tweak\n\n# see docs/repo/tickets/x.md\n"
    errors = lint(message)
    assert any("private planning reference" in error for error in errors)


# --- trailer gate -------------------------------------------------------------------


@pytest.mark.parametrize(
    "trailer",
    [
        "Co-Authored-By: Claude <noreply@anthropic.com>",
        "co-authored-by: shouty lowercase <x@example.com>",
        "Signed-off-by: Dev <dev@example.com>",
        "Reviewed-by: Someone <s@example.com>",
        "Acked-by: Someone <s@example.com>",
        "Tested-by: Someone <s@example.com>",
    ],
)
def test_attribution_trailers_are_rejected(trailer: str) -> None:
    message = f"fix(git-toolkit): handle an empty diff\n\nA real paragraph.\n\n{trailer}\n"
    errors = lint(message)
    assert any("attribution trailer" in error for error in errors)


# --- body shape ---------------------------------------------------------------------


def test_hard_wrapped_paragraph_is_rejected() -> None:
    message = (
        "fix(git-toolkit): handle an empty diff\n"
        "\n"
        "This paragraph was wrapped at seventy-two columns by a well-meaning\n"
        "agent, which is exactly the house style violation the gate exists for.\n"
    )
    errors = lint(message)
    assert any("hard-wrapped" in error for error in errors)


def test_second_line_must_be_blank() -> None:
    message = "fix(git-toolkit): handle an empty diff\nbody starts immediately\n"
    errors = lint(message)
    assert any("second line" in error for error in errors)


def test_list_continuation_lines_are_exempt() -> None:
    message = (
        "fix(git-toolkit): handle an empty diff\n"
        "\n"
        "- a bullet item\n"
        "  with an indented continuation\n"
        "- another bullet\n"
    )
    assert lint(message) == []


def test_indented_block_lines_are_exempt() -> None:
    # Tab / 4-space indent is the git and markdown preformatted-block convention.
    message = (
        "fix(git-toolkit): handle an empty diff\n"
        "\n"
        "Reproduce with:\n"
        "    git diff --cached\n"
        "    git commit -m x\n"
    )
    assert lint(message) == []


@pytest.mark.parametrize(
    "body",
    [
        # Lightly indenting the continuation must not dodge the check.
        "This paragraph was wrapped and\n  indented by two spaces.",
        # An all-indented paragraph is not a footer block either.
        "  wrapped prose disguised\n  as a trailer block",
        # Issue refs do not fold — indented prose cannot hide inside a footer.
        "Closes #12\n  wrapped prose pretending to continue the ref",
    ],
)
def test_indented_wrapped_prose_is_still_rejected(body: str) -> None:
    errors = lint(f"fix(git-toolkit): handle an empty diff\n\n{body}\n")
    assert any("hard-wrapped" in error for error in errors)


def test_folded_trailer_continuations_still_pass() -> None:
    # Git folds long trailer values onto indented continuation lines.
    message = (
        "fix(git-toolkit): handle an empty diff\n"
        "\n"
        "One real paragraph.\n"
        "\n"
        "References: a long value\n"
        "  folded onto a continuation line\n"
    )
    assert lint(message) == []


# --- subject ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "subject",
    [
        "Add a release-notes capability",  # no type prefix
        "feature(git-toolkit): add x",  # not a canonical type
        "feat(unknown-skill): add x",  # scope is neither a skill nor an area
        "fix(git-toolkit): handle an empty diff.",  # trailing period
        "fix(git-toolkit): handle an empty diff.  ",  # period hidden by trailing spaces
        "fix(git-toolkit): " + "x" * 80,  # over the 72-char cap
    ],
)
def test_invalid_subjects(subject: str) -> None:
    assert lint(subject) != []


def test_subject_errors_name_the_subject() -> None:
    errors = lint("fix(git-toolkit): " + "x" * 80)
    assert any("subject is" in error and "cap is" in error for error in errors)


def test_empty_message_is_rejected() -> None:
    assert lint("") == ["message is empty"]


# --- plan-ref hygiene ---------------------------------------------------------------


@pytest.mark.parametrize(
    "fragment",
    [
        "see docs/repo/tickets/some-plan.md for details",
        "per the skills-audit-2026 findings",
        "tracked in ai-hub-planning",
        "closes out R6",
        "the G2 follow-up",
    ],
)
def test_private_planning_references_are_rejected(fragment: str) -> None:
    message = f"fix(git-toolkit): handle an empty diff\n\n{fragment}\n"
    errors = lint(message)
    assert any("private planning reference" in error for error in errors)


@pytest.mark.parametrize(
    "fragment",
    [
        "bump PR6 handling",  # letter before the code: no word boundary
        "route R66 stays",  # two digits: not the single-digit series
        "lowercase r6 is ordinary text",
    ],
)
def test_plan_ref_denylist_is_narrow(fragment: str) -> None:
    message = f"fix(git-toolkit): handle an empty diff\n\n{fragment}\n"
    assert lint(message) == []


def test_plan_refs_are_rejected_even_inside_fences() -> None:
    message = (
        "fix(git-toolkit): handle an empty diff\n"
        "\n"
        "```\n"
        "docs/repo/tickets/some-plan.md\n"
        "```\n"
    )
    errors = lint(message)
    assert any("private planning reference" in error for error in errors)


# --- PR-body mode -------------------------------------------------------------------


def test_pr_body_mode_allows_markdown_prose() -> None:
    body = (
        "## What changed\n"
        "\n"
        "This body is markdown and may wrap\n"
        "across lines freely.\n"
    )
    assert lint(body, pr_body=True) == []


def test_pr_body_mode_still_rejects_trailers_and_plan_refs() -> None:
    body = "Thanks!\n\nCo-Authored-By: Bot <b@example.com>\n\nsee docs/repo/tickets/x.md\n"
    errors = lint(body, pr_body=True)
    assert any("attribution trailer" in error for error in errors)
    assert any("private planning reference" in error for error in errors)


def test_pr_body_mode_accepts_an_empty_body() -> None:
    assert lint("", pr_body=True) == []


# --- bot-author skip ----------------------------------------------------------------


@pytest.mark.parametrize(
    "email",
    [
        "dependabot[bot]@users.noreply.github.com",
        "49699333+dependabot[bot]@users.noreply.github.com",
        "41898282+github-actions[bot]@users.noreply.github.com",
        "snyk-bot@snyk.io",
        "bot@renovateapp.com",
    ],
)
def test_bot_author_emails_are_recognized(email: str) -> None:
    assert linter.is_bot_author(email)


@pytest.mark.parametrize(
    "email",
    [
        "milan.horvatovic@gmail.com",
        "noreply@github.com",  # the web editor: a real user, not a bot
    ],
)
def test_human_author_emails_are_not_skipped(email: str) -> None:
    assert not linter.is_bot_author(email)


@pytest.mark.parametrize(
    "login,is_bot",
    [
        ("dependabot[bot]", True),
        ("github-actions[bot]", True),
        ("renovate-bot", True),
        ("milanhorvatovic", False),
        ("botanist", False),  # "bot" substring alone is not a bot marker
    ],
)
def test_bot_logins_are_recognized(login: str, is_bot: bool) -> None:
    assert linter.is_bot_login(login) is is_bot


def test_bot_login_detection_is_not_forked() -> None:
    # Bot-login detection is defined once, in the title validator; the linter re-exports
    # it (`is_bot_login = _title.is_bot_login`) so both gates share one source. If a
    # future edit re-adds a local `def is_bot_login` here, it would shadow the re-export
    # and the two copies could drift — this identity check fails the moment that happens.
    assert linter.is_bot_login is linter._title.is_bot_login
    # And the pattern list lives only in the validator, not vendored back into the linter.
    assert not hasattr(linter, "BOT_LOGIN_PATTERNS")


# --- CLI surface --------------------------------------------------------------------


def _run_cli(args: list, stdin_text: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        input=stdin_text,
        capture_output=True,
        text=True,
    )


def test_cli_rejects_a_violation_and_annotates() -> None:
    result = _run_cli(["--annotate", "--label", "commit abc1234", "-"], "not conventional\n")
    assert result.returncode == 1
    assert "commit abc1234" in result.stderr
    assert "::error title=commit-style::" in result.stdout


def test_cli_accepts_a_clean_message() -> None:
    result = _run_cli(["-"], "fix(git-toolkit): handle an empty diff\n")
    assert result.returncode == 0
    assert "OK" in result.stdout


def test_cli_bot_skip_requires_both_bot_email_and_bot_pr_author() -> None:
    bot_email = "49699333+dependabot[bot]@users.noreply.github.com"
    skipped = _run_cli(
        ["--author-email", bot_email, "--pr-author-login", "dependabot[bot]", "-"],
        "not conventional\n",
    )
    assert skipped.returncode == 0
    assert "skipped" in skipped.stdout
    # A forged bot email on a human-authored PR is still linted.
    linted = _run_cli(
        ["--author-email", bot_email, "--pr-author-login", "somehuman", "-"],
        "not conventional\n",
    )
    assert linted.returncode == 1
    # Omitting the login fails closed: the email alone never skips.
    no_login = _run_cli(["--author-email", bot_email, "-"], "not conventional\n")
    assert no_login.returncode == 1


def test_cli_strip_comments_flag_applies_editor_cleanup() -> None:
    message = "fix(git-toolkit): tweak\n\n# an editor comment\nOne real paragraph.\n"
    assert _run_cli(["--strip-comments", "-"], message).returncode == 0
    assert _run_cli(["-"], message).returncode == 1


# --- hook and CI wiring ---------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="executable bits are not visible on Windows")
@pytest.mark.parametrize("hook", ["commit-msg", "pre-commit"])
def test_hooks_are_executable(hook: str) -> None:
    # git silently ignores a non-executable hook under core.hooksPath — losing the
    # bit would disable the gate locally with no error at all.
    assert os.access(_REPO_ROOT / ".githooks" / hook, os.X_OK)


def test_hook_applies_editor_cleanup() -> None:
    hook = (_REPO_ROOT / ".githooks" / "commit-msg").read_text(encoding="utf-8")
    assert "--strip-comments" in hook


@pytest.mark.parametrize(
    "required_fragment",
    [
        "commit-style:",
        "timeout-minutes:",
        # The linter that judges the PR must come from the base branch.
        "ref: ${{ github.event.pull_request.base.ref }}",
        # Merge commits are skipped; every other branch commit is linted.
        "git rev-list --no-merges",
        "--author-email",
        # The bot skip requires a bot PR author, not just a bot-looking email.
        "--pr-author-login",
        "${{ github.event.pull_request.user.login }}",
        "--pr-body",
        "--annotate",
        # Untrusted commit text reaches the linter via stdin, never the shell.
        "lint_commit_message.py",
    ],
)
def test_change_intent_workflow_wires_the_linter(required_fragment: str) -> None:
    assert required_fragment in _WORKFLOW.read_text(encoding="utf-8")


# --- declaration stays in sync with enforcement ---------------------------------------


@pytest.mark.parametrize(
    "required_fragment",
    [
        "**Commit bodies:**",
        "one source line",
        "**No private planning references:**",
        "no trailing period",
        "core.hooksPath .githooks",
    ],
)
def test_agents_md_declares_the_enforced_rules(required_fragment: str) -> None:
    # The gate enforces exactly the declared rules — a rule the linter checks but
    # AGENTS.md no longer states would leave agents guessing.
    assert required_fragment in (_REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "required_fragment",
    [
        "## Commit messages",
        "core.hooksPath .githooks",
        "no trailing period",
    ],
)
def test_contributing_declares_the_enforced_rules(required_fragment: str) -> None:
    assert required_fragment in (_REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
