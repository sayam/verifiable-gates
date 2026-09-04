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

from verifiable_gates import registry

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
    """ "Today" is the date it already is somewhere on Earth, the same answer the gate
    registry gives: a row written at 05:00 in Bangkok and dated with the machine's own
    `date` was "in the future" against plain UTC and turned the suite red, while the same
    date in a `proved_by` row passed (self-audit round 7, 2026-09-01)."""
    today = registry.latest_today().isoformat()
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


# ------------------------------------------------------- the rows are held by id
#
# The shape of every row was held; which rows exist was not — an outside audit
# on 2026-08-30 deleted a row and added one and the suite stayed green both
# times. A register whose members leave in silence says nothing in a year. The
# ids are copied here the way `tests/test_gate_evidence.py` holds proof rows:
# a row removed, or added, is red until the same pull request changes this
# list too, where a reviewer sees the decision being made or unmade.

# …and beside each id its revisit date (empty when the row has none): a clock
# removed from a row left the suite green (self-audit, 2026-08-31).
HELD = {
    "rules-vs-bundle": "",
    "proved-by-optional": "",
    "ref-crosses-repos": "",
    "freeze-tag-vs-release": "",
    "strict-checks-off": "",
    "pip-uppercase-not-a-gap": "",
    "xenon-floor-at-reality": "2026-11-30",
    "interrogate-at-84": "2026-11-30",
    "gitleaks-binary-not-action": "",
    "sbom-from-a-clean-env": "",
    "posture-token-is-a-secret": "2027-02-28",
    "harness-dogfood-one-gate": "",
    "about-field-under-350": "",
    "merge-switches-unreadable-by-the-token": "2026-11-30",
    "doctor-all-na-exits-zero": "2026-11-30",
    "harness-all-skip-exits-zero": "2026-11-30",
    "manifest-problems-is-a-test-time-check": "",
    "git-signing-not-required": "2027-02-28",
    "gitleaks-pinned-by-our-checksum": "2027-02-28",
    "codeql-not-semgrep": "",
    "no-risk-register-here": "",
    "no-cadence-register-here": "",
    "write-scanner-reads-session-delete": "",
    "dependency-licences-read-at-the-pin": "",
    # The seven the owner decided on 2026-09-01, closing §B of the self-audit.
    "proved-by-ref-is-a-shape": "2026-11-27",
    "removals-census-not-run-here": "",
    "asvs-worksheet-not-kept-here": "",
    "pillar-is-content-a-reviewer-sees": "",
    "decisions-have-one-owner": "",
    "a-rule-title-is-the-rule-not-the-scanner": "",
    "proved-by-is-history-not-a-warranty": "",
    # 2026-09-01: merging #201 as Dependabot opened it added the bot to the contributors
    # index, in the week a support ticket was open about that panel.
    "bumps-land-as-the-owners-commit": "",
    # 2026-09-01, later the same day: the owner turned the machine off altogether.
    "dependabot-runs-nowhere-here": "2026-11-30",
    # 2026-09-02: the rules an agent reads are the ones the installed scanners decide.
    "rules-are-read-off-the-installed-bundle": "",
    "the-sheets-live-under-skills": "",
    "distribution-is-two-pipes-nobody-here-owns": "",
    "agent-instructions-point-and-do-not-copy": "",
    "text-is-the-default-sarif-is-a-format": "",
    "ci-runs-the-bundle-the-project-installed": "",
    # 2026-09-03: the third front door judges the tree after the edit, and refuses nothing.
    "the-edit-hook-reports-and-does-not-refuse": "",
    # 2026-09-04: the mode an agent is told to trust checks the record before it speaks.
    "the-rules-are-read-off-a-bundle-that-is-still-intact": "",
    # 2026-09-04: the working catalogue — what a practice must carry before it is written down.
    "a-practice-is-promoted-by-held-on": "",
    "practices-are-held-by-what-they-name": "",
    "the-working-is-english-and-has-no-pillar": "",
    "the-ledger-ships-empty-and-private": "",
    "the-working-is-off-by-default": "",
}

# The rows whose `expires when` is `Never` — an expiry rewritten to "Never" was
# a silent way to make a decision permanent (self-audit, 2026-08-31).
NEVER_EXPIRES = frozenset(["freeze-tag-vs-release"])


def test_the_record_holds_every_row_it_held() -> None:
    """A row leaves the record only by leaving this list too — and arrives the same way."""
    present = [row["id"] for row in rows()]
    assert present == list(HELD), (
        f"removed {sorted(set(HELD) - set(present))}, added "
        f"{sorted(set(present) - set(HELD))}, or reordered — change both in one pull request"
    )


def test_every_rows_revisit_clock_is_the_one_held_here() -> None:
    """A revisit date leaves or changes only with this copy — a clock removed from a row
    turned a red-on-a-date into a row that never asks again (self-audit, 2026-08-31)."""
    clocks = {row["id"]: row["revisit"] for row in rows()}
    drifted = {i: (clocks[i], HELD[i]) for i in clocks if clocks[i] != HELD[i]}
    assert drifted == {}, (
        f"revisit differs (row, held): {drifted} — change both in one pull request"
    )


def test_a_decision_that_never_expires_is_one_this_file_names() -> None:
    """`Never` in `expires when` is a permanent decision; the set of those is held here so
    an expiry cannot be rewritten to it in silence (self-audit, 2026-08-31)."""
    never = {row["id"] for row in rows() if row["expires when"].lower().startswith("never")}
    newly, no_longer = sorted(never - NEVER_EXPIRES), sorted(NEVER_EXPIRES - never)
    assert never == set(NEVER_EXPIRES), f"newly permanent {newly}, no longer {no_longer}"


def test_a_date_that_is_today_somewhere_on_earth_is_not_the_future() -> None:
    """The boundary the two registers used to disagree about: at 22:00 UTC it is already
    tomorrow in Kiritimati, and a person east of UTC dates a row with their own clock."""
    noon_utc = datetime.datetime(2026, 8, 31, 12, 0, tzinfo=datetime.UTC)

    assert registry.latest_today(noon_utc) == datetime.date(2026, 9, 1)
    assert registry.latest_today(noon_utc).isoformat() > "2026-08-31"


def test_a_date_two_days_ahead_is_still_the_future() -> None:
    """The rule is one day of grace, not an open door."""
    noon_utc = datetime.datetime(2026, 8, 31, 12, 0, tzinfo=datetime.UTC)

    assert registry.latest_today(noon_utc).isoformat() < "2026-09-02"
