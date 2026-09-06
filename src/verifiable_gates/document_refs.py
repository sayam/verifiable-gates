"""Every number a document points at, opened on the platform — read-only.

The catalogues' refs are resolved by `proved_by_refs`: a gate's `proved_by.ref` and a
practice's `held_on`, both held to their shape at test time and asked about weekly. The
prose is the other half and was held by nothing. `CHANGELOG.md` alone points at more than a
hundred pull requests, and every one of them is a claim of the same kind — *this is where
it happened, go and read it* — with no shape check, no resolution and nothing to notice
when a number is a typo, a renumbering, or a pull request that no longer exists.

What counts as a ref here is what a reader would click: `#N`, and `owner/repo#N` when it is
somebody else's repository. GitHub numbers issues and pull requests in one sequence, so the
issues endpoint answers for both and this reader asks only whether the number **opens** —
which of the two it is, and whether it says what the sentence claims, is the reader's
judgement and stays theirs.

Code is not prose: a fenced block and a code span are stripped before the scan, because
`echo "step #1"` and `&#10;` are not references to anything, and a check that reported them
would be turned off within a week.

A register, `DELETED_ON_REQUEST`, carries the numbers that will never open again — pull
requests GitHub Support deleted at the owner's request, whose merge commits carried an
address that must not be published. The entries the register excuses are named in a
CHANGELOG entry that says exactly that, and history is not rewritten to hide them. It is
held in both directions: a number that opens again is a finding telling you to take it out,
and a number no document points at is a finding too, so the register cannot park anything.

Three answers, as every decider here:

- exit 0 — every number opens, or is one the register excuses;
- exit 1 — a number answers 404 and is not excused, an excused number opens after all, or
  the register names something no document points at;
- exit 2 — the platform or git could not be asked: "could not look" is not a pass.

Role: decider — it answers with an exit code, and a posture step blocks on it.
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import re
import sys

from verifiable_gates import proved_by_refs, scan_coverage

__all__ = ["DELETED_ON_REQUEST", "TRACKED", "collect", "main", "problems", "refs_in"]

# What a reader reads. Not `*.py`: a test fixture says `#1` and means a fixture, and a
# checker that walks fixtures is one nobody keeps (measured 2026-09-06 — thirteen such
# numbers in the suite, four of them invented).
TRACKED = ("*.md", "*.yaml", "*.yml")

FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
SPAN = re.compile(r"`[^`\n]*`")
# `#316`, `sayam/flask-todolist#225`. Not `#fff`, not a heading, not `x#3` — and the
# trailing guard keeps `#10;` out of it once the code spans are gone.
REF = re.compile(r"(?<![\w/])(?P<repo>[\w.-]+/[\w.-]+)?#(?P<n>\d{1,6})(?![\w-])")

# Pull requests deleted by GitHub Support on 2026-09-04 (ticket 4717542), because their
# merge commits carried an address that must never be published. The CHANGELOG entry that
# names them is the record of the purge and says they are gone; it is not rewritten.
DELETED_ON_REQUEST: dict[str, str] = {
    "#2": "deleted in the orphan purge of 2026-09-04, with #3–#6",
    "#7": "deleted in the orphan purge of 2026-09-04, the end of the #2–#7 range",
    "#32": "deleted in the orphan purge of 2026-09-04, with #33",
    "#34": "deleted in the orphan purge of 2026-09-04, the end of the #32–#34 range",
}


def refs_in(text: str) -> list[str]:
    """Every ref the prose of `text` points at, code stripped, in the order they appear."""
    prose = SPAN.sub(" ", FENCE.sub(" ", text))
    return [
        f"{found['repo']}#{found['n']}" if found["repo"] else f"#{found['n']}"
        for found in REF.finditer(prose)
    ]


def collect(root: pathlib.Path) -> dict[str, list[str]]:
    """Every distinct ref in the tracked documents, with the files that point at it."""
    cited: dict[str, list[str]] = collections.defaultdict(list)
    for pattern in TRACKED:
        for name in sorted(scan_coverage.tracked_files(root, pattern)):
            text = (root / name).read_text(encoding="utf-8", errors="replace")
            for ref in dict.fromkeys(refs_in(text)):
                cited[ref].append(name)
    return dict(cited)


def problems(cited: dict[str, list[str]], repo: str) -> list[str]:
    """Every ref that does not open and is not excused, said in one line each."""
    found: list[str] = []
    for text in sorted(
        cited, key=lambda ref: (ref.rpartition("#")[0], int(ref.rpartition("#")[2]))
    ):
        why = proved_by_refs.resolve(proved_by_refs.parse(text, repo))
        where = ", ".join(cited[text])
        if why is None:
            if text in DELETED_ON_REQUEST:
                found.append(
                    f"{text} opens after all — take it out of DELETED_ON_REQUEST,"
                    " the register only shrinks"
                )
            continue
        if text in DELETED_ON_REQUEST:
            continue
        found.append(f"{why} — pointed at by: {where}")
    found += [
        f"{text} is in DELETED_ON_REQUEST and no document points at it — the register"
        " names something nothing says"
        for text in sorted(set(DELETED_ON_REQUEST) - set(cited))
    ]
    return found


def main(argv: list[str] | None = None) -> int:
    """Scan the documents, resolve every number, return the code."""
    parser = argparse.ArgumentParser(
        description="Every #N a document points at, opened on GitHub (read-only)."
    )
    parser.add_argument("--root", default=".", help="the checkout (default: here)")
    parser.add_argument(
        "--repo", default=proved_by_refs.DEFAULT_REPO, help="owner/repo a bare #N belongs to"
    )
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root)
    try:
        cited = collect(root)
    except (OSError, RuntimeError) as unreadable:
        print(f"cannot read what this project tracks: {unreadable}", file=sys.stderr)
        return 2
    try:
        found = problems(cited, args.repo)
    except (PermissionError, RuntimeError) as unasked:
        print(f"could not ask the platform: {unasked}", file=sys.stderr)
        return 2
    for line in found:
        print(f"FAIL {line}", file=sys.stderr)
    if found:
        return 1
    excused = len(DELETED_ON_REQUEST)
    files = len({name for names in cited.values() for name in names})
    said = (
        f"every number the documents point at opens: {len(cited) - excused} of {len(cited)}"
        f" across {files} files"
    )
    print(said + (f", {excused} deleted on request" if excused else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
