"""gate: image-digest-pinned — a base image is pinned by digest, not only by tag.

A tag can be re-pointed, and then the image that passed the tests is not the image
that was deployed. Pinning also needs someone moving the pins (Dependabot's docker
ecosystem); that half is checked by the project's own dependabot gate, not here.

exit 0 = clean or N/A · 1 = findings · 2 = called wrongly
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

FROM_LINE = re.compile(r"^FROM\s+(\S+)", re.MULTILINE)
STAGE = re.compile(r"^FROM\s+\S+\s+AS\s+(\S+)", re.MULTILINE)
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")


def main(root: pathlib.Path) -> int:
    config = json.loads((root / "scaffold.json").read_text(encoding="utf-8"))
    names = config.get("dockerfiles", ["Dockerfile"])
    dockerfiles = [root / n for n in names if (root / n).is_file()]
    if not dockerfiles:
        print("NA: no Dockerfile — nothing to check yet")
        return 0

    findings: list[str] = []
    for path in dockerfiles:
        text = path.read_text(encoding="utf-8")
        stages = set(STAGE.findall(text))
        findings += [
            f"{path.relative_to(root)}: FROM {ref}"
            for ref in FROM_LINE.findall(text)
            if ref not in stages and not DIGEST.search(ref)
        ]

    for finding in findings:
        print(f"image-digest-pinned: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_dockerfile_digest.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
