"""A schedule that stopped firing must be louder than one that never existed.

The failure this exists for is that **zero runs looks exactly like zero failures**
in every tool there is. A census counting what happened cannot see it; only a
census that starts from what was *declared* can.

Two directions matter equally. Going red when a schedule really has gone quiet is
the obvious one. The other is that when the run history cannot be read at all,
the answer must be neither pass nor fail but a distinct third thing — a watcher
that goes quiet on the day it can see nothing reports every schedule as healthy
at exactly the wrong moment.
"""

from __future__ import annotations

import datetime
import subprocess
from typing import TYPE_CHECKING, Any

import pytest

from verifiable_gates import gh, removals
from verifiable_gates import schedule_census as census

if TYPE_CHECKING:
    import pathlib

NOW = "2026-08-26T12:00:00+00:00"


def a_workflow(directory: pathlib.Path, name: str, cron: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(
        f"on:\n  schedule:\n    - cron: '{cron}'\njobs:\n  x:\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------- reading the cron


@pytest.mark.parametrize(
    ("cron", "hours", "why"),
    [
        ("0 * * * *", census.HOUR, "nothing pinned but the minute"),
        ("0 3 * * *", census.DAY, "an hour is pinned"),
        ("0 3 1 * *", census.MONTH, "a day of the month is pinned"),
        ("0 3 * * 1", census.WEEK, "a day of the week is pinned"),
        ("0 3 1 * 1", census.WEEK, "day-of-week wins, being the coarsest pinned"),
    ],
)
def test_the_period_comes_from_the_coarsest_pinned_field(cron: str, hours: int, why: str) -> None:
    assert census.period_hours(cron) == hours, why


def test_a_short_cron_line_does_not_raise() -> None:
    """Malformed input from a file is a normal condition, not a crash."""
    assert census.period_hours("0 3") == census.DAY


# ---------------------------------------------------------------- what is declared


def test_only_workflows_with_a_cron_are_watched(tmp_path: pathlib.Path) -> None:
    a_workflow(tmp_path, "nightly.yml", "0 3 * * *")
    (tmp_path / "ci.yml").write_text("on: push\njobs: {}\n", encoding="utf-8")

    assert census.declared_schedules(tmp_path) == {"nightly.yml": census.DAY}


def test_the_shortest_period_wins_when_several_crons_are_declared(
    tmp_path: pathlib.Path,
) -> None:
    """Watching by the slowest would let the fast one go quiet unnoticed."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "many.yml").write_text(
        "on:\n  schedule:\n    - cron: '0 3 * * 1'\n    - cron: '0 * * * *'\njobs: {}\n",
        encoding="utf-8",
    )

    assert census.declared_schedules(tmp_path) == {"many.yml": census.HOUR}


# ---------------------------------------------------------------- the judgement


def test_a_schedule_that_never_fired_is_caught() -> None:
    """The case this whole census exists for — and it must say why it is ambiguous."""
    found = census.problems({"nightly.yml": census.DAY}, {"nightly.yml": None}, NOW, 2)

    assert len(found) == 1
    assert "never had a run" in found[0]
    assert "disabled for inactivity" in found[0], "does not name the second possible cause"


def test_a_schedule_firing_on_time_is_not_caught() -> None:
    found = census.problems(
        {"nightly.yml": census.DAY}, {"nightly.yml": "2026-08-26T03:00:00+00:00"}, NOW, 2
    )

    assert found == []


def test_a_schedule_late_beyond_tolerance_is_caught() -> None:
    found = census.problems(
        {"nightly.yml": census.DAY}, {"nightly.yml": "2026-08-20T03:00:00+00:00"}, NOW, 2
    )

    assert len(found) == 1
    assert "6.4 days ago" in found[0]


def test_tolerance_is_honoured_rather_than_ignored() -> None:
    """A run 1.5 periods late is within a tolerance of 2 and outside a tolerance of 1."""
    last = {"nightly.yml": "2026-08-25T00:00:00+00:00"}

    assert census.problems({"nightly.yml": census.DAY}, last, NOW, 2) == []
    assert census.problems({"nightly.yml": census.DAY}, last, NOW, 1) != []


def test_a_workflow_nobody_asked_about_is_ignored() -> None:
    """Extra rows in the fetched state are not this census's business."""
    assert census.problems({}, {"other.yml": None}, NOW, 2) == []


# ---------------------------------------------------------------- what cannot be checked


def test_dependabot_is_named_rather_than_guessed(tmp_path: pathlib.Path) -> None:
    """No public endpoint says when it last ran, so it is labelled, not judged."""
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "dependabot.yml").write_text(
        "version: 2\nupdates:\n  - package-ecosystem: pip\n    schedule:\n      interval: weekly\n",
        encoding="utf-8",
    )

    found = census.unverifiable_schedules(tmp_path)

    assert found == ["dependabot pip (weekly)"]


def test_a_project_without_dependabot_reports_nothing(tmp_path: pathlib.Path) -> None:
    assert census.unverifiable_schedules(tmp_path) == []


# ---------------------------------------------------------------- the command line


def test_a_project_with_no_schedules_says_so(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert census.main(["--root", str(tmp_path)]) == 0
    assert "nothing to watch" in capsys.readouterr().out


def test_a_healthy_project_passes(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a_workflow(tmp_path / ".github" / "workflows", "nightly.yml", "0 3 * * *")
    state = tmp_path / "state.json"
    state.write_text(
        '{"last_scheduled_run": {"nightly.yml": "2026-08-26T03:00:00+00:00"}}', encoding="utf-8"
    )

    code = census.main(["--root", str(tmp_path), "--input", str(state), "--now", NOW])

    assert code == 0
    assert "still firing" in capsys.readouterr().out


def test_the_summary_counts_what_fired_apart_from_what_is_excused(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A young cron that never fired is excused, not "still firing" — the line says which."""
    a_workflow(tmp_path / ".github" / "workflows", "weekly.yml", "0 5 * * 1")
    _a_git_repo(tmp_path)
    state = tmp_path / "state.json"
    state.write_text('{"last_scheduled_run": {"weekly.yml": null}}', encoding="utf-8")
    soon = "2026-08-27T00:00:00+00:00"

    code = census.main(["--root", str(tmp_path), "--input", str(state), "--now", soon])

    out = capsys.readouterr().out
    assert code == 0
    assert "still firing" not in out
    assert "0 of 1 declared schedules are firing" in out
    assert "1 declared but not due yet" in out
    assert "1 have never fired" in out


@pytest.mark.parametrize(
    ("declared", "fired", "waiting", "needle"),
    [
        (2, 2, 0, "every declared schedule is still firing within its period (2 workflows)"),
        (2, 1, 1, "1 of 2 declared schedules are firing"),
    ],
)
def test_the_summary_line_in_both_shapes(
    declared: int, fired: int, waiting: int, needle: str
) -> None:
    assert needle in census.summary(declared, fired, waiting)


def test_a_quiet_schedule_returns_a_blocking_code(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a_workflow(tmp_path / ".github" / "workflows", "nightly.yml", "0 3 * * *")
    state = tmp_path / "state.json"
    state.write_text('{"last_scheduled_run": {"nightly.yml": null}}', encoding="utf-8")

    code = census.main(["--root", str(tmp_path), "--input", str(state), "--now", NOW])

    assert code == 1
    assert "never had a run" in capsys.readouterr().err


def test_an_unreadable_history_is_its_own_answer(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neither pass nor fail — exit 2, because "cannot see" is a third thing.

    A watcher that reports success when it cannot read anything is at its most
    misleading exactly when something is wrong.
    """
    a_workflow(tmp_path / ".github" / "workflows", "nightly.yml", "0 3 * * *")

    def refuse(_files: list[str]) -> dict[str, Any]:
        raise PermissionError("HTTP 403")

    monkeypatch.setattr(census, "fetch", refuse)

    assert census.main(["--root", str(tmp_path), "--now", NOW]) == 2
    assert "never become a silent skip" in capsys.readouterr().err


def test_the_fetcher_asks_for_scheduled_runs_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Counting runs of any event would answer a different question entirely."""
    asked: list[str] = []

    def fake_api(path: str) -> dict[str, Any]:
        asked.append(path)
        return {"workflow_runs": [{"created_at": "2026-08-26T03:00:00+00:00"}]}

    monkeypatch.setattr(gh, "api", fake_api)

    found = census.fetch(["nightly.yml"])

    assert found["last_scheduled_run"]["nightly.yml"] == "2026-08-26T03:00:00+00:00"
    assert "event=schedule" in asked[0], "asked for runs of every event, not scheduled ones"


def test_a_workflow_with_no_runs_yet_comes_back_as_never(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gh, "api", lambda _path: {"workflow_runs": []})

    assert census.fetch(["nightly.yml"])["last_scheduled_run"]["nightly.yml"] is None


def test_what_cannot_be_checked_is_printed_beside_what_can(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The label has to reach the report, not just exist as a function.

    A row that is computed and never printed is the same as a row nobody wrote:
    the reader still cannot tell "checked and fine" from "not checkable at all".
    """
    a_workflow(tmp_path / ".github" / "workflows", "nightly.yml", "0 3 * * *")
    (tmp_path / ".github" / "dependabot.yml").write_text(
        "version: 2\nupdates:\n  - package-ecosystem: pip\n    schedule:\n      interval: weekly\n",
        encoding="utf-8",
    )
    state = tmp_path / "state.json"
    state.write_text(
        '{"last_scheduled_run": {"nightly.yml": "2026-08-26T03:00:00+00:00"}}', encoding="utf-8"
    )

    code = census.main(["--root", str(tmp_path), "--input", str(state), "--now", NOW])
    out = capsys.readouterr().out

    assert code == 0
    assert "not checkable by machine" in out
    assert "dependabot pip (weekly)" in out


# ------------------------------------------- a cron that has not come round yet
#
# Adding a weekly cron on a Thursday used to turn this census red until Monday.
# The message it printed — "rejected outright, or disabled for inactivity" — was
# false in a way the reader could not act on, and a check that cries wolf every
# time a schedule is added is one people learn to wave through. The history says
# which case it is: a file younger than one allowance has not been refused, it
# has not been asked to run yet.


def test_a_cron_younger_than_its_allowance_is_not_called_rejected() -> None:
    born = {"weekly.yml": "2026-08-25T00:00:00+00:00"}

    assert census.problems({"weekly.yml": census.WEEK}, {"weekly.yml": None}, NOW, 2, born) == []


def test_a_cron_past_its_allowance_is_still_caught() -> None:
    """The teeth stay in: silence outlasting the allowance is the case this exists for."""
    born = {"weekly.yml": "2026-07-01T00:00:00+00:00"}

    found = census.problems({"weekly.yml": census.WEEK}, {"weekly.yml": None}, NOW, 2, born)

    assert len(found) == 1
    assert "never had a run" in found[0]


def test_an_unknown_birthday_stays_strict() -> None:
    """No history is not a free pass — that would be the silent skip in another coat."""
    found = census.problems({"weekly.yml": census.WEEK}, {"weekly.yml": None}, NOW, 2, {})

    assert len(found) == 1


def test_the_young_cron_is_named_with_the_date_it_stops_being_excused() -> None:
    """Printed, not swallowed — and the reader must not have to work out the deadline."""
    born = {"weekly.yml": "2026-08-25T00:00:00+00:00"}

    rows = census.not_due_yet({"weekly.yml": census.WEEK}, {"weekly.yml": None}, born, NOW, 2)

    assert len(rows) == 1
    assert "has not come round yet" in rows[0]
    assert "2026-09-08" in rows[0], "the date it turns red is not in the line"


@pytest.mark.parametrize(
    ("last", "born", "why"),
    [
        ({"weekly.yml": "2026-08-25T00:00:00+00:00"}, {"weekly.yml": NOW}, "it has fired"),
        ({"weekly.yml": None}, {"weekly.yml": "2026-07-01T00:00:00+00:00"}, "past its allowance"),
        ({"weekly.yml": None}, {}, "birthday unknown"),
    ],
)
def test_only_the_young_and_silent_are_excused(
    last: dict[str, Any], born: dict[str, Any], why: str
) -> None:
    assert census.not_due_yet({"weekly.yml": census.WEEK}, last, born, NOW, 2) == [], why


def _a_git_repo(root: pathlib.Path) -> None:
    """A repository with one commit — the shortest history that can date a file."""
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "t"],
        ["git", "add", "-A"],
        ["git", "commit", "-qm", "add a weekly cron"],
    ):
        subprocess.run(  # noqa: S603 — every argv is a literal in the tuple above
            command, cwd=root, check=True, capture_output=True
        )


def test_first_seen_reads_the_commit_that_added_the_file(tmp_path: pathlib.Path) -> None:
    a_workflow(tmp_path / ".github" / "workflows", "weekly.yml", "0 5 * * 1")
    _a_git_repo(tmp_path)

    born = census.first_seen(tmp_path, ["weekly.yml"])

    assert born["weekly.yml"] is not None
    assert census.not_due_yet(
        {"weekly.yml": census.WEEK},
        {"weekly.yml": None},
        born,
        datetime.datetime.now(datetime.UTC).isoformat(),
        2,
    ), "a file committed a moment ago should still be inside its allowance"


def test_first_seen_without_a_history_says_unknown(tmp_path: pathlib.Path) -> None:
    """An uncommitted file has no birthday, and guessing one would excuse it forever."""
    assert census.first_seen(tmp_path, ["weekly.yml"]) == {"weekly.yml": None}


def test_first_seen_without_git_says_unknown(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_git(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError("git is not on this machine")

    monkeypatch.setattr(removals, "_git", no_git)

    assert census.first_seen(tmp_path, ["a.yml", "b.yml"]) == {"a.yml": None, "b.yml": None}


def test_the_young_cron_reaches_the_report(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A row computed and never printed is the same as a row nobody wrote."""
    a_workflow(tmp_path / ".github" / "workflows", "weekly.yml", "0 5 * * 1")
    state = tmp_path / "state.json"
    state.write_text('{"last_scheduled_run": {"weekly.yml": null}}', encoding="utf-8")
    monkeypatch.setattr(
        census, "first_seen", lambda _root, _files: {"weekly.yml": "2026-08-25T00:00:00+00:00"}
    )

    code = census.main(["--root", str(tmp_path), "--input", str(state), "--now", NOW])

    assert code == 0
    assert "declared but not due yet" in capsys.readouterr().out


def test_a_shallow_clone_cannot_say_when_a_file_was_added(tmp_path: pathlib.Path) -> None:
    """The generous failure: `--depth 1` reports every file as added by the graft.

    Left unhandled, every workflow reads as newborn and every silent cron is
    excused — and since `actions/checkout` clones depth 1 by default, that is the
    normal state of a CI run. The reference implementation's seam test caught this
    on the first run after the allowance shipped.
    """
    origin = tmp_path / "origin"
    a_workflow(origin / ".github" / "workflows", "weekly.yml", "0 5 * * 1")
    _a_git_repo(origin)
    clone = tmp_path / "clone"
    subprocess.run(  # noqa: S603 — a fixed git command, written out in a test
        ["git", "clone", "--depth", "1", "-q", f"file://{origin}", str(clone)],  # noqa: S607 — git resolved from PATH, the paths are tmp_path
        check=True,
        capture_output=True,
    )

    born = census.first_seen(clone, ["weekly.yml"])

    assert born == {"weekly.yml": None}, "a shallow clone was allowed to date a file"
    assert census.problems({"weekly.yml": census.WEEK}, {"weekly.yml": None}, NOW, 2, born), (
        "a shallow clone excused a schedule that has never fired"
    )


# ---------------------------------------------------------------- the history's shape


def test_a_history_that_is_not_an_object_is_unreadable(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A list where the platform's answer is an object: the census cannot see, exit 2."""
    a_workflow(tmp_path / ".github" / "workflows", "weekly.yml", "0 3 * * 1")
    state = tmp_path / "state.json"
    state.write_text("[]", encoding="utf-8")

    code = census.main(["--root", str(tmp_path), "--input", str(state), "--now", NOW])

    assert code == 2
    assert "not a dict" in capsys.readouterr().err

    """404 is "never" — a cron on a branch not yet on main cannot have run — not "cannot see"."""


def test_a_workflow_the_platform_does_not_know_yet_has_never_fired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """404 is "never" — a cron on a branch not yet on main cannot have run — not "cannot see"."""

    def unknown(_path: str) -> dict[str, object]:
        raise PermissionError("`gh api …` failed: gh: Not Found (HTTP 404)")

    monkeypatch.setattr(gh, "api", unknown)

    assert census.fetch(["posture.yml"]) == {"last_scheduled_run": {"posture.yml": None}}


def test_any_other_refusal_stays_the_third_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(_path: str) -> dict[str, object]:
        raise PermissionError("`gh api …` failed: HTTP 403")

    monkeypatch.setattr(gh, "api", forbidden)

    with pytest.raises(PermissionError, match="403"):
        census.fetch(["posture.yml"])
