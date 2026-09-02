"""The archive, read back: what Zenodo holds under the concept DOI, against the releases.

Every release here is archived on Zenodo, which mints a version DOI under one
concept DOI — and the archived copy is the one place a mistake cannot be
corrected. `own_numbers` holds the cards in the tree to each other and reads
the About field live; nothing read the archive itself. The 2026-08-30 re-audit
(round 24) compared the two by hand: 7 versions, 7 releases. This is that
comparison as a step on the cron, with the concept DOI the citation card
advertises held to the one the archive answers with.

Three answers: 0 the archive says what the releases say · 1 it does not, and the
difference is named · 2 the archive or the platform could not be asked.

Role: decider — it answers pass or fail with an exit code, and a job blocks on
it (`posture.yml`'s cron). What it decides on is two lists read live; the tests
feed it both lists as files.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from typing import IO, Any

from verifiable_gates import gh

__all__ = [
    "NETWORK_TIMEOUT_SECONDS",
    "PAGE_SIZE",
    "concept_doi",
    "fetch_records",
    "main",
    "problems",
    "versions",
]

# Every command fired outward declares a ceiling — the archive is somebody else's
# service, and it gets the same budget the platform does.
NETWORK_TIMEOUT_SECONDS = gh.NETWORK_TIMEOUT_SECONDS
API = "https://zenodo.org/api/records"
DOI_LINE = re.compile(r"^doi: (10\.5281/zenodo\.(\d+))\s*$", re.MULTILINE)


def concept_doi(citation: pathlib.Path) -> tuple[str, str]:
    """The concept DOI the citation card advertises, and its record id."""
    found = DOI_LINE.search(citation.read_text(encoding="utf-8"))
    if found is None:
        raise RuntimeError(f"{citation} carries no `doi: 10.5281/zenodo.<id>` line")
    return found.group(1), found.group(2)


# The archive refuses a page above 25 with a 400 (measured 2026-08-30) — so the
# list is paged, and a page that comes back full is followed by the next.
PAGE_SIZE = 25


# **A ceiling on time is not a ceiling on the answer.** `urlopen(timeout=N)` bounds the gap
# between packets, not the download: a server that sends a little and often never trips it.
# Measured against a server writing 1KB every 0.5s with the ceiling set to **1 second**, the
# reader was held for **12.0 seconds** — twelve times the ceiling — and it ended because the
# server stopped, not because the ceiling fired; `json.load(response)` meanwhile accumulates
# every byte with nothing to cap it (self-audit round 19, 2026-09-02). This is the failure
# the ceilings in this package exist to prevent, said in `gh.py`'s own words: a job's whole
# budget eaten while nothing happens, then reported as "the job timed out". So the answer
# carries two more ceilings — how large it may be, and by when it must have arrived.
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


def _page(url: str, timeout: int) -> Any:  # noqa: ANN401 — the shape is the archive's
    deadline = time.monotonic() + timeout
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 — a constant https URL with a numeric id in it
            return _answer(response, url, deadline)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as problem:
        raise RuntimeError(f"the archive could not be asked ({url}): {problem}") from problem


def fetch_records(
    record_id: str, *, timeout: int = NETWORK_TIMEOUT_SECONDS
) -> list[dict[str, Any]]:
    """Every version under the concept record, as the API returns them, page after page."""
    records: list[dict[str, Any]] = []
    for page in range(1, 41):
        url = f"{API}?q=conceptrecid:{record_id}&allversions=1&size={PAGE_SIZE}&page={page}"
        payload = _page(url, timeout)
        hits = payload.get("hits", {}).get("hits") if isinstance(payload, dict) else None
        if not isinstance(hits, list):
            raise RuntimeError(f"the archive answered without a record list ({url})")  # noqa: TRY004 — the archive's answer, not a caller's type
        records += [hit for hit in hits if isinstance(hit, dict)]
        if len(hits) < PAGE_SIZE:
            return records
    raise RuntimeError("the archive kept answering full pages — more than 1000 versions?")


def _version(record: dict[str, Any]) -> str:
    metadata = record.get("metadata")
    return str(metadata.get("version") or "") if isinstance(metadata, dict) else ""


def versions(records: list[dict[str, Any]]) -> dict[str, str]:
    """Archived version → its own DOI, for the records that carry a version."""
    return {_version(r): str(r.get("doi") or "") for r in records if _version(r)}


def _uncountable(records: list[dict[str, Any]]) -> list[str]:
    """Records the version map cannot represent: two under one version, or none at all.

    A dict keyed by version keeps the last record and drops the rest in silence —
    the review of 2026-08-30 fed two `0.1.6` records and one without a version and
    got "1 version, the archive says what the releases say".
    """
    found: list[str] = []
    seen: dict[str, str] = {}
    for record in records:
        version, doi = _version(record), str(record.get("doi") or "(no doi)")
        if not version:
            found.append(f"record {doi} carries no version — it cannot be matched to a release")
        elif version in seen:
            found.append(f"records {seen[version]} and {doi} both claim version {version}")
        else:
            seen[version] = doi
    return found


def problems(
    archived: dict[str, str], released: set[str], concept: str, records: list[dict[str, Any]]
) -> list[str]:
    """Both ways between the archive and the releases, and the concept DOI on every record."""
    found = [
        f"release {v} has no archived version on Zenodo" for v in sorted(released - set(archived))
    ]
    found += [
        f"archived version {v} ({archived[v]}) has no release here"
        for v in sorted(set(archived) - released)
    ]
    found += _uncountable(records)
    for record in records:
        said = str(record.get("conceptdoi") or "")
        if said != concept:
            found.append(
                f"record {record.get('doi')} sits under concept {said or '(none)'}, "
                f"but CITATION.cff advertises {concept}"
            )
    return found


def _record_list(loaded: object) -> list[dict[str, Any]]:
    """The records file's content, or a refusal — a wrong shape got an AttributeError
    traceback where every other unreadable input gets exit 2 (outside audit, 2026-08-31)."""
    if not isinstance(loaded, list) or not all(isinstance(r, dict) for r in loaded):
        message = "the records file does not hold a list of record mappings"
        raise ValueError(message)
    return loaded


def _tag_list(loaded: object) -> list[str]:
    """The releases file's content, or a refusal — `str()` was coercing any shape silently."""
    if not isinstance(loaded, list) or not all(isinstance(t, str) for t in loaded):
        message = "the releases file does not hold a list of tag strings"
        raise ValueError(message)
    return loaded


def bare(tag: str) -> str:
    """A release tag as the archive spells the version — without the leading `v`."""
    return tag.removeprefix("v")


def _released() -> set[str]:
    """Release tags on the platform, spelled as the archive spells them."""
    tags = gh.api_pages("repos/:owner/:repo/releases")
    return {bare(str(row.get("tag_name", ""))) for row in tags if isinstance(row, dict)}


def main(argv: list[str] | None = None) -> int:
    """Read the archive and the releases, hold them to each other, return the code."""
    parser = argparse.ArgumentParser(description="The archive, read back against the releases.")
    parser.add_argument("--root", default=".", help="the checkout (default: here)")
    parser.add_argument("--records", help="a JSON file of archive records (offline)")
    parser.add_argument("--releases", help="a JSON file of release tags (offline)")
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root)
    try:
        concept, record_id = concept_doi(root / "CITATION.cff")
        records = (
            _record_list(json.loads(pathlib.Path(args.records).read_text(encoding="utf-8")))
            if args.records
            else fetch_records(record_id)
        )
        tags = (
            _tag_list(json.loads(pathlib.Path(args.releases).read_text("utf-8")))
            if args.releases
            else None
        )
        released = {bare(tag) for tag in tags} if tags is not None else _released()
    except (PermissionError, RuntimeError, OSError, ValueError) as problem:
        print(f"cannot read the archive or the releases: {problem}", file=sys.stderr)
        return 2
    archived = versions(records)
    found = problems(archived, released, concept, records)
    for line in found:
        print(line, file=sys.stderr)
    if found:
        return 1
    print(
        f"the archive says what the releases say: {len(archived)} versions under {concept}, "
        f"{len(released)} releases"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
