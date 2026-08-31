"""gate: adr-index-complete — the ADR index covers every record, numbered without repeats or gaps,
and supersessions are recorded in both directions.

A stale index is worse than no index: the reader believes they are seeing all of
it while the most recent decisions are missing. In the reference implementation
the index once trailed by seven records, from the phase that decided the largest
things in the project.

The title's last clause had no code behind it: a record saying `Supersedes: 0001`
while 0001 said nothing was clean (self-audit, 2026-08-31). A supersession is read
from both records — `Supersedes:` on the new one, `Superseded by:` on the old — and
each side has to name the other. An index link may carry a title in its text
(`[0001: Use X](…)`) or sit in a table row (`| 0001 | [Use X](…) |`); both were
"missing from the index", and a record named in capitals was not a record at all.

exit 0 = clean or N/A · 1 = findings · 2 = called wrongly

Role: decider — it answers pass or fail with an exit code, and it ships as a
standalone file; its evidence is a planted violation and a clean tree in
`tests/test_checks_behaviour.py`.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

FILENAME = re.compile(r"^(\d{4})-[a-z0-9-]+\.md$", re.IGNORECASE)
# `[0001](file)`, `[0001: Use X](file)`, or a table row `| 0001 | [Use X](file) |`.
INDEX_LINK = re.compile(r"\[(\d{4})(?:[^\]]*)\]\(([^)]+)\)")
INDEX_ROW = re.compile(r"^\s*\|\s*(\d{4})\s*\|[^\n]*?\[[^\]]*\]\(([^)]+)\)", re.MULTILINE)
SUPERSEDES = re.compile(
    r"^\s*\**supersedes\**\s*:?\s*\**\s*(?:ADR[- ]?)?(\d{4})", re.IGNORECASE | re.MULTILINE
)
SUPERSEDED_BY = re.compile(
    r"^\s*\**superseded[- ]by\**\s*:?\s*\**\s*(?:ADR[- ]?)?(\d{4})", re.IGNORECASE | re.MULTILINE
)


def _supersession_findings(adr_dir: pathlib.Path, on_disk: dict[str, str]) -> list[str]:
    """Every `Supersedes:` names a record that says `Superseded by:` back, and the reverse."""
    supersedes: dict[str, set[str]] = {}
    superseded_by: dict[str, set[str]] = {}
    for number, name in on_disk.items():
        text = (adr_dir / name).read_text(encoding="utf-8", errors="replace")
        supersedes[number] = set(SUPERSEDES.findall(text))
        superseded_by[number] = set(SUPERSEDED_BY.findall(text))
    forward = [
        f"{new} supersedes {old}, but {old} does not say it is superseded by {new}"
        for new, olds in sorted(supersedes.items())
        for old in sorted(olds)
        if new not in superseded_by.get(old, set())
    ]
    backward = [
        f"{old} is superseded by {new}, but {new} does not say it supersedes {old}"
        for old, news in sorted(superseded_by.items())
        for new in sorted(news)
        if old not in supersedes.get(new, set())
    ]
    return forward + backward


MISCONFIGURED = (
    "scaffold.json names {key} {path}, which is not there — a configured path that "
    "is missing is a broken configuration, not nothing to check"
)


def main(root: pathlib.Path) -> int:
    config_path = root / "scaffold.json"
    # A project that has not configured the bundle is not a misuse — the paths
    # below fall back to their defaults, and a default that is not there reports
    # NA. A path the project *named* and does not have is the opposite case: a
    # broken configuration, reported as a finding — an outside audit on
    # 2026-08-29 planted a `scaffold.json` pointing at a Dockerfile that did not
    # exist beside a dirty one that did, and the answer was "nothing to check".
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    adr_dir = root / config.get("adr_path", "docs/adr")
    if not adr_dir.is_dir():
        if "adr_path" in config:
            print(
                "adr-index-complete: "
                + MISCONFIGURED.format(key="adr_path", path=adr_dir.relative_to(root))
            )
            return 1
        print(f"NA: no {adr_dir.relative_to(root)} — nothing to check yet")
        return 0

    by_number: dict[str, list[str]] = {}
    for record in sorted(adr_dir.glob("*.md")):
        if match := FILENAME.match(record.name):
            by_number.setdefault(match.group(1), []).append(record.name)
    on_disk = {number: names[0] for number, names in by_number.items()}
    index = adr_dir / "README.md"
    listed: dict[str, str] = {}
    if index.is_file():
        text = index.read_text(encoding="utf-8")
        listed = dict(INDEX_LINK.findall(text)) | dict(INDEX_ROW.findall(text))

    findings: list[str] = []
    # Two records with one number: a dict keyed by number kept one and lost the
    # other silently (outside audit, 2026-08-30) — the rule says without repeats.
    findings += [
        f"number used twice: {', '.join(names)}" for names in by_number.values() if len(names) > 1
    ]
    if on_disk and not index.is_file():
        findings.append("records exist but there is no README.md index")
    findings += [
        f"missing from the index: {on_disk[n]}" for n in sorted(on_disk.keys() - listed.keys())
    ]
    findings += [
        f"index points at a file that is gone: {listed[n]}"
        for n in sorted(listed.keys() - on_disk.keys())
    ]

    numbers = sorted(int(n) for n in on_disk)
    if numbers and numbers != list(range(numbers[0], numbers[0] + len(numbers))):
        findings.append(f"gap in the numbering: {numbers}")
    findings += _supersession_findings(adr_dir, on_disk)

    for finding in findings:
        print(f"adr-index-complete: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_adr_index.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
