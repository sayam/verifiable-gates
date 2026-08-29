"""gate: image-digest-pinned — a base image is pinned by digest, not only by tag.

A tag can be re-pointed, and then the image that passed the tests is not the image
that was deployed. Pinning also needs someone moving the pins (Dependabot's docker
ecosystem); that half is checked by the project's own dependabot gate, not here.

Dockerfile instructions are case-insensitive, and an image can enter a build
through `COPY --from=<image>` as well as `FROM` — an outside audit on 2026-08-29
found a lowercase `from` and an unpinned `COPY --from=` both passing a scanner
that read only uppercase `FROM` lines. So the instruction is matched in any case,
flags such as `--platform=` are stepped over so the token judged is the image, and
`COPY --from=` is judged by the same rule.

exit 0 = clean or N/A · 1 = findings · 2 = called wrongly
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

# `FROM [--flag=value ...] <image> [AS <stage>]` — flags are skipped, not judged.
FROM_LINE = re.compile(r"^\s*FROM\s+(?:--\S+\s+)*(\S+)", re.MULTILINE | re.IGNORECASE)
STAGE = re.compile(r"^\s*FROM\s+.*?\s+AS\s+(\S+)", re.MULTILINE | re.IGNORECASE)
# `COPY --from=<image-or-stage>` pulls an image into the build exactly as FROM does.
COPY_FROM = re.compile(r"^\s*COPY\s+(?:--\S+\s+)*?--from=(\S+)", re.MULTILINE | re.IGNORECASE)
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")


def main(root: pathlib.Path) -> int:
    config_path = root / "scaffold.json"
    # A project that has not configured the bundle is not a misuse — the paths
    # below fall back to their defaults, and a path that is not there reports NA.
    # Reading it unguarded turned "not configured yet" into a traceback.
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    names = config.get("dockerfiles", ["Dockerfile"])
    dockerfiles = [root / n for n in names if (root / n).is_file()]
    if not dockerfiles:
        print("NA: no Dockerfile — nothing to check yet")
        return 0

    findings: list[str] = []
    for path in dockerfiles:
        text = path.read_text(encoding="utf-8")
        stages = {stage.lower() for stage in STAGE.findall(text)}
        refs = [("FROM", ref) for ref in FROM_LINE.findall(text)]
        refs += [("COPY --from", ref) for ref in COPY_FROM.findall(text)]
        findings += [
            f"{path.relative_to(root)}: {how} {ref}"
            for how, ref in refs
            # A stage name is a local alias, not an image — and names are also
            # case-insensitive. A bare stage *index* (`--from=0`) is one too.
            if ref.lower() not in stages and not ref.isdigit() and not DIGEST.search(ref)
        ]

    for finding in findings:
        print(f"image-digest-pinned: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_dockerfile_digest.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
