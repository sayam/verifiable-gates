"""A ratchet's threshold has to sit against reality in both directions.

The direction people expect is the one nothing needs help with: a coverage tool
refuses to pass beneath its own floor. The direction that matters here is the
other one — **nobody raises the floor after the code gets better**, and a floor
left behind permits every line of that improvement to be given back in silence.

Each test below picks one shape of drift and holds the message to what a reader
would have to do about it, because a message that reports a problem without
naming its fix is a message people learn to skim.
"""

from __future__ import annotations

import math

import pytest

from verifiable_gates import ratchets

FLOOR = ratchets.Ratchet("coverage")
COUNT = ratchets.Ratchet("modules", slack=0.0)
CEILING = ratchets.Ratchet("suppressions", kind=ratchets.CEILING)
GUARD = ratchets.Ratchet("gates", kind=ratchets.REMOVAL_GUARD)
OWNED = ratchets.Ratchet("coverage", owned_by_a_tool=True)


def only(found: list[str]) -> str:
    assert len(found) == 1, f"expected exactly one problem, got {found}"
    return found[0]


# ------------------------------------------------------------------- a floor


def test_a_floor_just_below_reality_is_quiet() -> None:
    """The passes-when-it-should direction — inside the declared slack, say nothing."""
    found = ratchets.problems({"coverage": FLOOR}, {"coverage": 97.0}, {"coverage": 97.11})

    assert found == []


def test_a_floor_left_behind_by_reality_is_red() -> None:
    """A point of slack on a coverage floor is roughly fifty covered lines that can go."""
    found = ratchets.problems({"coverage": FLOOR}, {"coverage": 96.0}, {"coverage": 97.11})

    assert "97" in only(found), "the message has to say what the floor should become"


def test_a_floor_above_reality_belongs_to_the_tool_that_owns_it() -> None:
    """Splitting the two directions is the point: they need different advice.

    Reported together, a reader gets two instructions for one problem and half of
    them are wrong.
    """
    found = ratchets.problems({"coverage": OWNED}, {"coverage": 99.0}, {"coverage": 97.11})

    assert found == []


def test_a_floor_nothing_else_watches_reports_its_own_fall() -> None:
    """Without an owning tool this check is the only thing that sees the regression."""
    found = ratchets.problems({"modules": COUNT}, {"modules": 34.0}, {"modules": 33.0})

    assert "regression" in only(found)


def test_a_count_has_no_slack_at_all() -> None:
    """A percentage drifts on its own; a count moves only when a person edits a list.

    Giving a count the slack a percentage needs would let a whole added module sit
    unbanked, which is the exact gap the default exists to close for percentages.
    """
    found = ratchets.problems({"modules": COUNT}, {"modules": 34.0}, {"modules": 35.0})

    assert "35" in only(found)


def test_a_name_with_no_entry_behaves_like_an_ordinary_floor() -> None:
    """Declaring a number should not also require declaring that it is a floor."""
    quiet = ratchets.problems({}, {"anything": 97.0}, {"anything": 97.5})
    loud = ratchets.problems({}, {"anything": 90.0}, {"anything": 97.5})

    assert quiet == []
    assert "97" in only(loud)


# ----------------------------------------------------------------- a ceiling


def test_a_ceiling_that_was_exceeded_is_red() -> None:
    found = ratchets.problems(
        {"suppressions": CEILING}, {"suppressions": 99.0}, {"suppressions": 100.0}
    )

    assert "decision" in only(found), "going over a ceiling has to read as a decision, not a slip"


def test_a_ceiling_with_room_under_it_is_red_too() -> None:
    """The direction a ratchet check exists for, mirrored.

    Space won and not banked is space that gets refilled by the next change, and
    nobody is looking at the moment it happens.
    """
    found = ratchets.problems(
        {"suppressions": CEILING}, {"suppressions": 99.0}, {"suppressions": 90.0}
    )

    assert "90" in only(found), "the message has to say what the ceiling should become"


def test_a_ceiling_flush_against_reality_is_quiet() -> None:
    found = ratchets.problems(
        {"suppressions": CEILING}, {"suppressions": 99.0}, {"suppressions": 99.0}
    )

    assert found == []


# ----------------------------------------------------------- a removal guard


def test_something_removed_is_red() -> None:
    found = ratchets.problems({"gates": GUARD}, {"gates": 10.0}, {"gates": 9.0})

    assert "removed" in only(found), "this has to read as a removal, not as a threshold regressing"


def test_a_removal_guard_grows_freely() -> None:
    """**Where it differs from a ratchet.** Growth is already watched elsewhere.

    Made to travel like a floor, every change that adds a row would also have to
    edit a number somewhere else for nothing in return — and that cost is what
    makes people stop reading a check at all.
    """
    found = ratchets.problems({"gates": GUARD}, {"gates": 10.0}, {"gates": 25.0})

    assert found == []
    assert GUARD.allowed_gap == math.inf


# --------------------------------------------------------------- the wording


def test_the_wording_is_an_input() -> None:
    """The mechanism travels; the prose does not.

    A project reports to its own people, in its own language and its own house
    style, and a fixed string here would make that impossible without forking the
    module. The replacement below reorders the fields as well as rewording, because
    a substitution that only allows the same sentence in other words is not an
    input — it is a translation table.
    """
    found = ratchets.problems(
        {"coverage": FLOOR},
        {"coverage": 96.0},
        {"coverage": 97.11},
        messages={"floor_slack": "{actual:.0f} is where {name} should now sit ({gap:.2f} above)"},
    )

    assert only(found) == "97 is where coverage should now sit (1.11 above)"


def test_an_overridden_message_leaves_the_others_alone() -> None:
    """Overriding one line must not blank the four a project did not mention."""
    found = ratchets.problems(
        {"gates": GUARD},
        {"gates": 10.0},
        {"gates": 9.0},
        messages={"floor_slack": "unused"},
    )

    assert "removed" in only(found)


# ------------------------------------------------------------ shape of a row


def test_a_kind_nobody_defined_is_refused_at_the_point_it_is_written() -> None:
    """A typo in a kind must fail where it is written, not by behaving like a floor."""
    with pytest.raises(ValueError, match="unknown kind"):
        ratchets.Ratchet("x", kind="celing")
