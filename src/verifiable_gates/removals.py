"""What left, and was not put back — read from the history that already records it.

The record of every removal exists already, in the version history. Nothing is
lost in the strict sense. What is missing is **anybody reading it**, and that
shape recurs: a project does not need another place to write things down, it
needs a place to read them from.

The concrete difficulty is that a removal and a rewrite look identical. Asking
the history for deleted lines under one document in the reference implementation
returned 31 of them over the repository's lifetime, and no eye could tell which
were rows taken away from which were rows reworded — that needs opening each
change one at a time, which is why nobody did.

So this counts **what disappeared from a file and was not added back within the
same commit**. A rename is a removal and an addition together, and so is a
reworded row; neither is a removal in the sense anyone cares about. Both of the
entries that vanished from the reference implementation's own gate register over
its whole lifetime turned out to be renames.

**The similarity threshold is an interpretation, not a fact**, so the count of
things dismissed as rewrites is printed rather than dropped in silence. A census
that quietly discards what it could not classify is a census that reports good
news it did not earn.

This keeps no state of its own, deliberately. It reads the history and prints one
page.

Role: reader — it reports. Its evidence is that the numbers printed match the
source, and that nothing is dropped in silence.
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import pathlib
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import re

__all__ = [
    "EDIT_SIMILARITY",
    "GIT_TIMEOUT_SECONDS",
    "SEP",
    "Pile",
    "census",
    "deleted_files",
    "main",
    "removed_entries",
]

# `subprocess.run` without `timeout=` waits forever, which in CI is a job that
# never ends and reports nothing.
GIT_TIMEOUT_SECONDS = 120

# Separator between a commit's hash and its subject. **Never a null byte**: an
# argument containing `\x00` cannot be passed to a subprocess at all — it raises
# before the process starts. U+241F is a symbol that cannot occur in a real
# subject line.
SEP = "␟"

# How alike a line that vanished and a line that arrived have to be before this
# counts as one row reworded rather than one row taken away. **An interpretation,
# not a fact** — which is why what it dismisses is reported, never dropped.
EDIT_SIMILARITY = 0.6


@dataclasses.dataclass(frozen=True)
class Pile:
    """One kind of thing that can be taken away without anyone noticing.

    `path` is either a file whose lines are examined, or a directory (written
    with a trailing separator) whose deleted files are counted instead. `pattern`
    picks one entry out of one line; its first group is the entry's name.
    """

    path: str
    pattern: re.Pattern[str]

    @property
    def is_a_directory(self) -> bool:
        return self.path.endswith("/")


def _git(root: pathlib.Path, *args: str) -> str:
    binary = shutil.which("git")
    if not binary:
        raise RuntimeError(
            "git is not on this machine — this reader reads the history and nothing else"
        )
    done = subprocess.run(  # noqa: S603 — a fixed command, its path from shutil.which
        [binary, *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    return done.stdout


def deleted_files(root: pathlib.Path, path: str, since: str) -> list[tuple[str, str, str]]:
    """(commit, subject, file) for files deleted under a directory, renames excluded."""
    raw = _git(
        root,
        "log",
        f"--since={since}",
        "--diff-filter=D",
        "--name-only",
        f"--format=%h{SEP}%s",
        "--",
        path,
    )
    found = []
    commit = subject = ""
    for line in raw.splitlines():
        if SEP in line:
            commit, subject = line.split(SEP, 1)
        elif line.strip():
            found.append((commit, subject, line.strip()))
    return found


def _looks_like_an_edit(gone: str, added: set[str]) -> bool:
    """A line that left with a near-twin arriving in the same commit is a rewrite."""
    return any(
        difflib.SequenceMatcher(None, gone, candidate).ratio() >= EDIT_SIMILARITY
        for candidate in added
    )


def removed_entries(
    root: pathlib.Path, pile: Pile, since: str
) -> tuple[list[tuple[str, str, str]], int]:
    """(entries taken away, entries read as rewrites)

    A rename and a rewording are both a deletion and an addition inside one
    commit. Counting every line that begins with a minus turns both into
    removals, and the report fills up with things that never went anywhere —
    **which is exactly the difference no eye could see in the raw history.**
    """
    raw = _git(root, "log", f"--since={since}", "-p", f"--format=%h{SEP}%s", "--", pile.path)
    found: list[tuple[str, str, str]] = []
    edits = 0
    commit = subject = ""
    gone: list[str] = []
    added: set[str] = set()

    def flush() -> None:
        nonlocal edits
        for item in gone:
            if item in added or _looks_like_an_edit(item, added):
                edits += 1
            else:
                found.append((commit, subject, item))

    for line in raw.splitlines():
        if SEP in line and not line.startswith(("+", "-")):
            flush()
            commit, subject = line.split(SEP, 1)
            gone, added = [], set()
        elif line.startswith("-") and not line.startswith("---"):
            if match := pile.pattern.match(line[1:]):
                gone.append(match.group(1).strip())
        elif line.startswith("+") and not line.startswith("+++"):
            if match := pile.pattern.match(line[1:]):
                added.add(match.group(1).strip())
    flush()
    return found, edits


def census(
    root: pathlib.Path, watched: dict[str, Pile], since: str
) -> tuple[dict[str, list[tuple[str, str, str]]], int]:
    """(each pile → what left it, how many were read as rewrites)"""
    result: dict[str, list[tuple[str, str, str]]] = {}
    edits = 0
    for name, pile in watched.items():
        if pile.is_a_directory:
            result[name] = deleted_files(root, pile.path, since)
        else:
            result[name], counted = removed_entries(root, pile, since)
            edits += counted
    return result, edits


def report(
    found: dict[str, list[tuple[str, str, str]]], edits: int, since: str, epilogue: str = ""
) -> str:
    """One page — **an empty pile says it is empty** rather than leaving the report.

    A pile that disappears from the report when it has nothing in it reads the
    same as a pile nobody is watching any more.
    """
    total = sum(len(items) for items in found.values())
    lines = [f"What was taken away — since {since} · {total} in total", ""]
    for name, items in found.items():
        lines.append(f"## {name} — {len(items)}")
        lines += [
            f"  {commit} {item[:56]}  ({subject[:52]})" for commit, subject, item in items
        ] or ["  (none)"]
        lines.append("")
    lines += [
        f"Another {edits} were read as **rewrites** — something closely alike arrived in the",
        "same commit — and so are not counted as removals. That number is printed because it",
        "is an interpretation rather than a fact, and what gets cut in silence is what nobody",
        "reviews.",
        "",
        "A deliberate removal carries its reason in its own commit subject. A row whose",
        "subject does not say why it went is a row somebody has to be asked about.",
    ]
    if epilogue:
        lines += ["", epilogue]
    return "\n".join(lines)


def main(
    argv: list[str] | None = None,
    *,
    root: pathlib.Path | None = None,
    watched: dict[str, Pile] | None = None,
    epilogue: str = "",
) -> int:
    """Print the report. 0 when it read something, 2 when nothing was declared.

    **An empty manifest is not an empty report.** Driven by a project that
    declared no piles, this would otherwise print "0 in total" — the very page it
    prints when a month went by and nothing was taken away.
    """
    parser = argparse.ArgumentParser(description="What left the watched files, and stayed gone.")
    parser.add_argument("--root", default=".", help="repository to read (default: .)")
    parser.add_argument("--since", default="30.days", help="any span git understands")
    args = parser.parse_args(argv)

    if not watched:
        print(
            "no piles declared — this reader is driven by a project's manifest of what to "
            "watch, and has nothing to read without one",
            file=sys.stderr,
        )
        return 2

    found, edits = census(root or pathlib.Path(args.root).resolve(), watched, args.since)
    print(report(found, edits, args.since, epilogue))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
