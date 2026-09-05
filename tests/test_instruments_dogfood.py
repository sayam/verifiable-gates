"""The developer-side instruments this bundle ships, pointed at this repository.

`tests/test_dogfood.py` points every *scanner* here and stops. `preflight`, the
fail-fix harness and the two CI-side deciders (`advisories`, `check_issue_handoff`)
are the instruments a person or a job actually runs — and until 2026-08-29 they
had been proved on fixtures and never asked about this tree.
"""

from __future__ import annotations

import fnmatch
import json
import os
import pathlib
import re
import runpy
import shutil
import subprocess
import tomllib
from typing import Any

import pytest
import yaml

from verifiable_gates import (
    check_issue_handoff,
    harness,
    lint_commits,
    measure,
    preflight,
    workflows,
)

OWNER = "sayam"
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


def run_the_jobs_shell(script: str, *args: str, env: dict[str, str] | None = None) -> int:
    """Run a block lifted out of the workflow, so a test judges the job's own shell.

    One place holds the suppression, because a second copy of it is a second thing
    somebody has to justify, and the ceiling in this file only falls.
    """
    call = ["bash", "-c", script, "-", *args]
    return subprocess.run(call, env=env, check=False).returncode  # noqa: S603 — a block from this repository’s own CI, on fixed strings


def test_the_owners_own_cla_line_must_carry_the_address_the_commits_carry() -> None:
    """A signature by an identity with nothing to do with the work is false evidence.

    The generic check accepts any address, which is right for a contributor: the CLA
    wants a real identity from them. It is wrong for the owner, whose address is fixed
    by this repository and appears on every commit. On 2026-09-01 four merged pull
    requests were signed with a private address pasted out of an editor's context, and
    correcting a body does not take it back — GitHub keeps the body's edit history, and
    a fifth pull request kept it there after the visible text was fixed.

    Both directions are run against the job's own condition, because a check that only
    accepts is a check nobody has seen refuse.
    """
    block = next(s for s in preflight.jobs_on_disk(ROOT)["cla"]["steps"] if "OWN=" in s["run"])
    assert set(block["env"]) == {"PR_BODY", "PR_AUTHOR", "OWNER"}, block["env"]
    lines = block["run"].splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip().startswith("OWN="))
    end = next(i for i in range(start, len(lines)) if lines[i].strip() == "fi")
    condition = "\n".join(line.strip() for line in lines[start : end + 1])

    def verdict(author: str, line: str) -> int:
        script = f"set -euo pipefail\n{condition}"

        env = {"PATH": os.environ["PATH"], "PR_AUTHOR": author, "OWNER": OWNER, "PR_BODY": line}
        return run_the_jobs_shell(script, env=env)

    signed = "I have read and agree to CLA.md v1. — A Name "
    noreply = f"<976721+{OWNER}@users.noreply.github.com>"
    assert verdict(OWNER, signed + noreply) == 0, "the owner's own address is refused"
    assert verdict(OWNER, signed + "<someone@example.org>") == 1, "a private address passes"
    assert verdict(OWNER, signed + "<1+x@users.noreply.github.com>") == 1, "anyone's noreply passes"
    assert verdict("a-contributor", signed + "<x@example.org>") == 0, "a contributor is blocked"


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
    assert run_the_jobs_shell(script, example.group(1)) == 0, example.group(1)
    assert example.group(1) in block["run"], "the job's FAIL message should show the same example"
    # And the file the line names. `CLA.md` showed only `— <your name> <your email>`,
    # where the brackets mean a placeholder in one half and literal syntax in the other,
    # with no example and no sentence beside it — and it is the file a contributor opens,
    # because the line names it (self-audit round 11, 2026-09-01).
    cla = (ROOT / "CLA.md").read_text(encoding="utf-8")
    shown = re.search(r"`(I have read and agree to CLA\.md v1\. — Ada[^`]+)`", cla)
    assert shown is not None, "CLA.md shows no example line"
    assert shown.group(1) == example.group(1), "the two documents show different lines"
    assert cla.count(shown.group(1)) == BILINGUAL_HALVES, "both halves show the same line"
    assert not re.search(r"CLA\.md v1\. — <", cla), (
        "a template whose brackets mean a placeholder in one half and syntax in the other"
    )
    # The FAIL branch, run for real: the review of 2026-08-30 found the echo's
    # quoting broken — `<ada@example.org>` had become a redirection and the
    # contributor saw "No such file or directory" instead of the example.
    failing = subprocess.run(  # noqa: S603 — the job's own block, on an empty body
        ["bash", "-c", block["run"]],  # noqa: S607 — bash from PATH, as the runner finds it
        check=False,
        capture_output=True,
        text=True,
        # Every variable the step declares: the block runs under `set -u`, on purpose,
        # so a workflow that stopped passing one goes red instead of skipping a check.
        # A contributor's login, because the owner's stricter branch is proved separately.
        env={"PR_BODY": "", "PR_AUTHOR": "a-contributor", "OWNER": OWNER},
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
        # Three spaces where the name goes — `.+` took them for one (self-audit, 2026-08-31).
        ("I have read and agree to CLA.md v1. —    <a@b.co>", 0),
        ("I have read and agree to CLA.md v1. — \t <a@b.co>", 0),
        ("I have read and agree to CLA.md v1. — Ada Lovelace <ada@example.org>", 1),
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


def test_the_release_publishes_to_the_index_only_what_verified_and_only_after() -> None:
    """`pip install verifiable-gates` was in the README from the first release and the index
    answered 404 until 2026-09-04. The step that ends that sits after the two-way verification,
    uploads the bytes that verified and nothing rebuilt, leaves the SBOM on the release page,
    and tolerates a re-dispatch against a version already on the index."""
    jobs = preflight.jobs_on_disk(ROOT)
    job = jobs["release-sign"]
    steps = job["steps"]
    verify = next(s for s in steps if "verify in both directions" in str(s.get("name")))
    attach = next(s for s in steps if "attach the wheel" in str(s.get("name")))
    publish = next(s for s in steps if "gh-action-pypi-publish" in str(s.get("uses")))
    stage = steps[steps.index(publish) - 1]
    with_ = publish["with"]
    raw = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    uses_line = next(line for line in raw.splitlines() if "gh-action-pypi-publish@" in line)

    assert steps.index(publish) > steps.index(verify) > 0, "published before verified"
    assert steps.index(publish) > steps.index(attach), "the release page is the record"
    assert steps[-1] is publish, "nothing runs after the index has the bytes"
    sha = str(publish["uses"]).split("@")[1]
    assert len(sha) == 40, publish["uses"]
    assert sha == sha.lower(), publish["uses"]
    assert "# v" in uses_line, "a pin with no version comment is a pin nobody can move"
    assert with_["packages-dir"] == "pypi-dist", "dist/ holds the SBOM too — an index refuses it"
    assert with_["skip-existing"] is True, "a re-dispatch after a partial run is red at the end"
    assert "cp dist/*.whl dist/*.tar.gz pypi-dist/" in stage["run"], stage
    assert "sbom" not in stage["run"], "the SBOM is an asset of the release, not a distribution"
    assert job["permissions"]["id-token"] == "write", "trusted publishing is an OIDC exchange"
    releasing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    releasing = releasing[releasing.index("## Releasing") :]
    step_five = releasing[releasing.index("\n5. ") : releasing.index("\n6. ")]
    for phrase in (
        "to PyPI by trusted publishing",
        "skip-existing",
        "pip install verifiable-gates==",
        # The wheel is asked to install its own bundle before it is attested (2026-09-05).
        "installs the bundle from that wheel",
    ):
        assert phrase in step_five, f"checklist step 5 does not say: {phrase}"


# The nine colours GitHub's metadata syntax accepts for `branding.color`, and the Feather
# icons it omits (read from the docs, 2026-09-05; the full icon list is theirs to keep).
BRANDING_COLOURS = frozenset(
    ["white", "black", "yellow", "blue", "green", "orange", "red", "purple", "gray-dark"]
)
FEATHER_OMITTED = frozenset(
    [
        "coffee",
        "columns",
        "divide-circle",
        "divide-square",
        "divide",
        "frown",
        "hexagon",
        "key",
        "meh",
        "mouse-pointer",
        "smile",
        "tool",
        "x-octagon",
    ]
)


def test_the_action_is_listable_on_the_marketplace_and_the_checklist_says_so() -> None:
    """A Marketplace listing is a checkbox on the release form that validates `action.yml`
    — name, description, author, and a `branding` the listing shows. The box is ticked by
    a person, every release; the metadata is this repository's, held here with the
    checklist step that names the box, the way step 5 is held with the publish step."""
    loaded = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))
    for key in ("name", "description", "author"):
        assert str(loaded.get(key, "")).strip(), f"action.yml has no {key}"
    branding = loaded["branding"]
    assert set(branding) == {"icon", "color"}, branding
    assert branding["color"] in BRANDING_COLOURS, branding["color"]
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", branding["icon"]), branding["icon"]
    assert branding["icon"] not in FEATHER_OMITTED, "an icon GitHub does not accept"
    releasing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    releasing = releasing[releasing.index("## Releasing") :]
    step_four = releasing[releasing.index("\n4. ") : releasing.index("\n5. ")]
    for phrase in (
        "Publish this Action to the GitHub Marketplace",
        "github.com/marketplace/actions/verifiable-gates",
    ):
        assert phrase in step_four, f"checklist step 4 does not say: {phrase}"
    # Listed on 2026-09-05 (v0.2.0, the box ticked on the release form; the form read
    # `action.yml` from the default branch, so the branding showed before any tag carried
    # it). The README says so in both languages — the English file and the Thai one
    # beside it — and the English says to pin the SHA, not the tag.
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_th = (ROOT / "README.th.md").read_text(encoding="utf-8")
    listing = "https://github.com/marketplace/actions/verifiable-gates"
    assert listing in readme, "README.md does not name the listing"
    assert listing in readme_th, "README.th.md does not name the listing"
    assert "pin the SHA, not the tag the listing offers" in readme


def test_the_readme_says_beside_the_npx_command_what_the_pipe_sends() -> None:
    """`DECISIONS.md` `distribution-is-two-pipes-nobody-here-owns` says the README says it beside
    the command (round 23, A1). The README restructure (#265) moved the sentence to
    `docs/history.md` and nothing was red — this is the holder that was missing (round 24, F1).
    Same line as the command, in both languages: "beside" means the reader cannot miss it.
    """
    for name in ("README.md", "README.th.md"):
        lines = (ROOT / name).read_text(encoding="utf-8").splitlines()
        beside = [line for line in lines if "npx skills add sayam/verifiable-gates" in line]
        assert beside, f"{name} no longer shows the npx command"
        assert any("DISABLE_TELEMETRY=1" in line for line in beside), (
            f"{name}: the npx command is shown without what the pipe sends and how to turn it off"
        )


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


def _bump_script(*args: str) -> str:
    """What `pins/bump.sh` answers about itself — asked, never read off the page.

    Both facts below used to be read out of `.github/dependabot.yml`. The machine that
    file drove is gone (DECISIONS.md `dependabot-runs-nowhere-here`) and the mover is now a
    script a person runs; the guarantees are the same two, so they are still checked, by
    asking the new mover the same questions. Its `--list` and `--subject` modes touch
    nothing and reach nowhere, which is what lets them run inside the suite.
    """
    binary = shutil.which("bash")
    assert binary, "the mover is a shell script and this machine has no shell"
    done = subprocess.run(  # noqa: S603 — bash from shutil.which, arguments are literals here
        [binary, str(ROOT / "pins" / "bump.sh"), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return done.stdout


def test_every_pins_directory_is_moved_by_the_script() -> None:
    """A pin nobody moves is a vulnerability kept on ice — both ways: every
    `pins/*/requirements.txt` is a directory the mover moves, and the mover moves no other."""
    moved = {line for line in _bump_script("--list").split() if line}
    on_disk = {str(p.parent.relative_to(ROOT)) for p in ROOT.glob("pins/*/requirements.txt")}

    assert moved == on_disk, (moved, on_disk)


def test_the_movers_commit_subject_is_one_the_gate_accepts() -> None:
    """The script writes the subject; the commit gate reads it. The two must agree in advance.

    Dependabot's default subject ("Bump x from a to b") is not a Conventional Commit, so
    every bump it opened would have been red — found on 2026-08-29 before the first one
    opened, and fixed by a prefix in its configuration. A script a person runs can be wrong
    in exactly the same way, and the person would find out at the commit hook instead.
    """
    subject = _bump_script("--subject").strip()

    assert lint_commits.check_title(subject) == [], subject


# ---------------------------------------------------------------- the step gates

# The gates one named step of a job enforces (`kind: step`), held by copy two-way
# like the rows of DECISIONS.md: a step gate leaves or joins the registry only by
# leaving or joining this tuple, and the step it names has to be in the workflow
# under that name. Test gates are held by their test files and job gates by their
# jobs (`scan_gates_registry`); an outside audit on 2026-08-30 deleted each of the
# two step gates alone and the suite stayed green — nothing held that kind.
HELD_STEP_GATES = (
    ("a-declared-schedule-is-watched", "test", "every declared schedule is still firing"),
    (
        "the-about-field-is-read-not-remembered",
        "test",
        "the About field says what the repository measures",
    ),
)


def test_every_step_gate_is_held_by_copy_and_its_step_is_in_the_workflow() -> None:
    """A step gate leaves the registry only by leaving `HELD_STEP_GATES` too — and arrives
    the same way; and the step it names is a step the job really runs."""
    gates = yaml.safe_load((ROOT / "gates.yaml").read_text("utf-8"))["gates"]
    present = tuple(
        (g["id"], g["enforced_by"]["job"], g["enforced_by"]["step"])
        for g in gates
        if g["kind"] == "step"
    )
    assert present == HELD_STEP_GATES, (
        f"removed {sorted(set(HELD_STEP_GATES) - set(present))}, added "
        f"{sorted(set(present) - set(HELD_STEP_GATES))}, or reordered — change both in one"
        " pull request"
    )
    jobs = preflight.jobs_on_disk(ROOT)
    for gid, job, step in HELD_STEP_GATES:
        names = [s.get("name") for s in jobs[job]["steps"]]
        assert step in names, (gid, job, step, names)


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


def test_the_gitleaks_pin_has_a_mover_on_the_cron(tmp_path: pathlib.Path) -> None:
    """The binary is fetched by URL with our checksum, invisible to Dependabot; the upstream
    signs nothing (checked 2026-08-30), so the mover is a cron step that is red the week a
    newer release exists. Run through bash with a fake `gh` on PATH that answers `v8.30.1`:
    a tree pinning 8.30.1 is green, a tree pinning 8.0.0 is red naming both versions."""
    step = next(
        s
        for s in preflight.jobs_on_disk(ROOT)["posture"]["steps"]
        if "gitleaks" in str(s.get("name"))
    )
    assert step.get("if") == "${{ !cancelled() }}"
    assert "grep -oE 'gitleaks_" in step["run"], "the version has to come from security.yml"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "gh").write_text("#!/bin/sh\necho v8.30.1\n", encoding="utf-8")
    (fake_bin / "gh").chmod(0o755)
    real = (ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")

    def run_with(version: str) -> subprocess.CompletedProcess[str]:
        tree = tmp_path / version
        (tree / ".github" / "workflows").mkdir(parents=True)
        (tree / ".github" / "workflows" / "security.yml").write_text(
            real.replace("8.30.1", version), encoding="utf-8"
        )
        return subprocess.run(  # noqa: S603 — the step's own block, under bash from PATH
            ["bash", "-c", step["run"]],  # noqa: S607 — bash from PATH, as the runner finds it
            cwd=tree,
            check=False,
            capture_output=True,
            text=True,
            env={"PATH": f"{fake_bin}:/usr/bin:/bin"},
        )

    current = run_with("8.30.1")
    assert current.returncode == 0, current.stdout + current.stderr
    # A security.yml whose download line changed shape: the grep matches nothing,
    # and under `set -euo pipefail` that used to abort the step with no words at
    # all (pre-cut review, 2026-08-30) — now it says what it could not read.
    tree = tmp_path / "unreadable" / ".github" / "workflows"
    tree.mkdir(parents=True)
    (tree / "security.yml").write_text(
        real.replace("gitleaks_8.30.1_linux", "gitleaks-linux"), "utf-8"
    )
    unreadable = subprocess.run(  # noqa: S603 — the step's own block, under bash from PATH
        ["bash", "-c", step["run"]],  # noqa: S607 — bash from PATH, as the runner finds it
        cwd=tmp_path / "unreadable",
        check=False,
        capture_output=True,
        text=True,
        env={"PATH": f"{fake_bin}:/usr/bin:/bin"},
    )
    assert unreadable.returncode == 1
    assert "could not read the pinned gitleaks version" in unreadable.stdout, unreadable.stderr
    assert "8.30.1 is the latest release" in current.stdout
    behind = run_with("8.0.0")
    assert behind.returncode == 1, behind.stdout + behind.stderr
    assert "gitleaks 8.0.0 is pinned but 8.30.1 is out" in behind.stdout


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
    assert len(seen) == 21, seen
    assert len(set(seen)) == 7, sorted(set(seen))


def _admitted(want: dict[str, Any], owner: str, action: str) -> bool:
    """The platform's reading of a `selected` policy: the repository's own owner always,
    GitHub's own when `github_owned_allowed`, and otherwise a pattern — `owner/repo@*`,
    `owner/*` — matched as the platform matches it."""
    head = action.split("/", 1)[0]
    if head == owner or (want["github_owned_allowed"] and head in {"actions", "github"}):
        return True
    return any(fnmatch.fnmatchcase(action, str(p)) for p in want["patterns_allowed"])


def test_every_action_the_workflows_use_is_one_the_declared_policy_admits() -> None:
    """The Actions policy is `selected` — GitHub-owned and a list — and a `uses:` outside
    it is refused at **startup**, before any job: `release.yml` dispatched for v0.2.0 on
    2026-09-05 lasted one second (run 33937392727, *pypa/gh-action-pypi-publish@… is not
    allowed … all actions must be from a repository owned by sayam or created by GitHub*)
    after #243 had added the step and every check had been green, because no check read the
    register against the workflows. Both ways: every `uses:` is admitted by the declared
    policy, and every pattern the register allows is one some workflow uses — an allowance
    nobody uses is one nobody reviews.
    """
    register = json.loads((ROOT / "pins/dev/posture-declared.json").read_text("utf-8"))
    want = register["settings"]["selected_actions"]["want"]
    card = yaml.safe_load((ROOT / "CITATION.cff").read_text("utf-8"))
    owner_login = str(card["repository-code"]).removeprefix("https://github.com/").split("/")[0]
    used: set[str] = set()
    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for action, _rest in PINNED_USES.findall(path.read_text(encoding="utf-8")):
            used.add(action)
            assert _admitted(want, owner_login, action), (
                f"{path.name}: {action} is not admitted by pins/dev/posture-declared.json — "
                "the platform refuses the whole workflow at startup; name it there, both ways"
            )
    for pattern in want["patterns_allowed"]:
        assert any(fnmatch.fnmatchcase(a, str(pattern)) for a in used), (
            f"the register admits {pattern!r} and no workflow uses it — remove the allowance"
        )
    assert want["patterns_allowed"] == ["pypa/gh-action-pypi-publish@*"], want


def test_a_body_edit_reruns_the_checks_that_read_the_body() -> None:
    """The `cla` job reads the pull request description, but `on.pull_request` with the
    default types does not fire on `edited` — so a contributor who fixed the line saw no
    new run, and the 2026-08-30 re-audit had to close and reopen the pull request. The
    three defaults stay, since dropping one would silence the whole file."""
    body = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    declared = body.get(True, body.get("on"))

    assert set(declared["pull_request"]["types"]) == {"opened", "synchronize", "reopened", "edited"}


# ------------------------------------------- two published rules, pointed at home
#
# `rules.yaml` publishes `jobs-declare-a-time-budget` and
# `exception-registers-are-reasoned`, and until 2026-08-30 nothing here read this
# repository's own `timeout-minutes` or its own suppression lines: an outside audit
# removed one of each and 1171 tests stayed green. The measuring module was
# proved on fakes and pointed at nobody — the shape the second rule's own
# born_from describes.

# 110 → 108 on 2026-09-01: publishing `registry.latest_today()` so `DECISIONS.md`
# and `gates.yaml` answer "what day is it" the same way removed the two `SLF001`
# suppressions the tests needed to reach it while it was private (round 7).
# 108 → 109 on 2026-09-01: one `S603` in `tests/test_scan_coverage.py`, for the git
# call that has to run with `core.quotePath=false` — the configuration under which
# `git ls-files` stops quoting a name that is not UTF-8 (round 15).
# 109 → 110 on 2026-09-01: one `S603` in `tests/test_harness.py`, for the run that has
# to happen in a subprocess — the encoding `write_text` picks with no `encoding=` is the
# interpreter's at startup, so no in-process test can reach that question (round 15).
# 110 → 111 on 2026-09-01: one `S603` for the subprocess that asks `pins/bump.sh` what it
# moves and what subject it writes — the two facts that used to be read out of
# `.github/dependabot.yml`, now asked of the mover that replaced it.
# 116 → 117 on 2026-09-03: one `S603` in `src/verifiable_gates/edit_hook.py`, for the run
# of the doctor a project installed — the hook's whole job is that one subprocess, argv
# built from the project root and our own interpreter (PR-F).
# 117 → 118 on 2026-09-04: one `S102` in `tests/test_checks_are_standalone.py`, for the
# `exec` that runs each shipped copy of `_shown` for real — the ten copies are held by
# what they return, not by reading them (round 21's F2/F3).
# 118 → 119 on 2026-09-04: one `ANN401` in `tests/test_working_catalogue.py`, for the
# `**overrides` that builds a practice with one field replaced — the same shape, and the
# same reason, as the one `tests/test_rules_catalogue.py` already carries.
SUPPRESSED_LINES = 119  # every one with a reason; a new one moves this number, visibly


def test_every_job_in_our_own_workflows_declares_a_time_budget() -> None:
    """`timeout-minutes` on every job — a job that hangs is a runner nobody gets back."""
    without: list[str] = []
    for name, workflow in workflows.all_workflows(workflows.workflow_dir(ROOT)).items():
        for job_name, job in workflows.jobs(workflow).items():
            if "uses" in job:  # a reusable workflow carries its own budget
                continue
            if not isinstance(job.get("timeout-minutes"), int):
                without.append(f"{name}: {job_name}")
    assert without == [], f"jobs with no timeout-minutes: {without}"


def test_our_own_suppressions_all_carry_a_reason() -> None:
    """The register of switched-off checks, read for once — a line with no why is a gap."""
    counts = measure.suppression_counts(ROOT, ("src/**/*.py", "tests/**/*.py"))
    assert counts["suppressions_without_reason"] == 0, counts


def test_the_number_of_suppressions_is_the_one_written_here() -> None:
    """A suppression added or removed changes this number in the same pull request."""
    counts = measure.suppression_counts(ROOT, ("src/**/*.py", "tests/**/*.py"))
    assert counts["suppressions"] == SUPPRESSED_LINES, (
        f"{counts['suppressions']} lines switch a check off, this file says "
        f"{SUPPRESSED_LINES} — rewrite the number here, with the reason on the new line"
    )


def test_the_posture_cron_runs_the_archive_reader_live() -> None:
    """`the-archive-is-read-back` promises "posture's cron runs it live"; the step could
    be removed from posture.yml with every test green (self-audit, 2026-08-31)."""
    jobs = preflight.jobs_on_disk(ROOT)
    runs = [str(s.get("run")) for s in jobs["posture"]["steps"]]
    assert any("python -m verifiable_gates.zenodo --root ." in run for run in runs), runs


def test_the_lint_job_measures_docstring_coverage() -> None:
    """`our-own-floors-sit-against-reality` holds the interrogate floor to a row and to
    reality — but the step that measures it could be removed from the lint job with every
    test green (self-audit, 2026-08-31)."""
    jobs = preflight.jobs_on_disk(ROOT)
    runs = [str(s.get("run")) for s in jobs["lint"]["steps"]]
    assert any(run.strip() == "interrogate src" for run in runs), runs


def test_the_cla_version_is_one_version_everywhere() -> None:
    """CLA.md carries `v1` in its title and its signing line; CONTRIBUTING shows the line;
    the `cla` job greps for it — four places, held to each other by nothing, so a new
    CLA.md v2 would leave the job accepting v1 (self-audit, 2026-08-31)."""
    cla = (ROOT / "CLA.md").read_text(encoding="utf-8")
    title = re.search(r"^# .*— (v\d+),", cla, re.MULTILINE)
    assert title, "CLA.md's title names no version"
    version = title.group(1)
    line = f"I have read and agree to CLA.md {version}."
    assert line in cla, "CLA.md's signing line names another version than its title"
    assert line in (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    block = next(s for s in preflight.jobs_on_disk(ROOT)["cla"]["steps"] if "CLA=" in s["run"])
    definition = next(row for row in block["run"].splitlines() if row.startswith("CLA="))
    assert f"CLA\\.md {version}\\." in definition, definition


# The checks switched off for the whole tree, and per directory, in pyproject —
# a register of exceptions the suppression census never counted: a code added to
# either list relaxed a whole class with nothing in a pull request seeing it
# (self-audit, 2026-08-31). Held by copy, two-way, like SUPPRESSED_LINES.
RUFF_OFF_EVERYWHERE = (
    "COM812",
    "CPY001",
    "D",
    "EM101",
    "EM102",
    "ISC001",
    "RUF001",
    "RUF002",
    "RUF003",
    "TRY003",
)
RUFF_OFF_PER_FILE = {
    "src/verifiable_gates/checks/*.py": ("PLR2004", "T201"),
    "src/verifiable_gates/gates_doctor.py": ("T201",),
    "src/verifiable_gates/preflight.py": ("T201",),
    "src/verifiable_gates/skill.py": ("T201",),
    "src/verifiable_gates/harness.py": ("T201",),
    "src/verifiable_gates/install.py": ("T201",),
    "src/verifiable_gates/lint_commits.py": ("T201",),
    "src/verifiable_gates/check_issue_handoff.py": ("T201",),
    "src/verifiable_gates/skeleton.py": ("T201",),
    "src/verifiable_gates/schedule_census.py": ("T201",),
    "src/verifiable_gates/red_streak_census.py": ("T201",),
    "src/verifiable_gates/removals.py": ("T201",),
    "src/verifiable_gates/rerun_census.py": ("T201",),
    "src/verifiable_gates/measure_apps.py": ("T201",),
    "src/verifiable_gates/own_numbers.py": ("T201",),
    "src/verifiable_gates/advisories.py": ("T201",),
    "src/verifiable_gates/posture.py": ("T201",),
    "src/verifiable_gates/zenodo.py": ("T201",),
    "tests/**": ("INP001", "PLR2004", "S101"),
}


def test_the_checks_switched_off_in_pyproject_are_the_ones_written_here() -> None:
    """A ruff code added to `ignore` or `per-file-ignores` changes this copy in the same
    pull request — a reviewer sees a class of check being switched off."""
    lint = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["ruff"][
        "lint"
    ]
    everywhere = tuple(sorted(lint["ignore"]))
    per_file = {k: tuple(sorted(v)) for k, v in lint.get("per-file-ignores", {}).items()}
    assert everywhere == RUFF_OFF_EVERYWHERE, (everywhere, RUFF_OFF_EVERYWHERE)
    assert per_file == RUFF_OFF_PER_FILE, (per_file, RUFF_OFF_PER_FILE)


def test_every_check_switched_off_in_pyproject_carries_a_reason() -> None:
    """Each entry in `ignore` and each per-file list sits under a comment saying why —
    the same rule every noqa line here is held to."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = text.split("[tool.ruff.lint]", 1)[1].split("[tool.ruff.lint.per-file-ignores]", 1)
    lines = [line.strip() for line in block[0].splitlines()]
    previous = ""
    for line in lines:
        if line.startswith('"') and not previous.startswith("#") and not previous.startswith('"'):
            raise AssertionError(f"switched off with no reason above it: {line}")
        if line:
            previous = line


# `CLA.md` carries English above and Thai below; the example belongs in both.
BILINGUAL_HALVES = 2


def helpers() -> list[str]:
    """Every module in the package with no `main` of its own — read, not remembered.

    Round 11 gave this guard to a list of seven written by hand, and the list was seven
    short: `asvs_worksheet`, `gates_crosswalk`, `gh`, `manifest`, `ratchets`,
    `scan_coverage` and `workflows` all imported cleanly and exited **0** when run as
    commands (self-audit round 12, 2026-09-01). A list of names is a thing that goes
    stale; asking the package cannot.
    """
    package = pathlib.Path(preflight.__file__).parent
    return sorted(
        ".".join(path.relative_to(package).with_suffix("").parts)
        for path in package.rglob("*.py")
        if path.name != "__init__.py" and "\ndef main(" not in path.read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("helper", helpers())
def test_a_helper_run_as_a_command_says_so(helper: str, capsys: pytest.CaptureFixture[str]) -> None:
    """A helper has no entry point of its own. Run as a command they imported cleanly and
    exited 0 having done nothing — a wrong call that looked like a pass, which this
    repository's own register forbids in as many words ("A misuse must exit 2, never 0")
    and which `gates_doctor` had already decided once, by accepting `--root` as the
    spelling an operator reaches for (self-audit round 2, owner decision B6, 2026-09-01).

    Run through `runpy` rather than a subprocess: `run_name="__main__"` is what `python -m`
    does, and it needs no `subprocess` call and so no suppression — the count of those is
    a ceiling that only falls.
    """
    with pytest.raises(SystemExit) as refused:
        runpy.run_module(f"verifiable_gates.{helper}", run_name="__main__")

    assert refused.value.code == 2
    printed = capsys.readouterr()
    assert f"verifiable_gates.{helper} is a helper, not a command" in printed.err
    assert printed.out == "", "a helper cannot be mistaken for a reader that answered"
