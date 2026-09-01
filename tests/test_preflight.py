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
import socket
import unittest.mock
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


# ------------------------------------------------- services CI has and you do not


def a_job_with_redis(env: dict[str, str], published: str = "6379:6379") -> dict[str, object]:
    """A job shaped like the one that found this: a service container plus a suite."""
    return {
        "services": {"redis": {"image": "redis:7", "ports": [published]}},
        "steps": [{"name": "pytest", "run": "pytest -q", "env": env}],
    }


def nothing_listens(_port: int) -> bool:
    """A machine with no service containers running — the ordinary developer's machine."""
    return False


def everything_listens(_port: int) -> bool:
    """The developer who started the service, so preflight owes them full fidelity."""
    return True


def test_env_naming_an_absent_service_is_withheld_not_the_whole_step() -> None:
    """The failure this exists for: CI's address for a container nobody started here.

    Skipping the step instead would throw away a whole suite to protect the two
    tests that need the service — the gap preflight exists to close.
    """
    workflow = a_workflow(test=a_job_with_redis({"TEST_REDIS_URL": "redis://127.0.0.1:6379/0"}))
    entries = preflight.plan(workflow, ("test",), "main", probe=nothing_listens)

    assert "skip" not in entries[0], "the suite must still run; only the address is withheld"
    assert entries[0]["env"] == {}, "the address points at nothing and was passed on anyway"
    assert "TEST_REDIS_URL" in entries[0]["reduced"], "what was withheld has to be named"
    assert "redis" in entries[0]["reduced"], "the reason has to name the service"


def test_a_service_running_locally_is_used_exactly_as_ci_uses_it() -> None:
    """The other direction — start redis yourself and preflight must not degrade anything."""
    address = {"TEST_REDIS_URL": "redis://127.0.0.1:6379/0"}
    workflow = a_workflow(test=a_job_with_redis(address))
    entries = preflight.plan(workflow, ("test",), "main", probe=everything_listens)

    assert entries[0]["env"] == address, "the service is up, so the step must run as CI runs it"
    assert "reduced" not in entries[0], "nothing was withheld, so nothing was reduced"


def test_env_that_has_nothing_to_do_with_the_service_still_travels() -> None:
    """Withholding is per variable. A step's other env is why `env:` is honoured at all."""
    job = a_job_with_redis({"TEST_REDIS_URL": "redis://127.0.0.1:6379/0", "COVERAGE_FILE": "/t/c"})
    entries = preflight.plan(a_workflow(test=job), ("test",), "main", probe=nothing_listens)

    assert entries[0]["env"] == {"COVERAGE_FILE": "/t/c"}


def test_a_port_inside_a_longer_number_is_not_a_match() -> None:
    """`:63790` is not `:6379`, and withholding an unrelated address would be silent damage."""
    job = a_job_with_redis({"OTHER_URL": "redis://127.0.0.1:63790/0"})
    entries = preflight.plan(a_workflow(test=job), ("test",), "main", probe=nothing_listens)

    assert entries[0]["env"] == {"OTHER_URL": "redis://127.0.0.1:63790/0"}
    assert "reduced" not in entries[0]


def test_a_service_with_no_published_port_is_left_alone() -> None:
    """Reachable in CI by service name on the runner's network — no local equivalent at all."""
    job = {
        "services": {"redis": {"image": "redis:7"}},
        "steps": [{"run": "pytest", "env": {"TEST_REDIS_URL": "redis://redis:6379/0"}}],
    }
    entries = preflight.plan(a_workflow(test=job), ("test",), "main", probe=nothing_listens)

    assert entries[0]["env"] == {"TEST_REDIS_URL": "redis://redis:6379/0"}
    assert "reduced" not in entries[0]


def test_a_job_with_no_services_never_asks_the_network() -> None:
    """The common case must not pay for this, and must not depend on a probe at all."""

    def refuse(_port: int) -> bool:
        raise AssertionError("a job without services has no port to probe")

    entries = preflight.plan(
        a_workflow(lint={"steps": [{"run": "ruff check ."}]}), ("lint",), "main", probe=refuse
    )
    assert entries[0]["run"] == "ruff check ."


@pytest.mark.parametrize(
    ("published", "expected"),
    [
        # The asymmetric one carries the whole claim: `16379:6379` publishes 16379
        # on the host and CI's env names *that* side. With `6379:6379` both halves
        # are the same string, so it proves nothing about which one is read.
        ("16379:6379", {16379: "redis"}),
        ("6379:6379", {6379: "redis"}),
        ("6379", {6379: "redis"}),
        (5432, {5432: "redis"}),
    ],
    ids=["host-differs-from-container", "mapped", "string", "integer"],
)
def test_the_published_host_port_is_read_however_it_is_written(
    published: object, expected: dict[int, str]
) -> None:
    job = {"services": {"redis": {"ports": [published]}}}
    assert preflight.host_ports(job) == expected


def test_a_port_that_is_not_a_number_is_ignored_rather_than_crashing() -> None:
    """A `${{ }}` port would otherwise take the whole run down over a service."""
    job = {"services": {"redis": {"ports": ["${{ env.PORT }}:6379"]}}}
    assert preflight.host_ports(job) == {}


def test_a_service_declared_with_nothing_under_it_is_not_a_crash() -> None:
    """`redis:` with an empty body is valid YAML and parses to None."""
    assert preflight.host_ports({"services": {"redis": None}}) == {}


def test_the_probe_reports_a_port_that_nobody_is_serving() -> None:
    """The real probe, not a stub — a closed port is the whole basis of the decision."""
    with socket.socket() as taken:
        taken.bind((preflight.PROBE_HOST, 0))
        port = taken.getsockname()[1]
    assert preflight.listening(port) is False


def test_the_probe_finds_a_port_that_is_being_served() -> None:
    """Proved against a real listener, so the two directions cannot both be one bug."""
    with socket.socket() as server:
        server.bind((preflight.PROBE_HOST, 0))
        server.listen(1)
        assert preflight.listening(server.getsockname()[1]) is True


def test_a_reduced_step_is_reported_apart_from_a_clean_pass(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A run missing what CI provides must not read like a run that had everything."""
    write(
        tmp_path,
        "ci.yml",
        "jobs:\n"
        "  test:\n"
        "    services:\n"
        "      redis:\n"
        "        ports: ['6379:6379']\n"
        "    steps:\n"
        "      - name: suite\n"
        "        run: 'true'\n"
        "        env:\n"
        "          TEST_REDIS_URL: redis://127.0.0.1:6379/0\n",
    )

    with unittest.mock.patch.object(preflight, "listening", return_value=False):
        assert preflight.main(["--root", str(tmp_path), "--only", "test"]) == 0

    output = capsys.readouterr().out
    assert "~  [test] suite" in output, "a reduced step must not print as a plain pass"
    assert "TEST_REDIS_URL" in output, "the developer has to be told what was missing"
    assert "1 ran without a service CI provides" in output, "the summary hides it otherwise"


def test_an_ordinary_run_says_nothing_about_services(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The counter only appears when it has something to say — noise every run is ignored noise."""
    write(tmp_path, "ci.yml", "jobs:\n  lint:\n    steps:\n      - name: ok\n        run: 'true'\n")

    assert preflight.main(["--root", str(tmp_path), "--only", "lint"]) == 0
    assert "ran without a service" not in capsys.readouterr().out


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


# ---------------------------------------------------------------- what a step is lent

SHELL = {
    "PATH": "/usr/bin",
    "HOME": "/home/dev",
    "LC_ALL": "C.UTF-8",
    "GH_TOKEN": "gho_secret",
    "AWS_SECRET_ACCESS_KEY": "aws_secret",
}


def test_a_step_gets_the_baseline_and_none_of_the_shells_secrets() -> None:
    """`os.environ` whole used to travel into every `run:` line read from a workflow.

    An outside audit (2026-08-29) read that as: any workflow file under `--root`
    is a shell with the developer's tokens in it. The baseline is what a tool
    needs to start; a secret the step never names has no business being there.
    """
    env, borrowed = preflight.environment("ruff check .", {}, SHELL)

    assert env == {"PATH": "/usr/bin", "HOME": "/home/dev", "LC_ALL": "C.UTF-8"}
    assert borrowed == []


@pytest.mark.parametrize("command", ["gh api /x --token $GH_TOKEN", "echo ${GH_TOKEN}"])
def test_a_variable_the_step_names_is_lent_and_said_so(command: str) -> None:
    env, borrowed = preflight.environment(command, {}, SHELL)

    assert env["GH_TOKEN"] == SHELL["GH_TOKEN"]
    assert "AWS_SECRET_ACCESS_KEY" not in env, "naming one does not open the rest"
    assert borrowed == ["GH_TOKEN"], "a borrowed secret must be reported, never silent"


def test_a_name_in_the_steps_env_values_counts_as_naming_it() -> None:
    env, borrowed = preflight.environment("pytest", {"TOKEN": "$GH_TOKEN"}, SHELL)

    assert env["GH_TOKEN"] == SHELL["GH_TOKEN"]
    assert borrowed == ["GH_TOKEN"]


def test_a_name_the_shell_does_not_have_is_not_invented() -> None:
    """The step sees it unset, exactly as CI would without that secret."""
    env, borrowed = preflight.environment("echo $NOT_SET", {}, SHELL)

    assert "NOT_SET" not in env
    assert borrowed == []


def test_the_workflows_own_env_wins_and_is_not_reported_as_borrowed() -> None:
    env, borrowed = preflight.environment("echo $HOME $GH_TOKEN", {"GH_TOKEN": "from-ci"}, SHELL)

    assert env["GH_TOKEN"] == "from-ci"  # noqa: S105 — the workflow's own value, not a secret
    assert borrowed == [], "declared env is the workflow's, not something lent"


def test_the_shell_is_read_when_no_base_is_given(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PREFLIGHT_PROBE_VAR", "seen")

    env, _borrowed = preflight.environment("echo $PREFLIGHT_PROBE_VAR", {})

    assert env["PREFLIGHT_PROBE_VAR"] == "seen"


def test_execute_runs_a_step_in_the_narrowed_environment(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real bash, the real plan: a secret is absent unless the step names it."""
    monkeypatch.setenv("PREFLIGHT_SECRET", "s3cret")
    entries = [
        # The first step must not *name* the variable, or it would be lent by design;
        # it asks the environment as a whole whether anything by that prefix is there.
        {"job": "j", "label": "unnamed", "run": "! env | grep -q ^PREFLIGHT_SEC", "env": {}},
        {"job": "j", "label": "named", "run": 'test "$PREFLIGHT_SECRET" = s3cret', "env": {}},
    ]

    assert preflight.execute(entries, tmp_path) == 0
    out = capsys.readouterr().out
    assert "lent from your shell" in out
    assert "PREFLIGHT_SECRET" in out


@pytest.mark.parametrize(
    ("name", "content", "says"),
    [
        ("ci.yml", b"jobs:\n  lint:\n    name: caf\xe9\n", "not UTF-8"),
        ("ci.yml", b"jobs:\n  lint:\n   - [unclosed\n", "not YAML this reader can parse"),
    ],
    ids=["not-utf-8", "not-yaml"],
)
def test_a_workflow_this_walk_cannot_read_is_a_misuse_not_a_failed_job(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    name: str,
    content: bytes,
    says: str,
) -> None:
    """A workflow a Windows editor saved as cp1252 ended the walk with a raw
    `UnicodeDecodeError` and exit 1 — the code that means *a job failed*, sending the
    developer to look for a broken job (self-audit round 12, 2026-09-01). This reader
    already answers 2 for a job it cannot find; a file it cannot read is the same kind
    of answer."""
    path = tmp_path / ".github" / "workflows" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)

    assert preflight.main(["--root", str(tmp_path), "--only", "lint"]) == 2
    printed = capsys.readouterr().err
    assert f"cannot read {name}" in printed
    assert says in printed


def test_a_workflow_this_walk_may_not_open_is_a_misuse_too(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The glob finds the name, not a readable file: a directory called `ci.yml` — or one
    whose permissions say no — reaches the same reader and must reach the same answer."""
    (tmp_path / ".github" / "workflows" / "ci.yml").mkdir(parents=True)

    assert preflight.main(["--root", str(tmp_path), "--only", "lint"]) == 2
    assert "cannot read ci.yml" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("content", "says"),
    [
        (b'{"preflight_jobs": ["caf\xe9"]}\n', "not UTF-8"),
        (b"{not json at all\n", "Expecting property name"),
        (b'{"preflight_jobs": "test"}\n', "not a list of job names"),
        (b'{"preflight_jobs": 5}\n', "not a list of job names"),
        (b'{"preflight_jobs": {"lint": 1}}\n', "not a list of job names"),
        (b'{"preflight_jobs": ["lint", 5]}\n', "not a list of job names"),
    ],
    ids=["not-utf-8", "not-json", "a-string", "a-number", "an-object", "a-list-with-a-number"],
)
def test_a_config_this_walk_cannot_read_is_a_misuse_too(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], content: bytes, says: str
) -> None:
    """`scaffold.json` chooses which jobs to walk, so a file this reader cannot parse
    silently changed *what ran* — and did it with a traceback.

    The parse was guarded and the *shape* under it was not: `"preflight_jobs": "test"`
    was walked one character at a time (`no job ['t', 'e', 's', 't']`) and a number left
    a raw `TypeError` and exit 1 — the code that means *a job failed* — before a single
    job had been walked (self-audit round 17, 2026-09-01).
    """
    write(tmp_path, "ci.yml", "jobs:\n  lint:\n    steps:\n      - run: 'true'\n")
    (tmp_path / preflight.CONFIG).write_bytes(content)

    assert preflight.main(["--root", str(tmp_path)]) == 2
    printed = capsys.readouterr().err
    assert preflight.CONFIG in printed
    assert says in printed
