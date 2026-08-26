"""Settings that live off the repository, held to what the project declared.

Every other gate leans on these, and nothing inside a repository can see them.
So the tests here are about the shapes of *drift*, and about the one distinction
that decides whether this check is worth running at all: **cannot read is not the
same as switched off.** Reporting the first as the second is a lie in the
direction that causes wasted work; reporting it as "fine" is a lie in the
direction that causes breaches.

Both directions everywhere, because an exemption goes quiet exactly when the
thing it excuses disappears — which is when a register starts growing a tail of
lines that will one day excuse something nobody decided about.
"""

from __future__ import annotations

from verifiable_gates import posture

EXEMPT = {"scorecard": "a score, not a verdict, and it never runs on a pull request"}


def only(found: list[str]) -> str:
    assert len(found) == 1, f"expected exactly one problem, got {found}"
    return found[0]


# ------------------------------------------------------------ required checks


def test_a_repository_whose_checks_all_agree_is_quiet() -> None:
    found = posture.check_problems(
        required={"test", "lint"},
        on_pull_requests={"test", "lint"},
        produced={"test", "lint", "scorecard"},
        exempt=EXEMPT,
    )

    assert found == []


def test_a_check_that_runs_and_is_not_required_is_red() -> None:
    """It goes red and the pull request merges anyway."""
    found = posture.check_problems(
        required={"test"},
        on_pull_requests={"test", "lint"},
        produced={"test", "lint"},
        exempt=EXEMPT,
    )

    assert "lint" in found[0]


def test_a_required_check_no_job_can_produce_is_red() -> None:
    """**Nothing goes red — the pull request simply never becomes mergeable.**

    The worst shape of failure this module exists for: no signal at all, only a
    pull request that stays open.
    """
    found = posture.check_problems(
        required={"test", "typo"},
        on_pull_requests={"test"},
        produced={"test"},
        exempt=EXEMPT,
    )

    assert "typo" in next(line for line in found if "waits forever" in line)


def test_a_check_neither_required_nor_declared_is_red() -> None:
    """Not being required is allowed; not being *decided* is not."""
    found = posture.check_problems(
        required={"test"},
        on_pull_requests={"test"},
        produced={"test", "scorecard", "nightly"},
        exempt=EXEMPT,
    )

    assert "nightly" in only(found)


def test_the_exemption_register_is_held_against_every_check_not_only_pull_request_ones() -> None:
    """**Where the reference implementation's own register died.**

    Held against the pull-request set, an entry naming a scheduled job can never
    appear in it, so the register is consulted exactly never — it had sat unread
    since the day it was written.
    """
    quiet = posture.check_problems(
        required={"test"},
        on_pull_requests={"test"},
        produced={"test", "scorecard"},
        exempt=EXEMPT,
    )

    assert quiet == [], "a declared scheduled job must not be reported as undeclared"


def test_an_exemption_for_something_that_no_longer_exists_is_red() -> None:
    """The direction nobody watches: exemptions go quiet when their subject leaves."""
    found = posture.check_problems(
        required={"test"},
        on_pull_requests={"test"},
        produced={"test", "scorecard"},
        exempt={**EXEMPT, "removed-long-ago": "why"},
    )

    assert "removed-long-ago" in only(found)


def test_a_matrix_row_is_matched_by_the_job_it_belongs_to() -> None:
    """The register names jobs; the platform reports rows. One entry covers the rows."""
    found = posture.check_problems(
        required=set(),
        on_pull_requests={"dialect (mysql-8)", "dialect (mariadb-11)"},
        produced={"dialect (mysql-8)", "dialect (mariadb-11)"},
        exempt={"dialect": "runs against real database brands, on a schedule"},
    )

    assert found == []


# -------------------------------------------------------------- the switches

DECLARED = {
    "enforce_admins": posture.Setting(
        want=True, why="an exemption for admins is an exemption for anyone"
    ),
    "allow_squash_merge": posture.Setting(
        want=False, why="squash rewrites the subject line past its limit"
    ),
    "delete_branch_on_merge": posture.Setting(
        want=True, why="merged branches pile up unseen", readable=False
    ),
}


def test_a_switch_holding_its_declared_value_is_quiet() -> None:
    state = {"enforce_admins": True, "allow_squash_merge": False}

    assert posture.setting_problems(state, DECLARED) == []


def test_a_switch_that_drifted_is_red_and_says_why_it_matters() -> None:
    state = {"enforce_admins": False, "allow_squash_merge": False}

    found = only(posture.setting_problems(state, DECLARED))

    assert "enforce_admins" in found
    assert "exemption for anyone" in found, "a switch without its reason gets turned off again"


def test_a_field_that_could_not_be_read_is_not_reported_as_switched_off() -> None:
    """**The distinction the whole module turns on.**

    Calling it "off" sends somebody to fix what was never broken; calling it "on"
    is worse. It gets its own answer.
    """
    state = {"enforce_admins": True, "allow_squash_merge": False, "delete_branch_on_merge": None}

    assert posture.setting_problems(state, DECLARED) == []
    assert "delete_branch_on_merge" in only(posture.unreadable(state, DECLARED))


def test_a_readable_field_that_came_back_empty_is_not_absorbed_as_normal() -> None:
    """Only settings *declared* unreadable get the third answer.

    A readable one arriving empty means the platform or the token changed, and
    quietly filing that under "expected" is how a check stops checking.
    """
    state = {"enforce_admins": None}

    assert posture.unreadable(state, DECLARED) == [
        line for line in posture.unreadable(state, DECLARED) if "delete_branch" in line
    ]


def test_a_switch_nobody_can_read_still_carries_the_value_it_should_hold() -> None:
    """A setting that cannot be proven has no owner, and one without an owner has no default.

    The reference implementation lost one this way: the register recorded that no
    machine could see it, and nothing anywhere recorded what it should be. The rule
    it carried was then kept by one person's memory, and forgotten about thirty
    times running.
    """
    assert DECLARED["delete_branch_on_merge"].want is True
    assert DECLARED["delete_branch_on_merge"].why


# ----------------------------------------------------------------- the alerts

OPEN = {"tool": {"name": "CodeQL"}, "rule": {"id": "py/unused"}, "state": "open"}
DISMISSED = {
    "tool": {"name": "CodeQL"},
    "rule": {"id": "py/clear-text"},
    "state": "dismissed",
    "dismissed_comment": "the value is a fixture, not a credential",
}
FIXED = {"tool": {"name": "CodeQL"}, "rule": {"id": "py/gone"}, "state": "fixed"}


def test_an_alert_in_the_register_is_judged() -> None:
    assert posture.alert_problems([OPEN], {"CodeQL/py/unused": "known, tracked"}) == []


def test_an_alert_dismissed_with_a_reason_is_judged() -> None:
    """Two accepted shapes, and this is the one that lives on the platform."""
    assert posture.alert_problems([DISMISSED], {}) == []


def test_an_alert_dismissed_without_a_reason_is_not_judged() -> None:
    """Dismissing without saying why is closing the tab, not deciding."""
    silent = {**DISMISSED, "dismissed_comment": "   "}

    assert "py/clear-text" in only(posture.alert_problems([silent], {}))


def test_an_alert_nobody_has_touched_is_red() -> None:
    assert "py/unused" in only(posture.alert_problems([OPEN], {}))


def test_a_fixed_alert_needs_no_entry() -> None:
    """It went away because the code changed, not because somebody decided."""
    assert posture.alert_problems([FIXED], {}) == []


def test_a_register_line_for_a_fixed_alert_is_red() -> None:
    """A fixed alert must not count as present, or the line that should go stays forever."""
    found = posture.alert_problems([FIXED], {"CodeQL/py/gone": "accepted back then"})

    assert "CodeQL/py/gone" in only(found)


def test_alerts_that_could_not_be_read_are_red_rather_than_empty() -> None:
    """No alerts and no permission to look are the same picture and opposite facts."""
    assert "token lacks the scope" in only(posture.alert_problems(None, {}))


def test_an_empty_list_of_alerts_is_a_clean_answer() -> None:
    assert posture.alert_problems([], {}) == []


# --------------------------------------------------------------- the wording


def test_the_wording_is_an_input() -> None:
    """The mechanism travels; the prose reports to a project's own people."""
    found = posture.check_problems(
        required=set(),
        on_pull_requests={"test"},
        produced={"test"},
        exempt={},
        messages={"missing_check": "not required: {names}"},
    )

    assert found[0] == "not required: ['test']"


def test_one_replaced_message_leaves_the_others_alone() -> None:
    found = posture.alert_problems([OPEN], {}, messages={"stale_alert": "unused"})

    assert "has not been judged" in only(found)
