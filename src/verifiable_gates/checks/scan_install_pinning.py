"""gate: ci-tools-hash-pinned — tools CI installs for itself are pinned by hash.

`pip install <name>` takes whatever is newest at the second the job runs, and runs
it with the workflow's permissions. It has to be `--require-hashes -r <lockfile>`.
On the node side it has to be `npm ci`: `npm install pkg@x` pins that one package
and leaves the rest of the tree floating.

Installing the checkout itself (`pip install --no-deps -e .`) is not an index
install: nothing is fetched, so there is nothing to pin. That exemption needs both
halves, and there is a test for each of them — see `_installs_from_an_index`.

Comments are stripped before checking — these files like to explain themselves by
quoting the very command they are telling you not to use.

exit 0 = clean or N/A · 1 = findings · 2 = called wrongly
"""

from __future__ import annotations

import pathlib
import re
import sys

PIP_INSTALL = re.compile(r"(?:^|[\s/])pip3?\s+install\b")
NPM_INSTALL = re.compile(r"(?:^|[\s/])npm\s+(?:install|i|add)\b")
# `pip install --no-deps -e .` installs the checkout itself and resolves nothing
# from an index, so there is no hash to pin and nothing an attacker could swap.
# **Both halves are required.** `--no-deps requests` still reaches the index, and
# `-e .` without `--no-deps` drags the whole dependency tree in unpinned — either
# one alone would turn this rule off for the case it exists to catch.
LOCAL_TARGET = re.compile(r"(?:^|\s)(?:-e\s+)?(?:\.|\./|/)(?:\S*)?(?:\s|$)")


def _installs_from_an_index(command: str) -> bool:
    return not ("--no-deps" in command and LOCAL_TARGET.search(command) is not None)


def _commands(path: pathlib.Path) -> list[str]:
    joined, buffer = [], ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.lstrip().startswith("#"):
            continue
        buffer += raw.rstrip()
        if buffer.endswith("\\"):
            buffer = buffer[:-1]
            continue
        joined.append(buffer)
        buffer = ""
    if buffer:
        joined.append(buffer)
    return joined


def main(root: pathlib.Path) -> int:
    targets = sorted((root / ".github" / "workflows").glob("*.y*ml"))
    targets += [p for p in [root / "Dockerfile"] if p.is_file()]
    if not targets:
        print("NA: no workflows or Dockerfile — nothing to check yet")
        return 0

    findings: list[str] = []
    for path in targets:
        for line in _commands(path):
            if (
                PIP_INSTALL.search(line)
                and "--require-hashes" not in line
                and _installs_from_an_index(line)
            ):
                findings.append(f"{path.relative_to(root)}: {line.strip()[:70]}")
            if NPM_INSTALL.search(line):
                findings.append(
                    f"{path.relative_to(root)}: use npm ci instead — {line.strip()[:60]}"
                )

    for finding in findings:
        print(f"ci-tools-hash-pinned: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_install_pinning.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
