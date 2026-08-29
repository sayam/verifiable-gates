"""The developer-side instruments this bundle ships, pointed at this repository.

`tests/test_dogfood.py` points every *scanner* here and stops. `preflight`, the
fail-fix harness and the two CI-side deciders (`advisories`, `check_issue_handoff`)
are the instruments a person or a job actually runs — and until 2026-08-29 they
had been proved on fixtures and never asked about this tree.
"""

from __future__ import annotations

import json
import pathlib
from typing import TYPE_CHECKING

from verifiable_gates import check_issue_handoff, harness, preflight

if TYPE_CHECKING:
    import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- preflight and the harness

# The commands a developer's machine can run from the two jobs `scaffold.json`
# names. Named, not counted: a count of "4 runnable steps" stays true while the
# wrong four run.
LOCAL_STEPS = ("ruff check .", "ruff format --check .", "mypy src tests", "pytest -q --cov")


def test_preflight_plans_this_repositorys_own_jobs_losing_no_step() -> None:
    """Every step of `lint` and `test` is either run or skipped with a reason — none dropped."""
    workflow = {"jobs": preflight.jobs_on_disk(ROOT)}
    # Read from the config, not through the fallback: here the default jobs happen
    # to be the same two names, so a scaffold.json that lost the key would plan
    # identically and a test asking only the plan could never tell.
    config = json.loads((ROOT / "scaffold.json").read_text(encoding="utf-8"))
    assert config.get("preflight_jobs") == ["lint", "test"], "scaffold.json must name the jobs"
    jobs = preflight.wanted_jobs(ROOT, [])
    assert jobs == ("lint", "test")

    entries = preflight.plan(workflow, jobs, "main")
    declared = sum(len(workflow["jobs"][job]["steps"]) for job in jobs)

    assert len(entries) == declared, "a step left the plan without a word"
    planned = [entry["run"] for entry in entries if "skip" not in entry]
    for command in LOCAL_STEPS:
        assert command in planned, f"{command!r} is not planned to run here"
    for entry in entries:
        if "skip" in entry:
            assert entry["skip"], f"{entry['label']} skipped with no reason"


def test_the_harness_answers_for_one_of_this_repositorys_own_gates(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """One cheap gate, for real, with the round log kept out of the tree.

    The whole registry would run the whole suite from inside the suite; one gate
    is enough to prove the loop closes on this tree and not only on fixtures.
    """
    monkeypatch.setattr(harness, "ROUND_LOG", str(tmp_path / "rounds.jsonl"))

    code = harness.main(
        [
            "--registry",
            str(ROOT / "gates.yaml"),
            "--root",
            str(ROOT),
            "--only",
            "the-manifest-is-an-input",
        ]
    )

    assert code == 0, capsys.readouterr().out
    assert "1 pass" in capsys.readouterr().out
    record = json.loads((tmp_path / "rounds.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert record["counts"]["pass"] == 1


def test_the_harness_refuses_a_gate_it_cannot_find(tmp_path: pathlib.Path) -> None:
    code = harness.main(
        ["--registry", str(ROOT / "gates.yaml"), "--root", str(tmp_path), "--only", "no-such-gate"]
    )

    assert code == 2


def test_the_handoff_job_reads_what_the_module_reads() -> None:
    """The job feeds the module through env — the three names are the module's contract."""
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    jobs = preflight.jobs_on_disk(ROOT)
    step = next(s for s in jobs["handoff"]["steps"] if "check_issue_handoff" in str(s.get("run")))

    # Run as the shipped file under a bare python3 — the way a consumer runs it.
    # `python -m verifiable_gates.…` would import the package, whose `__init__`
    # needs pyyaml, and the first live run went red on exactly that.
    assert step["run"].strip() == "python3 src/verifiable_gates/check_issue_handoff.py"
    assert set(step["env"]) == {"GH_TOKEN", "PR_NUMBER", "PR_BODY"}
    assert "PR_NUMBER" in pathlib.Path(check_issue_handoff.__file__).read_text(encoding="utf-8")
    assert "if: github.event_name == 'pull_request'" in ci, "the gate means nothing off a PR"


def test_the_advisories_job_lets_the_decider_decide() -> None:
    """`pip-audit` writes, `advisories` decides — the scanner's exit code is not the verdict."""
    jobs = preflight.jobs_on_disk(ROOT)
    step = next(s for s in jobs["advisories"]["steps"] if "pip-audit" in str(s.get("run")))

    assert "|| true" in step["run"]
    assert "python -m verifiable_gates.advisories" in step["run"]
    assert "--register pins/dev/advisories-accepted.txt" in step["run"]
