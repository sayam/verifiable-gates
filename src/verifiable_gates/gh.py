"""Talking to GitHub through `gh` — **the one wrapper**.

Keeping a command in two places means the second copy drifts the moment somebody
edits one side. That applies to *parsers* as much as to commands people type: the
reference implementation counted this wrapper copied in **five places**, two of
them identical character for character, each carrying its own `S603` suppression
for the same call — five exemptions for one command.

**Never pass a string somebody else composed as an argument.** Every caller
builds its argv from constants in code, which is the only reason the suppression
here is defensible.

Role: helper — an environment convenience. It decides nothing and is never cited
as evidence.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
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
    done = subprocess.run(  # noqa: S603 — path from shutil.which, argv built by the caller
        [binary, *args],
        capture_output=True,
        text=True,
        check=False,
        env=_environment(token_env),
        timeout=timeout,
    )
    if done.returncode != 0:
        raise PermissionError(f"`gh {' '.join(args)}` failed: {done.stderr.strip()}")
    return done.stdout.strip()


def api(path: str, *, token_env: str | None = None) -> Any:  # noqa: ANN401 — the shape is whatever that endpoint returns
    """Ask the GitHub API and hand back parsed JSON."""
    return json.loads(run(["api", path], token_env=token_env))


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
        batch = answer.get(key, []) if key else answer
        if not batch:
            break
        rows.extend(batch)
        page += 1
    return rows if limit is None else rows[:limit]
