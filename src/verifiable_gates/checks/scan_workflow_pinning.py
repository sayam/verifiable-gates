"""gate: actions-sha-pinned — every action in a workflow is pinned to a commit SHA.

A tag can be moved; a commit cannot. And an action runs with the permissions of
the project's own workflow, reading its source and whatever token that job holds.

A composite action under `.github/actions/<name>/action.yml` runs its `uses:`
steps with those same permissions, and moving a step into one used to move it
out of this scanner's sight — an outside audit on 2026-08-29 planted a floating
action there and got a clean exit. Both places are read, and so is every local
action a read file names with `uses: ./<path>`, wherever it lives.

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
# YAML lets the value fold onto the next line — `uses: >` then the action — and
# the regex above reported the fold marker as the action: `actions-sha-pinned:
# ci.yml: >`, red for the right reason with a finding that named nothing (outside
# audit, 2026-08-30). The marker is followed to the line that carries the value.
BLOCK = re.compile(r"^[|>][-+]?$")


def _uses_refs(text: str) -> list[str]:
    """Every `uses:` value in the file, a folded or literal one read from its next line."""
    lines = text.splitlines()
    found: list[str] = []
    for index, line in enumerate(lines):
        match = USES.match(line)
        if not match:
            continue
        ref = match.group(1)
        if BLOCK.match(ref):
            rest = [later.strip() for later in lines[index + 1 :] if later.strip()]
            ref = rest[0].strip("\"'") if rest else ref
        found.append(ref)
    return found


PINNED = re.compile(r"@[0-9a-f]{40}$")
# A `docker://` step runs an image with the job's permissions, and a tag can be
# re-pointed exactly as an action tag can — so it is held to a digest, not
# exempted (an outside audit on 2026-08-29 planted `docker://alpine:latest`
# and the whole prefix was excused). Only a path in this checkout is local.
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")
LOCAL = ("./",)

# The bundle's own starting workflow, as `install.py` writes `ci-template.yml`:
# one pinned checkout and one run of the doctor. A tree where every workflow is
# that has nothing of the project's to judge yet, and the answer is NA — so
# "every scan NA" can mean what README says it means. An outside audit on
# 2026-08-30 installed into an empty directory and three scans said `pass` on
# the file the bundle had just written. Any line added or changed makes the
# workflow the project's, and it is judged like any other.
STEP = re.compile(r"^\s*-?\s*(uses|run):\s*(.+?)\s*$", re.MULTILINE)
TEMPLATE_STEPS = (("uses", re.compile(r"^actions/checkout@[0-9a-f]{40}$")), ("run", None))
DOCTOR_RUN = "python3 tools/gates_doctor.py"


def _bundles_own(text: str) -> bool:
    """Is this workflow the untouched starting one — a pinned checkout, then the doctor?"""
    steps = [(kind, value.split(" #")[0].strip()) for kind, value in STEP.findall(text)]
    if len(steps) != len(TEMPLATE_STEPS):
        return False
    (uses_kind, uses), (run_kind, run) = steps
    return (
        uses_kind == "uses"
        and TEMPLATE_STEPS[0][1] is not None
        and TEMPLATE_STEPS[0][1].match(uses) is not None
        and run_kind == "run"
        and run == DOCTOR_RUN
    )


# A local action is whatever `uses: ./<path>` names — GitHub reads
# `<path>/action.yml` wherever it lives, so reading `.github/actions/` alone left
# `uses: ./ci/actions/setup` unread: an outside audit on 2026-08-30 planted one
# there and both pinning scanners exited 0 while CHANGELOG said composite actions
# were read. Every file read is followed, so an action calling an action is read.
LOCAL_USES = re.compile(r"""^\s*-?\s*uses:\s*["']?\./([^\s"']*)""", re.MULTILINE)


def _followed(root: pathlib.Path, targets: list[pathlib.Path]) -> list[pathlib.Path]:
    """`targets` plus every local action a read file points at, wherever it lives."""
    seen = list(targets)
    queue = list(targets)
    while queue:
        for relative in LOCAL_USES.findall(queue.pop().read_text(encoding="utf-8")):
            for name in ("action.yml", "action.yaml"):
                candidate = root / relative / name
                if candidate.is_file() and candidate not in seen:
                    seen.append(candidate)
                    queue.append(candidate)
    return seen


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
    if all(_bundles_own(path.read_text(encoding="utf-8")) for path in workflows):
        print(
            "NA: only the bundle's own starting workflow, untouched — nothing of yours to check yet"
        )
        return 0

    findings: list[str] = []
    for path in _followed(root, workflows):
        findings += [
            f"{path.relative_to(root)}: {ref}"
            for ref in _uses_refs(path.read_text(encoding="utf-8"))
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
