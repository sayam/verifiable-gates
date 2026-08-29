"""DECISIONS.md — every deliberate non-decision has a reason and a condition, none stale.

An outside audit on 2026-08-29 read deliberate choices as gaps because the
reasons lived in comments and commit messages. The record is a table with a
shape a machine can hold: a `why`, an `expires when`, unique ids, ISO dates —
and a `revisit` date that, once passed, turns the suite red until the row is
re-decided. A decision nobody has to revisit is a decision that outlives its
reason in silence.
"""

from __future__ import annotations

import datetime
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
RECORD = ROOT / "DECISIONS.md"
COLUMNS = ("id", "decided", "decision", "why", "expires when", "revisit")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def rows() -> list[dict[str, str]]:
    """The table's rows as dicts — the header defines the columns, the test holds the header."""
    lines = [
        line for line in RECORD.read_text(encoding="utf-8").splitlines() if line.startswith("|")
    ]
    header = tuple(cell.strip() for cell in lines[0].strip("|").split("|"))
    assert header == COLUMNS, f"the columns are {header}, expected {COLUMNS}"
    found = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        assert len(cells) == len(COLUMNS), f"a row with {len(cells)} cells: {line}"
        found.append(dict(zip(COLUMNS, cells, strict=True)))
    return found


def test_there_are_decisions_recorded() -> None:
    assert len(rows()) >= 5


def test_ids_are_unique_and_kebab_case() -> None:
    ids = [row["id"] for row in rows()]

    assert len(ids) == len(set(ids)), "an id appears twice"
    assert all(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", i) for i in ids), ids


@pytest.mark.parametrize("column", ["decision", "why", "expires when"])
def test_every_row_says(column: str) -> None:
    """A decision with no reason is a preference; one with no expiry outlives its reason."""
    empty = [row["id"] for row in rows() if not row[column]]

    assert empty == [], f"rows with an empty `{column}`: {empty}"


def test_dates_are_iso_and_not_in_the_future() -> None:
    today = datetime.datetime.now(datetime.UTC).date().isoformat()
    for row in rows():
        assert ISO.match(row["decided"]), f"{row['id']}: decided {row['decided']!r}"
        assert row["decided"] <= today, f"{row['id']}: decided in the future"
        if row["revisit"]:
            assert ISO.match(row["revisit"]), f"{row['id']}: revisit {row['revisit']!r}"


def test_no_revisit_date_has_passed() -> None:
    """The one mechanical expiry: a date. Past it, somebody re-decides or the suite stays red."""
    today = datetime.datetime.now(datetime.UTC).date().isoformat()
    overdue = [row["id"] for row in rows() if row["revisit"] and row["revisit"] < today]

    assert overdue == [], (
        f"decisions past their revisit date: {overdue} — re-decide each one: delete the row, "
        "rewrite it, or move the date in a commit that says why"
    )
