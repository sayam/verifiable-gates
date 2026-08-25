"""gate: actions-sha-pinned — every action in a workflow is pinned to a commit SHA.

A tag can be moved; a commit cannot. And an action runs with the permissions of
the project's own workflow, reading its source and whatever token that job holds.

exit 0 = clean or N/A · 1 = findings · 2 = called wrongly
"""

from __future__ import annotations

import pathlib
import re
import sys

USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)", re.MULTILINE)
PINNED = re.compile(r"@[0-9a-f]{40}$")
LOCAL = ("./", "docker://")


def main(root: pathlib.Path) -> int:
    workflows = sorted((root / ".github" / "workflows").glob("*.y*ml"))
    if not workflows:
        print("NA: no workflows — nothing to check yet")
        return 0

    findings: list[str] = []
    for path in workflows:
        findings += [
            f"{path.relative_to(root)}: {ref}"
            for ref in USES.findall(path.read_text(encoding="utf-8"))
            if not ref.startswith(LOCAL) and not PINNED.search(ref)
        ]

    for finding in findings:
        print(f"actions-sha-pinned: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_workflow_pinning.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
