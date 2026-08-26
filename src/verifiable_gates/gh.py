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
import shutil
import subprocess
from typing import Any

__all__ = ["NETWORK_TIMEOUT_SECONDS", "api", "run"]

# Every command fired outward declares a ceiling. `subprocess.run` without a
# `timeout=` waits forever, and these run inside CI jobs: a `gh` that never
# answers eats the job's whole budget while doing nothing, and is then reported
# as "the job timed out", which points at the wrong place.
NETWORK_TIMEOUT_SECONDS = 60


def run(args: list[str]) -> str:
    """Call `gh <args>` and hand back stdout, stripped.

    A failure is always a `PermissionError`, because in practice the cause is
    almost always insufficient scope or an expired token — and `gh`'s own message
    is attached whole rather than summarised, since it usually says which.
    """
    binary = shutil.which("gh")
    if not binary:
        raise RuntimeError("no gh on this machine — this tool talks to GitHub through it")
    done = subprocess.run(  # noqa: S603 — path from shutil.which, argv built by the caller
        [binary, *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=NETWORK_TIMEOUT_SECONDS,
    )
    if done.returncode != 0:
        raise PermissionError(f"`gh {' '.join(args)}` failed: {done.stderr.strip()}")
    return done.stdout.strip()


def api(path: str) -> Any:  # noqa: ANN401 — the shape is whatever that endpoint returns
    """Ask the GitHub API and hand back parsed JSON."""
    return json.loads(run(["api", path]))
