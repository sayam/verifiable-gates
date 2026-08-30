"""gate: ci-tools-hash-pinned — tools CI installs for itself are pinned by hash.

`pip install <name>` takes whatever is newest at the second the job runs, and runs
it with the workflow's permissions. It has to be `--require-hashes -r <lockfile>`.
On the node side it has to be `npm ci`: `npm install pkg@x` pins that one package
and leaves the rest of the tree floating.
The installers with no `pip` in the line — `uv tool install`, `uv add`, `uvx`,
`poetry add`, `pdm add`, `pipenv install` — resolve against the index too, and
were unread until an outside audit on 2026-08-30 planted two of them.

Installing the checkout itself (`pip install --no-deps --no-build-isolation -e .`)
is not an index install: nothing is fetched, so there is nothing to pin. That
exemption needs all three halves, and there is a test for each of them — see
`_installs_from_an_index`.

A `run:` line that hands off to a shell script in the checkout is followed into
the script, because the install it hides runs with the job's permissions all the
same (outside audit, 2026-08-30: `pip install ruff` in `scripts/setup.sh`, exit 0).

Comments are stripped before checking — these files like to explain themselves by
quoting the very command they are telling you not to use. A comment at the end of
a line goes too: `pip install ruff  # TODO --require-hashes` was green because the
word it needs sat in the comment (outside audit, 2026-08-30).

A composite action under `.github/actions/<name>/action.yml` installs with the
calling workflow's permissions, so its `run:` steps are read too — an outside
audit on 2026-08-29 planted an unpinned install there and got a clean exit. So
is every local action a read file names with `uses: ./<path>`, wherever it lives.

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
# The option shape starts with a letter after the dashes so `--x` parses one way
# only — `-{1,2}[\w-]+` parsed it two ways and a line of twenty `--flags` with no
# `install` took a second, forty took minutes (review, 2026-08-30). `pip3.13`
# and `python3.13` are the interpreter spellings Actions runners ship.
PIP_INSTALL = re.compile(
    r"(?:^|[\s/])pip(?:3(?:\.\d+)?)?(?:\s+--?[A-Za-z][\w-]*(?:=\S+|\s+[^-\s]\S*)?)*\s+install(?=\s|$)"
)
NPM_INSTALL = re.compile(r"(?:^|[\s/])npm\s+(?:install|i|add)\b")
# `pipx install` / `pipx run` resolve the tool from the index like `pip install`.
PIPX_INSTALL = re.compile(r"(?:^|[\s/])pipx\s+(?:install|run)\b")
# So do the installers with no `pip` in the line: `uv tool install`, `uv add`,
# `uvx`, `poetry add`, `pdm add`, `pipenv install` each resolve a name against
# the index with nothing but a tag or a range to hold it — an outside audit on
# 2026-08-30 planted `uv tool install ruff` and `poetry add ruff` and got exit 0
# from a scanner that keyed on the word `pip`. `uv run --locked` and `uv sync
# --locked` install from `uv.lock`, which carries hashes, and are left alone.
NO_PIP_INSTALL = re.compile(
    r"(?:^|[\s/])(?:uv\s+(?:tool\s+install|add)|uvx|poetry\s+add|pdm\s+add|pipenv\s+install)\b"
)
# `python -m build` (and `pyproject-build`) creates an isolated environment and
# `pip install`s the build backend from the index, unpinned — a tool CI installs
# for itself, under the job's privileges, with no `pip` on the line at all.
# `--no-isolation` makes the backend come from whatever the job already pinned.
BUILD = re.compile(r"(?:^|[\s/])(?:python(?:3(?:\.\d+)?)?\s+-m\s+build|pyproject-build)\b")
NO_ISOLATION = re.compile(r"(?:^|\s)(?:--no-isolation|-n)(?:\s|$)")
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


def _targets(command: str) -> list[str]:
    """What one `pip install` would install: its non-option tokens."""
    # Slice after the matched subcommand, not the first substring `install` —
    # `--python /opt/installer/bin/python install` has one before it.
    matched = PIP_INSTALL.search(command)
    tokens = command[matched.end() if matched else 0 :].split()
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
    # Three halves now: `--no-deps` for the tree, every target local, and
    # `--no-build-isolation` — without it pip builds the checkout in a fresh
    # environment and fetches the build backend from the index, unhashed, which
    # is the same fetch `python -m build` makes (review of 2026-08-30; this
    # repository's own four `pip install --no-deps -e .` lines had it).
    targets = _targets(command)
    return not (
        "--no-deps" in command
        and "--no-build-isolation" in command
        and targets
        and all(LOCAL_TARGET.match(target) for target in targets)
    )


def _without_comment(line: str) -> str:
    """The line up to its first `#` outside quotes — a `#` inside quotes is text."""
    quote = ""
    for index, char in enumerate(line):
        if quote:
            quote = "" if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char == "#":
            return line[:index]
    return line


# A `run:` line that hands off to a shell script in the checkout — `./scripts/
# setup.sh`, `bash scripts/setup.sh`, `sh …`, `source …`, `. …` — installs with
# the job's permissions from lines the workflow never shows. An outside audit on
# 2026-08-30 planted `pip install ruff` in a script the workflow called and got
# exit 0. Every script a read file names is read too, scripts calling scripts
# included; a path that climbs out of the checkout or is absolute is not ours.
SCRIPT = re.compile(
    r"(?:^|[\s;&|(])(?:(?:bash|sh|source|\.)\s+)?(?P<path>(?:\./)?[\w./-]+\.(?:sh|bash))(?=[\s;&|)]|$)"
)


def _scripts_named(root: pathlib.Path, path: pathlib.Path) -> list[pathlib.Path]:
    """The shell scripts in the checkout that one read file hands off to."""
    named = [
        pathlib.PurePosixPath(match.group("path"))
        for line in _commands(path)
        for match in SCRIPT.finditer(line)
    ]
    return [
        root / name
        for name in named
        if not name.is_absolute() and ".." not in name.parts and (root / name).is_file()
    ]


def _with_scripts(root: pathlib.Path, targets: list[pathlib.Path]) -> list[pathlib.Path]:
    """`targets` plus every shell script they hand off to, however deep."""
    seen = list(targets)
    queue = list(targets)
    while queue:
        for script in _scripts_named(root, queue.pop()):
            if script not in seen:
                seen.append(script)
                queue.append(script)
    return seen


def _commands(path: pathlib.Path) -> list[str]:
    joined, buffer = [], ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.lstrip().startswith("#"):
            continue
        buffer += _without_comment(raw).rstrip()
        if buffer.endswith("\\"):
            buffer = buffer[:-1]
            continue
        joined.append(buffer)
        buffer = ""
    if buffer:
        joined.append(buffer)
    return joined


def _nothing_of_yours(targets: list[pathlib.Path]) -> bool:
    """Every file read is the bundle's untouched starting workflow — said as NA."""
    if not all(_bundles_own(path.read_text(encoding="utf-8")) for path in targets):
        return False
    print("NA: only the bundle's own starting workflow, untouched — nothing of yours to check yet")
    return True


def _files_read(root: pathlib.Path) -> list[pathlib.Path]:
    """The files read as written: workflows, composite actions, the root Dockerfile."""
    targets = sorted((root / ".github" / "workflows").glob("*.y*ml"))
    targets += sorted((root / ".github" / "actions").glob("**/action.y*ml"))
    return targets + [p for p in [root / "Dockerfile"] if p.is_file()]


def _line_findings(where: pathlib.Path, line: str) -> list[str]:
    """Everything one command does that reaches an index unpinned."""
    found: list[str] = []
    if (
        PIP_INSTALL.search(line)
        and "--require-hashes" not in line
        and _installs_from_an_index(line)
    ):
        found.append(f"{where}: {line.strip()[:70]}")
    if NPM_INSTALL.search(line):
        found.append(f"{where}: use npm ci instead — {line.strip()[:60]}")
    if PIPX_INSTALL.search(line):
        found.append(f"{where}: pipx resolves from the index — {line.strip()[:55]}")
    if NO_PIP_INSTALL.search(line):
        found.append(f"{where}: resolves from the index with no lock — {line.strip()[:50]}")
    if BUILD.search(line) and not NO_ISOLATION.search(line):
        found.append(
            f"{where}: build fetches its backend unpinned;"
            f" pin it and pass --no-isolation — {line.strip()[:50]}"
        )
    return found


def main(root: pathlib.Path) -> int:
    targets = _files_read(root)
    if not targets:
        print("NA: no workflows, composite actions or Dockerfile — nothing to check yet")
        return 0
    if _nothing_of_yours(targets):
        return 0

    findings: list[str] = []
    for path in _with_scripts(root, _followed(root, targets)):
        # One `run:` line can chain several commands; each is judged on its own,
        # or the second hides behind the first's exemption.
        for line in (part for joined in _commands(path) for part in CHAIN.split(joined)):
            findings += _line_findings(path.relative_to(root), line)

    for finding in findings:
        print(f"ci-tools-hash-pinned: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_install_pinning.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
