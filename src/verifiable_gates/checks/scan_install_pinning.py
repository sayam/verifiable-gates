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

A composite action under `.github/actions/<name>/action.yml` installs with the
calling workflow's permissions, so its `run:` steps are read too — an outside
audit on 2026-08-29 planted an unpinned install there and got a clean exit.

exit 0 = clean or N/A · 1 = findings · 2 = called wrongly

Role: decider — it answers pass or fail with an exit code, and it ships as a
standalone file; its evidence is a planted violation and a clean tree in
`tests/test_checks_behaviour.py`.
"""

from __future__ import annotations

import pathlib
import re
import sys

# `pip` takes global options *before* the subcommand — `pip --python <interpreter>
# install`, `pip -q install` — and this repository's own release job used the
# first shape on an unpinned wheel install for five releases while the scanner
# read only `pip install` side by side (re-audit, 2026-08-30).
PIP_INSTALL = re.compile(r"(?:^|[\s/])pip3?(?:\s+-{1,2}[\w-]+(?:=\S+|\s+[^-\s]\S*)?)*\s+install\b")
NPM_INSTALL = re.compile(r"(?:^|[\s/])npm\s+(?:install|i|add)\b")
# `pipx install` / `pipx run` resolve the tool from the index like `pip install`.
PIPX_INSTALL = re.compile(r"(?:^|[\s/])pipx\s+(?:install|run)\b")
# `python -m build` (and `pyproject-build`) creates an isolated environment and
# `pip install`s the build backend from the index, unpinned — a tool CI installs
# for itself, under the job's privileges, with no `pip` on the line at all.
# `--no-isolation` makes the backend come from whatever the job already pinned.
BUILD = re.compile(r"(?:^|[\s/])(?:python3?\s+-m\s+build|pyproject-build)\b")
# `pip install --no-deps -e .` installs the checkout itself and resolves nothing
# from an index, so there is no hash to pin and nothing an attacker could swap.
# **Both halves are required.** `--no-deps requests` still reaches the index, and
# `-e .` without `--no-deps` drags the whole dependency tree in unpinned — either
# one alone would turn this rule off for the case it exists to catch. And the
# local target has to be the *only* target: `--no-deps requests .` has both
# halves and still fetches `requests` from the index — an outside audit on
# 2026-08-29 planted exactly that line and the exemption covered it.
LOCAL_TARGET = re.compile(r"^(?:\.|\./|/)")
# Options whose next token is a value, not a package — `-r`/`-c` are left out on
# purpose: a requirements file names packages, so it is an index install.
TAKES_A_VALUE = frozenset(
    {
        "-i",
        "--index-url",
        "--extra-index-url",
        "-f",
        "--find-links",
        "-t",
        "--target",
        "--prefix",
        "--root",
        "--src",
        "-C",
        "--config-settings",
        "--cache-dir",
        "--python",
    }
)
CHAIN = re.compile(r"\s*(?:&&|\|\||;|\|)\s*")


def _targets(command: str) -> list[str]:
    """What one `pip install` would install: its non-option tokens."""
    tokens = command[command.index("install") + len("install") :].split()
    found: list[str] = []
    skip = False
    for token in tokens:
        if skip:
            skip = False
        elif token in TAKES_A_VALUE:
            skip = True
        elif not token.startswith("-"):
            found.append(token)
    return found


def _installs_from_an_index(command: str) -> bool:
    targets = _targets(command)
    return not (
        "--no-deps" in command and targets and all(LOCAL_TARGET.match(target) for target in targets)
    )


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
    targets += sorted((root / ".github" / "actions").glob("**/action.y*ml"))
    targets += [p for p in [root / "Dockerfile"] if p.is_file()]
    if not targets:
        print("NA: no workflows, composite actions or Dockerfile — nothing to check yet")
        return 0

    findings: list[str] = []
    for path in targets:
        # One `run:` line can chain several commands; each is judged on its own,
        # or the second hides behind the first's exemption.
        for line in (part for joined in _commands(path) for part in CHAIN.split(joined)):
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
            if PIPX_INSTALL.search(line):
                findings.append(
                    f"{path.relative_to(root)}: pipx resolves from the index — {line.strip()[:55]}"
                )
            if BUILD.search(line) and "--no-isolation" not in line:
                findings.append(
                    f"{path.relative_to(root)}: build fetches its backend unpinned;"
                    f" pin it and pass --no-isolation — {line.strip()[:50]}"
                )

    for finding in findings:
        print(f"ci-tools-hash-pinned: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_install_pinning.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
