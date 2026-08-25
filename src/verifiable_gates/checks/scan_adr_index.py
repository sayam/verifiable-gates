"""gate: adr-index-complete — the ADR index covers every record, numbered without gaps.

A stale index is worse than no index: the reader believes they are seeing all of
it while the most recent decisions are missing. In the reference implementation
the index once trailed by seven records, from the phase that decided the largest
things in the project.

exit 0 = clean or N/A · 1 = findings · 2 = called wrongly
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

FILENAME = re.compile(r"^(\d{4})-[a-z0-9-]+\.md$")
INDEX_LINK = re.compile(r"\[(\d{4})\]\(([^)]+)\)")


def main(root: pathlib.Path) -> int:
    config = json.loads((root / "scaffold.json").read_text(encoding="utf-8"))
    adr_dir = root / config.get("adr_path", "docs/adr")
    if not adr_dir.is_dir():
        print(f"NA: no {adr_dir.relative_to(root)} — nothing to check yet")
        return 0

    on_disk = {m.group(1): p.name for p in adr_dir.glob("*.md") if (m := FILENAME.match(p.name))}
    index = adr_dir / "README.md"
    listed = dict(INDEX_LINK.findall(index.read_text(encoding="utf-8"))) if index.is_file() else {}

    findings: list[str] = []
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

    for finding in findings:
        print(f"adr-index-complete: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_adr_index.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
