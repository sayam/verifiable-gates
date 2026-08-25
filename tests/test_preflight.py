"""preflight turns a workflow into a plan, and every step ends up in it.

The value is entirely in the planning: reading the real commands out of the real
workflow is what stops a second, drifting copy of them existing. So the tests are
about the plan, not about running things — running is a thin loop over `bash`.

**The property that matters most is that nothing disappears.** A step that cannot
run locally is skipped *with its reason printed*; a step that vanishes silently
gives exactly the false confidence this tool exists to remove. Every test here
counts the entries against the steps, not just the ones it cares about.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from verifiable_gates import preflight

if TYPE_CHECKING:
    import pathlib

PINNED = "actions/checkout@" + "a" * 40
# A stand-in for `runner.temp`; the value never touches the filesystem here.
LOCAL_TEMP = "/build/tmp"


def a_workflow(**jobs: object) -> dict[str, object]:
    return {"jobs": jobs}


def write(root: pathlib.Path, name: str, text: str) -> None:
    path = root / ".github" / "workflows" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- the plan


def test_every_step_appears_exactly_once() -> None:
    """The whole point: a plan that loses a step lies in the direction of comfort."""
    workflow = a_workflow(
        lint={
            "steps": [
                {"uses": PINNED},
                {"run": "pip install ruff"},
                {"name": "check", "run": "ruff check ."},
                {"run": "echo ${{ secrets.TOKEN }}"},
            ]
        }
    )
    entries = preflight.plan(workflow, ("lint",), "main")
    assert len(entries) == 4, "a step went missing between the workflow and the plan"
    assert sum(1 for e in entries if "skip" in e) == 3
    assert next(e for e in entries if "run" in e)["label"] == "check"


@pytest.mark.parametrize(
    ("step", "needle"),
    [
        ({"uses": PINNED}, "an action"),
        ({"run": "pip install ruff"}, "installs the runner's tools"),
        ({"run": "pipenv sync --dev"}, "arranges an environment"),
        ({"run": "echo ${{ secrets.TOKEN }}"}, "no local value"),
        ({"run": "true", "env": {"K": "${{ secrets.TOKEN }}"}}, "env holds a CI expression"),
    ],
    ids=["action", "pip-install", "env-setup", "expression-in-command", "expression-in-env"],
)
def test_a_step_that_cannot_run_locally_is_skipped_with_a_reason(
    step: dict[str, object], needle: str
) -> None:
    entries = preflight.plan(a_workflow(lint={"steps": [step]}), ("lint",), "main")
    assert "skip" in entries[0], "this step cannot run locally but was planned to run"
    assert needle in entries[0]["skip"], "the reason does not say why"


def test_the_expressions_with_a_local_equivalent_are_substituted() -> None:
    """`base_ref` and `runner.temp` have local answers, so they are not a reason to skip."""
    step = {"run": "diff-cover --compare-branch origin/${{ github.base_ref }} ${{ runner.temp }}/x"}
    entries = preflight.plan(
        a_workflow(lint={"steps": [step]}), ("lint",), "trunk", temp=LOCAL_TEMP
    )
    assert "skip" not in entries[0]
    assert entries[0]["run"] == f"diff-cover --compare-branch origin/trunk {LOCAL_TEMP}/x"


def test_a_steps_env_travels_with_its_command() -> None:
    """CI sets these on purpose; running the command without them asks a different question."""
    step = {"run": "pytest", "env": {"COVERAGE_FILE": "${{ runner.temp }}/.coverage"}}
    entries = preflight.plan(a_workflow(test={"steps": [step]}), ("test",), "main", temp=LOCAL_TEMP)
    assert entries[0]["env"] == {"COVERAGE_FILE": f"{LOCAL_TEMP}/.coverage"}


def test_a_step_with_no_name_is_labelled_by_its_command() -> None:
    entries = preflight.plan(
        a_workflow(lint={"steps": [{"run": "ruff check .\nmore"}]}), ("lint",), "main"
    )
    assert entries[0]["label"] == "ruff check ."


def test_jobs_are_walked_in_the_order_they_were_asked_for() -> None:
    workflow = a_workflow(lint={"steps": [{"run": "a"}]}, test={"steps": [{"run": "b"}]})
    entries = preflight.plan(workflow, ("test", "lint"), "main")
    assert [e["job"] for e in entries] == ["test", "lint"]


# ---------------------------------------------------------------- which jobs


def test_jobs_come_from_every_workflow_file(tmp_path: pathlib.Path) -> None:
    """Job names are unique across files, so splitting a workflow must not hide one."""
    write(tmp_path, "ci.yml", "jobs:\n  lint:\n    steps:\n      - run: a\n")
    write(tmp_path, "extra.yml", "jobs:\n  test:\n    steps:\n      - run: b\n")
    assert set(preflight.jobs_on_disk(tmp_path)) == {"lint", "test"}


def test_the_command_line_beats_the_config(tmp_path: pathlib.Path) -> None:
    (tmp_path / "scaffold.json").write_text(json.dumps({"preflight_jobs": ["x"]}), encoding="utf-8")
    assert preflight.wanted_jobs(tmp_path, ["y"]) == ("y",)


def test_the_config_beats_the_default(tmp_path: pathlib.Path) -> None:
    (tmp_path / "scaffold.json").write_text(json.dumps({"preflight_jobs": ["x"]}), encoding="utf-8")
    assert preflight.wanted_jobs(tmp_path, []) == ("x",)


def test_without_a_config_the_default_applies(tmp_path: pathlib.Path) -> None:
    assert preflight.wanted_jobs(tmp_path, []) == preflight.DEFAULT_JOBS


def test_a_config_without_the_key_falls_back(tmp_path: pathlib.Path) -> None:
    (tmp_path / "scaffold.json").write_text(json.dumps({"src_path": "app"}), encoding="utf-8")
    assert preflight.wanted_jobs(tmp_path, []) == preflight.DEFAULT_JOBS


# ---------------------------------------------------------------- hooks


def test_hooks_that_are_not_installed_are_named(tmp_path: pathlib.Path) -> None:
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    (tmp_path / ".git" / "hooks" / "pre-commit").write_text("pre-commit\n", encoding="utf-8")
    assert preflight.missing_hooks(tmp_path) == ["commit-msg", "pre-push"]


def test_a_hook_file_from_something_else_does_not_count(tmp_path: pathlib.Path) -> None:
    """A file being there is not the same as the tool being installed."""
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    (tmp_path / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    assert "pre-commit" in preflight.missing_hooks(tmp_path)


def test_all_hooks_installed_is_silence(tmp_path: pathlib.Path) -> None:
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True)
    for kind in preflight.HOOK_TYPES:
        (hooks / kind).write_text("pre-commit\n", encoding="utf-8")
    assert preflight.missing_hooks(tmp_path) == []


def test_outside_a_git_checkout_there_is_nothing_to_say(tmp_path: pathlib.Path) -> None:
    assert preflight.missing_hooks(tmp_path) == []


# ---------------------------------------------------------------- end to end


def test_a_clean_run_reports_and_returns_zero(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path, "ci.yml", "jobs:\n  lint:\n    steps:\n      - name: ok\n        run: 'true'\n")
    (tmp_path / "scaffold.json").write_text(
        json.dumps({"preflight_jobs": ["lint"]}), encoding="utf-8"
    )

    assert preflight.main(["--root", str(tmp_path)]) == 0
    assert "1 passed · 0 failed" in capsys.readouterr().out


def test_a_failing_step_is_counted_and_returns_one(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(
        tmp_path,
        "ci.yml",
        "jobs:\n  lint:\n    steps:\n      - name: the failing one\n        run: 'false'\n",
    )

    assert preflight.main(["--root", str(tmp_path), "--only", "lint"]) == 1
    output = capsys.readouterr().out
    assert "XX  [lint] the failing one" in output
    assert "0 passed · 1 failed" in output


def test_a_job_that_does_not_exist_is_refused(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit 2, not 0 — asking for a job nobody has is a misuse, not a clean run."""
    write(tmp_path, "ci.yml", "jobs:\n  lint:\n    steps:\n      - run: 'true'\n")
    assert preflight.main(["--root", str(tmp_path), "--only", "absent"]) == 2
    assert "no job ['absent']" in capsys.readouterr().err


def test_missing_hooks_are_warned_about_but_do_not_fail_the_run(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Someone who skips hooks on purpose has reasons; not knowing is the problem."""
    write(tmp_path, "ci.yml", "jobs:\n  lint:\n    steps:\n      - name: ok\n        run: 'true'\n")
    (tmp_path / ".git" / "hooks").mkdir(parents=True)

    assert preflight.main(["--root", str(tmp_path), "--only", "lint"]) == 0
    assert "hooks not installed" in capsys.readouterr().out


def test_a_skipped_step_is_printed_while_the_rest_still_run(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A skip has to be visible in the output, not merely absent from the failures."""
    write(
        tmp_path,
        "ci.yml",
        "jobs:\n  lint:\n    steps:\n"
        f"      - uses: {PINNED}\n"
        "      - name: ok\n        run: 'true'\n",
    )
    assert preflight.main(["--root", str(tmp_path), "--only", "lint"]) == 0
    output = capsys.readouterr().out
    assert "skipped: an action" in output
    assert "1 passed · 0 failed · 1 skipped with a reason" in output


def test_without_bash_it_refuses_rather_than_guessing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Workflow steps are written to bash's rules; `/bin/sh` would run them differently.

    Silently falling back would make a local run mean something other than the CI
    run it claims to reproduce — the exact confusion this tool exists to remove.
    """
    monkeypatch.setattr("verifiable_gates.preflight.shutil.which", lambda _name: None)
    entries = preflight.plan(a_workflow(lint={"steps": [{"run": "true"}]}), ("lint",), "main")
    with pytest.raises(RuntimeError, match="no bash"):
        preflight.execute(entries, tmp_path)
