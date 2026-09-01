"""Talking to GitHub through `gh` — **the one wrapper**.

Keeping a command in two places means the second copy drifts the moment somebody
edits one side. That applies to *parsers* as much as to commands people type: the
reference implementation counted this wrapper copied in **five places**, two of
them identical character for character, each carrying its own `S603` suppression
for the same call — five exemptions for one command.

**Never pass a string somebody else composed as an argument.** Every caller
builds its argv from constants in code, which is the only reason the suppression
here is defensible.

**The censuses in this package do not name a token** — they run with whatever
`gh` already has, which in a job is the step's `GH_TOKEN`. That is the platform's
own way of scoping: a step that needs a narrower or a broader token sets
`env: GH_TOKEN: …` on that step, and nothing here has to know. `token_env` is
for one caller that must ask two questions needing two tokens inside one
process; a census asks one kind of question and needs no second name.

**One shipped file carries a copy of `run`** — `check_issue_handoff.py`, which
is copied into a project's `tools/` and cannot import this module there.
`tests/test_issue_handoff.py` holds that copy to this contract.

Role: helper — an environment convenience. It decides nothing and is never cited
as evidence.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from typing import Any

__all__ = ["NETWORK_TIMEOUT_SECONDS", "PAGE_SIZE", "api", "api_pages", "run"]

# Every command fired outward declares a ceiling. `subprocess.run` without a
# `timeout=` waits forever, and these run inside CI jobs: a `gh` that never
# answers eats the job's whole budget while doing nothing, and is then reported
# as "the job timed out", which points at the wrong place.
NETWORK_TIMEOUT_SECONDS = 60

# **A page tops out at 100.** Asking for 200 returns 100 in silence, which means
# a window somebody configured as 200 was half the width they wrote down, with
# nothing to say so. The reference implementation found this the hard way: a
# checker that read one page declared "no alerts outstanding" while the 101st
# was open.
PAGE_SIZE = 100


def _environment(token_env: str | None) -> dict[str, str] | None:
    """The environment for one call — a borrowed token when the caller names one.

    `token_env` names the variable holding the token for *this question*; unset
    or empty, the call falls back to whatever `gh` already has, which is what
    happens on a maintainer's machine. Two questions in one job can need two
    tokens (branch protection wants a PAT, code-scanning alerts want the job's
    own), and a wrapper that only knows one forces the broader scope onto both.
    """
    borrowed = os.environ.get(token_env or "")
    if not borrowed:
        return None
    return {**os.environ, "GH_TOKEN": borrowed, "GITHUB_TOKEN": borrowed}


def run(
    args: list[str],
    *,
    timeout: int = NETWORK_TIMEOUT_SECONDS,
    token_env: str | None = None,
) -> str:
    """Call `gh <args>` and hand back stdout, stripped.

    A failure is always a `PermissionError`, because in practice the cause is
    almost always insufficient scope or an expired token — and `gh`'s own message
    is attached whole rather than summarised, since it usually says which.

    `timeout` is a parameter rather than a constant because one endpoint is not
    like the others: a job's log can be enormous, and giving every call the
    ceiling that endpoint needs would let a hung question about a single field
    sit for minutes. The ceiling belongs to the caller that knows what it asked.
    """
    binary = shutil.which("gh")
    if not binary:
        raise RuntimeError("no gh on this machine — this tool talks to GitHub through it")
    try:
        done = subprocess.run(  # noqa: S603 — path from shutil.which, argv built by the caller
            [binary, *args],
            capture_output=True,
            text=True,
            check=False,
            env=_environment(token_env),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as expired:
        # The ceiling is ours; the answer at the ceiling has to be ours too. Left
        # alone, `TimeoutExpired` walks past every caller's `except (PermissionError,
        # RuntimeError)` and a census over three hundred runs ends in a traceback —
        # which is what happened on 2026-08-30, on this repository's own history.
        raise RuntimeError(
            f"`gh {' '.join(args)}` did not answer within {timeout} seconds"
            " — the platform could not be asked"
        ) from expired
    if done.returncode != 0:
        raise PermissionError(f"`gh {' '.join(args)}` failed: {done.stderr.strip()}")
    return done.stdout.strip()


def api(path: str, *, token_env: str | None = None) -> Any:  # noqa: ANN401 — the shape is whatever that endpoint returns
    """Ask the GitHub API and hand back parsed JSON."""
    return json.loads(run(["api", path], token_env=token_env))


def _page_of_rows(answer: object, key: str | None, url: str) -> list[Any]:
    """One page's rows, or a `RuntimeError` saying the answer was not a page of rows.

    `rows.extend(...)` takes anything that iterates, and `api` is honestly typed `Any`, so
    nothing here could tell rows from not-rows. An object answered where a list was
    expected extended the result with its **keys**, a string with its **characters**, and
    because neither is ever empty the loop asked for the next page for ever — one `gh api`
    subprocess per page, with nothing to stop it (self-audit round 18, 2026-09-02). The
    callers of this function publish counts; rows nobody can account for become numbers
    nobody can account for, and an unbounded loop is the job that never ends.

    A page that is not a page of rows is the third answer, not a guess and not a zero:
    `RuntimeError` is what a timeout here already raises, and every caller routes it to
    "the platform could not be asked", exit 2. A **named `key` the answer does not carry**
    goes the same way rather than counting as an empty page — the platform sends
    `{"workflow_runs": []}` for "none", so a missing key is a platform this reader does
    not understand, and reading it as zero is how a silent nothing becomes a green claim.
    """
    if key is not None:
        if not isinstance(answer, dict) or key not in answer:
            raise RuntimeError(
                f"`gh api {url}` did not answer with an object carrying {key!r}"
                " — the platform could not be read"
            )
        answer = answer[key]
    if not isinstance(answer, list):
        # Not the `TypeError` the linter prefers: nothing here is a programming mistake
        # to debug — the platform refused to be read, and `RuntimeError` is the answer
        # every caller of this module already routes to "could not ask", exit 2.
        raise RuntimeError(  # noqa: TRY004 — the platform is wrong here, not the program
            f"`gh api {url}` did not answer with a list of rows — the platform could not be read"
        )
    return answer


def api_pages(
    path: str,
    *,
    limit: int | None = None,
    key: str | None = None,
    token_env: str | None = None,
) -> list[Any]:
    """Every row behind a list endpoint — **paged**, because the API hands over 100 at a time.

    The reference implementation carried this loop in three places, one of them
    a checker whose whole point was not to stop at page one. `key` names the
    field holding the rows when the endpoint wraps them (`workflow_runs`); left
    unset, the answer itself is the list. `limit` is the caller's ceiling — the
    last page is trimmed to it, and no page past it is asked for. Paging stops at
    the first empty page: an empty page means the history ended, and asking
    again never returns.

    `token_env` is forwarded only when set, so a test that replaces `api` with a
    one-argument fake keeps working — the fakes are part of the contract here.
    """
    rows: list[Any] = []
    page = 1
    joiner = "&" if "?" in path else "?"
    while limit is None or len(rows) < limit:
        size = PAGE_SIZE if limit is None else min(PAGE_SIZE, limit - len(rows))
        url = f"{path}{joiner}per_page={size}&page={page}"
        answer = api(url) if token_env is None else api(url, token_env=token_env)
        batch = _page_of_rows(answer, key, url)
        if not batch:
            break
        rows.extend(batch)
        page += 1
    return rows if limit is None else rows[:limit]


if __name__ == "__main__":
    # A helper is not a command. Run as one, these modules imported cleanly and exited 0
    # with nothing done — a wrong call that looked like a pass, which `gates.yaml` forbids
    # in as many words ("A misuse must exit 2, never 0"). Round 11 gave seven modules this
    # guard from a list written by hand, and the list was seven short (self-audit round 12,
    # 2026-09-01); the test now reads the package instead of remembering it.
    sys.stderr.write(
        "verifiable_gates.gh is a helper, not a command — it has no entry point of\n"
        "its own; the readers that answer for themselves are listed in CONTRIBUTING.\n"
    )
    sys.exit(2)
