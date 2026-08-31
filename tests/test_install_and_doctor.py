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
import pathlib
import re
import shutil
import subprocess
import sys

import pytest
from bundle import DOCTOR, do_install, run_doctor

from verifiable_gates import gates_doctor
from verifiable_gates import install as install_module
from verifiable_gates import manifest as manifest_module


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
    passes = [line for line in done.stdout.splitlines() if line.startswith("[ pass]")]
    assert passes == ["[ pass] gates-registry-total"], (
        "only the shipped index is measured on an empty project — see test_box_opens_true"
    )


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


def test_a_kept_registry_that_names_no_gate_for_the_job_is_said_out_loud(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A project with its own `gates.yaml` gets the workflow, and the seam between them named."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "gates.yaml").write_text("version: 1\ngates: []\n", encoding="utf-8")
    assert do_install(project, bundle_copy) == 0
    out, err = capsys.readouterr()
    assert "kept: gates.yaml" in out
    assert "names no gate for job `scans`" in err
    assert "enforced_by: {job: scans}" in err
    assert run_doctor(project).returncode == 1, (
        "the seam the installer named is the doctor's finding"
    )


def test_a_kept_registry_that_names_the_job_is_quiet(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other direction: a kept registry with a row for `scans` earns no warning."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "gates.yaml").write_text(
        "version: 1\ngates:\n  - id: scans-run\n    title: t\n    kind: job\n"
        "    severity: blocking\n    enforced_by: {job: scans}\n",
        encoding="utf-8",
    )
    assert do_install(project, bundle_copy) == 0
    assert "names no gate" not in capsys.readouterr().err


def test_a_kept_registry_naming_only_other_jobs_still_gets_the_warning(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The reference implementation's shape: every gate points at `test`, none at `scans`."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "gates.yaml").write_text(
        "version: 1\ngates:\n  - id: own\n    title: t\n    kind: job\n"
        "    severity: blocking\n    enforced_by: {job: test}\n",
        encoding="utf-8",
    )
    assert do_install(project, bundle_copy) == 0
    assert "names no gate for job `scans`" in capsys.readouterr().err


def test_the_template_runs_the_job_the_installer_names(bundle_copy: pathlib.Path) -> None:
    """`TEMPLATE_JOB` is a copy of the template's job key — this holds the copy to the original."""
    template = (bundle_copy / "ci-template.yml").read_text(encoding="utf-8")
    assert f"\n  {install_module.TEMPLATE_JOB}:\n" in template


def test_a_refused_install_leaves_no_trace_at_the_destination(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The directories used to be made before the refusal — an empty `tools/checks/`
    at a destination the install refused is a trace of work that never happened."""
    bad = manifest_module.load(bundle_copy / "overlay.json")
    bad["ship"].append("../escape.txt")
    (bundle_copy / "overlay.json").write_text(json.dumps(bad), encoding="utf-8")
    dest = tmp_path / "never-touched"

    code = install_module.main([str(dest), "--manifest", str(bundle_copy / "overlay.json")])
    capsys.readouterr()
    assert code == 1
    assert not dest.exists(), "a refused install made directories anyway"


def test_a_manifest_that_ships_a_climbing_name_is_refused_before_any_copy(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A manifest from outside the package may ship `../../x`; it must not land beside `dest`."""
    bundle = tmp_path / "a" / "b" / "bundle"
    shutil.copytree(bundle_copy, bundle)
    planted = tmp_path / "a" / "outside" / "PLANTED.txt"
    planted.parent.mkdir()
    planted.write_text("planted\n", encoding="utf-8")
    manifest = manifest_module.load(bundle / "overlay.json")
    manifest["ship"].append("../../outside/PLANTED.txt")
    (bundle / "overlay.json").write_text(json.dumps(manifest), encoding="utf-8")
    dest = tmp_path / "c" / "dest"
    landing = tmp_path / "c" / "outside" / "PLANTED.txt"

    assert install_module.main([str(dest), "--manifest", str(bundle / "overlay.json")]) == 1
    assert "would land outside the destination" in capsys.readouterr().err
    assert not landing.exists(), "the file left the destination"
    assert not (dest / "tools" / "gates_doctor.py").exists(), "nothing was copied before refusing"


def test_a_manifest_with_a_bad_entry_is_refused_by_the_installer(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every problem `manifest.problems()` names stops the install, not only a missing file."""
    manifest = manifest_module.load(bundle_copy / "overlay.json")
    manifest["gates"]["actions-sha-pinned"]["kind"] = "bogus"
    (bundle_copy / "overlay.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert do_install(tmp_path / "project", bundle_copy) == 1
    assert "kind 'bogus'" in capsys.readouterr().err


def test_an_incomplete_bundle_refuses_to_install(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Half an install that reports success is worse than no install."""
    (bundle_copy / "checks" / "scan_entrypoint_debug.py").unlink()
    assert do_install(tmp_path / "project", bundle_copy) == 1
    assert "the bundle is incomplete" in capsys.readouterr().err


def test_a_scan_that_crashes_is_an_error_with_its_traceback_not_a_finding(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A broken `scaffold.json` makes the scans traceback; the doctor must say so, not `[found]`."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    capsys.readouterr()
    (project / "scaffold.json").write_text("{bad", encoding="utf-8")

    done = run_doctor(project)
    assert done.returncode == 1
    assert "[found]" not in done.stdout
    assert "[error] no-debug-entrypoint — the scan did not answer (exit 1)" in done.stdout
    assert "scans did not answer, which is no verdict" in done.stdout
    assert "found problems" not in done.stdout
    assert "Traceback" in done.stderr
    assert "JSONDecodeError" in done.stderr


def test_a_scan_that_hangs_is_an_error_not_a_traceback(
    tmp_path: pathlib.Path,
    bundle_copy: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The doctor used to die of `TimeoutExpired`; a hang is an answer the report carries."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    (project / "tools" / "checks" / "scan_workflow_pinning.py").write_text(
        "import time\ntime.sleep(30)\n", encoding="utf-8"
    )
    monkeypatch.setattr(gates_doctor, "SCAN_TIMEOUT", 1)
    capsys.readouterr()

    code = gates_doctor.main([str(project), "--manifest", str(project / "tools" / "overlay.json")])
    out = capsys.readouterr().out
    assert code == 1
    assert "[error] actions-sha-pinned — the scan did not answer (timed out after 1s)" in out
    assert "did not answer, which is no verdict" in out


def test_a_scan_that_prints_half_a_verdict_and_crashes_is_an_error(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit 1 with stdout *and* a traceback on stderr: the scan did not finish judging."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    (project / "tools" / "checks" / "scan_workflow_pinning.py").write_text(
        "print('actions-sha-pinned: x.yml: half a verdict')\nraise RuntimeError('boom')\n",
        encoding="utf-8",
    )
    capsys.readouterr()

    done = run_doctor(project)
    assert done.returncode == 1
    assert "[error] actions-sha-pinned" in done.stdout
    assert "[found] actions-sha-pinned" not in done.stdout
    assert "RuntimeError: boom" in done.stderr


def test_a_scan_that_warns_on_stderr_beside_a_real_finding_is_still_found(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other direction: a warning is not a traceback; the verdict stands."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    (project / "tools" / "checks" / "scan_workflow_pinning.py").write_text(
        "import sys\nprint('actions-sha-pinned: x.yml: actions/checkout@v4')\n"
        "print('warning: slow tree', file=sys.stderr)\nsys.exit(1)\n",
        encoding="utf-8",
    )
    capsys.readouterr()

    done = run_doctor(project)
    assert done.returncode == 1
    assert "[found] actions-sha-pinned" in done.stdout
    assert "warning: slow tree" in done.stderr


def test_a_scan_that_is_called_wrongly_is_an_error_too(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit 2 with a usage line on stderr is the scanner's protocol for misuse — no verdict."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    capsys.readouterr()
    (project / "tools" / "checks" / "scan_workflow_pinning.py").write_text(
        "import sys\nprint('usage: nope', file=sys.stderr)\nsys.exit(2)\n", encoding="utf-8"
    )

    done = run_doctor(project)
    assert done.returncode == 1
    assert "[error] actions-sha-pinned — the scan did not answer (exit 2)" in done.stdout
    assert "usage: nope" in done.stderr


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


def test_the_doctor_reports_a_crashed_scan_when_called_in_process(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same `[error]` answer through the library entry point, stderr passed through."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    (project / "scaffold.json").write_text("{bad", encoding="utf-8")
    capsys.readouterr()

    code = gates_doctor.main([str(project), "--manifest", str(project / "tools" / "overlay.json")])
    captured = capsys.readouterr()
    assert code == 1
    assert "[error] no-debug-entrypoint" in captured.out
    assert "did not answer, which is no verdict" in captured.out
    assert "JSONDecodeError" in captured.err


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


# ---------------------------------------------------------------- --root, like the other tools
#
# Every other tool here takes `--root`. The re-audit's operator typed it at the
# doctor and got a usage error (round 18, 2026-08-30). The flag is an alias for
# the positional, and the two must answer alike.
#
# The tests below point the doctor at a project that is NOT the one above its
# bundle. That is deliberate: a `--root` that parsed but was ignored would fall
# back to the default, and on the usual layout the default is the same directory
# — the mutation would pass. Only a root that differs from the default can show
# that the flag was read.


def _elsewhere(tmp_path: pathlib.Path) -> pathlib.Path:
    """A second, dirty project the installed bundle knows nothing about."""
    other = tmp_path / "elsewhere"
    other.mkdir()
    (other / "scaffold.json").write_text(json.dumps({"entrypoints": ["run.py"]}), encoding="utf-8")
    (other / "run.py").write_text("app = object()\napp.run(debug=True)\n", encoding="utf-8")
    return other


def test_root_flag_answers_exactly_as_the_positional(
    tmp_path: pathlib.Path, installed: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    other = _elsewhere(tmp_path)
    capsys.readouterr()

    manifest = str(installed / "tools" / "overlay.json")
    positional = gates_doctor.main([str(other), "--manifest", manifest])
    by_position = capsys.readouterr().out
    flagged = gates_doctor.main(["--root", str(other), "--manifest", manifest])
    by_flag = capsys.readouterr().out

    assert positional == flagged == 1
    assert "[found] no-debug-entrypoint" in by_flag, "--root did not reach the scans"
    assert by_flag == by_position, "the two spellings of the root must give one report"


def test_root_flag_works_when_the_doctor_is_run_as_a_file(
    tmp_path: pathlib.Path, installed: pathlib.Path
) -> None:
    """The operator's exact call, against the shipped file rather than the module."""
    other = _elsewhere(tmp_path)

    done = subprocess.run(  # noqa: S603 — argv is built here, interpreter is sys.executable
        [sys.executable, str(installed / DOCTOR), "--root", str(other)],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    assert done.returncode == 1, done.stdout + done.stderr
    assert "[found] no-debug-entrypoint" in done.stdout


def test_naming_the_root_twice_is_a_misuse(
    installed: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit 2 with a message — not a silent choice between two directories."""
    manifest = str(installed / "tools" / "overlay.json")
    with pytest.raises(SystemExit) as raised:
        gates_doctor.main([str(installed), "--root", str(installed), "--manifest", manifest])
    assert raised.value.code == 2
    assert "not both" in capsys.readouterr().err


def test_a_manifest_under_another_name_installs_whole(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--manifest bundle.json` used to land sixteen files and then die looking for
    `overlay.json` — half a bundle at the destination (self-audit, 2026-08-31)."""
    (bundle_copy / "overlay.json").rename(bundle_copy / "bundle.json")
    dest = tmp_path / "project"
    assert install_module.main([str(dest), "--manifest", str(bundle_copy / "bundle.json")]) == 0
    assert (dest / "tools" / "overlay.json").read_text(encoding="utf-8") == (
        bundle_copy / "bundle.json"
    ).read_text(encoding="utf-8")
    assert "installed into" in capsys.readouterr().out


@pytest.mark.parametrize("link", ["tools", ".github/workflows"])
def test_a_symlink_on_the_way_out_of_the_destination_is_refused_before_any_copy(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str], link: str
) -> None:
    """Fourteen files landed outside `dest` through a `tools` symlink, exit 0 (self-audit,
    2026-08-31). A directory on the way to a target that leads outside is a refusal."""
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    dest = tmp_path / "project"
    (dest / link).parent.mkdir(parents=True, exist_ok=True)
    (dest / link).symlink_to(outside)
    code = install_module.main([str(dest), "--manifest", str(bundle_copy / "overlay.json")])
    err = capsys.readouterr().err
    assert code == 1
    assert "leads outside the destination" in err
    assert "refusing to install" in err
    assert list(outside.iterdir()) == []
    assert not (dest / "tools" / "checks").exists() or link == ".github/workflows"


def test_a_symlink_that_stays_inside_the_destination_is_fine(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "project"
    (dest / "real-tools").mkdir(parents=True)
    (dest / "tools").symlink_to(dest / "real-tools")
    assert install_module.main([str(dest), "--manifest", str(bundle_copy / "overlay.json")]) == 0
    assert (dest / "real-tools" / "gates_doctor.py").is_file()
    capsys.readouterr()


@pytest.mark.parametrize(
    "text",
    ["{nope", "[]", '{"ship": []}', '{"ship": "x", "gates": {}}', '{"ship": [1], "gates": {}}'],
    ids=["not-json", "a-list", "no-gates", "ship-not-a-list", "ship-not-names"],
)
def test_a_manifest_that_cannot_be_read_is_said_plainly_and_is_exit_2(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], text: str
) -> None:
    """Eight malformed shapes were each a raw traceback with exit 1 — the code that means
    "refused" — not the "cannot read" and exit 2 every other input gets (self-audit,
    2026-08-31)."""
    path = tmp_path / "overlay.json"
    path.write_text(text, encoding="utf-8")
    dest = tmp_path / "project"
    code = install_module.main([str(dest), "--manifest", str(path)])
    err = capsys.readouterr().err
    assert code in {1, 2}
    assert "Traceback" not in err
    assert "cannot read the manifest" in err or "refusing to install" in err
    assert not dest.exists()


def test_a_manifest_that_is_not_there_is_exit_2(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = install_module.main([str(tmp_path / "p"), "--manifest", str(tmp_path / "gone.json")])
    assert code == 2
    assert "cannot read the manifest" in capsys.readouterr().err


def test_a_destination_that_is_a_file_is_refused(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "a-file"
    dest.write_text("x", encoding="utf-8")
    code = install_module.main([str(dest), "--manifest", str(bundle_copy / "overlay.json")])
    err = capsys.readouterr().err
    assert code == 1
    assert "exists and is not a directory" in err
    assert "Traceback" not in err


def test_a_destination_nobody_can_write_is_refused(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "locked"
    dest.mkdir()
    dest.chmod(0o500)
    try:
        code = install_module.main([str(dest), "--manifest", str(bundle_copy / "overlay.json")])
    finally:
        dest.chmod(0o700)
    err = capsys.readouterr().err
    assert code == 1
    assert "is not writable" in err


def test_a_comment_naming_the_job_does_not_silence_the_warning(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`# enforced_by: {job: scans} would be the row to add` is a comment, not a row
    (self-audit, 2026-08-31: it silenced the warning)."""
    dest = tmp_path / "project"
    dest.mkdir()
    (dest / "gates.yaml").write_text(
        "# note: enforced_by: {job: scans} would be the row to add\n"
        "version: 1\ngates:\n  - id: x\n    title: t\n    kind: job\n"
        "    enforced_by: {job: test}\n",
        encoding="utf-8",
    )
    assert install_module.main([str(dest), "--manifest", str(bundle_copy / "overlay.json")]) == 0
    assert "names no gate for job `scans`" in capsys.readouterr().err


def test_a_write_that_fails_midway_is_said_plainly(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A file where `tools/checks/` must be a directory passes the look-ahead (it is inside
    the destination) and fails at the first write — said plainly, exit 1, no traceback."""
    dest = tmp_path / "project"
    (dest / "tools").mkdir(parents=True)
    (dest / "tools" / "checks").write_text("not a directory", encoding="utf-8")
    code = install_module.main([str(dest), "--manifest", str(bundle_copy / "overlay.json")])
    err = capsys.readouterr().err
    assert code == 1
    assert "could not write to" in err
    assert "Traceback" not in err


def test_a_scans_stderr_lands_beside_its_own_gate_line_under_a_pipe(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path
) -> None:
    """Under a pipe — a CI log — stdout is block-buffered and stderr is not, so every
    scan's stderr surfaced above the first gate line (self-audit, 2026-08-31). With one
    stream for both, the traceback of the second scan must come after the first gate's
    line and before its own."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    second = project / "tools" / "checks" / "scan_adr_index.py"
    marker = "from __future__ import annotations\n"
    text = second.read_text(encoding="utf-8")
    second.write_text(text.replace(marker, marker + 'raise RuntimeError("boom")\n', 1), "utf-8")
    out = run_doctor(project, one_stream=True).stdout
    first_gate = out.index("] actions-sha-pinned")
    traceback = out.index("Traceback")
    its_gate = out.index("[error] adr-index-complete")
    assert first_gate < traceback < its_gate, out


def test_the_templates_checkout_is_the_pin_our_own_workflows_carry() -> None:
    """Dependabot moves `uses:` pins under `.github/workflows/` and never sees
    `ci-template.yml`, so the checkout the installer writes for every project would
    stay where it was the day it was written — a pin nobody moves (self-audit,
    2026-08-31). Held to ours: when Dependabot bumps ci.yml, this goes red until the
    template follows in the same pull request."""
    root = pathlib.Path(__file__).resolve().parent.parent
    ours = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    template = (root / "src" / "verifiable_gates" / "ci-template.yml").read_text(encoding="utf-8")
    pin = re.compile(r"uses: actions/checkout@[0-9a-f]{40} # v[\d.]+")
    our_pins = set(pin.findall(ours))
    assert len(our_pins) == 1, our_pins
    assert set(pin.findall(template)) == our_pins, (pin.findall(template), our_pins)


@pytest.mark.parametrize(
    ("body", "why"),
    [("not json", "unparsable"), ("[]", "a list, not a manifest"), (None, "not there")],
    ids=["unparsable", "wrong-shape", "missing"],
)
def test_a_manifest_the_doctor_cannot_read_is_a_misuse(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], body: str | None, why: str
) -> None:
    """The installer answers an unreadable manifest with exit 2 (#154); the doctor beside
    it still died of a traceback and exit 1 (round 2, 2026-08-31)."""
    manifest = tmp_path / "overlay.json"
    if body is not None:
        manifest.write_text(body, encoding="utf-8")

    assert gates_doctor.main(["--manifest", str(manifest)]) == 2, why
    assert "cannot read the manifest" in capsys.readouterr().err


def test_a_scanner_whose_body_was_replaced_is_not_intact(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path
) -> None:
    """`--installed` said "the bundle arrived intact" while checking only that each file
    is present and compiles. A scanner whose body had been replaced with `return 0`
    passed that check and then reported its gate as `pass` on a tree that violates it
    (self-audit round 4, 2026-09-01)."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    assert run_doctor(project, "--installed").returncode == 0, "a fresh install is intact"

    scanner = project / "tools" / "checks" / "scan_install_pinning.py"
    body = scanner.read_text(encoding="utf-8")
    scanner.write_text(
        body.replace(
            "def main(root: pathlib.Path) -> int:",
            "def main(root: pathlib.Path) -> int:\n    return 0",
            1,
        ),
        encoding="utf-8",
    )

    done = run_doctor(project, "--installed")
    assert done.returncode == 1
    assert "is not what was installed" in done.stdout + done.stderr


def test_a_file_the_install_wrote_and_is_gone_is_not_intact(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path
) -> None:
    """The other half of the record: present-and-compiles could not see a file removed
    from a bundle whose manifest the remover also edited."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    (project / "tools" / "check_issue_handoff.py").unlink()

    done = run_doctor(project, "--installed")
    assert done.returncode == 1
    assert "was installed and is gone" in done.stdout + done.stderr


def test_the_projects_own_files_are_not_held_to_the_bundle(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path
) -> None:
    """A project owns its registry, its scaffold and its workflow from the moment they
    land — editing them must stay clean, or the check would hold the project to the
    bundle's defaults instead of holding the bundle to what it shipped."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    (project / "gates.yaml").write_text("version: 1\ngates: []\n", encoding="utf-8")
    (project / "scaffold.json").write_text('{"preflight_jobs": ["lint"]}\n', encoding="utf-8")

    assert run_doctor(project, "--installed").returncode == 0


def test_a_bundle_with_no_record_says_so(tmp_path: pathlib.Path, bundle_copy: pathlib.Path) -> None:
    """A bundle installed before the installer recorded what it wrote says that, rather
    than claiming either answer."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    (project / "tools" / "installed.json").unlink()

    done = run_doctor(project, "--installed")
    assert done.returncode == 1
    assert "no tools/installed.json" in done.stdout + done.stderr
    assert gates_doctor.check_installed_record(project) == [
        "no tools/installed.json — this bundle was installed before the installer "
        "recorded what it wrote, so intact cannot be checked; re-run the installer"
    ]


def test_a_record_that_cannot_be_read_says_so(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path
) -> None:
    """And one that is there and unreadable is the third answer, not a green."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    (project / "tools" / "installed.json").write_text("not json", encoding="utf-8")

    done = run_doctor(project, "--installed")
    assert done.returncode == 1
    assert "cannot be read" in done.stdout + done.stderr
    assert "cannot be read" in gates_doctor.check_installed_record(project)[0]
