"""Install into an empty directory, then let the doctor judge what arrived.

This is the end-to-end claim the whole bundle rests on: a project that has
installed nothing gets a `tools/` directory and can run `python3
tools/gates_doctor.py` immediately. Testing the pieces separately would leave the
one thing that matters — that they fit together in a directory with no package
present — proven by nobody.

Three properties, and the second is the one that decays quietly:

- **A fresh install is usable**: the doctor reports the bundle intact and the
  scans run.
- **Files holding decisions are never overwritten.** `scaffold.json`,
  `gates.yaml`, and the workflow are written once. A second install that
  clobbered them would destroy exactly the work the bundle exists to protect,
  and nothing about the output would look wrong.
- **An incomplete bundle fails loudly.** Deleting one shipped file has to turn
  the installer red rather than produce a half-install that reports success.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
from bundle import DOCTOR, do_install, run_doctor

from verifiable_gates import gates_doctor
from verifiable_gates import install as install_module

if TYPE_CHECKING:
    import pathlib


def test_a_fresh_install_gives_a_project_something_that_runs(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    capsys.readouterr()

    for expected in (DOCTOR, "tools/overlay.json", "scaffold.json", "gates.yaml"):
        assert (project / expected).is_file(), f"{expected} did not arrive"
    assert (project / ".github" / "workflows" / "gates.yml").is_file()

    intact = run_doctor(project, "--installed")
    assert intact.returncode == 0, intact.stdout + intact.stderr
    assert "installed:" in intact.stdout


def test_the_doctor_runs_the_scans_on_a_bare_project(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A project with nothing in it yet: every scan reports NA, and says so."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    capsys.readouterr()

    done = run_doctor(project)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "[   NA]" in done.stdout, "an empty project should be all not-applicable"
    assert "[found]" not in done.stdout


def test_the_doctor_reports_findings_and_names_them(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    capsys.readouterr()
    (project / "run.py").write_text("app = object()\napp.run(debug=True)\n", encoding="utf-8")

    done = run_doctor(project)
    assert done.returncode == 1
    assert "[found] no-debug-entrypoint" in done.stdout
    assert "scans found problems in 1 gates" in done.stdout


def test_a_second_install_keeps_the_decisions_already_made(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The files that hold someone's work are written once, and never again."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    edited = {"src_path": "source", "_edited": True}
    (project / "scaffold.json").write_text(json.dumps(edited), encoding="utf-8")
    (project / "gates.yaml").write_text("version: 1\ngates: []  # mine\n", encoding="utf-8")

    assert do_install(project, bundle_copy) == 0
    assert "kept:" in capsys.readouterr().out
    assert json.loads((project / "scaffold.json").read_text(encoding="utf-8")) == edited
    assert "# mine" in (project / "gates.yaml").read_text(encoding="utf-8")


def test_an_incomplete_bundle_refuses_to_install(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Half an install that reports success is worse than no install."""
    (bundle_copy / "checks" / "scan_entrypoint_debug.py").unlink()
    assert do_install(tmp_path / "project", bundle_copy) == 1
    assert "the bundle is incomplete" in capsys.readouterr().err


def test_the_doctor_notices_a_scan_that_went_missing_after_install(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Files can disappear after the install too, and that must not read as clean."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    capsys.readouterr()
    (project / "tools" / "checks" / "scan_workflow_pinning.py").unlink()

    done = run_doctor(project, "--installed")
    assert done.returncode == 1
    assert "is missing" in done.stdout


def test_the_doctor_needs_a_finished_install(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No scaffold.json means the project was never configured — not that it is clean."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    capsys.readouterr()
    (project / "scaffold.json").unlink()

    done = run_doctor(project, "--installed")
    assert done.returncode == 1
    assert "the install did not finish" in done.stdout


def test_suite_gates_are_reported_as_pending_not_passed(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A rule the bundle cannot decide must never be counted among the ones it did."""
    manifest = json.loads((bundle_copy / "overlay.json").read_text(encoding="utf-8"))
    manifest["gates"]["written-by-the-project"] = {
        "kind": "suite",
        "title": "Something only the project's own tests can answer",
    }
    (bundle_copy / "overlay.json").write_text(json.dumps(manifest), encoding="utf-8")

    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    capsys.readouterr()

    done = run_doctor(project)
    assert "waiting on this project's own tests: 1 gates" in done.stdout
    assert "written-by-the-project" not in done.stdout.split("waiting on")[0], (
        "a suite gate appeared among the results, where it would read as decided"
    )


# ---------------------------------------------------------------- in process too
#
# The subprocess runs above prove the shipped file works where it is shipped.
# Calling the same code in process is what lets the coverage measurement see it,
# and it reports failures with a traceback instead of a captured string. Both are
# needed: only the first proves the claim, only the second says why it broke.


def test_the_doctor_reports_a_finding_when_called_in_process(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    (project / "run.py").write_text("app = object()\napp.run(debug=True)\n", encoding="utf-8")
    capsys.readouterr()

    code = gates_doctor.main([str(project), "--manifest", str(project / "tools" / "overlay.json")])
    assert code == 1
    assert "[found] no-debug-entrypoint" in capsys.readouterr().out


def test_the_doctor_checks_the_install_when_called_in_process(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    capsys.readouterr()

    manifest = str(project / "tools" / "overlay.json")
    assert gates_doctor.main([str(project), "--manifest", manifest, "--installed"]) == 0
    assert "installed:" in capsys.readouterr().out


def test_the_doctor_defaults_to_the_project_above_its_own_bundle(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Run with no arguments from `tools/`, it judges the project it was installed into."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    capsys.readouterr()

    done = subprocess.run(  # noqa: S603 — argv is built here, interpreter is sys.executable
        [sys.executable, str(project / DOCTOR)],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "[   NA]" in done.stdout


def test_a_manifest_without_gates_is_refused(tmp_path: pathlib.Path) -> None:
    """Unusable is not the same as empty, and must not be read as "nothing to do"."""
    path = tmp_path / "overlay.json"
    path.write_text('{"ship": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="not a manifest"):
        gates_doctor.load_manifest(path)


def test_the_installer_can_be_driven_from_the_command_line(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "project"
    code = install_module.main([str(project), "--manifest", str(bundle_copy / "overlay.json")])
    assert code == 0
    assert "installed into" in capsys.readouterr().out
    assert (project / DOCTOR).is_file()


@pytest.fixture
def installed(tmp_path: pathlib.Path, bundle_copy: pathlib.Path) -> pathlib.Path:
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    return project


def _installed_check(project: pathlib.Path) -> int:
    manifest = str(project / "tools" / "overlay.json")
    return gates_doctor.main([str(project), "--manifest", manifest, "--installed"])


def test_a_scan_that_does_not_compile_is_an_incomplete_install(
    installed: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A broken scan would otherwise fail at run time, one gate at a time, as a finding.

    Nothing else in this file reaches that branch: a file that exists but cannot
    be parsed is not the same failure as a file that is gone, and the whole point
    of `--installed` is to separate "the bundle is wrong" from "your code is".
    """
    broken = installed / "tools" / "checks" / "scan_workflow_pinning.py"
    broken.write_text("def main(root:\n", encoding="utf-8")
    capsys.readouterr()

    assert _installed_check(installed) == 1
    assert "does not compile" in capsys.readouterr().out


def test_a_scan_removed_after_install_is_reported_in_process(
    installed: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (installed / "tools" / "checks" / "scan_adr_index.py").unlink()
    capsys.readouterr()

    assert _installed_check(installed) == 1
    output = capsys.readouterr().out
    assert "the installation is incomplete" in output
    assert "scan_adr_index.py is missing" in output


def test_a_missing_config_is_reported_in_process(
    installed: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (installed / "scaffold.json").unlink()
    capsys.readouterr()

    assert _installed_check(installed) == 1
    assert "the install did not finish" in capsys.readouterr().out


def test_the_summary_line_names_every_gate_that_found_something(
    installed: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Several findings, so the count and the list are exercised rather than implied.

    Replacing the workflow with one that pins nothing breaks three gates, not two,
    and the third is the interesting one: the starting registry points at the
    `scans` job, which this just removed. A registry is an index of things that
    exist, so deleting the thing deletes the index's claim with it.
    """
    (installed / "run.py").write_text("app = object()\napp.run(debug=True)\n", encoding="utf-8")
    workflows = installed / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    (workflows / "gates.yml").write_text(
        "jobs:\n  a:\n    steps:\n      - uses: actions/checkout@v4\n", encoding="utf-8"
    )
    capsys.readouterr()

    manifest = str(installed / "tools" / "overlay.json")
    assert gates_doctor.main([str(installed), "--manifest", manifest]) == 1
    output = capsys.readouterr().out
    assert "scans found problems in 3 gates" in output
    for gate in ("actions-sha-pinned", "no-debug-entrypoint", "gates-registry-total"):
        assert gate in output, f"{gate} is broken by this tree but was not named"


def test_a_clean_run_returns_zero_in_process(
    installed: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The passing path deserves a test of its own, not just the failing one.

    Everything above drives the doctor towards a finding. A tool that could only
    ever return 1 would satisfy all of them, and the one thing every user relies
    on — that a clean project is reported clean — would rest on the subprocess
    runs alone, where a wrong exit code is easy to miss among captured output.
    """
    capsys.readouterr()
    manifest = str(installed / "tools" / "overlay.json")
    assert gates_doctor.main([str(installed), "--manifest", manifest]) == 0
    output = capsys.readouterr().out
    assert "[found]" not in output
    assert "waiting on this project's own tests" in output
