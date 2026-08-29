"""gate: actions-sha-pinned — every action in a workflow is pinned to a commit SHA.

A tag can be moved; a commit cannot. And an action runs with the permissions of
the project's own workflow, reading its source and whatever token that job holds.

A composite action under `.github/actions/<name>/action.yml` runs its `uses:`
steps with those same permissions, and moving a step into one used to move it
out of this scanner's sight — an outside audit on 2026-08-29 planted a floating
action there and got a clean exit. Both places are read.

exit 0 = clean or N/A · 1 = findings · 2 = called wrongly

Role: decider — it answers pass or fail with an exit code, and it ships as a
standalone file; its evidence is a planted violation and a clean tree in
`tests/test_checks_behaviour.py`.
"""

from __future__ import annotations

import pathlib
import re
import sys

# The value may be quoted — YAML allows it and people do it — and the quotes are
# not part of the action: a pinned `uses: "actions/checkout@<sha>"` was reported
# as unpinned because the closing quote sat where the digit had to be.
USES = re.compile(r"""^\s*-?\s*uses:\s*["']?([^\s"']+)""", re.MULTILINE)
PINNED = re.compile(r"@[0-9a-f]{40}$")
# A `docker://` step runs an image with the job's permissions, and a tag can be
# re-pointed exactly as an action tag can — so it is held to a digest, not
# exempted (an outside audit on 2026-08-29 planted `docker://alpine:latest`
# and the whole prefix was excused). Only a path in this checkout is local.
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")
LOCAL = ("./",)


def _pinned(ref: str) -> bool:
    if ref.startswith("docker://"):
        return DIGEST.search(ref) is not None
    return PINNED.search(ref) is not None


def main(root: pathlib.Path) -> int:
    workflows = sorted((root / ".github" / "workflows").glob("*.y*ml"))
    workflows += sorted((root / ".github" / "actions").glob("**/action.y*ml"))
    if not workflows:
        print("NA: no workflows or composite actions — nothing to check yet")
        return 0

    findings: list[str] = []
    for path in workflows:
        findings += [
            f"{path.relative_to(root)}: {ref}"
            for ref in USES.findall(path.read_text(encoding="utf-8"))
            if not ref.startswith(LOCAL) and not _pinned(ref)
        ]

    for finding in findings:
        print(f"actions-sha-pinned: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_workflow_pinning.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
