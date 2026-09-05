"""One answer, two ceilings — the reader every live check in this package shares.

**A ceiling on time is not a ceiling on the answer.** `urlopen(timeout=N)` bounds the gap
between packets, not the download: a server that sends a little and often never trips it.
Measured against a server writing 1KB every 0.5s with the ceiling set to **1 second**, the
reader was held for **12.0 seconds** — twelve times the ceiling — and it ended because the
server stopped, not because the ceiling fired; `json.load(response)` meanwhile accumulates
every byte with nothing to cap it (self-audit round 19, 2026-09-02). That is the failure the
ceilings in this package exist to prevent, in `gh.py`'s own words: a job's whole budget eaten
while nothing happens, then reported as "the job timed out". So an answer carries two more
ceilings — how large it may be, and by when it must have arrived.

This file exists because that reader was written **twice**, in `zenodo.py` and in
`asvs_worksheet.py`, each with a comment saying the other one says the same "because a rule
that lives in one of two places is a rule the other one loses". Nothing held the two equal,
and a third live check (`marketplace.py`, 2026-09-05) would have made three. A rule that
lives in one place is held by being the only one.

Role: helper — it decides nothing and prints nothing; it hands back an answer or raises
with the ceiling it went past named. The checks that call it decide.
"""

from __future__ import annotations

import time
from typing import IO

__all__ = ["MAX_ANSWER_BYTES", "READ_CHUNK", "body"]

MAX_ANSWER_BYTES = 16 * 1024 * 1024
READ_CHUNK = 64 * 1024


def body(response: IO[bytes], url: str, deadline: float) -> bytes:
    """Every byte of the answer — or `RuntimeError` naming the ceiling it went past."""
    read = bytearray()
    while chunk := response.read(READ_CHUNK):
        read += chunk
        if len(read) > MAX_ANSWER_BYTES:
            message = f"the answer from {url} is longer than {MAX_ANSWER_BYTES} bytes"
            raise RuntimeError(message)
        if time.monotonic() > deadline:
            message = f"the answer from {url} was still arriving after the ceiling passed"
            raise RuntimeError(message)
    return bytes(read)


if __name__ == "__main__":
    # A helper is not a command. Run as one, these modules imported cleanly and exited 0 with
    # nothing done — a wrong call that looked like a pass, which `gates.yaml` forbids in as
    # many words ("A misuse must exit 2, never 0") (self-audit round 2, owner decision B6,
    # 2026-09-01). `sys.stderr.write` rather than `print`, because a helper may not print and
    # the suppression ceiling only falls.
    import sys

    sys.stderr.write(
        "verifiable_gates.net is a helper, not a command — it has no entry point of\n"
        "its own; the readers that answer for themselves are listed in CONTRIBUTING.\n"
    )
    sys.exit(2)
