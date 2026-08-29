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


# ---------------------------------------------------------------- the security workflow


def test_the_codeql_job_ends_with_a_decider_on_this_ref() -> None:
    """CodeQL's own step never fails on a finding — the decision has to be a step that reads."""
    jobs = preflight.jobs_on_disk(ROOT)
    steps = jobs["codeql"]["steps"]
    init = next(s for s in steps if "codeql-action/init" in str(s.get("uses")))
    decide = next(s for s in steps if "verifiable_gates.posture" in str(s.get("run")))

    assert init["with"]["queries"] == "security-extended"
    assert "python" in init["with"]["languages"]
    assert steps.index(decide) > max(
        i for i, s in enumerate(steps) if "codeql-action" in str(s.get("uses"))
    )
    assert '--ref "$GITHUB_REF"' in decide["run"]
    assert "--register pins/dev/code-scanning-accepted.txt" in decide["run"]


def test_the_secret_scan_runs_a_checksummed_binary_over_the_whole_history() -> None:
    jobs = preflight.jobs_on_disk(ROOT)
    steps = jobs["secret-scan"]["steps"]
    checkout = next(s for s in steps if "actions/checkout" in str(s.get("uses")))
    fetch = next(s for s in steps if "sha256sum -c" in str(s.get("run")))
    scan = next(s for s in steps if "gitleaks git" in str(s.get("run")))

    assert checkout["with"]["fetch-depth"] == 0, "a shallow clone scans one commit, not the history"
    assert "gitleaks_8.30.1_linux_x64.tar.gz" in fetch["run"]
    assert "--exit-code 1" in scan["run"]
    assert "--redact" in scan["run"], "a found secret must not be printed into the log"


# ---------------------------------------------------------------- the release workflow


def test_the_release_job_verifies_both_ways_before_it_attaches_anything() -> None:
    """A verifier nobody has watched refusing is one nobody has proved reads anything."""
    jobs = preflight.jobs_on_disk(ROOT)
    steps = jobs["release-sign"]["steps"]
    names = [str(s.get("name") or s.get("uses") or s.get("run")) for s in steps]
    verify = next(s for s in steps if "verify in both directions" in str(s.get("name")))
    attach = next(s for s in steps if "attach the wheel" in str(s.get("name")))
    attests = [s for s in steps if "actions/attest-" in str(s.get("uses"))]

    assert len(attests) == 2, names
    assert all("@" in str(s["uses"]) and len(str(s["uses"]).split("@")[1]) == 40 for s in attests)
    assert "tampered.whl" in verify["run"], "no negative direction — the verifier is unproved"
    assert "--predicate-type https://cyclonedx.org/bom" in verify["run"]
    assert steps.index(verify) > max(steps.index(s) for s in attests)
    assert steps.index(attach) > steps.index(verify), "attached before verified"


def test_the_sbom_is_taken_from_a_clean_environment_holding_the_wheel() -> None:
    jobs = preflight.jobs_on_disk(ROOT)
    sbom = next(s for s in jobs["release-sign"]["steps"] if "cyclonedx-py" in str(s.get("run")))

    assert "python -m venv --without-pip sbom-env" in sbom["run"]
    assert "install dist/*.whl" in sbom["run"]
    assert "'verifiable-gates' in n and 'PyYAML' in n" in sbom["run"], "an SBOM of nothing is green"


# ---------------------------------------------------------------- posture and the census


def test_the_posture_job_reads_with_the_custodians_token_on_a_schedule() -> None:
    jobs = preflight.jobs_on_disk(ROOT)
    step = next(s for s in jobs["posture"]["steps"] if "posture --settings" in str(s.get("run")))
    text = (ROOT / ".github" / "workflows" / "posture.yml").read_text(encoding="utf-8")

    assert step["env"]["GH_TOKEN"] == "${{ secrets.POSTURE_TOKEN }}", "job token cannot read it"  # noqa: S105 — the secret's name, not its value
    assert "--settings pins/dev/posture-declared.json" in step["run"]
    assert "cron:" in text
    assert "workflow_dispatch" in text


def test_the_schedule_census_runs_over_a_full_clone() -> None:
    """A shallow clone reports every workflow as newborn — the free pass the census refuses."""
    jobs = preflight.jobs_on_disk(ROOT)
    steps = jobs["test"]["steps"]
    checkout = next(s for s in steps if "actions/checkout" in str(s.get("uses")))
    census = next(s for s in steps if "schedule_census" in str(s.get("run")))

    assert checkout["with"]["fetch-depth"] == 0
    assert census["name"] == "every declared schedule is still firing"
