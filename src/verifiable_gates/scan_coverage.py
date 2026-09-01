"""A scan that found nothing looks exactly like a scan that ran on nothing.

Exit zero from a static analyser means "no findings", and that is indistinguishable
from "no files". A whole directory can drop out of a scan — a default exclude
nobody read, a working directory that was not what somebody assumed, a pattern
that stopped matching — and the result is green, quiet, and permanent. **Nothing
in the output differs from the day it worked.**

This happened in the reference implementation: a scanner's own built-in defaults
excluded the test tree, so 61 of 136 files were never scanned at all, while the
workflow said it excluded two directories it had named itself. Nobody lied and
nobody measured.

So the answer is not a minimum count. A floor catches "the whole thing vanished"
and misses "one directory vanished", and the second is the shape the real bug
took. What is checked instead is the **set of files the scan reports having read,
against the set that should have been read** — derived from what the project
actually tracks, minus what it declares it skips.

Three more things a report has to prove, because each of them fails green:

- **Rules were loaded at all.** A run with an empty rule set finds nothing.
- **No rule was skipped.** A rule the tool could not parse is one that stops
  checking without anybody deciding it should.
- **The tool reported no errors of its own.** A file it failed to read is a file
  it did not scan.

**Scanning more than expected is not a fault** — files not yet tracked get read
on a developer's machine, and reading extra is safety. Only the missing direction
is a hole, so only that direction is red.

**The numbers are printed even when it passes.** A check that is silent when
green gives nobody a way to notice the day it starts reading less.

Role: decider — it answers pass or fail. Running the scanner belongs to the
caller; this is handed its report.
"""

from __future__ import annotations

import dataclasses
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pathlib

__all__ = [
    "GIT_TIMEOUT_SECONDS",
    "MESSAGES",
    "Report",
    "expected_files",
    "problems",
    "skipped_prefixes",
    "tracked_files",
]

# `subprocess.run` without `timeout=` waits forever, which in CI is a job that
# never ends and reports nothing.
GIT_TIMEOUT_SECONDS = 60

MESSAGES = {
    "no_rules": (
        "no rules were used at all — the config did not load, or the flag that reports "
        "rule timings is missing"
    ),
    "errors": "the scanner reported {count} error(s) of its own: {sample}",
    "skipped_rules": "{count} rule(s) were skipped — a rule that cannot load stops checking",
    "missed": (
        "{count} file(s) that should have been scanned were not: {sample} · if skipping them "
        "is intended, declare it where the skips are declared — do not let them vanish"
    ),
}


def skipped_prefixes(path: pathlib.Path) -> list[str]:
    """Directories a project declares it does not scan, read from its own ignore file.

    **Plain directory names only**, which is all such a file usually holds. A glob
    would make the expected set wrong rather than merely incomplete, so a project
    keeping this simple is a precondition worth writing down where the file lives.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip().rstrip("/") for line in lines if line.strip() and not line.startswith("#")]


def tracked_files(root: pathlib.Path, pattern: str) -> set[str]:
    """What the project tracks, asked of the version control rather than the disk.

    "What is our code" is a question the history answers better than a directory
    walk: something not committed is not code the pipeline is answerable for.
    """
    binary = shutil.which("git")
    if not binary:
        raise RuntimeError("git is not on this machine — this reader asks it what is tracked")
    listed = subprocess.run(  # noqa: S603 — a fixed command, its path from shutil.which
        [binary, "ls-files", pattern],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    return set(listed.stdout.split())


def expected_files(root: pathlib.Path, pattern: str, skipped: list[str]) -> set[str]:
    """Everything tracked and matching, minus everything declared skipped."""
    prefixes = tuple(f"{prefix}/" for prefix in skipped)
    return {path for path in tracked_files(root, pattern) if not path.startswith(prefixes)}


@dataclasses.dataclass(frozen=True)
class Report:
    """What a scanner's own report says about the run, apart from its findings.

    Four facts, kept together because each of them fails green on its own and a
    caller passing three of the four would not know which it forgot.
    """

    scanned: set[str]
    rules: int
    errors: list[object] = dataclasses.field(default_factory=list)
    skipped_rules: list[object] = dataclasses.field(default_factory=list)


def problems(
    report: Report, expected: set[str], messages: dict[str, str] | None = None
) -> list[str]:
    """Everything about this run that would otherwise pass green.

    Findings themselves are the caller's to report: they are what the scanner is
    for, and they read differently from "the scan did not happen".
    """
    text = {**MESSAGES, **(messages or {})}
    found = []
    if not report.rules:
        found.append(text["no_rules"])
    if report.errors:
        found.append(text["errors"].format(count=len(report.errors), sample=report.errors[:3]))
    if report.skipped_rules:
        found.append(text["skipped_rules"].format(count=len(report.skipped_rules)))

    missed = sorted(expected - report.scanned)
    if missed:
        found.append(text["missed"].format(count=len(missed), sample=missed[:10]))
    return found


if __name__ == "__main__":
    # A helper is not a command. Run as one, these modules imported cleanly and exited 0
    # with nothing done — a wrong call that looked like a pass, which `gates.yaml` forbids
    # in as many words ("A misuse must exit 2, never 0"). Round 11 gave seven modules this
    # guard from a list written by hand, and the list was seven short (self-audit round 12,
    # 2026-09-01); the test now reads the package instead of remembering it.
    sys.stderr.write(
        "verifiable_gates.scan_coverage is a helper, not a command — it has no entry point of\n"
        "its own; the readers that answer for themselves are listed in CONTRIBUTING.\n"
    )
    sys.exit(2)
