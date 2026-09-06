"""The checker reference answers, for every checker, what a pass does not say.

Round 22's second track asked which of the nine measure *presence* — a file exists,
a row is there — and which read the thing itself, because a suite that never says
which kind a check is lets the two be read as one. The question outlived every round
that was supposed to answer it: the reference page grew a table of what each checker
overlaps with other tools (round 28) and one of what each *reads*, and neither is
that question (re-measurement, 2026-09-06).

The table is now in `docs/checker-reference.md`, and this file holds it to the
catalogue: the nine rows are the nine rules that ship a scanner, in the page's own
section order, each with a non-empty *what a pass does not say* — the cell that is
the point, and the cell a tidy-up would drop first because nothing else reads it.
Every `DECISIONS.md` id the table cites has to be a row there, for the same reason
the audit guide's paths are checked: a page that cites a record which is gone sends
a reader to nothing.
"""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "checker-reference.md"
DECISIONS = ROOT / "DECISIONS.md"
SECTION = "## What each one decides, and what a pass does not say"

ROW = re.compile(r"^\| `(?P<id>[a-z0-9-]+)` \|(?P<about>[^|]*)\|(?P<silent>[^|]*)\|$", re.MULTILINE)
HEADING = re.compile(r"^## (?P<id>[a-z0-9-]+)$", re.MULTILINE)
DECISION_CITED = re.compile(r"`DECISIONS\.md` `(?P<id>[a-z0-9-]+)`")


def page() -> str:
    return PAGE.read_text(encoding="utf-8")


def table() -> list[re.Match[str]]:
    text = page()
    assert SECTION in text, f"{SECTION!r} is gone from the page — the section was renamed"
    return list(ROW.finditer(text.split(SECTION, 1)[1].split("\n## ", 1)[0]))


def shipped() -> list[str]:
    rules = yaml.safe_load((ROOT / "rules.yaml").read_text(encoding="utf-8"))["rules"]
    return [rule["id"] for rule in rules if "script" in rule]


def test_the_table_covers_every_checker_the_bundle_ships_and_no_other() -> None:
    """Two-way. A scanner added to the bundle with no row here is a checker whose silence
    nobody wrote down; a row for a rule that ships no scanner describes a tool that is not
    there."""
    assert sorted(found["id"] for found in table()) == sorted(shipped())


def test_the_table_is_in_the_order_the_page_walks_them() -> None:
    """The page says its sections are in the order the doctor prints them, and a reader
    goes from the table to the section. Two orders on one page is one of them wrong."""
    walked = [found["id"] for found in HEADING.finditer(page()) if found["id"] in set(shipped())]

    assert [found["id"] for found in table()] == walked


@pytest.mark.parametrize("gid", shipped())
def test_every_row_says_what_a_pass_does_not_say(gid: str) -> None:
    """The cell that is the whole point of the table, and the one nothing else reads."""
    row = next(found for found in table() if found["id"] == gid)
    assert row["about"].strip(), f"{gid}: what a finding is about is empty"
    silent = row["silent"].strip()
    assert len(silent) > 30, f"{gid}: `what a pass does not say` is {silent!r} — that is a shrug"


def test_every_decision_the_table_cites_is_a_row_in_the_record() -> None:
    """A citation that resolves to nothing is worse than none: it looks checked."""
    lines = [line for line in DECISIONS.read_text(encoding="utf-8").splitlines() if line[:1] == "|"]
    ids = {line.strip("|").split("|")[0].strip() for line in lines[2:]}
    cited = {found["id"] for found in DECISION_CITED.finditer(page())}

    assert cited, "the page cites no decision at all — if that is deliberate, delete this check"
    assert cited <= ids, f"the page cites {sorted(cited - ids)}, which is not in DECISIONS.md"
