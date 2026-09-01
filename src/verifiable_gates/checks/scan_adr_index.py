"""gate: adr-index-complete — the ADR index covers every record, numbered without repeats or gaps,
and supersessions are recorded in both directions.

A stale index is worse than no index: the reader believes they are seeing all of
it while the most recent decisions are missing. In the reference implementation
the index once trailed by seven records, from the phase that decided the largest
things in the project.

The title's last clause had no code behind it: a record saying `Supersedes: 0001`
while 0001 said nothing was clean (self-audit, 2026-08-31). A supersession is read
from both records — `Supersedes:` on the new one, `Superseded by:` on the old — and
each side has to name the other. An index link may carry a title in its text
(`[0001: Use X](…)`) or sit in a table row (`| 0001 | [Use X](…) |`); both were
"missing from the index", and a record named in capitals was not a record at all.

exit 0 = clean or N/A · 1 = findings · 2 = called wrongly

Role: decider — it answers pass or fail with an exit code, and it ships as a
standalone file; its evidence is a planted violation and a clean tree in
`tests/test_checks_behaviour.py`.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys


def _shown(path: str | pathlib.Path) -> str:
    """A path as text that can always be printed.

    A file name here is bytes, not characters. One that is not UTF-8 arrives from the
    directory listing carrying surrogates, and printing it raises `UnicodeEncodeError`:
    a traceback and exit 1 — the code that means *findings* — from a scanner that had a
    verdict to give, losing every finding it had already collected (self-audit round 15,
    2026-09-01). A name nobody can decode is still a name; it is shown with its bytes
    escaped, and the verdict stands.
    """
    return os.fsencode(str(path)).decode("utf-8", "backslashreplace")


class _UnreadableError(Exception):
    """Bytes this scanner cannot decode. No verdict — never a clean one."""


def _text(path: pathlib.Path) -> str:
    """The file's text, or `_UnreadableError` naming it.

    A file that is not UTF-8 made every scanner but the two AST readers die of a raw
    `UnicodeDecodeError` and exit 1 — the code that means findings (self-audit round 3,
    2026-09-01). A byte sequence nobody can decode is the third answer, not a verdict.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as problem:
        # `OSError` too: a file the scanner is not allowed to read, or that turned into
        # a directory between the glob and the read, was still a raw traceback after the
        # decode guard landed — the guard was written for the exception in hand rather
        # than for the question (self-audit round 5, 2026-09-01).
        message = f"{_shown(path)}: {problem}"
        raise _UnreadableError(message) from problem


def _config(path: pathlib.Path) -> dict[str, object]:
    """The project's `scaffold.json`, or the third answer saying why it is not one.

    Round 3 wrapped the *read* of this file and stopped one line short of the parse, so a
    configuration that is malformed, empty, or saved with a byte-order mark — and one that
    parses to a list, a string or `null` rather than an object — was still a raw traceback
    and exit 1, the code that means *findings*, out of a scanner that had judged nothing
    (self-audit round 17, 2026-09-01). A file nobody can read as a configuration is the
    same answer as one nobody can decode: no verdict, said plainly.
    """
    if not path.is_file():
        return {}
    try:
        config = json.loads(_text(path))
    except json.JSONDecodeError as problem:
        raise _UnreadableError(
            f"{_shown(path)}: not JSON — {problem.msg}, line {problem.lineno}"
        ) from problem
    if not isinstance(config, dict):
        raise _UnreadableError(
            f"{_shown(path)}: not an object — a configuration names keys, "
            f"and this one holds {json.dumps(config)[:40]}"
        )
    return config


FILENAME = re.compile(r"^(\d{4})-[a-z0-9-]+\.md$", re.IGNORECASE)
# The record names this scanner prints all came through that pattern, so they are
# ASCII by construction: unlike its siblings, this one never renders a name it read
# off the disk unfiltered, and only the root it was handed needs `_shown`
# (self-audit round 15, 2026-09-01).
# `[0001](file)`, `[0001: Use X](file)`, or a table row `| 0001 | [Use X](file) |`.
INDEX_LINK = re.compile(r"\[(\d{4})(?:[^\]]*)\]\(([^)]+)\)")
INDEX_ROW = re.compile(r"^\s*\|\s*(\d{4})\s*\|[^\n]*?\[[^\]]*\]\(([^)]+)\)", re.MULTILINE)
SUPERSEDES = re.compile(
    r"^\s*\**supersedes\**\s*:?\s*\**\s*(?:ADR[- ]?)?(\d{4})", re.IGNORECASE | re.MULTILINE
)
SUPERSEDED_BY = re.compile(
    r"^\s*\**superseded[- ]by\**\s*:?\s*\**\s*(?:ADR[- ]?)?(\d{4})", re.IGNORECASE | re.MULTILINE
)


def _supersession_findings(adr_dir: pathlib.Path, on_disk: dict[str, str]) -> list[str]:
    """Every `Supersedes:` names a record that says `Superseded by:` back, and the reverse."""
    supersedes: dict[str, set[str]] = {}
    superseded_by: dict[str, set[str]] = {}
    for number, name in on_disk.items():
        text = (adr_dir / name).read_text(encoding="utf-8", errors="replace")
        supersedes[number] = set(SUPERSEDES.findall(text))
        superseded_by[number] = set(SUPERSEDED_BY.findall(text))
    forward = [
        f"{new} supersedes {old}, but {old} does not say it is superseded by {new}"
        for new, olds in sorted(supersedes.items())
        for old in sorted(olds)
        if new not in superseded_by.get(old, set())
    ]
    backward = [
        f"{old} is superseded by {new}, but {new} does not say it supersedes {old}"
        for old, news in sorted(superseded_by.items())
        for new in sorted(news)
        if old not in supersedes.get(new, set())
    ]
    return forward + backward


OUTSIDE = (
    "scaffold.json names {key} {path}, which leads outside the project — a checker "
    "pointed out of the tree judges files this project does not own"
)


def _inside(root: pathlib.Path, path: pathlib.Path) -> bool:
    """Is `path` still inside the tree this scanner was pointed at?

    The installer was taught this in an earlier round — fourteen files landed outside the
    destination through a `tools` symlink — and the readers were never asked the same
    question. A `scaffold.json` path starting with `/` or climbing with `..` walked out of
    the project, judged files it does not own, and printed them under a path no reviewer
    can open; an absolute one also made `relative_to` raise, so the misconfiguration
    answered with a traceback (self-audit round 13, 2026-09-01).
    """
    return path.resolve().is_relative_to(root.resolve())


MISCONFIGURED = (
    "scaffold.json names {key} {path}, which is not there — a configured path that "
    "is missing is a broken configuration, not nothing to check"
)


MISSHAPEN = (
    "scaffold.json gives {key} {value}, which is not {want} — a configured value of the "
    "wrong shape is a broken configuration, not a value"
)


def _configured_path(config: dict[str, object], key: str, default: str) -> tuple[str | None, str]:
    """The path configured under `key`, or `None` and the finding saying it is not a path.

    `scaffold.json.default` ships the shape of every key it declares and nothing held a
    project to it. A path written as a list, a number or `null` reached `root / value`
    and left a raw `TypeError` and exit 1 — the code that means *findings* — out of a
    scanner that had judged nothing (self-audit round 17, 2026-09-01).
    """
    value = config.get(key, default)
    if isinstance(value, str):
        return value, ""
    return None, MISSHAPEN.format(key=key, value=json.dumps(value)[:40], want="a string")


def _records(adr_dir: pathlib.Path, root: pathlib.Path) -> dict[str, list[str]] | None:
    """The ADR records by number, or `None` when there is nothing of the kind to read.

    A directory that is there and holds no record is not a clean index — it is one this
    scanner cannot see, which the manifest's own words forbid reporting as checked:
    "A rule the tool cannot check must not look like a rule it checked." A Go project
    came back `[ pass]` from the doctor (self-audit round 8, 2026-09-01).
    """
    records = sorted(adr_dir.glob("*.md"))
    if not records:
        print(f"NA: no record under {adr_dir.relative_to(root)} — nothing to check yet")
        return None
    by_number: dict[str, list[str]] = {}
    for record in records:
        if match := FILENAME.match(record.name):
            by_number.setdefault(match.group(1), []).append(record.name)
    return by_number


def _adr_dir(root: pathlib.Path) -> tuple[pathlib.Path | None, int]:
    """Where to look, or why there is nothing to look at — with the exit code for that."""
    config_path = root / "scaffold.json"
    # A project that has not configured the bundle is not a misuse — the paths
    # below fall back to their defaults, and a default that is not there reports
    # NA. A path the project *named* and does not have is the opposite case: a
    # broken configuration, reported as a finding — an outside audit on
    # 2026-08-29 planted a `scaffold.json` pointing at a Dockerfile that did not
    # exist beside a dirty one that did, and the answer was "nothing to check".
    config = _config(config_path)
    named, wrong = _configured_path(config, "adr_path", "docs/adr")
    if named is None:
        print(f"adr-index-complete: {wrong}")
        return None, 1
    adr_dir = root / named
    if not _inside(root, adr_dir):
        print("adr-index-complete: " + OUTSIDE.format(key="adr_path", path=named))
        return None, 1
    if adr_dir.is_dir():
        return adr_dir, 0
    if "adr_path" in config:
        print(
            "adr-index-complete: "
            + MISCONFIGURED.format(key="adr_path", path=adr_dir.relative_to(root))
        )
        return None, 1
    print(f"NA: no {adr_dir.relative_to(root)} — nothing to check yet")
    return None, 0


def _judge(root: pathlib.Path) -> int:
    if not root.is_dir():
        # NA means "this project has nothing of that kind"; a root that is not
        # there has no project to say it about, and answering the second with
        # the first is a green over nothing (self-audit round 2, 2026-08-31).
        print(f"cannot read the tree: {_shown(root)} is not a directory", file=sys.stderr)
        return 2
    adr_dir, code = _adr_dir(root)
    if adr_dir is None:
        return code

    by_number = _records(adr_dir, root)
    if by_number is None:
        return 0

    on_disk = {number: names[0] for number, names in by_number.items()}
    index = adr_dir / "README.md"
    listed: dict[str, str] = {}
    if index.is_file():
        text = _text(index)
        listed = dict(INDEX_LINK.findall(text)) | dict(INDEX_ROW.findall(text))

    findings: list[str] = []
    # Two records with one number: a dict keyed by number kept one and lost the
    # other silently (outside audit, 2026-08-30) — the rule says without repeats.
    findings += [
        f"number used twice: {', '.join(names)}" for names in by_number.values() if len(names) > 1
    ]
    if on_disk and not index.is_file():
        findings.append("records exist but there is no README.md index")
    findings += [
        f"missing from the index: {on_disk[n]}" for n in sorted(on_disk.keys() - listed.keys())
    ]
    findings += [
        f"index points at a file that is gone: {listed[n]}"
        for n in sorted(listed.keys() - on_disk.keys())
    ]

    numbers = sorted(int(n) for n in on_disk)
    if numbers and numbers != list(range(numbers[0], numbers[0] + len(numbers))):
        findings.append(f"gap in the numbering: {numbers}")
    findings += _supersession_findings(adr_dir, on_disk)

    for finding in findings:
        print(f"adr-index-complete: {finding}")
    return 1 if findings else 0


def main(root: pathlib.Path) -> int:
    """The verdict, or the third answer when a file cannot be decoded."""
    try:
        return _judge(root)
    except _UnreadableError as problem:
        print(f"cannot read the tree: {problem}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_adr_index.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
