"""A promise with no instrument behind it expires in silence.

A gate that cannot block declares who sees it within how many days. Checking the
*shape* of that number — is it an integer, is it under a cap — is not a check;
this measures whether the promise is kept.

The two subtleties below are the ones that made the first attempt at this
measurement wrong by a factor of seven, and neither shows up as an error:

- runs the platform rejected outright are named by **path**, not by the declared
  `name`, so grouping by name splits one history in two;
- a run's conclusion belongs to the whole **file**, so a file with blocking jobs
  in it cannot answer for a watched job — its figure is dominated by redness that
  stops merges and is therefore always fixed fast.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from verifiable_gates import gh
from verifiable_gates import red_streak_census as census

if TYPE_CHECKING:
    import pathlib


def run(path: str, stamp: str, conclusion: str | None) -> dict[str, Any]:
    return {"path": path, "created_at": stamp, "conclusion": conclusion}


def a_registry(tmp_path: pathlib.Path, body: str) -> pathlib.Path:
    path = tmp_path / "gates.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def a_workflow(directory: pathlib.Path, name: str, body: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(body, encoding="utf-8")


# ---------------------------------------------------------------- measuring red


def test_a_stretch_of_red_is_measured_from_first_failure_to_next_success() -> None:
    runs = [
        run("a.yml", "2026-08-26T00:00:00+00:00", "success"),
        run("a.yml", "2026-08-26T01:00:00+00:00", "failure"),
        run("a.yml", "2026-08-26T04:00:00+00:00", "success"),
    ]

    assert census.longest_red_hours(runs) == {"a.yml": 3.0}


def test_consecutive_failures_are_one_stretch_not_several() -> None:
    """Otherwise a workflow failing five times reads as five short outages."""
    runs = [
        run("a.yml", "2026-08-26T01:00:00+00:00", "failure"),
        run("a.yml", "2026-08-26T02:00:00+00:00", "failure"),
        run("a.yml", "2026-08-26T03:00:00+00:00", "failure"),
        run("a.yml", "2026-08-26T06:00:00+00:00", "success"),
    ]

    assert census.longest_red_hours(runs) == {"a.yml": 5.0}


def test_the_longest_stretch_wins_not_the_latest() -> None:
    runs = [
        run("a.yml", "2026-08-20T00:00:00+00:00", "failure"),
        run("a.yml", "2026-08-25T00:00:00+00:00", "success"),
        run("a.yml", "2026-08-26T00:00:00+00:00", "failure"),
        run("a.yml", "2026-08-26T01:00:00+00:00", "success"),
    ]

    assert census.longest_red_hours(runs)["a.yml"] == 120.0


def test_red_still_standing_now_is_counted_not_dropped() -> None:
    """An unfinished stretch is always the longest one seen from here.

    Dropping it would make a workflow that is red *right now* report zero, which
    is the most misleading answer the tool could give.
    """
    runs = [
        run("a.yml", "2026-08-20T00:00:00+00:00", "failure"),
        run("b.yml", "2026-08-26T00:00:00+00:00", "success"),
    ]

    assert census.longest_red_hours(runs)["a.yml"] == 144.0


def test_runs_are_grouped_by_path_so_one_history_stays_whole() -> None:
    """A rejected run is named by path; grouping by name splits it in two silently.

    That is not hypothetical: the first version of this measurement reported 2.2
    hours where the truth was 14.6.
    """
    runs = [
        {
            "path": "a.yml",
            "name": "Declared Name",
            "created_at": "2026-08-26T00:00:00+00:00",
            "conclusion": "failure",
        },
        {
            "path": "a.yml",
            "name": ".github/workflows/a.yml",
            "created_at": "2026-08-26T10:00:00+00:00",
            "conclusion": "success",
        },
    ]

    assert census.longest_red_hours(runs) == {"a.yml": 10.0}


def test_a_never_red_workflow_measures_zero() -> None:
    runs = [run("a.yml", "2026-08-26T00:00:00+00:00", "success")]

    assert census.longest_red_hours(runs) == {"a.yml": 0.0}


def test_no_runs_at_all_is_an_empty_answer_not_a_crash() -> None:
    assert census.longest_red_hours([]) == {}


# ---------------------------------------------------------------- what was promised

WATCHED = """version: 1
gates:
  - id: watched-one
    enforced_by: {job: nightly}
    watched_by: {who: maintainer, within_days: 3, how: the census}
  - id: watched-two
    enforced_by: {job: nightly}
    watched_by: {who: maintainer, within_days: 7, how: the census}
  - id: blocking-one
    enforced_by: {job: test}
"""

CRON_ONLY = "on:\n  schedule:\n    - cron: '0 3 * * *'\njobs:\n  nightly:\n    runs-on: x\n"
ON_PR = "on: [pull_request]\njobs:\n  nightly:\n    runs-on: x\n"


def test_the_shortest_promise_in_a_file_is_the_one_measured(tmp_path: pathlib.Path) -> None:
    """The narrowest promise breaks first; satisfying it satisfies the others."""
    a_workflow(tmp_path / ".github" / "workflows", "nightly.yml", CRON_ONLY)

    found = census.promised_days(a_registry(tmp_path, WATCHED), tmp_path / ".github" / "workflows")

    assert found == {".github/workflows/nightly.yml": 3}


def test_a_file_that_runs_on_pull_request_is_not_judged(tmp_path: pathlib.Path) -> None:
    """Its figure is dominated by blocking redness, which is fixed fast by definition.

    A green that means nothing is worse than no measurement.
    """
    a_workflow(tmp_path / ".github" / "workflows", "nightly.yml", ON_PR)

    found = census.promised_days(a_registry(tmp_path, WATCHED), tmp_path / ".github" / "workflows")

    assert found == {}


def test_a_gate_with_no_watcher_promises_nothing(tmp_path: pathlib.Path) -> None:
    a_workflow(tmp_path / ".github" / "workflows", "nightly.yml", CRON_ONLY)
    registry = a_registry(
        tmp_path, "version: 1\ngates:\n  - id: g\n    enforced_by: {job: nightly}\n"
    )

    assert census.promised_days(registry, tmp_path / ".github" / "workflows") == {}


# ---------------------------------------------------------------- the judgement


def test_a_promise_that_reality_broke_is_caught() -> None:
    found = census.problems({"a.yml": 1}, {"a.yml": 48.0})

    assert len(found) == 1
    assert "2.0 days" in found[0]
    assert "stop promising" in found[0], "does not offer the second way out"


def test_a_promise_that_holds_is_not_caught() -> None:
    assert census.problems({"a.yml": 3}, {"a.yml": 48.0}) == []


def test_a_workflow_with_no_runs_in_the_window_is_left_to_the_other_census() -> None:
    """ "Never ran" and "ran and stood red" are different questions with different fixes."""
    assert census.problems({"a.yml": 1}, {}) == []


# ---------------------------------------------------------------- the command line


def test_a_project_whose_promises_hold_passes(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a_workflow(tmp_path / ".github" / "workflows", "nightly.yml", CRON_ONLY)
    a_registry(tmp_path, WATCHED)
    runs = tmp_path / "runs.json"
    runs.write_text(
        '[{"path": ".github/workflows/nightly.yml", '
        '"created_at": "2026-08-26T00:00:00+00:00", "conclusion": "success"}]',
        encoding="utf-8",
    )

    assert census.main(["--root", str(tmp_path), "--input", str(runs)]) == 0
    assert "still holds" in capsys.readouterr().out


def test_a_workflow_nobody_watches_and_nothing_blocks_on_is_red(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The worst of the three states, said as such — it used to print "it blocks"."""
    a_workflow(tmp_path / ".github" / "workflows", "nightly.yml", CRON_ONLY)
    a_workflow(tmp_path / ".github" / "workflows", "orphan.yml", CRON_ONLY)
    a_registry(tmp_path, WATCHED)
    runs = tmp_path / "runs.json"
    runs.write_text(
        '[{"path": ".github/workflows/nightly.yml", '
        '"created_at": "2026-08-26T00:00:00+00:00", "conclusion": "success"}, '
        '{"path": ".github/workflows/orphan.yml", '
        '"created_at": "2026-08-26T00:00:00+00:00", "conclusion": "success"}]',
        encoding="utf-8",
    )

    assert census.main(["--root", str(tmp_path), "--input", str(runs)]) == 1
    out, err = capsys.readouterr()
    assert "orphan.yml" in out
    assert "nobody watches it and nothing blocks on it" in out
    assert "declare `watched_by`" in err


@pytest.mark.parametrize(
    ("path", "body", "note"),
    [
        (".github/workflows/pr.yml", ON_PR, "runs on pull_request (it blocks)"),
        ("dynamic/dependabot/dependabot-updates", None, "the platform's own run"),
    ],
)
def test_a_blocking_workflow_and_a_platform_run_are_named_not_judged(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    path: str,
    body: str | None,
    note: str,
) -> None:
    a_workflow(tmp_path / ".github" / "workflows", "nightly.yml", CRON_ONLY)
    if body:
        a_workflow(tmp_path / ".github" / "workflows", path.rsplit("/", 1)[1], body)
    a_registry(tmp_path, WATCHED)
    runs = tmp_path / "runs.json"
    runs.write_text(
        '[{"path": ".github/workflows/nightly.yml", '
        '"created_at": "2026-08-26T00:00:00+00:00", "conclusion": "success"}, '
        f'{{"path": "{path}", "created_at": "2026-08-26T00:00:00+00:00", '
        '"conclusion": "failure"}]',
        encoding="utf-8",
    )

    assert census.main(["--root", str(tmp_path), "--input", str(runs)]) == 0
    assert note in capsys.readouterr().out


def test_a_broken_promise_returns_a_blocking_code(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a_workflow(tmp_path / ".github" / "workflows", "nightly.yml", CRON_ONLY)
    a_registry(tmp_path, WATCHED)
    runs = tmp_path / "runs.json"
    runs.write_text(
        '[{"path": ".github/workflows/nightly.yml", '
        '"created_at": "2026-08-01T00:00:00+00:00", "conclusion": "failure"},'
        '{"path": ".github/workflows/nightly.yml", '
        '"created_at": "2026-08-26T00:00:00+00:00", "conclusion": "success"}]',
        encoding="utf-8",
    )

    assert census.main(["--root", str(tmp_path), "--input", str(runs)]) == 1
    assert "not being kept" in capsys.readouterr().err


def test_the_output_of_gh_run_list_is_the_third_answer_not_a_traceback(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`createdAt` where `created_at` was expected raised KeyError (2026-08-30) — exit 2 now."""
    a_workflow(tmp_path / ".github" / "workflows", "nightly.yml", CRON_ONLY)
    a_registry(tmp_path, WATCHED)
    runs = tmp_path / "gh.json"
    runs.write_text(
        '[{"databaseId": 1, "createdAt": "2026-08-30T00:00:00Z", "conclusion": "failure"}]',
        encoding="utf-8",
    )

    assert census.main(["--root", str(tmp_path), "--input", str(runs)]) == 2
    err = capsys.readouterr().err
    assert "cannot read the run history" in err
    assert "record 0 has no ['path', 'created_at']" in err


def test_an_unreadable_history_is_its_own_answer(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neither pass nor fail — exit 2, because "cannot see" is a third thing."""

    a_workflow(tmp_path / ".github" / "workflows", "nightly.yml", CRON_ONLY)
    a_registry(tmp_path, WATCHED)

    def refuse(_limit: int) -> list[dict[str, Any]]:
        raise PermissionError("HTTP 403")

    monkeypatch.setattr(census, "_fetch", refuse)

    assert census.main(["--root", str(tmp_path)]) == 2
    assert "never become a silent skip" in capsys.readouterr().err


def test_the_registry_can_be_pointed_at_explicitly(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A project that keeps its registry elsewhere must still be measurable."""
    a_workflow(tmp_path / ".github" / "workflows", "nightly.yml", CRON_ONLY)
    elsewhere = tmp_path / "config"
    elsewhere.mkdir()
    registry = elsewhere / "gates.yaml"
    registry.write_text(WATCHED, encoding="utf-8")
    runs = tmp_path / "runs.json"
    runs.write_text(
        '[{"path": ".github/workflows/nightly.yml", '
        '"created_at": "2026-08-26T00:00:00+00:00", "conclusion": "success"}]',
        encoding="utf-8",
    )

    code = census.main(["--root", str(tmp_path), "--registry", str(registry), "--input", str(runs)])

    assert code == 0
    assert "1 watched workflows" in capsys.readouterr().out


def test_the_fetcher_asks_for_the_default_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runs from every branch would measure redness nobody was blocked by."""
    asked: list[str] = []

    def fake_api(path: str) -> dict[str, Any]:
        asked.append(path)
        if len(asked) > 3:
            raise AssertionError("kept paging past an empty page")
        return {"workflow_runs": []}

    monkeypatch.setattr(gh, "api", fake_api)
    census._fetch(10)  # noqa: SLF001 — the paging behaviour is the thing being checked

    assert "branch=main" in asked[0], "asked for every branch, not the one that gates merges"


def test_paging_stops_when_the_platform_runs_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty page means the history ended — keep asking and the loop never returns.

    The fake refuses after a few calls rather than answering forever. Without a
    bound, a version that failed to stop would **hang** instead of failing, and a
    hang and a slow test give the same signal — which is the failure this project
    made every command declare a time budget to avoid.
    """
    calls: list[str] = []
    ceiling = 5

    def fake_api(path: str) -> dict[str, Any]:
        calls.append(path)
        if len(calls) > ceiling:
            raise AssertionError(f"kept paging past an empty page: {len(calls)} calls")
        return {"workflow_runs": [] if len(calls) > 1 else [{"created_at": "x"}]}

    monkeypatch.setattr(gh, "api", fake_api)

    assert len(census._fetch(500)) == 1  # noqa: SLF001 — paging is the behaviour under test
    assert len(calls) == 2, "did not stop at the first empty page"


def test_paging_stops_when_the_limit_is_reached(monkeypatch: pytest.MonkeyPatch) -> None:
    """The other exit from the loop — full pages until the caller's ceiling.

    Only the empty-page exit was covered. A version that ignored the limit would
    keep paging through a busy repository's whole history, which is a different
    failure from never stopping at all and deserves its own test.
    """
    calls: list[str] = []

    def fake_api(path: str) -> dict[str, Any]:
        calls.append(path)
        if len(calls) > 4:
            raise AssertionError("kept paging past the limit")
        return {"workflow_runs": [{"created_at": "x"} for _ in range(2)]}

    monkeypatch.setattr(gh, "api", fake_api)

    assert len(census._fetch(4)) == 4  # noqa: SLF001 — paging is the behaviour under test
    assert len(calls) == 2, "asked for more pages than the limit needed"
    assert "per_page=4" in calls[0], "the first page should ask for the whole limit"
    assert "per_page=2" in calls[1], "the second page asked for more than was left to fetch"


# ---------------------------------------------------------------- a census over nothing


def test_a_promise_with_no_history_behind_it_is_not_kept_but_unseen(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A `watched_by` promise and zero runs: exit 2, never "every promise holds".

    An outside audit on 2026-08-29 fed this census a valid, empty history and
    read back a pass — the exact silent skip its own message warns about. Empty
    is one more way of not seeing, and gets the third answer like the others.
    """
    a_workflow(tmp_path / ".github" / "workflows", "nightly.yml", CRON_ONLY)
    a_registry(tmp_path, WATCHED)
    runs = tmp_path / "runs.json"
    runs.write_text("[]", encoding="utf-8")

    assert census.main(["--root", str(tmp_path), "--input", str(runs)]) == 2
    err = capsys.readouterr().err
    assert "history is empty" in err
    assert "never become a silent skip" in err


def test_no_promise_at_all_is_said_out_loud_and_passes(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Nothing declares a watcher: nothing to measure, and the green must say so."""
    a_workflow(tmp_path / ".github" / "workflows", "ci.yml", "on: push\njobs: {}\n")
    a_registry(tmp_path, "version: 1\ngates: []\n")

    assert census.main(["--root", str(tmp_path)]) == 0
    assert "nothing to measure" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("{}", "an object where a list of runs was expected"),
        ("[", "not JSON at all"),
    ],
)
def test_a_history_of_the_wrong_shape_is_unreadable(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], text: str, why: str
) -> None:
    a_workflow(tmp_path / ".github" / "workflows", "nightly.yml", CRON_ONLY)
    a_registry(tmp_path, WATCHED)
    runs = tmp_path / "runs.json"
    runs.write_text(text, encoding="utf-8")

    assert census.main(["--root", str(tmp_path), "--input", str(runs)]) == 2, why
    assert "cannot read the run history" in capsys.readouterr().err


def test_a_missing_input_file_is_unreadable_not_a_traceback(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a_workflow(tmp_path / ".github" / "workflows", "nightly.yml", CRON_ONLY)
    a_registry(tmp_path, WATCHED)

    assert census.main(["--root", str(tmp_path), "--input", str(tmp_path / "no.json")]) == 2
    assert "cannot read the run history" in capsys.readouterr().err


@pytest.mark.parametrize("created_at", [1700000000, "yesterday"], ids=["epoch-number", "a-word"])
def test_a_stamp_that_is_not_a_timestamp_is_unreadable(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], created_at: object
) -> None:
    """A `created_at` the census cannot parse raised `ValueError` from inside the measure,
    exit 1 — the code for a broken promise (self-audit, 2026-08-31)."""
    a_workflow(tmp_path / ".github" / "workflows", "nightly.yml", CRON_ONLY)
    a_registry(tmp_path, WATCHED)
    runs = tmp_path / "runs.json"
    runs.write_text(
        json.dumps([{"path": ".github/workflows/nightly.yml", "created_at": created_at}]),
        encoding="utf-8",
    )
    assert census.main(["--root", str(tmp_path), "--input", str(runs)]) == 2
    assert "cannot read the run history" in capsys.readouterr().err
