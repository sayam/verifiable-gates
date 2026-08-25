"""An issue held open for newcomers must not be closed out from under them.

**From a real incident, 2026-08-20.** An issue was created and labelled
`good first issue` at 12:14Z. The maintainer opened their own pull request for
the same issue at 16:40Z and merged it at 16:51Z. An outside contributor opened
theirs at 17:39Z, having started hours earlier. The label stayed on the whole
time, with no assignee and no comment saying somebody was on it — so there was
no way for them to know, and they lost an afternoon to work already closed.

This is the machine that enforces the rule that followed, because a promise made
in a comment on a closed pull request is a promise nobody can find again.

**Maintainers are not forbidden from doing the work** — they are forbidden from
doing it *silently*. Removing the label first is the right move; deliberately
taking it back while the label stands is fine too, as long as the pull request
body says so in a line a machine can read.

Role: decider — it answers pass or fail and returns an exit code that can block
a pull request.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any

__all__ = ["LABEL", "OVERRIDE", "main", "problems", "report"]

# The declaration in a pull request body that releases this gate. It needs a
# reason after it, not a bare incantation: an override nobody has to justify is
# one that gets pasted in reflexively.
OVERRIDE = re.compile(r"^good-first-issue-taken-back:\s*(?P<reason>.+\S.*)$", re.MULTILINE)
LABEL = "good first issue"

# Every command fired outward declares a ceiling. `subprocess.run` without one
# waits forever, and a `gh` that never answers would eat the whole job's budget
# while doing nothing, then be reported as "the job timed out".
TOOL_TIMEOUT_SECONDS = 60


def _gh(*args: str) -> str:
    """Run `gh` and hand back stdout — a failure here is the gate's, not the PR's."""
    return subprocess.run(  # noqa: S603 — fixed argv, no shell
        ["gh", *args],  # noqa: S607 — gh comes from the runner's PATH by design
        capture_output=True,
        text=True,
        check=True,
        timeout=TOOL_TIMEOUT_SECONDS,
    ).stdout


def closing_issues(pull_request: str) -> list[dict[str, Any]]:
    """The issues this pull request will close — read from GitHub, not guessed.

    `closingIssuesReferences` is what the platform *will actually do* on merge,
    which is not the same as grepping the body for "Closes #N": that phrase can
    sit in a comment or a commit, and a malformed one closes nothing. A gate that
    reads something other than what the platform acts on is a gate that answers
    correctly only while the two happen to agree.
    """
    raw = _gh("pr", "view", pull_request, "--json", "closingIssuesReferences")
    references: list[dict[str, Any]] = json.loads(raw)["closingIssuesReferences"]
    return references


def labels_of(issue_number: int) -> set[str]:
    raw = _gh("issue", "view", str(issue_number), "--json", "labels")
    return {label["name"] for label in json.loads(raw)["labels"]}


def problems(closing: list[dict[str, Any]], labelled: dict[int, set[str]], body: str) -> list[str]:
    """What is wrong, as a list — empty means pass.

    Pure logic that touches no network, which is what makes it testable.
    """
    if OVERRIDE.search(body or ""):
        return []
    return [
        f"this pull request closes #{issue['number']} ({issue['title']}),"
        f" which still carries the {LABEL!r} label"
        for issue in closing
        if LABEL in labelled.get(issue["number"], set())
    ]


def report(found: list[str]) -> str:
    """What to print when red — it has to name both ways out, not just the fault."""
    return "\n".join(
        [
            "An issue held open for newcomers is being closed with its label still on:",
            *(f"  - {line}" for line in found),
            "",
            "Two ways forward — take either:",
            f"  1. Remove the {LABEL!r} label from the issue first, then comment that",
            "     you are working on it yourself.",
            "  2. If you mean to take it back with the label standing, put this line",
            "     in the pull request body:",
            "       good-first-issue-taken-back: <reason>",
            "",
            "A label still showing is an invitation still open. Somebody who accepted",
            "it and started work finds out only when their work is already closed.",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a pull request's issue handoff.")
    parser.add_argument("--pr", default=os.environ.get("PR_NUMBER", ""))
    parser.add_argument("--body", default=os.environ.get("PR_BODY", ""))
    args = parser.parse_args(argv)

    if not args.pr:
        print("no pull request number — this gate only means anything on a pull request")
        return 0

    closing = closing_issues(args.pr)
    if not closing:
        print("this pull request closes no issue")
        return 0

    labelled = {issue["number"]: labels_of(issue["number"]) for issue in closing}
    found = problems(closing, labelled, args.body)
    if found:
        print(report(found), file=sys.stderr)
        return 1

    closed = " ".join(f"#{issue['number']}" for issue in closing)
    print(f"closes {closed} — none of them left carrying the {LABEL!r} label")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
