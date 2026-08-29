"""A rerun can turn a job that was red into one that was never red.

The platform reports the latest attempt only. Press rerun until it goes green and
the original failure leaves the record — and "never red" is what decides whether
a gate carries evidence and whether a flaky-test review has anything to look at.

Two mistakes made in earnest, both of which these tests hold open:

- **classifying by step name** reads a failure inside somebody else's action as
  ours, on the very day the platform is down and that action is failing because
  the platform answered 503;
- **walking failures job by job** loses a run the platform rejected before
  creating any job — zero jobs, so zero failures, so invisible.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from verifiable_gates import gh
from verifiable_gates import rerun_census as census

if TYPE_CHECKING:
    import pathlib


def failure(**fields: Any) -> dict[str, Any]:  # noqa: ANN401 — a record is whatever the API sent
    return {"attempt": 1, "job": "test", "step": "", "message": "", **fields}


def a_workflow(directory: pathlib.Path, name: str, body: str) -> pathlib.Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(body, encoding="utf-8")
    return directory


# ---------------------------------------------------------------- who broke it


def test_a_platform_message_is_the_platforms_even_in_our_own_step() -> None:
    """The message is evidence; the step name is only context."""
    assert census.classify(failure(step="Run pytest", message="HTTP 503 from the API")) == (
        census.PLATFORM
    )


def test_a_runner_step_is_the_platforms_even_with_no_message() -> None:
    assert census.classify(failure(step="Set up job")) == census.PLATFORM


def test_our_own_step_with_our_own_message_is_ours() -> None:
    assert census.classify(failure(step="Run pytest", message="assert 1 == 2")) == census.OURS


def test_no_message_at_all_cannot_be_classified() -> None:
    """Nothing to read is not evidence of innocence."""
    assert census.classify(failure(step="Run pytest")) == census.UNKNOWN


def test_somebody_elses_action_without_a_platform_message_needs_a_person() -> None:
    """The exact case that made an earlier version blame us four times in one outage."""
    verdict = census.classify(
        failure(step="Run github/codeql-action/init@v3", message="Encountered a fatal error")
    )

    assert verdict == census.UNKNOWN


def test_a_bare_status_number_is_not_enough_to_blame_the_platform() -> None:
    """A project's own tests assert on 503 for a health endpoint.

    Reading a bare number as the platform's would push our failures out of the
    count — the direction of error that ripens a flake threshold with things
    nobody can fix.
    """
    assert census.classify(failure(step="Run pytest", message="assert 503 == 200")) == census.OURS


def test_a_rate_limit_is_the_platforms() -> None:
    assert (
        census.classify(
            failure(step="Run gh api", message="You have exceeded a secondary rate limit")
        )
        == census.PLATFORM
    )


# ---------------------------------------------------------------- what a rerun erased


def test_a_failure_in_an_earlier_attempt_is_counted_as_hidden() -> None:
    records = [{"id": 1, "attempt": 2, "failures": [failure(attempt=1, job="lint")]}]

    summary = census.census(records)

    assert summary["runs_failed_hidden"] == 1
    assert summary["runs_failed_visible"] == 0
    assert summary["jobs"]["lint"] == {"hidden": 1}


def test_a_failure_in_the_last_attempt_is_the_one_everyone_can_already_see() -> None:
    records = [{"id": 1, "attempt": 2, "failures": [failure(attempt=2, job="lint")]}]

    summary = census.census(records)

    assert summary["runs_failed_visible"] == 1
    assert summary["runs_failed_hidden"] == 0


def test_one_run_failing_twice_in_one_attempt_counts_as_one_run() -> None:
    """Otherwise a run with five failing jobs reads as five bad runs."""
    records = [
        {
            "id": 1,
            "attempt": 1,
            "failures": [failure(job="lint"), failure(job="test")],
        }
    ]

    summary = census.census(records)

    assert summary["runs_failed_visible"] == 1
    assert set(summary["jobs"]) == {"lint", "test"}


def test_a_check_name_is_resolved_back_to_the_job_id() -> None:
    """Otherwise one report says `dialect` failed and `dialects` never went red."""
    records = [{"id": 1, "attempt": 1, "failures": [failure(job="dialect (mysql-8)")]}]

    summary = census.census(records, {"dialect": "dialects"})

    assert set(summary["jobs"]) == {"dialects"}


def test_a_record_with_no_attempt_is_read_as_the_first() -> None:
    summary = census.census([{"id": 1, "failures": [{"job": "lint"}]}])

    assert summary["runs_failed_visible"] == 1


def test_an_empty_window_says_so_rather_than_failing() -> None:
    assert census.census([])["runs_examined"] == 0


# ---------------------------------------------------------------- a run that never started


def test_a_run_that_failed_with_no_jobs_is_not_lost() -> None:
    """Zero jobs means zero failures, which is how this disappeared entirely."""
    made = census.startup_failure({"conclusion": "failure", "name": "scorecard"}, [])

    assert len(made) == 1
    assert "scorecard" in made[0]["job"]


def test_a_run_that_failed_with_jobs_is_left_alone() -> None:
    existing = [failure(job="lint")]

    assert census.startup_failure({"conclusion": "failure"}, existing) == existing


def test_a_run_that_succeeded_invents_no_failure() -> None:
    assert census.startup_failure({"conclusion": "success"}, []) == []


def test_a_nameless_run_still_gets_a_row() -> None:
    made = census.startup_failure({"conclusion": "failure"}, [])

    assert made[0]["job"], "a run with no name vanished instead of being reported"


def test_a_run_that_never_started_is_not_reported_as_a_strange_name() -> None:
    """It is named after its workflow on purpose, so it must not read as unresolved."""
    made = census.startup_failure({"conclusion": "failure", "name": "scorecard.yml"}, [])
    summary = census.census([{"id": 1, "attempt": 1, "failures": made}])

    assert census.unresolved_labels(summary, set()) == []


def test_a_name_that_resolves_to_no_job_is_reported() -> None:
    summary = census.census([{"id": 1, "attempt": 1, "failures": [failure(job="ghost")]}])

    assert census.unresolved_labels(summary, {"lint"}) == ["ghost"]


# ---------------------------------------------------------------- reading the workflows


def test_a_matrix_name_maps_back_to_its_job_id(tmp_path: pathlib.Path) -> None:
    directory = a_workflow(
        tmp_path,
        "ci.yml",
        "jobs:\n  dialects:\n    name: dialect (${{ matrix.db }})\n    steps: []\n",
    )

    ids, by_name, by_path = census.job_identity(directory)

    assert ids == {"dialects"}
    assert by_name["dialect"] == "dialects"
    assert by_path[".github/workflows/ci.yml"] == ["dialects"]


def test_a_job_with_no_declared_name_is_known_by_its_id(tmp_path: pathlib.Path) -> None:
    directory = a_workflow(tmp_path, "ci.yml", "jobs:\n  lint:\n    steps: []\n")

    _ids, by_name, _paths = census.job_identity(directory)

    assert by_name == {"lint": "lint"}


def test_a_name_that_is_nothing_but_a_template_is_not_a_second_key(
    tmp_path: pathlib.Path,
) -> None:
    """`name: ${{ matrix.x }}` leaves nothing fixed to match on."""
    directory = a_workflow(
        tmp_path, "ci.yml", "jobs:\n  lint:\n    name: ${{ matrix.x }}\n    steps: []\n"
    )

    _ids, by_name, _paths = census.job_identity(directory)

    assert by_name == {"lint": "lint"}


def test_a_workflow_with_no_jobs_is_read_without_complaint(tmp_path: pathlib.Path) -> None:
    directory = a_workflow(tmp_path, "ci.yml", "on: push\n")

    ids, _by_name, by_path = census.job_identity(directory)

    assert ids == set()
    assert by_path[".github/workflows/ci.yml"] == []


def test_a_job_that_never_went_red_is_named() -> None:
    summary = census.census([{"id": 1, "attempt": 1, "failures": [failure(job="lint")]}])

    assert census.jobs_never_red(summary, {"lint", "test"}) == ["test"]


# ---------------------------------------------------------------- evidence from real redness


def test_a_gate_without_evidence_that_went_red_is_proposed() -> None:
    gates = [{"id": "g1", "enforced_by": {"tests": ["tests/test_a.py"]}}]
    records = [
        {
            "id": 7,
            "attempt": 1,
            "failures": [failure(step="Run pytest", message="assert", tests=["tests/test_a.py"])],
        }
    ]

    assert census.evidence_proposals(records, gates) == [
        {"gate": "g1", "run": 7, "tests": ["tests/test_a.py"]}
    ]


def test_a_gate_that_already_has_evidence_is_not_proposed_again() -> None:
    gates = [
        {
            "id": "g1",
            "enforced_by": {"tests": ["tests/test_a.py"]},
            "proved_by": [{"kind": "mutation"}],
        }
    ]
    records = [
        {
            "id": 7,
            "attempt": 1,
            "failures": [failure(step="Run pytest", message="assert", tests=["tests/test_a.py"])],
        }
    ]

    assert census.evidence_proposals(records, gates) == []


def test_a_test_file_belonging_to_no_gate_proposes_nothing() -> None:
    records = [
        {
            "id": 7,
            "attempt": 1,
            "failures": [failure(step="Run pytest", message="assert", tests=["tests/test_x.py"])],
        }
    ]

    assert census.evidence_proposals(records, []) == []


def test_a_failure_that_is_not_ours_proposes_nothing() -> None:
    """The platform being down proves nothing about any gate."""
    gates = [{"id": "g1", "enforced_by": {"tests": ["tests/test_a.py"]}}]
    records = [
        {
            "id": 7,
            "attempt": 1,
            "failures": [failure(step="Set up job", message="503", tests=["tests/test_a.py"])],
        }
    ]

    assert census.evidence_proposals(records, gates) == []


def test_the_failing_test_files_are_read_out_of_a_log() -> None:
    log = "FAILED tests/test_a.py::test_one - AssertionError\nFAILED tests/test_a.py::test_two"

    assert census.failing_tests(log) == {"tests/test_a.py"}


def test_a_log_with_no_failures_yields_nothing() -> None:
    assert census.failing_tests("everything passed") == set()


# ---------------------------------------------------------------- talking to the platform


def test_the_fetcher_pages_until_it_has_what_it_asked_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages: list[str] = []

    def fake_api(path: str) -> dict[str, Any]:
        pages.append(path)
        if len(pages) > 3:
            raise AssertionError("kept paging past the limit")
        return {"workflow_runs": [{"id": len(pages)}] * census.PAGE_SIZE}

    monkeypatch.setattr(gh, "api", fake_api)

    assert len(census._recent_runs(150)) == 150  # noqa: SLF001 — paging is the thing checked
    assert "per_page=100" in pages[0]
    assert "per_page=50" in pages[1], "asked for a full page after the remainder was known"


def test_the_fetcher_stops_when_the_history_runs_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty page means the end — keep asking and the loop never returns."""
    calls: list[str] = []

    def fake_api(path: str) -> dict[str, Any]:
        calls.append(path)
        if len(calls) > 3:
            raise AssertionError("kept paging past an empty page")
        return {"workflow_runs": []}

    monkeypatch.setattr(gh, "api", fake_api)

    assert census._recent_runs(500) == []  # noqa: SLF001 — paging is the thing checked


def test_collect_reads_every_attempt_not_only_the_last(monkeypatch: pytest.MonkeyPatch) -> None:
    """The attempt a rerun replaced survives only under its own path."""
    asked: list[str] = []

    def fake_api(path: str) -> Any:  # noqa: ANN401 — two endpoints, two shapes
        asked.append(path)
        if "per_page" in path:
            return {"workflow_runs": [{"id": 5, "run_attempt": 2, "conclusion": "success"}]}
        if "annotations" in path:
            return [{"annotation_level": "failure", "message": "assert 1 == 2"}]
        return {
            "jobs": [
                {
                    "name": "lint",
                    "conclusion": "failure",
                    "steps": [{"name": "Run ruff", "conclusion": "failure"}],
                    "check_run_url": "check/1",
                    "id": 11,
                }
            ]
        }

    monkeypatch.setattr(gh, "api", fake_api)
    records = census.collect(1)

    assert any("attempts/1/jobs" in path for path in asked), "the replaced attempt was skipped"
    assert [f["attempt"] for f in records[0]["failures"]] == [1, 2]
    assert records[0]["failures"][0]["message"] == "assert 1 == 2"


def test_a_job_that_passed_is_not_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_api(path: str) -> Any:  # noqa: ANN401 — two endpoints, two shapes
        if "per_page" in path:
            return {"workflow_runs": [{"id": 5, "run_attempt": 1, "conclusion": "success"}]}
        return {"jobs": [{"name": "lint", "conclusion": "success"}]}

    monkeypatch.setattr(gh, "api", fake_api)

    assert census.collect(1)[0]["failures"] == []


def test_a_failure_with_no_failing_step_still_gets_a_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_api(path: str) -> Any:  # noqa: ANN401 — two endpoints, two shapes
        if "per_page" in path:
            return {"workflow_runs": [{"id": 5, "run_attempt": 1, "conclusion": "failure"}]}
        return {"jobs": [{"name": "lint", "conclusion": "failure", "steps": []}]}

    monkeypatch.setattr(gh, "api", fake_api)

    assert census.collect(1)[0]["failures"][0]["step"] == ""


def test_a_job_with_no_check_run_has_no_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gh, "api", lambda path: (_ for _ in ()).throw(AssertionError(path)))

    assert census._annotations({}) == ""  # noqa: SLF001 — the fallback is the thing checked


def test_annotations_that_cannot_be_read_fall_back_to_silence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A census that dies on one unreadable job cannot run during an outage."""

    def refuse(path: str) -> Any:  # noqa: ANN401 — never returns
        raise PermissionError(path)

    monkeypatch.setattr(gh, "api", refuse)

    assert census._annotations({"check_run_url": "check/1"}) == ""  # noqa: SLF001 — the fallback


def test_only_failure_annotations_become_the_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        gh,
        "api",
        lambda _path: [
            {"annotation_level": "notice", "message": "just so you know"},
            {"annotation_level": "failure", "message": "assert"},
            "not even a dict",
        ],
    )

    assert census._annotations({"check_run_url": "c"}) == "assert"  # noqa: SLF001 — filtering


def test_harvest_reads_a_log_only_for_our_own_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[list[str]] = []

    def fake_run(args: list[str], *, timeout: int = 0) -> str:  # noqa: ARG001 — the signature has to match the real wrapper
        asked.append(args)
        return "FAILED tests/test_a.py::test_one"

    monkeypatch.setattr(gh, "run", fake_run)
    records: list[dict[str, Any]] = [
        {
            "id": 1,
            "attempt": 1,
            "failures": [
                failure(step="Run pytest", message="assert", job_id=11),
                failure(step="Set up job", job_id=22),
            ],
        }
    ]
    census.harvest(records)
    ours, theirs = records[0]["failures"]

    assert ours["tests"] == ["tests/test_a.py"]
    assert "tests" not in theirs, "read a log for a platform failure"
    assert len(asked) == 1


def test_a_failure_with_no_job_id_reads_no_log(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **_kwargs: object) -> str:
        raise AssertionError(args)

    monkeypatch.setattr(gh, "run", refuse)

    assert census._job_log(None) == ""  # noqa: SLF001 — the guard is the thing checked


def test_a_log_that_cannot_be_read_is_empty_not_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(args: list[str], *, timeout: int = 0) -> str:  # noqa: ARG001 — signature parity
        raise PermissionError(args)

    monkeypatch.setattr(gh, "run", refuse)

    assert census._job_log(11) == ""  # noqa: SLF001 — the fallback is the thing checked


def test_a_log_is_given_a_ceiling_of_its_own(monkeypatch: pytest.MonkeyPatch) -> None:
    """A job's log can be enormous; the ceiling every other call uses is too small."""
    seen: dict[str, int] = {}

    def fake_run(args: list[str], *, timeout: int = 0) -> str:  # noqa: ARG001 — argv is not the point here
        seen["timeout"] = timeout
        return ""

    monkeypatch.setattr(gh, "run", fake_run)
    census._job_log(11)  # noqa: SLF001 — the ceiling is the thing checked

    assert seen["timeout"] == census.LOG_TIMEOUT_SECONDS


# ---------------------------------------------------------------- the report


def a_records_file(tmp_path: pathlib.Path, records: list[dict[str, Any]]) -> pathlib.Path:
    path = tmp_path / "records.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


def test_a_clean_window_reports_and_passes(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a_workflow(tmp_path / ".github" / "workflows", "ci.yml", "jobs:\n  lint:\n    steps: []\n")
    records = a_records_file(tmp_path, [{"id": 1, "attempt": 1, "failures": []}])

    code = census.main(["--root", str(tmp_path), "--input", str(records)])

    assert code == 0
    assert "examined 1 runs" in capsys.readouterr().out


def test_hidden_failures_over_the_ceiling_are_a_blocking_answer(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a_workflow(tmp_path / ".github" / "workflows", "ci.yml", "jobs:\n  lint:\n    steps: []\n")
    records = a_records_file(
        tmp_path, [{"id": 1, "attempt": 2, "failures": [failure(attempt=1, job="lint")]}]
    )

    code = census.main(["--root", str(tmp_path), "--input", str(records), "--max-hidden", "0"])

    assert code == 1
    assert "ceiling 0" in capsys.readouterr().err


def test_hidden_failures_under_the_ceiling_pass(tmp_path: pathlib.Path) -> None:
    a_workflow(tmp_path / ".github" / "workflows", "ci.yml", "jobs:\n  lint:\n    steps: []\n")
    records = a_records_file(
        tmp_path, [{"id": 1, "attempt": 2, "failures": [failure(attempt=1, job="lint")]}]
    )

    code = census.main(["--root", str(tmp_path), "--input", str(records), "--max-hidden", "1"])

    assert code == 0


def test_the_unclassified_count_asks_for_a_person(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a_workflow(tmp_path / ".github" / "workflows", "ci.yml", "jobs:\n  lint:\n    steps: []\n")
    records = a_records_file(
        tmp_path, [{"id": 1, "attempt": 1, "failures": [failure(job="lint", step="Run x")]}]
    )

    census.main(["--root", str(tmp_path), "--input", str(records)])

    assert "could not be classified" in capsys.readouterr().out


def test_a_hidden_failure_is_marked_beside_its_job(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a_workflow(tmp_path / ".github" / "workflows", "ci.yml", "jobs:\n  lint:\n    steps: []\n")
    records = a_records_file(
        tmp_path, [{"id": 1, "attempt": 2, "failures": [failure(attempt=1, job="lint")]}]
    )

    census.main(["--root", str(tmp_path), "--input", str(records)])

    assert "hidden 1" in capsys.readouterr().out


def test_a_strange_name_is_reported_on_the_error_stream(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a_workflow(tmp_path / ".github" / "workflows", "ci.yml", "jobs:\n  lint:\n    steps: []\n")
    records = a_records_file(
        tmp_path, [{"id": 1, "attempt": 1, "failures": [failure(job="ghost")]}]
    )

    census.main(["--root", str(tmp_path), "--input", str(records)])

    assert "ghost" in capsys.readouterr().err


def test_the_summary_can_be_printed_as_json(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a_workflow(tmp_path / ".github" / "workflows", "ci.yml", "jobs:\n  lint:\n    steps: []\n")
    records = a_records_file(tmp_path, [{"id": 1, "attempt": 1, "failures": []}])

    census.main(["--root", str(tmp_path), "--input", str(records), "--json"])

    assert json.loads(capsys.readouterr().out)["runs_examined"] == 1


def test_the_never_red_list_is_printed_on_request(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a_workflow(
        tmp_path / ".github" / "workflows",
        "ci.yml",
        "jobs:\n  lint:\n    steps: []\n  test:\n    steps: []\n",
    )
    records = a_records_file(tmp_path, [{"id": 1, "attempt": 1, "failures": [failure(job="lint")]}])

    census.main(["--root", str(tmp_path), "--input", str(records), "--never-red"])
    out = capsys.readouterr().out

    assert "never went red in this window (1): test" in out


def test_a_workflow_that_never_started_marks_its_jobs_as_not_silent(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ "Never red" and "never ran" are different answers, and one hides the other."""
    a_workflow(tmp_path / ".github" / "workflows", "ci.yml", "jobs:\n  lint:\n    steps: []\n")
    made = census.startup_failure({"conclusion": "failure", "name": ".github/workflows/ci.yml"}, [])
    records = a_records_file(tmp_path, [{"id": 1, "attempt": 1, "failures": made}])

    census.main(["--root", str(tmp_path), "--input", str(records), "--never-red"])

    assert "never went red on their own" in capsys.readouterr().out


def test_a_job_cannot_appear_in_both_halves_of_the_report(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The two halves are one subtraction apart, so they cannot disagree.

    This is stated as a test rather than as a guard in the code because no input
    can reach such a guard — and a check nothing can trigger makes a reader
    believe something is being watched when nothing is.
    """
    a_workflow(
        tmp_path / ".github" / "workflows",
        "ci.yml",
        "jobs:\n  lint:\n    steps: []\n  test:\n    steps: []\n",
    )
    records = a_records_file(tmp_path, [{"id": 1, "attempt": 1, "failures": [failure(job="lint")]}])

    census.main(["--root", str(tmp_path), "--input", str(records), "--never-red"])
    out = capsys.readouterr().out
    never = out.split("never went red in this window (1): ")[1].split("\n")[0]

    assert never == "test"
    assert "    lint: 1" in out, "the job that failed left the counted half too"


def test_evidence_asked_for_without_a_file_reads_the_logs(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Offline the tests are already in the file; online they have to be fetched."""

    def fake_api(path: str) -> Any:  # noqa: ANN401 — two endpoints, two shapes
        if "per_page" in path:
            return {"workflow_runs": [{"id": 7, "run_attempt": 1, "conclusion": "failure"}]}
        if "annotations" in path:
            return [{"annotation_level": "failure", "message": "assert 1 == 2"}]
        return {
            "jobs": [
                {
                    "name": "lint",
                    "conclusion": "failure",
                    "steps": [{"name": "Run pytest", "conclusion": "failure"}],
                    "check_run_url": "check/1",
                    "id": 11,
                }
            ]
        }

    monkeypatch.setattr(gh, "api", fake_api)
    monkeypatch.setattr(gh, "run", lambda *_a, **_k: "FAILED tests/test_a.py::test_one")
    a_workflow(tmp_path / ".github" / "workflows", "ci.yml", "jobs:\n  lint:\n    steps: []\n")
    (tmp_path / "gates.yaml").write_text(
        "gates:\n  - id: g1\n    enforced_by:\n      tests: [tests/test_a.py]\n",
        encoding="utf-8",
    )

    census.main(["--root", str(tmp_path), "--evidence", "--limit", "1"])

    assert "ref: run/7" in capsys.readouterr().out


def test_evidence_rows_are_proposed_from_a_file(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a_workflow(tmp_path / ".github" / "workflows", "ci.yml", "jobs:\n  lint:\n    steps: []\n")
    (tmp_path / "gates.yaml").write_text(
        "gates:\n  - id: g1\n    enforced_by:\n      tests: [tests/test_a.py]\n",
        encoding="utf-8",
    )
    records = a_records_file(
        tmp_path,
        [
            {
                "id": 7,
                "attempt": 1,
                "failures": [
                    failure(job="lint", step="Run pytest", message="a", tests=["tests/test_a.py"])
                ],
            }
        ],
    )

    census.main(["--root", str(tmp_path), "--input", str(records), "--evidence"])
    out = capsys.readouterr().out

    assert "ref: run/7" in out
    assert "read the log before accepting" in out


def test_no_gate_lacking_evidence_says_so(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a_workflow(tmp_path / ".github" / "workflows", "ci.yml", "jobs:\n  lint:\n    steps: []\n")
    (tmp_path / "gates.yaml").write_text("gates: []\n", encoding="utf-8")
    records = a_records_file(tmp_path, [{"id": 1, "attempt": 1, "failures": []}])

    census.main(["--root", str(tmp_path), "--input", str(records), "--evidence"])

    assert "no gate lacking evidence" in capsys.readouterr().out


def test_the_registry_can_be_pointed_at_explicitly(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a_workflow(tmp_path / ".github" / "workflows", "ci.yml", "jobs:\n  lint:\n    steps: []\n")
    registry = tmp_path / "elsewhere.yaml"
    registry.write_text("gates: []\n", encoding="utf-8")
    records = a_records_file(tmp_path, [{"id": 1, "attempt": 1, "failures": []}])

    code = census.main(
        [
            "--root",
            str(tmp_path),
            "--registry",
            str(registry),
            "--input",
            str(records),
            "--evidence",
        ]
    )

    assert code == 0
    assert "no gate lacking evidence" in capsys.readouterr().out


def test_a_history_that_cannot_be_read_is_its_own_answer(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Going quiet here would report a clean window on the day nothing can be seen."""

    def refuse(path: str) -> Any:  # noqa: ANN401 — never returns
        raise PermissionError(path)

    monkeypatch.setattr(gh, "api", refuse)
    a_workflow(tmp_path / ".github" / "workflows", "ci.yml", "jobs:\n  lint:\n    steps: []\n")

    code = census.main(["--root", str(tmp_path)])

    assert code == 2
    assert "never become a silent skip" in capsys.readouterr().err


def test_the_wording_is_an_input(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A project prints in the language its people read."""
    a_workflow(tmp_path / ".github" / "workflows", "ci.yml", "jobs:\n  lint:\n    steps: []\n")
    records = a_records_file(tmp_path, [{"id": 1, "attempt": 1, "failures": []}])

    # **Assembled, not written.** A literal here would make the file that proves
    # wording is an input into an instance of what this repository's language
    # policy forbids — the enforcer breaking its own rule.
    word = "".join(map(chr, (0x0E15, 0x0E23, 0x0E27, 0x0E08)))

    census.main(
        ["--root", str(tmp_path), "--input", str(records)],
        messages={"examined": word + " {count} run"},
    )

    assert word + " 1 run" in capsys.readouterr().out


# ---------------------------------------------------------------- a census over nothing


def test_zero_runs_is_a_window_nobody_looked_through(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`examined 0 runs` is not a clean window — it is exit 2, like any other blindness.

    An outside audit on 2026-08-29 fed this census an empty history and read back
    a pass with every counter at zero, which is indistinguishable from a real
    clean window and therefore must not be reported as one.
    """
    a_workflow(tmp_path / ".github" / "workflows", "ci.yml", "jobs:\n  lint:\n    steps: []\n")
    records = a_records_file(tmp_path, [])

    assert census.main(["--root", str(tmp_path), "--input", str(records)]) == 2
    out = capsys.readouterr()
    assert "history is empty" in out.err
    assert "examined" not in out.out


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("{}", "an object where a list of records was expected"),
        ("[", "not JSON at all"),
    ],
)
def test_a_history_of_the_wrong_shape_is_unreadable(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], text: str, why: str
) -> None:
    a_workflow(tmp_path / ".github" / "workflows", "ci.yml", "jobs:\n  lint:\n    steps: []\n")
    path = tmp_path / "records.json"
    path.write_text(text, encoding="utf-8")

    assert census.main(["--root", str(tmp_path), "--input", str(path)]) == 2, why
    assert "never become a silent skip" in capsys.readouterr().err
