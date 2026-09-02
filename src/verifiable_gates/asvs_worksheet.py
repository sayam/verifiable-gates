"""An ASVS worksheet that is refreshed from a pinned standard and never overwrites a verdict.

**The script never writes a verdict for anyone.** It can add *rows* for
requirements the document does not yet have (status: the caller's word for
"unassessed") and it keeps every status and evidence a person already wrote.
Assessment is a person's job; the tool only stops requirements from being
dropped on the floor when the standard moves.

Why the standard is pinned into the repository instead of fetched at test time:

- a gate that needs the network is a gate that goes red because of the network,
  not because of the code;
- a standard that changes under one's feet means yesterday's "pass" may not be
  today's, with no commit saying so — moving the version has to be a visible act.

Two things are the caller's: the **words** the document uses (its marker line,
its table header, the status for an unjudged row) and the **levels** in scope.
Both are inputs, because a worksheet in another language is still a worksheet.

Role: generator — the evidence is that the committed file equals the render.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import sys
import time
import urllib.request
from typing import IO, TYPE_CHECKING, Any

from verifiable_gates import files

if TYPE_CHECKING:
    import pathlib

__all__ = [
    "CELLS",
    "ROW",
    "Words",
    "assessment_part",
    "digest_of",
    "existing_verdicts",
    "fetch",
    "load",
    "pin",
    "preamble",
    "rebuild",
    "render",
    "sort_key",
]

# A requirement row always starts `| V<n>.<n>.<n> |` — which is how it is told
# apart from any other table in the same document.
ROW = re.compile(r"^\|\s*(V\d+\.\d+\.\d+)\s*\|")

# A worksheet row has exactly these cells: id · level · text · status · evidence.
CELLS = 5


@dataclasses.dataclass(frozen=True)
class Words:
    """What the document says in its own language — the parts the generator must not invent."""

    marker: str
    """The line below which the generator owns the file; everything above is a person's."""
    unassessed: str
    """Status written into a row nobody has judged yet."""
    header: str
    """The table header row, e.g. `| id | L | requirement | status | evidence |`."""
    divider: str = "|---|---|---|---|---|"
    blank_evidence: str = "—"


def sort_key(requirement: dict[str, Any]) -> tuple[int, ...]:
    """`V1.2.10` sorts after `V1.2.9` — as numbers, never as text."""
    return tuple(int(part) for part in str(requirement["req_id"])[1:].split("."))


# **A ceiling on time is not a ceiling on the answer.** `urlopen(timeout=N)` bounds the gap
# between packets, not the download: a server that sends a little and often never trips it.
# Measured against a server writing 1KB every 0.5s with the ceiling set to **1 second**, the
# reader was held for **12.0 seconds** and it ended because the server stopped, not because
# the ceiling fired; `json.load(response)` meanwhile accumulates every byte with nothing to
# cap it (self-audit round 19, 2026-09-02). The copy of this reader in `zenodo.py` says the
# same, because a rule that lives in one of two places is a rule the other one loses.
MAX_ANSWER_BYTES = 16 * 1024 * 1024
READ_CHUNK = 64 * 1024


def _answer(response: IO[bytes], url: str, deadline: float) -> object:
    """The body, parsed — or `RuntimeError` naming the ceiling it went past."""
    body = bytearray()
    while chunk := response.read(READ_CHUNK):
        body += chunk
        if len(body) > MAX_ANSWER_BYTES:
            message = f"the answer from {url} is longer than {MAX_ANSWER_BYTES} bytes"
            raise RuntimeError(message)
        if time.monotonic() > deadline:
            message = f"the answer from {url} was still arriving after the ceiling passed"
            raise RuntimeError(message)
    return json.loads(body)


def fetch(url: str, *, timeout: int = 60) -> list[dict[str, Any]]:
    """Pull the standard from upstream, trimmed to the fields kept — by hand, never at run time.

    The digest is taken over these fields and nothing else, so a reformat
    upstream does not read as a changed standard.
    """
    deadline = time.monotonic() + timeout
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 — the caller passes a constant https URL; nothing here composes it
        payload = _answer(response, url, deadline)
    if not isinstance(payload, dict) or "requirements" not in payload:
        # The standard is somebody else's document on somebody else's server, so its shape
        # is a claim rather than a fact: a `KeyError` here would be a traceback where this
        # reader has a sentence for everything else (round 19, 2026-09-02).
        message = f"the answer from {url} is not the standard — no `requirements` in it"
        raise RuntimeError(message)
    trimmed = [
        {
            "req_id": item["req_id"],
            "chapter_id": item["chapter_id"],
            "chapter_name": item["chapter_name"],
            "section_id": item["section_id"],
            "section_name": item["section_name"],
            "level": item["L"],
            "text": item["req_description"],
        }
        for item in payload["requirements"]
    ]
    return sorted(trimmed, key=sort_key)


def digest_of(requirements: list[dict[str, Any]]) -> str:
    """A checksum of the *requirements* — it moves only when a requirement does."""
    canonical = json.dumps(requirements, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def pin(path: pathlib.Path, requirements: list[dict[str, Any]], *, version: str, url: str) -> None:
    """Write the pinned standard the repository will read from now on."""
    body = {"version": version, "source": url, "requirements": requirements}
    files.write_text_atomically(path, json.dumps(body, ensure_ascii=False, indent=1) + "\n")


def load(path: pathlib.Path) -> list[dict[str, Any]]:
    """The standard as pinned in the repository."""
    requirements = json.loads(path.read_text(encoding="utf-8"))["requirements"]
    return [dict(item) for item in requirements]


def preamble(text: str, marker: str) -> str:
    """Everything a person wrote above the marker — kept byte for byte."""
    return text.split(marker, maxsplit=1)[0] if marker in text else ""


def assessment_part(text: str, marker: str) -> str:
    """Only the part the generator owns — everything below the marker.

    **The head must be cut first, always.** A preamble can hold a backlog table
    whose rows begin with the very same requirement ids; the first version of
    this tool did not cut it, and rewrote those rows in the assessment table's
    shape. It failed silently, because the result was still a valid table.
    """
    return text.split(marker, 1)[1] if marker in text else ""


def existing_verdicts(text: str, marker: str) -> dict[str, tuple[str, str]]:
    """(status, evidence) already written per requirement — a refresh must not overwrite them."""
    verdicts: dict[str, tuple[str, str]] = {}
    for line in assessment_part(text, marker).splitlines():
        if not ROW.match(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == CELLS:
            verdicts[cells[0]] = (cells[3], cells[4])
    return verdicts


def render(
    requirements: list[dict[str, Any]],
    verdicts: dict[str, tuple[str, str]],
    *,
    levels: tuple[str, ...],
    words: Words,
) -> str:
    """The whole table, grouped by the standard's chapters and sections."""
    lines: list[str] = []
    chapter = section = None
    for requirement in sorted(requirements, key=sort_key):
        if requirement["level"] not in levels:
            continue
        if requirement["chapter_id"] != chapter:
            chapter = requirement["chapter_id"]
            section = None
            lines += ["", f"## {chapter} — {requirement['chapter_name']}"]
        if requirement["section_id"] != section:
            section = requirement["section_id"]
            lines += [
                "",
                f"### {section} {requirement['section_name']}",
                "",
                words.header,
                words.divider,
            ]
        status, evidence = verdicts.get(
            requirement["req_id"], (words.unassessed, words.blank_evidence)
        )
        lines.append(
            f"| {requirement['req_id']} | {requirement['level']} | {requirement['text']} "
            f"| {status} | {evidence} |"
        )
    return "\n".join(lines) + "\n"


def rebuild(
    text: str,
    requirements: list[dict[str, Any]],
    *,
    levels: tuple[str, ...],
    words: Words,
) -> str:
    """The document as it should be: the person's preamble, the marker, then the refreshed table."""
    return (
        preamble(text, words.marker)
        + words.marker
        + "\n"
        + render(requirements, existing_verdicts(text, words.marker), levels=levels, words=words)
    )


if __name__ == "__main__":
    # A helper is not a command. Run as one, these modules imported cleanly and exited 0
    # with nothing done — a wrong call that looked like a pass, which `gates.yaml` forbids
    # in as many words ("A misuse must exit 2, never 0"). Round 11 gave seven modules this
    # guard from a list written by hand, and the list was seven short (self-audit round 12,
    # 2026-09-01); the test now reads the package instead of remembering it.
    sys.stderr.write(
        "verifiable_gates.asvs_worksheet is a helper, not a command — it has no entry point of\n"
        "its own; the readers that answer for themselves are listed in CONTRIBUTING.\n"
    )
    sys.exit(2)
