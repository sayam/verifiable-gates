"""The anti-moves are a register too, and a register nothing holds is a wish.

`CONTRIBUTING.md` § "Anti-moves" names five things this repository will not trade
away. They were the last row of the 2026-09-04 survey of what the gate, rule and
action ecosystem has already paid for — *these are strengths to keep, write them
down* — and for two days nothing did: the survey's own table had a row for every
pitfall to close and a sentence, outside the table, for the five to keep. A
commitment with no row is one nothing ever reports as open (round 28's
re-measurement, 2026-09-06).

What this file holds is the part a machine can: the five, in order, and every
holder each row names — a path that must be in the tree, a `DECISIONS.md` id that
must be a row there. Two-way, so a holder added to the page is added here, and a
test file renamed cannot leave the page pointing at nothing.

What it cannot hold is whether the anti-move is still *kept*; that is what the
holders themselves are for, and where a row has none the page says so in the open.
"""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
DECISIONS = ROOT / "DECISIONS.md"
SECTION = "## Anti-moves — the five things this repository will not trade away"

# The lead phrase of each row, in the page's order, with what that row says holds it:
# (paths that must be in the tree, `DECISIONS.md` ids that must be rows there).
HELD: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "One record per project, and no second dialect.": (
        ("tests/test_install_and_doctor.py",),
        ("rules-are-read-off-the-installed-bundle",),
    ),
    "A rule the bundle decides has a scanner, and the scanner has a pair of trees of its own.": (
        ("tests/test_checks_behaviour.py", "tests/test_scan_coverage.py"),
        (),
    ),
    "Two severities, and something reads each of them: `blocking` and `watched`.": (
        ("src/verifiable_gates/registry.py", "tests/test_registry.py"),
        (),
    ),
    "An instruction file points at the installed bundle; it never copies what the bundle says.": (
        ("tests/test_manifest.py",),
        (
            "agent-instructions-point-and-do-not-copy",
            "rules-are-read-off-the-installed-bundle",
        ),
    ),
    "A gate arrives carrying the incident it caught, and the list of gates allowed to lack one"
    " only shrinks.": (
        ("tests/test_gate_evidence.py", "tests/test_proved_by_refs.py"),
        (),
    ),
}

ROW = re.compile(r"^\| \*\*(?P<lead>.+?)\*\*(?P<rest>.*)\|$", re.MULTILINE)
PATH_LIKE = re.compile(r"`([a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)+\.(?:py|md|yaml|yml|json))`")


def section() -> str:
    """The anti-moves section, or an assertion naming what moved."""
    text = CONTRIBUTING.read_text(encoding="utf-8")
    assert SECTION in text, f"{SECTION!r} is not in CONTRIBUTING.md — the section was renamed"
    return text.split(SECTION, 1)[1].split("\n## ", 1)[0]


def rows() -> list[tuple[str, str]]:
    return [(found["lead"], found["rest"]) for found in ROW.finditer(section())]


def decision_ids() -> set[str]:
    lines = [line for line in DECISIONS.read_text(encoding="utf-8").splitlines() if line[:1] == "|"]
    return {line.strip("|").split("|")[0].strip() for line in lines[2:]}


def test_the_page_names_these_five_in_this_order() -> None:
    """A row leaves the page only by leaving this file too, and arrives the same way."""
    assert [lead for lead, _ in rows()] == list(HELD), (
        "the anti-moves on the page and the ones held here differ — change both together"
    )


@pytest.mark.parametrize("lead", HELD, ids=lambda text: text.split(",")[0][:40])
def test_every_holder_a_row_names_is_really_there(lead: str) -> None:
    """A page that cites a test file which is gone points a reader at nothing."""
    rest = dict(rows())[lead]
    paths, decisions = HELD[lead]
    for path in paths:
        assert path in rest, f"{lead!r} no longer names {path}"
        assert (ROOT / path).is_file(), f"{lead!r} names {path}, which is not in the tree"
    for decision in decisions:
        assert decision in rest, f"{lead!r} no longer names {decision}"
        assert decision in decision_ids(), f"{lead!r} names {decision}, not a row in DECISIONS.md"


@pytest.mark.parametrize("lead", HELD, ids=lambda text: text.split(",")[0][:40])
def test_a_path_added_to_a_row_is_added_here_too(lead: str) -> None:
    """The other direction: a holder cited on the page that this file does not know is a
    holder nothing checks — which is how the page starts naming files that have moved."""
    rest = dict(rows())[lead]
    assert sorted(set(PATH_LIKE.findall(rest))) == sorted(set(HELD[lead][0])), (
        f"{lead!r} cites paths this file does not hold — add them to HELD in the same change"
    )
