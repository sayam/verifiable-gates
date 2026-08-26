"""What is true today, read from the things themselves rather than from a comment.

A ratchet is worth nothing without a number to hold it against, and where that
number comes from decides whether the check means anything. Every reader here
follows one rule: **ask the source, never the summary.** A coverage figure comes
from the coverage data, not from a badge; a count of switched-off checkers comes
from the lines themselves, not from a register somebody keeps by hand.

Two failures shaped this module, both from the reference implementation:

- Its first ratchet checker read only the numbers that lived in a tool's own
  config. A ratchet written as an English sentence — mypy's strict list, which
  had said "may grow, never shrink" for sixteen phases — survived it untouched,
  because there was no number to read. A promise that no reader can see is not a
  promise.
- A second parser, written next to the first because it was easier than importing
  the one that already existed, gave 24 where the real reader gave 23 on the same
  day. Where a project already has a reader for something, this module is not the
  place for a second one.

Every reader raises `RuntimeError` when it cannot answer, and never guesses. A
missing measurement file means the step that produces it did not run, which has
to be louder than a silent pass — the whole point of the measurement is that
somebody would otherwise not notice.

Role: reader — it reports numbers. Nothing here decides pass or fail.
"""

from __future__ import annotations

import ast
import fnmatch
import json
import re
import shutil
import subprocess
import tomllib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pathlib

__all__ = [
    "SUPPRESSION",
    "TOOL_TIMEOUT_SECONDS",
    "classify_suppression",
    "coverage_json_percent",
    "coverage_total",
    "docstring_coverage",
    "list_literal_length",
    "strict_modules",
    "suppression_counts",
]

# **A ceiling on how long we wait for a tool we started** — `subprocess.run`
# without `timeout=` waits forever, which in CI is a job that never ends and
# reports nothing.
TOOL_TIMEOUT_SECONDS = 300

# A line that switches a checker off, and whatever follows the rule codes.
#
# The trailing group is what separates "which rule is off" from "why", and those
# are different questions. A bare `noqa: F401` answers the first and not the
# second, and a register that demands a reason everywhere else has no business
# exempting the lines that disable the registers.
SUPPRESSION = (
    re.compile(r"#\s*noqa(?::\s*[A-Z]+[0-9]+(?:\s*,\s*[A-Z]+[0-9]+)*)?(?P<rest>.*)$"),
    re.compile(r"#\s*type:\s*ignore(?:\[[^\]]*\])?(?P<rest>.*)$"),
)

_INTERROGATE_ACTUAL = re.compile(r"actual:\s*([0-9.]+)%")


def _run(root: pathlib.Path, command: list[str]) -> subprocess.CompletedProcess[str]:
    binary = shutil.which(command[0])
    if not binary:
        raise RuntimeError(f"{command[0]} is not on this machine — this reader has to run it")
    return subprocess.run(  # noqa: S603 — a fixed command, its path from shutil.which
        [binary, *command[1:]],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=TOOL_TIMEOUT_SECONDS,
    )


def _is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def classify_suppression(line: str) -> tuple[bool, bool]:
    """(is this a switched-off checker, does it say why) for one line.

    A separate function because **the total cannot prove this logic**. A test that
    watches only the count stays green through a change that stops telling the two
    questions apart at all — which is what a mutation of exactly that shape showed
    in the reference implementation.
    """
    for probe in SUPPRESSION:
        found = probe.search(line)
        if found:
            return True, bool(found.group("rest").strip(" -—·:"))
    return False, False


def suppression_counts(
    root: pathlib.Path,
    sources: tuple[str, ...],
    skip: tuple[str, ...] = (),
) -> dict[str, int]:
    """How many checkers are switched off line by line, and how many say nothing.

    `skip` matches on the file name and on any directory in the path, so a
    generated file or a whole excluded tree can be named once.

    **A file matched by two patterns is counted once.** Overlapping globs are easy
    to write by accident — `*.py` beside `**/*.py` is the obvious pair — and a
    counter that added the file twice would make a ceiling jump on a change that
    switched nothing off, which teaches people that the ceiling means nothing.

    **This counts the file it is written in too.** Writing about these directives
    in prose is enough to be counted as using one, which is why every mention in
    this module's own text avoids the leading marker.
    """
    seen = {
        path.resolve()
        for pattern in sources
        for path in root.glob(pattern)
        if path.name not in skip and not any(part in skip for part in path.parts)
    }
    total = bare = 0
    for path in sorted(seen):
        for line in path.read_text(encoding="utf-8").splitlines():
            found, with_reason = classify_suppression(line)
            if found:
                total += 1
                bare += not with_reason
    return {"suppressions": total, "suppressions_without_reason": bare}


def coverage_total(root: pathlib.Path) -> float:
    """The overall coverage percentage from the data an earlier run left behind.

    `--precision=2` because a figure rounded to a whole number swallows the
    fractional slack, and that slack is the exact thing a ratchet check exists to
    see. `--ignore-errors` because a suite that creates and deletes files leaves
    coverage data pointing at paths that no longer exist; the strict reading still
    happens where it belongs, at `fail_under` during the run itself.
    """
    total = _run(root, ["coverage", "report", "--format=total", "--precision=2", "--ignore-errors"])
    if total.returncode != 0 or not _is_number(total.stdout.strip()):
        raise RuntimeError(
            "cannot read coverage — run the suite under `coverage` first so the data file "
            f"exists (stderr: {total.stderr.strip()[:120]})"
        )
    return float(total.stdout.strip())


def docstring_coverage(root: pathlib.Path, package: str) -> float:
    """The percentage `interrogate` reports for one package."""
    docs = _run(root, ["interrogate", package])
    found = _INTERROGATE_ACTUAL.search(docs.stdout + docs.stderr)
    if not found:
        raise RuntimeError("cannot read interrogate's result — its output format has changed")
    return float(found.group(1))


def coverage_json_percent(path: pathlib.Path, hint: str = "") -> float:
    """A percentage from a coverage JSON report an earlier step wrote.

    **It does not run the suite itself.** A check that re-runs the tests is a check
    people skip, and a number measured twice by two different invocations is two
    numbers. A missing file means the step before it did not run, which has to be
    louder than passing in silence — `hint` is where the caller says how to produce
    it, because that command belongs to the project rather than here.
    """
    if not path.is_file():
        raise RuntimeError(f"{path.name} is missing — the step that writes it has not run{hint}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return float(data["totals"]["percent_covered"])


def _strict_patterns(config: dict[str, Any]) -> list[str]:
    for override in config["tool"]["mypy"]["overrides"]:
        if override.get("disallow_untyped_defs"):
            return list(override["module"])
    raise RuntimeError("cannot find mypy's strict list — the shape of the config has changed")


def strict_modules(
    root: pathlib.Path,
    pyproject: pathlib.Path,
    package: pathlib.Path,
    skip_parts: tuple[str, ...] = ("__pycache__",),
) -> int:
    """How many modules actually fall under mypy's strict list.

    **Counted from the files that exist, matched against the patterns** — not from
    the length of the list. One line reading `app.services.*` covers many modules,
    so counting lines gives a number that measures the shape of the config rather
    than the strictness of the project, and a floor set from it measures nothing.
    """
    config = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    patterns = _strict_patterns(config)
    modules = [
        str(path.relative_to(root).with_suffix("")).replace("/", ".").removesuffix(".__init__")
        for path in sorted(package.rglob("*.py"))
        if not any(part in skip_parts for part in path.parts)
    ]
    return sum(any(fnmatch.fnmatch(module, pattern) for pattern in patterns) for module in modules)


def list_literal_length(path: pathlib.Path, name: str) -> int:
    """How many entries a list literal assigned to `name` holds.

    A register kept as a list in source is read here **without importing the file**.
    Importing would drag in whatever else the module does at import time — for a
    register that lives in a test file, that is the entire fixture apparatus, in a
    job that has no test runner installed.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
            raise TypeError(f"{name} in {path.name} is not a literal sequence")
        return len(node.value.elts)
    raise RuntimeError(f"cannot find the register {name} in {path.name}")
