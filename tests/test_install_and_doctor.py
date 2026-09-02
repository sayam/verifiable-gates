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
import os
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any

import pytest
import yaml
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


def test_a_configuration_that_cannot_be_read_is_an_error_in_a_sentence(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A `scaffold.json` that is not JSON is refused the way undecodable bytes are: exit 2,
    naming the file and what is wrong with it. Round 3 wrapped the *read* of this file and
    stopped one line short of the parse, so every scan answered a malformed configuration
    with a `JSONDecodeError` traceback and exit 1 — the code that means *findings* — and
    what reached the project was a stack (self-audit round 17, 2026-09-01). The doctor
    caught it as an error either way; a traceback is still not a sentence anyone can act on.
    """
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    capsys.readouterr()
    (project / "scaffold.json").write_text("{bad", encoding="utf-8")

    done = run_doctor(project)
    assert done.returncode == 1
    assert "[found]" not in done.stdout
    assert "[error] no-debug-entrypoint — the scan did not answer (exit 2)" in done.stdout
    assert "scans did not answer, which is no verdict" in done.stdout
    assert "found problems" not in done.stdout
    assert "Traceback" not in done.stderr, "a project reads a stack instead of the reason"
    assert "scaffold.json: not JSON" in done.stderr


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


# ------------------------------------------- an install that did not get to the end
#
# An install that stops partway leaves a tree that is half one bundle and half the one
# before it. Until the installer said so, the record went on describing the previous
# install, and every file the stopped one *had* written came back from the doctor as
# "its contents have changed" — the sentence round 4 wrote to mean *somebody edited the
# bundle*. A tree the installer itself left that way was reported as tampering
# (self-audit round 16, 2026-09-01).


def a_stopped_install(
    project: pathlib.Path, bundle_copy: pathlib.Path
) -> subprocess.CompletedProcess[str]:
    """Install, then upgrade to a changed bundle with one target that cannot be written."""
    assert do_install(project, bundle_copy) == 0
    (bundle_copy / DOCTOR.removeprefix("tools/")).write_text(
        (bundle_copy / DOCTOR.removeprefix("tools/")).read_text(encoding="utf-8")
        + "\n# a second bundle, so the copied files differ from the recorded ones\n",
        encoding="utf-8",
    )
    locked = project / "tools" / "checks" / "scan_install_pinning.py"
    locked.chmod(0o444)
    try:
        assert do_install(project, bundle_copy) == 1
    finally:
        locked.chmod(0o644)
    return run_doctor(project, "--installed")


def test_an_install_that_stopped_partway_says_so_instead_of_accusing_the_files(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The doctor has to name the cause the installer already knew."""
    project = tmp_path / "project"

    done = a_stopped_install(project, bundle_copy)
    capsys.readouterr()

    record = json.loads((project / "tools" / "installed.json").read_text(encoding="utf-8"))
    assert record["finished"] is False, "the installer did not record that it stopped"
    assert done.returncode == 1
    assert "did not finish" in done.stdout, done.stdout
    assert "contents have changed" not in done.stdout, (
        "a tree the installer itself left half-written was reported as tampering"
    )


def test_the_record_of_a_stopped_install_is_a_problem_in_process_too(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same judgement, read straight out of the function a consumer imports."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    capsys.readouterr()
    record = project / "tools" / "installed.json"
    stopped = json.loads(record.read_text(encoding="utf-8")) | {"finished": False}
    record.write_text(json.dumps(stopped), encoding="utf-8")

    problems = gates_doctor.check_installed_record(project)

    assert any("did not finish" in problem for problem in problems), problems


def test_a_finished_install_records_that_it_finished(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The control: without it, recording `false` always would pass the test above."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    capsys.readouterr()

    record = json.loads((project / "tools" / "installed.json").read_text(encoding="utf-8"))
    done = run_doctor(project, "--installed")

    assert record["finished"] is True
    assert done.returncode == 0
    assert "did not finish" not in done.stdout


def test_a_record_from_an_installer_that_did_not_know_the_question_reads_as_finished(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A project that installed before this key existed must not be told its install
    stopped — the doctor reads a record with no `finished` as one that did."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    capsys.readouterr()
    record = project / "tools" / "installed.json"
    older = json.loads(record.read_text(encoding="utf-8"))
    del older["finished"]
    record.write_text(json.dumps(older), encoding="utf-8")

    done = run_doctor(project, "--installed")

    assert done.returncode == 0, done.stdout
    assert "did not finish" not in done.stdout


def test_an_install_that_landed_nothing_leaves_the_record_of_the_one_before_it(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Nothing landed, so nothing changed — and a true account of the install before must
    not be overwritten with an empty one that says it stopped."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    capsys.readouterr()
    before = (project / "tools" / "installed.json").read_text(encoding="utf-8")
    # The first file the installer copies: it stops before anything has landed.
    first = project / DOCTOR
    first.chmod(0o444)
    try:
        assert do_install(project, bundle_copy) == 1
    finally:
        first.chmod(0o644)

    assert (project / "tools" / "installed.json").read_text(encoding="utf-8") == before


def test_an_install_whose_record_cannot_be_written_says_so_rather_than_a_traceback(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every file landed and the record could not be written: round 5's shape, in the one
    writer it had not reached. It ended a complete, correct install in a raw
    `PermissionError` (self-audit round 16, 2026-09-01)."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    capsys.readouterr()
    (project / "tools" / "installed.json").chmod(0o444)

    try:
        with pytest.raises(SystemExit) as refused:
            do_install(project, bundle_copy)
    finally:
        (project / "tools" / "installed.json").chmod(0o644)

    assert refused.value.code == 1
    said = capsys.readouterr().err
    assert "the record of it could not be written" in said, said
    assert "the doctor cannot check this install" in said


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
    assert "scaffold.json: not JSON" in captured.err


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


@pytest.mark.parametrize(
    "body",
    ['{"gates": []}', '{"gates": "scan_x.py"}', '{"gates": null}', "[]", '"overlay"'],
    ids=["a-list", "a-string", "null", "not-an-object", "a-bare-string"],
)
def test_a_manifest_whose_gates_is_not_an_object_is_refused_here_not_later(
    tmp_path: pathlib.Path, body: str
) -> None:
    """The key being present was the whole check, and `scan_entries` calls
    `manifest["gates"].items()` on the next line (self-audit round 18, 2026-09-02)."""
    path = tmp_path / "overlay.json"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ValueError, match="not a manifest"):
        gates_doctor.load_manifest(path)


# A record whose `files` is not the object the installer writes. Round 16's guard was
# written for the exceptions the parse and the subscript raise and stopped one line short
# of `files.items()`, so the question "is this bundle still what arrived?" was answered
# with a raw `AttributeError` (self-audit round 18, 2026-09-02). A corrupt record is not
# hypothetical: round 16 is the round that established a write can stop halfway.

MISSHAPEN_RECORDS = [
    pytest.param('{"files": "tools/gates_doctor.py"}', id="files-is-a-string"),
    pytest.param('{"files": ["tools/gates_doctor.py"]}', id="files-is-a-list"),
    pytest.param('{"files": null}', id="files-is-null"),
    pytest.param('{"files": 7}', id="files-is-a-number"),
    pytest.param('{"files": {"tools/gates_doctor.py": 7}}', id="a-digest-that-is-a-number"),
    pytest.param('{"files": {"tools/gates_doctor.py": ["a"]}}', id="a-digest-that-is-a-list"),
]


@pytest.mark.parametrize("body", MISSHAPEN_RECORDS)
def test_a_record_whose_files_is_not_an_object_is_said_out_loud(
    tmp_path: pathlib.Path, body: str
) -> None:
    """Said, not raised: the doctor's answer for a record it cannot use already exists."""
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "installed.json").write_text(body, encoding="utf-8")

    problems = gates_doctor.check_installed_record(tmp_path)

    assert len(problems) == 1, problems
    assert "installed.json cannot be read" in problems[0]
    assert "not the name-to-digest object" in problems[0]


@pytest.mark.parametrize("body", MISSHAPEN_RECORDS)
def test_an_install_over_a_misshapen_record_names_no_letters_as_files(
    tmp_path: pathlib.Path,
    bundle_copy: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    body: str,
) -> None:
    """Declaring the record's `files` as `dict[str, str]` did not make it one: the value
    comes from `json.loads`, and an annotation on an `Any` is a type the checker believes
    rather than verifies. Over the string that actually arrived, `set(...)` made a set of
    **characters**, and the installer reported single letters as files a previous install
    had left behind (self-audit round 18, 2026-09-02)."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    (project / "tools" / "installed.json").write_text(body, encoding="utf-8")
    capsys.readouterr()

    assert do_install(project, bundle_copy) == 0
    left = [line for line in capsys.readouterr().out.splitlines() if line.startswith("left behind")]
    assert not left, left


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
    said = gates_doctor.check_installed_record(project)
    assert said == [
        (
            "no tools/installed.json — this bundle was installed before the installer "
            "recorded what it wrote, so intact cannot be checked; re-run the installer"
        )
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


def a_bundle_without(bundle: pathlib.Path, gate: str, tmp_path: pathlib.Path) -> pathlib.Path:
    """A copy of the bundle that no longer ships one gate's scanner — a newer version."""
    newer = tmp_path / "newer-bundle"
    shutil.copytree(bundle, newer)
    manifest = json.loads((newer / "overlay.json").read_text(encoding="utf-8"))
    script = manifest["gates"].pop(gate)["script"]
    manifest["ship"] = [name for name in manifest["ship"] if name != script]
    (newer / script).unlink()
    (newer / "overlay.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return newer


def test_an_upgrade_says_what_it_stopped_shipping(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A bundle that drops or renames a scanner left the old file in the project's
    repository forever: nothing names it, the doctor never runs it, and `--installed`
    said "every scan runs" because it checks only what the current record names. The
    project could not tell dead code from live code in a directory this bundle owns
    (self-audit round 9, 2026-09-01)."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    newer = a_bundle_without(bundle_copy, "adr-index-complete", tmp_path)
    capsys.readouterr()

    assert install_module.main([str(project), "--manifest", str(newer / "overlay.json")]) == 0

    printed = capsys.readouterr().out
    assert "left behind: tools/checks/scan_adr_index.py" in printed
    assert "delete it or keep it on purpose" in printed
    assert (project / "tools" / "checks" / "scan_adr_index.py").is_file(), (
        "a file in somebody else's repository is theirs to remove — say it, do not delete it"
    )


def test_a_first_install_and_a_reinstall_leave_nothing_behind(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The direction that must stay quiet: nothing was dropped, so nothing is said."""
    project = tmp_path / "project"

    assert do_install(project, bundle_copy) == 0
    assert "left behind" not in capsys.readouterr().out
    assert do_install(project, bundle_copy) == 0
    assert "left behind" not in capsys.readouterr().out


def test_a_record_it_cannot_read_says_nothing_about_leftovers(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The record is this bundle's own note to itself. One it cannot read is not a reason
    to accuse a project of leftovers it may not have — the install proceeds and writes a
    fresh record, and the doctor's `--installed` says separately that it could not be
    read (round 9, 2026-09-01)."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    (project / "tools" / "installed.json").write_text("not json", encoding="utf-8")
    capsys.readouterr()

    assert do_install(project, bundle_copy) == 0

    printed = capsys.readouterr().out
    assert "left behind" not in printed
    assert json.loads((project / "tools" / "installed.json").read_text(encoding="utf-8"))[
        "files"
    ], "the install rewrites the record it could not read"


def test_every_na_line_says_what_the_scan_looked_for(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The scanners were changed so that NA **names what it looked for** — "no docs/adr",
    "no Python under app" — because a rule the tool cannot check must not look like a rule
    it checked. The doctor, which is the thing an operator actually runs, printed the bare
    word and threw the reason away: five different answers read identically, and nobody
    could tell "there is no such directory" from "a directory this scanner cannot read"
    (self-audit round 14, 2026-09-01)."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    capsys.readouterr()

    done = run_doctor(project)
    assert done.returncode == 0, done.stdout + done.stderr
    na = [line for line in done.stdout.splitlines() if line.startswith("[   NA]")]
    assert na, "an empty project should be all not-applicable"
    for line in na:
        assert " — " in line, f"this NA gives no reason: {line!r}"
    reasons = {line.split(" — ", 1)[1] for line in na}
    assert len(reasons) > 1, "every NA gave the same reason — the scans' own words are gone"


# ---------------------------------------------------------------- the rules, read off the bundle


def test_the_doctor_prints_every_rule_a_scanner_here_decides(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--rules` is what a project's agent instructions point at instead of carrying a copy:
    read off the installed manifest at run time, so an upgrade cannot leave an agent on
    yesterday's rule, and only the rules a scanner here decides, so no instruction stands
    without a gate behind it (self-audit, 2026-09-02)."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    capsys.readouterr()
    manifest = json.loads((project / "tools" / "overlay.json").read_text(encoding="utf-8"))
    scans = {gid: e for gid, e in manifest["gates"].items() if e.get("kind") == "scan"}

    assert (
        gates_doctor.main(
            [str(project), "--manifest", str(project / "tools" / "overlay.json"), "--rules"]
        )
        == 0
    )
    out = capsys.readouterr().out

    assert f"decides for this project: {len(scans)}," in out
    for gid, entry in scans.items():
        assert f"{gid} [{entry['layer']}]" in out, f"{gid} is missing or unlabelled"
        assert entry["born_from"] in out, f"{gid} lost its origin"
        assert f"decided by: tools/{entry['script']}" in out, f"{gid} does not name its scanner"
    assert "does not switch a scanner off" in out, "the one sentence of guidance is missing"
    assert "only these are decided here" in out, "what the bundle cannot decide is not said"


def test_the_rules_name_the_suite_gates_a_manifest_carries(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A manifest that ships `suite` gates says how many, and whose they are to decide."""
    bundle = tmp_path / "tools"
    bundle.mkdir()
    (bundle / "overlay.json").write_text(
        json.dumps(
            {
                "bundle": "x",
                "ship": [],
                "gates": {
                    "a-rule": {"kind": "scan", "script": "checks/scan_a.py", "title": "A"},
                    "b-rule": {"kind": "suite", "title": "B"},
                    "c-rule": {"kind": "suite", "title": "C"},
                },
            }
        ),
        encoding="utf-8",
    )

    assert (
        gates_doctor.main([str(tmp_path), "--manifest", str(bundle / "overlay.json"), "--rules"])
        == 0
    )
    out = capsys.readouterr().out
    assert "2 more rules in tools/overlay.json are of kind `suite`" in out
    assert "b-rule" not in out, "a suite gate is counted, not listed as if a scanner decided it"


def test_a_rule_whose_origin_the_manifest_lost_says_so(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A manifest from before origins travelled with titles still answers — with the
    missing field named, not with a traceback and not with an invented sentence."""
    bundle = tmp_path / "tools"
    bundle.mkdir()
    (bundle / "overlay.json").write_text(
        json.dumps(
            {
                "bundle": "x",
                "ship": [],
                "gates": {"a-rule": {"kind": "scan", "script": "checks/scan_a.py", "title": "A"}},
            }
        ),
        encoding="utf-8",
    )

    assert (
        gates_doctor.main([str(tmp_path), "--manifest", str(bundle / "overlay.json"), "--rules"])
        == 0
    )
    out = capsys.readouterr().out
    assert "a-rule [baseline]" in out
    assert "(origin not recorded in this manifest)" in out


def test_the_doctor_refuses_two_questions_at_once(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path
) -> None:
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    manifest = str(project / "tools" / "overlay.json")

    with pytest.raises(SystemExit) as refused:
        gates_doctor.main([str(project), "--manifest", manifest, "--installed", "--rules"])
    assert refused.value.code == 2


def test_the_installer_points_the_agents_at_the_rules(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The adoption cost is one line in the project's own instruction file, and the
    installer says which line — it never writes into that file itself."""
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    out = capsys.readouterr().out

    assert "gates_doctor.py --rules" in out
    assert not (project / "AGENTS.md").exists(), "the installer must not write the project's file"


# ---------------------------------------------------------------- SARIF, a format


def _sarif_after(project: pathlib.Path, *args: str) -> tuple[int, dict[str, Any], str]:
    out = project / "gates.sarif"
    done = run_doctor(project, "--sarif", str(out), *args)
    return done.returncode, json.loads(out.read_text(encoding="utf-8")), done.stdout


def _plant(project: pathlib.Path, scanner: str, body: str) -> None:
    (project / "tools" / "checks" / scanner).write_text(body, encoding="utf-8")


def test_a_finding_with_a_line_is_a_located_result_and_the_rules_carry_their_incident(
    installed: pathlib.Path,
) -> None:
    """The reader that speaks SARIF gets the finding where the scanner saw it, and the
    rule's incident beside it — a rule with no `born_from` is a rule nobody can retire."""
    (installed / "x.yml").write_text("uses: actions/checkout@v4\n", encoding="utf-8")
    _plant(
        installed,
        "scan_workflow_pinning.py",
        "print('actions-sha-pinned: x.yml:1 actions/checkout@v4 is a floating tag')\n"
        "raise SystemExit(1)\n",
    )
    code, log, report = _sarif_after(installed)
    assert code == 1, "the exit code is the report's, not the format's"
    assert "[found] actions-sha-pinned" in report, "the text report still prints"
    assert log["version"] == "2.1.0"
    assert log["$schema"] == gates_doctor.SARIF_SCHEMA
    (run,) = log["runs"]
    (result,) = run["results"]
    assert result["ruleId"] == "actions-sha-pinned"
    assert result["level"] == "error"
    assert result["message"]["text"] == "x.yml:1 actions/checkout@v4 is a floating tag"
    (location,) = result["locations"]
    assert location["physicalLocation"]["artifactLocation"] == {
        "uri": "x.yml",
        "uriBaseId": "%SRCROOT%",
    }
    assert location["physicalLocation"]["region"] == {"startLine": 1}
    assert run["originalUriBaseIds"]["%SRCROOT%"]["uri"] == installed.resolve().as_uri() + "/"
    driver = run["tool"]["driver"]
    assert driver["name"] == "verifiable-gates"
    assert (
        driver["version"]
        == json.loads((installed / "tools" / "installed.json").read_text(encoding="utf-8"))[
            "version"
        ]
    )
    manifest = json.loads((installed / "tools" / "overlay.json").read_text(encoding="utf-8"))
    scans = {gid for gid, _s in gates_doctor.scan_entries(manifest)}
    assert {rule["id"] for rule in driver["rules"]} == scans, "every scan gate is a rule"
    for rule in driver["rules"]:
        gate = manifest["gates"][rule["id"]]
        assert rule["shortDescription"]["text"] == gate["title"]
        assert rule["help"]["text"] == gate["born_from"], "the incident travels with the rule"
        assert rule["properties"]["layer"] == gate["layer"]


def test_a_finding_that_names_no_file_under_the_root_is_a_result_with_no_location(
    installed: pathlib.Path,
) -> None:
    """A key from scaffold.json, a sentence, a path outside: a message, never an
    annotation on a file the reader would be sent to and could not open."""
    _plant(
        installed,
        "scan_adr_index.py",
        "print('adr-index-complete: records exist but there is no README.md index')\n"
        "print('adr-index-complete: /etc/hostname:1 leads outside the project')\n"
        "print('adr-index-complete: adr_path: is not one path')\n"
        "raise SystemExit(1)\n",
    )
    code, log, _ = _sarif_after(installed)
    assert code == 1
    results = log["runs"][0]["results"]
    assert [r["message"]["text"] for r in results] == [
        "records exist but there is no README.md index",
        "/etc/hostname:1 leads outside the project",
        "adr_path: is not one path",
    ]
    assert all("locations" not in r for r in results), "a location nobody can open"


def test_an_na_is_a_note_on_the_invocation_and_never_a_result(installed: pathlib.Path) -> None:
    """The third answer survives the translation: a reader counting results sees none,
    and a reader of the invocation sees why."""
    code, log, _ = _sarif_after(installed)
    assert code == 0, "a fresh install is clean or NA everywhere"
    run = log["runs"][0]
    assert run["results"] == []
    (invocation,) = run["invocations"]
    assert invocation["executionSuccessful"] is True, "NA is not a failure to run"
    notes = invocation["toolExecutionNotifications"]
    assert notes, "eight NA gates on a fresh install, and not one note"
    assert {n["level"] for n in notes} == {"note"}
    by_rule = {n["associatedRule"]["id"]: n["message"]["text"] for n in notes}
    assert by_rule["delete-means-soft-delete"].startswith("no app"), by_rule


def test_a_scan_that_did_not_answer_marks_the_invocation_unsuccessful(
    installed: pathlib.Path,
) -> None:
    """Exit 2, a crash, a timeout: an error notification, no result, and the run says
    it did not succeed — a clean-looking log over a scan that could not look is the
    sentence the manifest forbids."""
    _plant(
        installed,
        "scan_workflow_pinning.py",
        "import sys\nprint('cannot read the tree: x: Permission denied', file=sys.stderr)\n"
        "raise SystemExit(2)\n",
    )
    code, log, _ = _sarif_after(installed)
    assert code == 1, "the doctor's own answer for a scan that did not answer"
    run = log["runs"][0]
    assert not [r for r in run["results"] if r["ruleId"] == "actions-sha-pinned"]
    (invocation,) = run["invocations"]
    assert invocation["executionSuccessful"] is False
    (error,) = [n for n in invocation["toolExecutionNotifications"] if n["level"] == "error"]
    assert error["associatedRule"] == {"id": "actions-sha-pinned"}
    assert "did not answer (exit 2)" in error["message"]["text"]
    assert "Permission denied" in error["message"]["text"], "the scan's own words travel"


def test_sarif_is_a_run_of_the_scans_and_refuses_the_other_two_questions(
    installed: pathlib.Path,
) -> None:
    for other in ("--installed", "--rules"):
        done = run_doctor(installed, "--sarif", str(installed / "x.sarif"), other)
        assert done.returncode == 2, other
        assert "--sarif describes a run of the scans" in done.stderr
        assert not (installed / "x.sarif").exists(), "nothing was written on a misuse"


def test_a_sarif_that_cannot_be_written_is_a_sentence_after_the_report(
    installed: pathlib.Path,
) -> None:
    """The verdict stood; the artefact asked for did not arrive — exit 2, not a
    traceback, and not the verdict's own code, which would say the file is there."""
    done = run_doctor(installed, "--sarif", str(installed / "no-such-dir" / "gates.sarif"))
    assert done.returncode == 2
    assert "[   NA] delete-means-soft-delete" in done.stdout, "the report printed first"
    assert "cannot write the SARIF" in done.stderr
    assert "the report above stands" in done.stderr
    assert "Traceback" not in done.stderr


def test_the_sarif_carries_what_code_scanning_requires(installed: pathlib.Path) -> None:
    """The fields GitHub's upload rejects a file without, named so a reader of this
    test knows which readers were in mind; the full schema is validated outside the
    suite, because the suite is held not to use the network."""
    _plant(
        installed,
        "scan_write_discipline.py",
        "print('delete-means-soft-delete: app/a.py:3 session.delete(x)')\nraise SystemExit(1)\n",
    )
    (installed / "app").mkdir()
    (installed / "app" / "a.py").write_text("\n\nsession.delete(x)\n", encoding="utf-8")
    _, log, _ = _sarif_after(installed)
    assert set(log) >= {"$schema", "version", "runs"}
    run = log["runs"][0]
    assert set(run) >= {"tool", "results", "invocations"}
    assert set(run["tool"]["driver"]) >= {"name", "rules", "informationUri"}
    (result,) = run["results"]
    assert set(result) >= {"ruleId", "level", "message", "locations"}
    assert result["locations"][0]["physicalLocation"]["region"] == {"startLine": 3}
    assert all(
        isinstance(rule["id"], str) and rule["id"] for rule in run["tool"]["driver"]["rules"]
    )
    assert run["invocations"][0]["executionSuccessful"] is True


# The same roads in-process, so coverage sees them; the subprocess tests above are the
# ones that prove the file as it ships.


def _sarif_in_process(project: pathlib.Path, *args: str) -> tuple[int, dict[str, Any]]:
    manifest = str(project / "tools" / "overlay.json")
    out = project / "in-process.sarif"
    code = gates_doctor.main([str(project), "--manifest", manifest, "--sarif", str(out), *args])
    return code, json.loads(out.read_text(encoding="utf-8"))


def test_in_process_a_located_and_an_unlocated_finding_share_one_log(
    installed: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (installed / "x.yml").write_text("uses: actions/checkout@v4\n", encoding="utf-8")
    _plant(
        installed,
        "scan_workflow_pinning.py",
        "print('actions-sha-pinned: x.yml:1 floating tag')\n"
        "print('actions-sha-pinned: a sentence with no file in it')\n"
        "print('actions-sha-pinned: x.yml: the whole file, no line')\n"
        "print('actions-sha-pinned: :: nothing a path could be read from')\n"
        "raise SystemExit(1)\n",
    )
    code, log = _sarif_in_process(installed)
    capsys.readouterr()
    assert code == 1
    located, plain, whole, odd = log["runs"][0]["results"]
    assert located["locations"][0]["physicalLocation"]["region"] == {"startLine": 1}
    assert "locations" not in plain
    assert "region" not in whole["locations"][0]["physicalLocation"], "no line, no region"
    assert whole["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "x.yml"
    assert "locations" not in odd, "a head no path can be read from is a message only"


def test_a_rule_without_an_incident_or_a_layer_is_still_a_rule(tmp_path: pathlib.Path) -> None:
    """A manifest from before the overlay carried `born_from` and `layer` (#219) still
    renders — the rule is its id and title, and the optional fields are absent, not
    invented."""
    manifest = {"gates": {"bare": {"kind": "scan", "script": "checks/x.py", "title": "t"}}}
    log = gates_doctor.sarif_log(tmp_path, manifest, [])
    (rule,) = log["runs"][0]["tool"]["driver"]["rules"]
    assert rule == {"id": "bare", "shortDescription": {"text": "t"}}


def test_in_process_a_record_with_no_version_leaves_the_driver_without_one(
    installed: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A version the installer did not record is not guessed at — the field is absent."""
    (installed / "tools" / "installed.json").write_text("[]", encoding="utf-8")
    code, log = _sarif_in_process(installed)
    capsys.readouterr()
    assert code == 0
    assert "version" not in log["runs"][0]["tool"]["driver"]
    (installed / "tools" / "installed.json").unlink()
    code, log = _sarif_in_process(installed)
    capsys.readouterr()
    assert "version" not in log["runs"][0]["tool"]["driver"]


def test_in_process_a_scan_that_hangs_is_an_error_notification(
    installed: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gates_doctor, "SCAN_TIMEOUT", 1)
    _plant(installed, "scan_workflow_pinning.py", "import time\ntime.sleep(30)\n")
    code, log = _sarif_in_process(installed)
    capsys.readouterr()
    assert code == 1
    (invocation,) = log["runs"][0]["invocations"]
    assert invocation["executionSuccessful"] is False
    (error,) = [n for n in invocation["toolExecutionNotifications"] if n["level"] == "error"]
    assert "timed out after 1s" in error["message"]["text"]


def test_in_process_the_misuse_and_the_unwritable_file_are_exit_two(
    installed: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = str(installed / "tools" / "overlay.json")
    with pytest.raises(SystemExit) as stopped:
        gates_doctor.main([str(installed), "--manifest", manifest, "--sarif", "x", "--rules"])
    assert stopped.value.code == 2
    capsys.readouterr()
    nowhere = installed / "no-such-dir" / "gates.sarif"
    code = gates_doctor.main([str(installed), "--manifest", manifest, "--sarif", str(nowhere)])
    assert code == 2
    assert "cannot write the SARIF" in capsys.readouterr().err


# ---------------------------------------------------------------- the two front doors
#
# `action.yml` and `.pre-commit-hooks.yaml` are how a project that installed the bundle
# runs it from CI and from a commit hook without writing the line itself. Both run what
# the project installed under tools/, never a copy carried by the action or the hook
# repository — a `rev` or a SHA bump must not change what the project is held to.

ROOT_OF_REPO = pathlib.Path(__file__).resolve().parent.parent
ACTION = ROOT_OF_REPO / "action.yml"
HOOKS = ROOT_OF_REPO / ".pre-commit-hooks.yaml"


def _bash(script: str, cwd: pathlib.Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """A block lifted out of the action or a hook entry, run as the runner would."""
    return subprocess.run(  # noqa: S603 — a block from this repository's own action, on fixed strings
        ["bash", "-c", script],  # noqa: S607 — bash from PATH, as the runner finds it
        cwd=cwd,
        env={"PATH": os.environ["PATH"], **env},
        capture_output=True,
        text=True,
        check=False,
    )


def _action_step() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
    (step,) = loaded["runs"]["steps"]
    typed: dict[str, Any] = step
    return typed


def test_the_action_is_a_composite_of_run_steps_with_nothing_inside_it_to_pin() -> None:
    """An action that used another action would need pinning inside — and would be the
    one thing a consumer's actions-sha-pinned scan cannot see."""
    loaded = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
    assert loaded["runs"]["using"] == "composite"
    for step in loaded["runs"]["steps"]:
        assert "run" in step, step
        assert "uses" not in step, "an action inside the action is one nobody can pin"
        assert step["shell"] == "bash"
    assert set(loaded["inputs"]) == {"root", "sarif"}
    assert loaded["inputs"]["root"]["default"] == "."
    step = _action_step()
    assert set(step["env"]) == {"ROOT", "SARIF"}, "inputs reach the shell as variables"
    assert "${{" not in step["run"], "no expression inside the shell — an injection road"
    assert "tools/gates_doctor.py" in step["run"], "it runs the doctor the project installed"


def test_the_action_runs_the_doctor_the_project_installed(installed: pathlib.Path) -> None:
    run = _action_step()["run"]
    clean = _bash(run, installed, {"ROOT": str(installed), "SARIF": ""})
    assert clean.returncode == 0, clean.stderr
    assert "[   NA] delete-means-soft-delete" in clean.stdout, "the installed doctor spoke"

    _plant(
        installed,
        "scan_workflow_pinning.py",
        "print('actions-sha-pinned: x.yml:1 floating tag')\nraise SystemExit(1)\n",
    )
    found = _bash(run, installed, {"ROOT": str(installed), "SARIF": ""})
    assert found.returncode == 1, "the action fails the job on a finding"
    assert "[found] actions-sha-pinned" in found.stdout

    out = installed / "gates.sarif"
    with_sarif = _bash(run, installed, {"ROOT": str(installed), "SARIF": str(out)})
    assert with_sarif.returncode == 1
    log = json.loads(out.read_text(encoding="utf-8"))
    assert log["runs"][0]["results"][0]["ruleId"] == "actions-sha-pinned"


def test_the_action_refuses_a_tree_with_no_bundle_in_a_sentence(tmp_path: pathlib.Path) -> None:
    """Running a doctor of its own would judge the project by rules it never installed."""
    empty = tmp_path / "nothing-installed"
    empty.mkdir()
    done = _bash(_action_step()["run"], empty, {"ROOT": str(empty), "SARIF": ""})
    assert done.returncode == 2
    assert "no bundle installed under" in done.stderr
    assert "python -m verifiable_gates.install" in done.stderr, "it says what to do"
    assert "Traceback" not in done.stderr


def _hooks() -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = yaml.safe_load(HOOKS.read_text(encoding="utf-8"))
    return loaded


def test_the_hooks_name_the_doctor_and_every_installed_scan_and_nothing_else() -> None:
    """One hook per scan gate, by the rule's id, plus the doctor — held to the manifest
    both ways, so a scanner added or renamed is red here until the hook follows."""
    manifest = json.loads(
        (ROOT_OF_REPO / "src" / "verifiable_gates" / "overlay.json").read_text(encoding="utf-8")
    )
    scans = dict(gates_doctor.scan_entries(manifest))
    hooks = {hook["id"]: hook for hook in _hooks()}
    assert set(hooks) == {"gates-doctor", *scans}, "a hook with no scan, or a scan with no hook"
    assert "tools/gates_doctor.py" in hooks["gates-doctor"]["entry"]
    for gid, script in scans.items():
        assert f"tools/{script} " in hooks[gid]["entry"], f"{gid}: the entry runs another script"
    for hook in hooks.values():
        assert hook["language"] == "system", (
            f"{hook['id']}: a copy from this checkout, not the project's"
        )
        assert hook["pass_filenames"] is False, f"{hook['id']}: a scanner takes a root, not files"
        assert hook["always_run"] is True, f"{hook['id']}: a scan skipped is a scan not run"


def test_a_hook_entry_runs_the_scanner_the_project_installed(installed: pathlib.Path) -> None:
    hooks = {hook["id"]: hook for hook in _hooks()}
    assert _bash(hooks["gates-doctor"]["entry"], installed, {}).returncode == 0
    assert _bash(hooks["actions-sha-pinned"]["entry"], installed, {}).returncode == 0
    _plant(
        installed,
        "scan_workflow_pinning.py",
        "print('actions-sha-pinned: x.yml:1 floating tag')\nraise SystemExit(1)\n",
    )
    assert _bash(hooks["actions-sha-pinned"]["entry"], installed, {}).returncode == 1
    assert _bash(hooks["gates-doctor"]["entry"], installed, {}).returncode == 1
    nothing = installed.parent / "nothing-installed"
    nothing.mkdir()
    assert _bash(hooks["actions-sha-pinned"]["entry"], nothing, {}).returncode != 0, (
        "a hook over a tree with no bundle must not pass"
    )
