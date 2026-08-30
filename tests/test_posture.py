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

import json
import pathlib
import re
from typing import Any

import pytest

from verifiable_gates import advisories, check_names, gh, posture, workflows

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
    said = only(posture.unreadable(state, DECLARED))
    assert "delete_branch_on_merge" in said
    assert "True" in said, "a reader told only that it is unreadable has nothing to act on"


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


# ---------------------------------------------------------------- the command line

OPEN_ALERT = {"state": "open", "tool": {"name": "CodeQL"}, "rule": {"id": "py/code-injection"}}


def a_register(tmp_path: pathlib.Path, text: str) -> str:
    path = tmp_path / "accepted.txt"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_an_unjudged_open_alert_is_red_and_named(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gh, "api_pages", lambda _path: [OPEN_ALERT])

    code = posture.main(["--ref", "refs/heads/main", "--register", a_register(tmp_path, "")])

    assert code == 1
    assert "CodeQL/py/code-injection" in capsys.readouterr().err


def test_a_judged_alert_is_green_and_counted(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gh, "api_pages", lambda _path: [OPEN_ALERT])
    register = a_register(tmp_path, "CodeQL/py/code-injection  # a fixture, input is ours\n")

    assert posture.main(["--ref", "refs/heads/main", "--register", register]) == 0
    assert "1 open alert(s) on refs/heads/main, every one judged" in capsys.readouterr().out


def test_the_ref_reaches_the_query(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Alerts belong to a ref; asking without one answers for the default branch, not this PR."""
    asked: list[str] = []

    def record(path: str) -> list[object]:
        asked.append(path)
        return []

    monkeypatch.setattr(gh, "api_pages", record)

    posture.main(["--ref", "refs/pull/9/merge", "--register", a_register(tmp_path, "")])

    assert asked
    assert "ref=refs/pull/9/merge" in asked[0]
    assert "state=open" in asked[0]


def test_alerts_the_token_cannot_read_are_the_third_answer(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(_path: str) -> list[object]:
        raise PermissionError("HTTP 403")

    monkeypatch.setattr(gh, "api_pages", refuse)

    assert posture.main(["--ref", "refs/heads/main", "--register", a_register(tmp_path, "")]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_this_repositorys_alert_register_is_reasoned() -> None:
    root = pathlib.Path(__file__).resolve().parent.parent
    register = advisories.accepted(root / "pins" / "dev" / "code-scanning-accepted.txt")

    assert all(register.values()), f"an entry with no reason: {register}"


# ------------------------------------------------------------ the settings mode

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROTECTION: dict[str, Any] = {
    "enforce_admins": {"enabled": True},
    "required_linear_history": {"enabled": True},
    "allow_force_pushes": {"enabled": False},
    "allow_deletions": {"enabled": False},
    "required_conversation_resolution": {"enabled": True},
    "required_signatures": {"enabled": False},
    "required_status_checks": {"strict": False, "contexts": ["lint"]},
    "required_pull_request_reviews": {"required_approving_review_count": 0},
}
REPO: dict[str, Any] = {
    "allow_squash_merge": False,
    "allow_merge_commit": False,
    "allow_rebase_merge": True,
    "delete_branch_on_merge": True,
    "web_commit_signoff_required": True,
}
SMALL: dict[str, Any] = {
    "branch": "main",
    "settings": {"enforce_admins": {"want": True, "why": "an exemption for admins is for anyone"}},
    "not_required": {},
}


ACTIONS: dict[str, Any] = {"allowed_actions": "selected", "sha_pinning_required": True}
SELECTED: dict[str, Any] = {
    "github_owned_allowed": True,
    "verified_allowed": False,
    "patterns_allowed": [],
}


def a_platform(  # noqa: PLR0913, PLR0917 — one fake, five answers, each optional
    monkeypatch: pytest.MonkeyPatch,
    protection: dict[str, Any],
    repo: dict[str, Any],
    actions: dict[str, Any] | None = None,
    alerts: str = "204",
    selected: dict[str, Any] | None = None,
) -> None:
    """Four answers: protection, the repository, the Actions policy, and the alerts switch
    (`204` on, `404` off, anything else a refusal the census cannot read through)."""

    def answer(path: str) -> dict[str, Any]:
        if "protection" in path:
            return protection
        if path.endswith("selected-actions"):
            return SELECTED if selected is None else selected
        if "actions/permissions" in path:
            return ACTIONS if actions is None else actions
        return repo

    def run(args: list[str], **_kwargs: Any) -> str:  # noqa: ANN401 — mirroring the wrapper
        if alerts == "204":
            return ""
        raise PermissionError(f"`gh {' '.join(args)}` failed: HTTP {alerts}")

    monkeypatch.setattr(gh, "api", answer)
    monkeypatch.setattr(gh, "run", run)


def a_tree(tmp_path: pathlib.Path, register: dict[str, Any]) -> tuple[str, str]:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        "on: [push, pull_request]\njobs:\n  lint:\n    steps: []\n", encoding="utf-8"
    )
    path = tmp_path / "declared.json"
    path.write_text(json.dumps(register), encoding="utf-8")
    return str(path), str(tmp_path)


def test_a_platform_that_matches_the_register_is_green(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    a_platform(monkeypatch, PROTECTION, REPO)
    register, root = a_tree(tmp_path, SMALL)

    assert posture.main(["--settings", register, "--root", root]) == 0
    assert "1 switches hold their declared values on main" in capsys.readouterr().out


def test_a_switch_that_drifted_is_red_with_its_why(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    a_platform(monkeypatch, {**PROTECTION, "enforce_admins": {"enabled": False}}, REPO)
    register, root = a_tree(tmp_path, SMALL)

    assert posture.main(["--settings", register, "--root", root]) == 1
    err = capsys.readouterr().err
    assert "enforce_admins = False" in err
    assert "exemption for admins" in err


def test_a_check_that_runs_on_pull_requests_and_is_not_required_is_red(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    nothing_required = {**PROTECTION, "required_status_checks": {"strict": False, "contexts": []}}
    a_platform(monkeypatch, nothing_required, REPO)
    register, root = a_tree(tmp_path, SMALL)

    assert posture.main(["--settings", register, "--root", root]) == 1
    assert "not required: ['lint']" in capsys.readouterr().err


def test_a_platform_the_token_cannot_read_is_the_third_answer(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No secret, or the wrong scope: exit 2, never a pass."""

    def refuse(_path: str) -> dict[str, Any]:
        raise PermissionError("HTTP 403: Resource not accessible by personal access token")

    monkeypatch.setattr(gh, "api", refuse)
    register, root = a_tree(tmp_path, SMALL)

    assert posture.main(["--settings", register, "--root", root]) == 2
    assert "cannot read the platform's settings" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("alerts", "value"),
    [("204", True), ("404", False), ("403", None), ("403: see /repos/x/404-org", None)],
    ids=["on", "off", "blind", "a-404-in-the-words-is-not-the-status"],
)
def test_the_alerts_switch_is_read_by_status_code_with_a_third_answer(
    monkeypatch: pytest.MonkeyPatch,
    alerts: str,
    value: bool | None,  # noqa: FBT001 — the parametrised expectation
) -> None:
    """The endpoint has no body: 204 is on, 404 is off, and a refusal the token cannot see
    through is `None` — never "off" (the switch was found off and undeclared, 2026-08-30)."""
    a_platform(monkeypatch, PROTECTION, REPO, alerts=alerts)

    state, _required = posture.platform_state("main")

    assert state["dependabot_alerts"] is value
    assert state["sha_pinning_required"] is True
    assert state["required_signatures"] is False, "declared, so it has to be read (2026-08-30)"
    assert state["allowed_actions"] == "selected"


def test_the_selected_actions_detail_is_read_and_a_pattern_is_not_github_owned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`selected` alone is a word; a pattern `*` under it is `all` (pre-cut review)."""
    a_platform(monkeypatch, PROTECTION, REPO, selected={**SELECTED, "patterns_allowed": ["*"]})
    state, _required = posture.platform_state("main")
    want = posture.declared(ROOT / "pins" / "dev" / "posture-declared.json")[1]["selected_actions"]

    assert state["selected_actions"] == {**SELECTED, "patterns_allowed": ["*"]}
    assert posture.setting_problems(state, {"selected_actions": want}) != []


def test_a_selected_actions_answer_that_is_not_a_mapping_is_the_third_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 409 body or an error string in place of the detail is "could not look", not a value."""
    a_platform(monkeypatch, PROTECTION, REPO, selected=["not", "a", "mapping"])  # type: ignore[arg-type]  # the platform's shape, not ours

    assert posture.platform_state("main")[0]["selected_actions"] is None


def test_the_selected_actions_detail_is_none_when_the_policy_is_not_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_platform(monkeypatch, PROTECTION, REPO, actions={**ACTIONS, "allowed_actions": "all"})

    assert posture.platform_state("main")[0]["selected_actions"] is None


def test_a_field_the_answer_does_not_carry_is_none_not_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flattening must keep the third answer: a missing block is `None`, never `False`."""
    a_platform(monkeypatch, {"enforce_admins": {"enabled": True}}, {}, actions={})

    state, required = posture.platform_state("main")

    assert state["enforce_admins"] is True
    assert state["required_linear_history"] is None
    assert state["allow_squash_merge"] is None
    assert state["sha_pinning_required"] is None
    assert required == set()


def test_the_two_modes_are_exclusive_and_ref_needs_a_register() -> None:
    with pytest.raises(SystemExit):
        posture.main(["--settings", "a", "--ref", "b"])
    with pytest.raises(SystemExit):
        posture.main(["--ref", "refs/heads/main"])


def test_this_repositorys_register_names_only_checks_it_produces() -> None:
    """An excused check that no workflow produces is a line that excuses nothing."""
    _branch, settings, excused = posture.declared(ROOT / "pins" / "dev" / "posture-declared.json")
    produced = check_names.all_checks(workflows.all_workflows(workflows.workflow_dir(ROOT)))

    assert set(excused) <= produced, set(excused) - produced
    assert all(setting.why for setting in settings.values())
    assert all(reason.strip() for reason in excused.values())


# ------------------------------------------------------------ a switch that came back empty


def test_a_readable_switch_that_came_back_empty_is_red_not_holding(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The false green found live on 2026-08-29: the token could not see the switches.

    `setting_problems` skips `None` and `unreadable` covers only switches declared
    unreadable, so a readable one arriving empty read as "holds". It is red now,
    by name, with the value it should hold.
    """
    a_platform(monkeypatch, PROTECTION, {})  # the token sees protection, not the repo switches
    register, root = a_tree(
        tmp_path,
        {
            "branch": "main",
            "settings": {"allow_squash_merge": {"want": False, "why": "squash rewrites subjects"}},
            "not_required": {},
        },
    )

    assert posture.main(["--settings", register, "--root", root]) == 1
    err = capsys.readouterr().err
    assert "allow_squash_merge came back empty" in err
    assert "should be False" in err


def test_blind_reports_only_readable_switches() -> None:
    """A switch declared unreadable is `unreadable`'s to report, not a second time here."""
    declared = {
        "seen": posture.Setting(want=True, why="a"),
        "hidden": posture.Setting(want=True, why="b", readable=False),
    }

    found = posture.blind({"seen": None, "hidden": None}, declared)

    assert len(found) == 1
    assert "seen" in found[0]


def test_a_switch_declared_unreadable_is_printed_by_hand_and_does_not_decide(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The third outcome: shown with its declared value — never green by silence, never red."""
    a_platform(monkeypatch, PROTECTION, {})
    register, root = a_tree(
        tmp_path,
        {
            "branch": "main",
            "settings": {
                "allow_squash_merge": {"want": False, "why": "squash", "readable": False},
            },
            "not_required": {},
        },
    )

    assert posture.main(["--settings", register, "--root", root]) == 0
    out = capsys.readouterr().out
    assert "by hand: allow_squash_merge = cannot be read, and should be False" in out


def test_an_unreadable_switch_the_maintainer_can_see_is_still_judged(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """From a session whose token sees the field, drift is red even when declared unreadable."""
    a_platform(monkeypatch, PROTECTION, {"allow_squash_merge": True})
    register, root = a_tree(
        tmp_path,
        {
            "branch": "main",
            "settings": {
                "allow_squash_merge": {"want": False, "why": "squash", "readable": False},
            },
            "not_required": {},
        },
    )

    assert posture.main(["--settings", register, "--root", root]) == 1
    assert "allow_squash_merge = True" in capsys.readouterr().err


def test_contributing_names_exactly_the_checks_the_register_requires() -> None:
    """The sentence in CONTRIBUTING that lists the required checks is held to the register.

    The list is prose — nothing derives it — and it had already drifted once:
    at `v0.1.0` it named three checks while the platform required seven, and an
    outside audit (2026-08-29) read a fixed list that goes stale silently as
    the same failure this repository's index rule exists to catch. What a pull
    request must show is what the workflows produce on a pull request minus
    the checks the register excuses; the sentence has to name that set, no
    more and no less.
    """
    _branch, _settings, excused = posture.declared(ROOT / "pins" / "dev" / "posture-declared.json")
    found = workflows.all_workflows(workflows.workflow_dir(ROOT))
    required = {name for name in check_names.pull_request_checks(found) if name not in excused}

    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    heading = "## What runs on this repository's own pull requests"
    paragraph = text.split(heading, 1)[1].split("are required", 1)[0]
    named = set(re.findall(r"`([^`]+)`", paragraph))

    assert named == required, (
        f"CONTRIBUTING names {sorted(named)}; the workflows and the register require "
        f"{sorted(required)} on a pull request"
    )
