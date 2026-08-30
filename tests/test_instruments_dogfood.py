"""The developer-side instruments this bundle ships, pointed at this repository.

`tests/test_dogfood.py` points every *scanner* here and stops. `preflight`, the
fail-fix harness and the two CI-side deciders (`advisories`, `check_issue_handoff`)
are the instruments a person or a job actually runs — and until 2026-08-29 they
had been proved on fixtures and never asked about this tree.
"""

from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import tomllib

import pytest
import yaml

from verifiable_gates import check_issue_handoff, harness, preflight

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


def test_the_cla_job_skips_by_the_pull_requests_author_not_the_runs_actor() -> None:
    """`github.actor` is whoever triggered the run: a maintainer re-running a Dependabot pull
    request's checks becomes the actor, the job runs, and the bot's body has no line — red
    on a bump for the wrong reason. The author of the pull request is the bot every time."""
    condition = str(preflight.jobs_on_disk(ROOT)["cla"].get("if"))

    assert "github.event.pull_request.user.login != 'dependabot[bot]'" in condition
    assert "github.actor" not in condition, condition
    assert "github.event_name == 'pull_request'" in condition


def test_the_example_line_contributing_shows_is_one_the_job_accepts() -> None:
    """A document's example that the gate refuses teaches the wrong shape — and the
    template `<name> <email>` reads as two placeholders when the brackets are literal."""
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    block = next(s for s in preflight.jobs_on_disk(ROOT)["cla"]["steps"] if "CLA=" in s["run"])
    definition = next(line for line in block["run"].splitlines() if line.startswith("CLA="))
    example = re.search(r"for example\s+`(I have read[^`]+)`", contributing)

    assert example is not None, "CONTRIBUTING shows no example line"
    assert "<" in example.group(1), example.group(1)
    assert ">" in example.group(1), example.group(1)
    script = f'{definition}\nprintf \'%s\\n\' "$1" | grep -qE "$CLA"'
    accepted = subprocess.run(["bash", "-c", script, "-", example.group(1)], check=False)  # noqa: S603, S607 — the job's own grep, on a fixed string
    assert accepted.returncode == 0, example.group(1)
    assert example.group(1) in block["run"], "the job's FAIL message should show the same example"
    # The FAIL branch, run for real: the review of 2026-08-30 found the echo's
    # quoting broken — `<ada@example.org>` had become a redirection and the
    # contributor saw "No such file or directory" instead of the example.
    failing = subprocess.run(  # noqa: S603 — the job's own block, on an empty body
        ["bash", "-c", block["run"]],  # noqa: S607 — bash from PATH, as the runner finds it
        check=False,
        capture_output=True,
        text=True,
        env={"PR_BODY": ""},
    )
    assert failing.returncode == 1
    assert example.group(1) in failing.stdout, (failing.stdout, failing.stderr)
    assert failing.stderr == "", failing.stderr


@pytest.mark.parametrize(
    ("body", "accepted"),
    [
        ("Some prose.\n\nI have read and agree to CLA.md v1. — A Person <a@b.co>\n", 1),
        ("I have read and agree to CLA.md v1. — A Person <a@b.co>   ", 1),
        ("I have read and agree to CLA.md v1. —  <@>", 0),
        ("I have read and agree to CLA.md v1. — A Person", 0),
        # The address bare, without the brackets — the 2026-08-30 re-audit's first
        # pull request, red at `cla`; CONTRIBUTING now shows a line with them.
        ("I have read and agree to CLA.md v1. — A Person a@b.co", 0),
        ("I have read and agree to CLA.md v2. — A Person <a@b.co>", 0),
        ("I agree to the CLA — A Person <a@b.co>", 0),
        ("", 0),
    ],
)
def test_the_cla_job_reads_the_line_contributing_asks_for(body: str, accepted: int) -> None:
    """The job's own regex, run by bash, on the shapes a description can take.

    An empty name or address is refused for the sign-off's reason: an acceptance
    nobody can follow up on binds nobody.
    """
    jobs = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    job = jobs["jobs"]["cla"]
    assert "pull_request" in job["if"]
    assert "dependabot" in job["if"]
    block = str(next(step["run"] for step in job["steps"] if "run" in step))
    definition = next(line for line in block.splitlines() if line.startswith("CLA="))
    bash = shutil.which("bash")
    assert bash, "the CI block is written for bash"
    script = f'{definition}\nprintf \'%s\\n\' "$1" | grep -qE "$CLA"'
    shell = subprocess.run(  # noqa: S603 — the script is this repository's own CI block
        [bash, "-c", script, "_", body], check=False
    )
    assert (shell.returncode == 0) == bool(accepted), body


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
    """The SBOM records what was verified by hash, not what the index served that minute."""
    jobs = preflight.jobs_on_disk(ROOT)
    sbom = next(s for s in jobs["release-sign"]["steps"] if "cyclonedx-py" in str(s.get("run")))
    lines = [line.strip() for line in sbom["run"].splitlines()]
    installs = [line for line in lines if " install " in line]

    assert "python -m venv --without-pip sbom-env" in sbom["run"]
    assert installs == [
        (
            "pip --python sbom-env/bin/python install --require-hashes"
            " -r pins/runtime/requirements.txt"
        ),
        "pip --python sbom-env/bin/python install --no-deps --no-build-isolation ./dist/*.whl",
    ], installs
    assert "'verifiable-gates' in n and 'PyYAML' in n" in sbom["run"], "an SBOM of nothing is green"


def test_the_release_builds_with_the_pinned_backend_not_an_isolated_fetch() -> None:
    """`python -m build` alone pip-installs the backend from the index, unpinned, in the job that
    holds `id-token: write` — found floating on 2026-08-30 (setuptools 84.0.0 arrived unhashed)."""
    jobs = preflight.jobs_on_disk(ROOT)
    build = next(s for s in jobs["release-sign"]["steps"] if "python -m build" in str(s.get("run")))
    pinned = (ROOT / "pins" / "dev" / "requirements.txt").read_text(encoding="utf-8")

    assert "--no-isolation" in build["run"], build["run"]
    assert "\nsetuptools==" in pinned, "the backend --no-isolation relies on is not in the pins"


NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")


def _names(lines: list[str]) -> set[str]:
    """Package names out of requirement lines — the part before any extra, specifier or marker."""
    found: set[str] = set()
    for line in lines:
        bare = line.split("#")[0].strip()
        if bare and (match := NAME.match(bare)):
            found.add(match.group(0).lower().replace("_", "-"))
    return found


def _compiled_roots(compiled: str, source_name: str) -> set[str]:
    """The packages a hash-pinned file lists as asked for by `-r <source>` directly."""
    roots: set[str] = set()
    current = ""
    for line in compiled.splitlines():
        if line and not line.startswith((" ", "#")):
            current = line.split("==")[0].strip().lower()
        elif f"-r {source_name}" in line and current:
            roots.add(current)
    return roots


@pytest.mark.parametrize("pins", sorted(p.parent for p in ROOT.glob("pins/*/requirements.in")))
def test_the_compiled_pins_are_compiled_from_the_source_beside_them(pins: pathlib.Path) -> None:
    """`requirements.in` and `requirements.txt` are one list twice: a name dropped from the
    source stays pinned, audited and installed forever, and a name added to the source is not
    installed until somebody runs pip-compile. The 2026-08-30 removal experiment dropped
    `interrogate` from the source and 1121 tests stayed green."""
    source = _names((pins / "requirements.in").read_text(encoding="utf-8").splitlines())
    compiled = (pins / "requirements.txt").read_text(encoding="utf-8")
    roots = _compiled_roots(compiled, f"{pins.relative_to(ROOT)}/requirements.in")

    assert roots == source, (sorted(roots - source), sorted(source - roots))


def test_the_wheels_dependencies_are_the_runtime_pins_and_the_backend_is_in_the_dev_pins() -> None:
    """The release job installs the wheel with `--no-deps` and its dependencies from
    `pins/runtime`, so a dependency added to `pyproject.toml` and not to the pins would be
    missing from the attested SBOM in silence; the backend `--no-isolation` relies on has
    to be in `pins/dev` or the build fails at tag time (review, 2026-08-30)."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    runtime = _names((ROOT / "pins/runtime/requirements.in").read_text("utf-8").splitlines())
    dev = _names((ROOT / "pins/dev/requirements.in").read_text("utf-8").splitlines())

    assert _names(project["project"]["dependencies"]) == runtime, (runtime,)
    assert _names(project["build-system"]["requires"]) <= dev, (dev,)


def test_every_pins_directory_is_moved_by_dependabot() -> None:
    """A pin nobody moves is a vulnerability kept on ice — both ways: every
    `pins/*/requirements.txt` has a Dependabot entry, and every pip entry points at one."""
    config = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    watched = {u["directory"] for u in config["updates"] if u["package-ecosystem"] == "pip"}
    on_disk = {"/" + str(p.parent.relative_to(ROOT)) for p in ROOT.glob("pins/*/requirements.txt")}

    assert watched == on_disk, (watched, on_disk)


# ---------------------------------------------------------------- posture and the census


def test_every_excused_job_declares_a_watcher_and_the_two_promises_agree() -> None:
    """A job excused from being required is watched by a person instead — and the days the
    register promises in prose and the days the gate promises in `watched_by` are one number,
    measured by `red_streak_census` on the cron (no gate declared a watcher until 2026-08-30)."""
    register = json.loads((ROOT / "pins/dev/posture-declared.json").read_text("utf-8"))
    gates = yaml.safe_load((ROOT / "gates.yaml").read_text("utf-8"))["gates"]
    by_job = {g["enforced_by"].get("job"): g for g in gates if g["kind"] == "job"}
    words = {"one": 1, "seven": 7}

    for job, why in register["not_required"].items():
        gate = by_job[job]
        assert gate["severity"] == "watched", (job, gate["severity"])
        promised = int(gate["watched_by"]["within_days"])
        said = re.search(r"within (\w+) days?", why)
        assert said is not None, why
        spoken = words.get(said.group(1)) or int(said.group(1))
        assert spoken == promised, (job, said.group(1), promised)
    census = next(
        s
        for s in preflight.jobs_on_disk(ROOT)["posture"]["steps"]
        if "red_streak_census" in str(s.get("run"))
    )
    assert census.get("if") == "${{ !cancelled() }}"


def test_the_two_clocks_tick_on_the_cron_not_only_on_a_push() -> None:
    """The schedule census and the revisit check ran only in ci.yml's `test` job, which runs
    on push and pull request — so with nobody pushing they stopped, and GitHub's 60-day cron
    disable went unreported by the very census that reports it (re-audit round 26)."""
    jobs = preflight.jobs_on_disk(ROOT)
    posture = jobs["posture"]["steps"]
    runs = [str(s.get("run") or "") for s in posture]
    checkout = next(s for s in posture if "actions/checkout" in str(s.get("uses")))
    census = next(s for s in posture if "schedule_census" in str(s.get("run")))
    revisit = next(s for s in posture if "test_decisions" in str(s.get("run")))

    assert checkout.get("with", {}).get("fetch-depth") == 0, "a shallow clone has no birthdays"
    assert "--root ." in census["run"]
    assert census.get("if") == "${{ !cancelled() }}", "the first red must not hide the clocks"
    assert revisit.get("if") == "${{ !cancelled() }}"
    assert "schedule_census" in " ".join(str(s.get("run")) for s in jobs["test"]["steps"]), (
        "the push-time copy stays: a pull request must not merge past a silent cron either"
    )
    assert any("posture --settings" in r for r in runs)


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


# ---------------------------------------------------------------- the pins in the workflows

# The action and its 40-hex pin, then whatever follows on the line. `uses:` values
# in the workflows are unquoted; the pinning scanner is the one that tolerates quotes.
PINNED_USES = re.compile(r"^\s*-?\s*uses:\s*(\S+/\S+@[0-9a-f]{40})(.*)$", re.MULTILINE)
# A tag a person can read: `v7.0.1`, or the only tag the SHA carries when the
# upstream names its releases otherwise (`codeql-bundle-v2.26.4`).
VERSION_COMMENT = re.compile(r"^\s+#\s*\S*v\d+(\.\d+)*\s*$")


def test_every_action_sha_is_followed_by_its_version_in_a_comment() -> None:
    """The rule `actions-sha-pinned` reads "pinned to a commit SHA with the version
    in a comment". On 2026-08-30 all 6 distinct pins were SHAs and 0 of the 6 carried
    the comment: a reader saw forty hex digits and could not tell v7 from v4, and
    Dependabot had no version to rewrite. Read as text, not YAML — a YAML loader
    drops the comment this test is about; and per occurrence, not per SHA, because
    Dependabot rewrites the comment on each line it bumps.
    """
    workflows = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    assert workflows
    seen: list[str] = []
    for path in workflows:
        for action, rest in PINNED_USES.findall(path.read_text(encoding="utf-8")):
            seen.append(action)
            assert VERSION_COMMENT.match(rest), f"{path.name}: {action} names no version"
    assert len(seen) == 20, seen
    assert len(set(seen)) == 6, sorted(set(seen))
