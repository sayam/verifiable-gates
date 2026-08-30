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
import urllib.error
import urllib.request
from typing import Any

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

# Every command fired outward declares a ceiling — the archive is somebody else's service.
NETWORK_TIMEOUT_SECONDS = 60
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


def _page(url: str, timeout: int) -> Any:  # noqa: ANN401 — the shape is the archive's
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 — a constant https URL with a numeric id in it
            return json.load(response)
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


def versions(records: list[dict[str, Any]]) -> dict[str, str]:
    """Archived version → its own DOI."""
    return {
        str(record["metadata"]["version"]): str(record.get("doi") or "")
        for record in records
        if isinstance(record.get("metadata"), dict) and record["metadata"].get("version")
    }


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
    for record in records:
        said = str(record.get("conceptdoi") or "")
        if said != concept:
            found.append(
                f"record {record.get('doi')} sits under concept {said or '(none)'}, "
                f"but CITATION.cff advertises {concept}"
            )
    return found


def _released() -> set[str]:
    """Release tags on the platform, with the `v` the archive does not carry."""
    tags = gh.api_pages("repos/:owner/:repo/releases")
    return {str(row.get("tag_name", "")).removeprefix("v") for row in tags if isinstance(row, dict)}


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
            json.loads(pathlib.Path(args.records).read_text(encoding="utf-8"))
            if args.records
            else fetch_records(record_id)
        )
        released = (
            {
                str(tag).removeprefix("v")
                for tag in json.loads(pathlib.Path(args.releases).read_text("utf-8"))
            }
            if args.releases
            else _released()
        )
    except (PermissionError, RuntimeError, OSError, json.JSONDecodeError) as problem:
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
