"""Conventional Commits and a DCO sign-off, checked on what a branch actually adds.

Two modes, because the same rule is enforced in two places and neither alone is
enough:

    python lint_commits.py --msg-file .git/COMMIT_EDITMSG   # commit-msg hook
    python lint_commits.py --range origin/main..HEAD        # CI

The hook catches it while the author can still fix it with one keystroke; CI
catches it on a fork, where no hook of ours ever ran.

The shape enforced is:

    <type>[(scope)][!]: <subject, at most 72 characters>

and every commit must carry a **`Signed-off-by:` line (DCO 1.1)**, written by
`git commit -s`. That line is a statement by the person who wrote the commit,
at the time they wrote it, certifying they have the legal right to send it —
which is the one thing a project cannot add retroactively on their behalf.

**A `Co-authored-by:` trailer is refused.** It hands authorship credit — and,
on the platform, a contributor entry — to an address that signed nothing. A
tool that helped write the change is not an author under the DCO; the person
who signed is. The same goes for `Claude-Session:` and any other trailer an
assistant appends by default: the reference implementation had a rule against
them in a maintainer's notes and still shipped four commits carrying one on the
day the rule was only a note, which is the whole argument for a gate.

Role: decider — it answers pass or fail and returns an exit code that can block
a pull request.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

__all__ = [
    "MAX_TITLE",
    "TYPES",
    "check_sign_off",
    "check_title",
    "check_trailers",
    "commits_in_range",
    "main",
    "parse_log",
]

# Every command fired outward declares a ceiling. `subprocess.run` without a
# `timeout=` waits forever, and these run inside CI jobs: a `git` that never
# answers eats the job's whole budget and is then reported as "the job timed
# out", which points at the wrong place.
LOCAL_TIMEOUT_SECONDS = 60

TYPES = "feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert"
TITLE = re.compile(rf"^({TYPES})(\([\w./-]+\))?!?: \S.{{0,70}}$")
MAX_TITLE = 72

# `Signed-off-by: Name <email>` — the shape `git commit -s` writes, and the shape
# other projects' DCO bots read. **An address is required**: a signature with no
# way to reach the signer certifies nothing anybody can follow up on.
# The name is at least one character that is not a space — `Signed-off-by:    <a@b.co>`
# passed `.+`, three spaces making a name (self-audit, 2026-08-31).
SIGN_OFF = re.compile(r"^Signed-off-by: [^\s<>][^<>]*? <[^<>@\s]+@[^<>\s]+>\s*$", re.MULTILINE)

# Trailers that credit somebody who did not sign. Matched case-insensitively
# because git itself treats trailer keys that way (`Co-Authored-By` and
# `Co-authored-by` are both in the wild).
FORBIDDEN_TRAILERS = ("Co-authored-by", "Claude-Session")
FORBIDDEN_TRAILER = re.compile(
    r"^(" + "|".join(re.escape(key) for key in FORBIDDEN_TRAILERS) + r"):",
    re.MULTILINE | re.IGNORECASE,
)


def check_title(title: str) -> list[str]:
    """What is wrong with one subject line, as a list — empty means pass."""
    problems = []
    if len(title) > MAX_TITLE:
        problems.append(f"subject is {len(title)} characters (over {MAX_TITLE})")
    if not TITLE.match(title):
        problems.append(f"subject is not a Conventional Commit: {title!r}")
    return problems


def check_sign_off(message: str) -> list[str]:
    """DCO — the sender certifies their legal right to what they sent.

    This reads the *whole message*, not just the subject, because `git commit -s`
    writes the line at the end of the body.
    """
    if SIGN_OFF.search(message):
        return []
    return [
        (
            "no `Signed-off-by: Name <email>` line — sign with `git commit -s` "
            "(DCO 1.1), or `git commit --amend -s` if the commit already exists"
        )
    ]


def check_trailers(message: str) -> list[str]:
    """One author per commit — the one who signed.

    Reads the whole message, like the sign-off check, because trailers sit at
    the end of the body.
    """
    return [
        (
            f"carries a `{found.group(1)}:` trailer — credit goes to the signer alone; "
            "drop the line (an assistant that helped is not an author under the DCO)"
        )
        for found in FORBIDDEN_TRAILER.finditer(message)
    ]


# Separators for `git log --format`. **A commit body may contain newlines**, so a
# line-based separator silently splits one commit into several. These are kept as
# constants beside the format string handed to git, so the two cannot drift; a
# test compares them.
RECORD_SEP = "\x1e"
FIELD_SEP = "\x00"
LOG_FORMAT = "%H%x00%s%x00%b%x1e"


def parse_log(out: str) -> list[tuple[str, str, str]]:
    """Turn `git log --format=LOG_FORMAT` output into (short sha, subject, body)."""
    return [
        (sha[:9], subject, body)
        for chunk in out.split(RECORD_SEP)
        if chunk.strip()
        for sha, subject, body in [chunk.strip("\n").split(FIELD_SEP, 2)]
    ]


def commits_in_range(rev_range: str) -> list[tuple[str, str, str]]:
    """The commits in this range, **merge commits excluded**.

    A merge commit's message is written by the platform ("Merge branch 'main'
    into ..."), not by a person. Holding it to a format makes the "Update branch"
    button turn this gate red every time, with nobody having typed anything
    wrong — which teaches people to reach for `--no-verify`. A repository with
    linear history required will not take one onto its default branch anyway, so
    it exists only on the branch.
    """
    out = subprocess.run(  # noqa: S603 — input comes from CI or the developer, not a user
        ["git", "log", "--no-merges", f"--format={LOG_FORMAT}", rev_range],  # noqa: S607 — git resolved from PATH, as the developer's own shell does
        capture_output=True,
        text=True,
        check=True,
        timeout=LOCAL_TIMEOUT_SECONDS,
    ).stdout
    return parse_log(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check commit messages and sign-offs.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--msg-file", help="the commit message file (hook mode)")
    group.add_argument("--range", dest="rev_range", help="a commit range (CI mode)")
    args = parser.parse_args(argv)

    failures: list[tuple[str | None, str, str]] = []
    if args.msg_file:
        try:
            message = pathlib.Path(args.msg_file).read_text(encoding="utf-8")
        except OSError as unreadable:
            print(f"cannot read the message file: {args.msg_file}: {unreadable}", file=sys.stderr)
            return 2
        title = message.splitlines()[0]
        failures.extend((None, title, problem) for problem in check_title(title))
        failures.extend((None, title, problem) for problem in check_sign_off(message))
        failures.extend((None, title, problem) for problem in check_trailers(message))
    else:
        for sha, subject, body in commits_in_range(args.rev_range):
            failures.extend((sha, subject, problem) for problem in check_title(subject))
            failures.extend((sha, subject, problem) for problem in check_sign_off(body))
            failures.extend((sha, subject, problem) for problem in check_trailers(body))

    for maybe_sha, _subject, problem in failures:
        prefix = f"{maybe_sha}: " if maybe_sha else ""
        print(f"FAIL {prefix}{problem}")
    if not failures:
        print("every commit message passes")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
