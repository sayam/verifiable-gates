"""preflight — walk the CI gates on your own machine, **reading the commands from the workflow**.

A commit hook usually checks a handful of fast things. The slow ones — complexity,
docstring coverage, the coverage floor, diff coverage, regenerating derived files —
live only in CI. That gap is a real failure class: in the reference implementation
it turned two consecutive pull requests red while everything was green locally
(governance audit round 6).

**The commands are not copied here.** A second copy drifts the moment somebody
edits one side, so this reads every workflow under `.github/workflows/` and runs
the steps of the chosen jobs in their original order. A step that cannot run on a
developer's machine is **skipped with its reason printed**, never dropped
silently: a preflight that quietly loses a step gives the same false confidence as
a harness that reports green while the tests are red.

**A job's `services:` are the one thing a developer's machine cannot conjure.**
CI hands such a job an address for a container it started; here that address
points at nothing. Rather than skip the step — throwing away a whole test suite to
protect the two tests that need the service — preflight withholds only the
variables naming an absent service, so those tests take the skip they already
declare, and reports the step apart from a clean pass. Start the service locally
and it is used exactly as CI uses it.

**A step is lent only what it names.** CI runs a step in a fresh runner whose
environment holds the runner's own variables and the `env:` the workflow wrote;
a developer's shell holds tokens for every service they have ever logged into.
Handing a step `os.environ` whole means a `run:` line read from a workflow file
— any workflow file `--root` points at — executes with all of them (an outside
audit, 2026-08-29). So a step gets a fixed baseline a tool needs to run at all
(`PATH`, `HOME`, the locale, the temp directory), the `env:` the workflow declares
for it, and any variable its own text names (`$GH_TOKEN`) — that last set is
printed before the step runs, so a borrowed secret is never borrowed in silence.

**This file ships with the bundle**, so it must not know the name of any one
project's jobs or workflow files. Which jobs to walk comes from `scaffold.json`
under `preflight_jobs`, and jobs are looked up across every workflow file, since
job names are unique across them anyway.

**It is the one shipped file that is not stdlib-only.** It needs a YAML reader for
whole workflows, which the deliberately narrow subset reader in the scans cannot
be. That dependency is declared in the manifest under `requires`, and a test holds
the declaration to what the file actually imports — a shipped file with an
undeclared dependency fails in someone else's project, where nobody here can see
it. It is also the only file that runs on a developer's machine rather than a bare
CI runner, which is why the trade is acceptable at all.

    python3 tools/preflight.py                # every job declared in scaffold.json
    python3 tools/preflight.py --only lint    # just that job (repeatable)
    python3 tools/preflight.py --base main    # the base for diff coverage

Role: reader — it runs the workflow's steps locally and reports. It decides
nothing CI does not; a step it cannot run is a skip with a reason, never a pass.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


import yaml

# **A ceiling on anything we launch.** `subprocess.run` without a timeout waits
# forever, which in CI becomes a job that never ends and a bill that does not stop.
STEP_TIMEOUT_SECONDS = 3600  # one workflow step — a full suite with coverage fits inside

WORKFLOW_DIR = pathlib.Path(".github") / "workflows"
CONFIG = "scaffold.json"

# Walked when the config does not say. Other jobs usually need docker, a service
# container, or a secret that only CI has.
DEFAULT_JOBS = ("lint", "test")

# Steps skipped locally, each with the reason that gets printed every time.
SKIP_RUNS = (
    ("pip install", "installs the runner's tools — your machine already has an environment"),
    ("pipenv sync", "arranges an environment rather than judging anything, and it edits yours"),
)

EXPRESSION = re.compile(r"\$\{\{[^}]*\}\}")

# What every step gets from the developer's shell: what a tool needs to start at
# all, and nothing that identifies the developer to a service.
BASELINE_ENV = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "SHELL",
        "LANG",
        "LANGUAGE",
        "TERM",
        "TMPDIR",
        "TEMP",
        "TMP",
        "VIRTUAL_ENV",
        "PYTHONPATH",
        "PYTHONDONTWRITEBYTECODE",
    }
)
BASELINE_PREFIXES = ("LC_",)
# `$NAME` or `${NAME}` in a step's text — what the step says it will read.
NAMED_VARIABLE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")

# How long to wait for a service container's port before calling it absent. This
# is a loopback connect to a port that is either open or refused immediately, so
# the wait only matters when something is filtering the port; a quarter second is
# long enough to be sure and short enough that nobody notices it.
PROBE_TIMEOUT_SECONDS = 0.25
PROBE_HOST = "127.0.0.1"


def listening(port: int, host: str = PROBE_HOST) -> bool:
    """Is anything answering on that port right now?"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(PROBE_TIMEOUT_SECONDS)
        return probe.connect_ex((host, port)) == 0


def host_ports(job: dict[str, Any]) -> dict[int, str]:
    """host port → the service container that publishes it, from the job's `services:`.

    Only published ports are readable this way. A service with no `ports:` is
    reachable in CI by its service name on the runner's container network, which
    has no local equivalent at all — those are left alone here rather than guessed
    at, and the step keeps whatever env names them.
    """
    found: dict[int, str] = {}
    for name, spec in (job.get("services") or {}).items():
        for mapping in (spec or {}).get("ports") or []:
            head = str(mapping).split(":")[0]
            if head.isdigit():
                found[int(head)] = str(name)
    return found


def _substitute(text: str, base: str, temp: str) -> str:
    """Replace the CI expressions that have a local equivalent; the caller skips the rest."""
    return text.replace("${{ github.base_ref }}", base).replace("${{ runner.temp }}", temp)


def _label(step: dict[str, Any]) -> str:
    """What a person sees: the step's name, or the first line of its command."""
    if step.get("name"):
        return str(step["name"])
    lines = str(step.get("run") or step.get("uses") or "?").strip().splitlines()
    return lines[0][:70] if lines else "?"


def _read_workflow(path: pathlib.Path) -> dict[str, Any]:
    """One workflow, or a `ValueError` naming the file and what stopped the read.

    A workflow in any other encoding — a job name a Windows editor saved as cp1252 —
    ended this walk with a raw `UnicodeDecodeError` and exit 1, the code that means
    *a job failed* (self-audit round 12, 2026-09-01). This reader already has a third
    answer for a job it cannot find; a file it cannot read takes the same route.
    """
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except UnicodeDecodeError as problem:
        raise ValueError(f"{path.name}: not UTF-8 ({problem.reason})") from problem
    except OSError as problem:
        raise ValueError(f"{path.name}: {problem.strerror or problem}") from problem
    except yaml.YAMLError as problem:
        raise ValueError(f"{path.name}: not YAML this reader can parse") from problem


def jobs_on_disk(root: pathlib.Path) -> dict[str, Any]:
    """job → its definition, from **every** workflow file; job names are unique across them."""
    found: dict[str, Any] = {}
    for path in sorted((root / WORKFLOW_DIR).glob("*.y*ml")):
        found.update(_read_workflow(path).get("jobs") or {})
    return found


def wanted_jobs(root: pathlib.Path, chosen: list[str]) -> tuple[str, ...]:
    """Which jobs to walk: the command line beats the config, the config beats the default."""
    if chosen:
        return tuple(chosen)
    config = root / CONFIG
    if config.is_file():
        try:
            declared = json.loads(config.read_text(encoding="utf-8")).get("preflight_jobs")
        except UnicodeDecodeError as problem:
            raise ValueError(f"{CONFIG}: not UTF-8 ({problem.reason})") from problem
        except (OSError, json.JSONDecodeError) as problem:
            raise ValueError(f"{CONFIG}: {problem}") from problem
        # `scaffold.json.default` declares this key as a list of job names and nothing
        # held a project to it: `"preflight_jobs": "test"` was walked one character at a
        # time — `no job ['t', 'e', 's', 't']` — and a number left a raw `TypeError` and
        # exit 1, the code that means *a job failed*, before a single job had been
        # walked (self-audit round 17, 2026-09-01).
        if declared is not None and not (
            isinstance(declared, list) and all(isinstance(job, str) for job in declared)
        ):
            raise ValueError(
                f"{CONFIG}: preflight_jobs is {json.dumps(declared)[:40]}, "
                "which is not a list of job names"
            )
        if declared:
            return tuple(declared)
    return DEFAULT_JOBS


def _absent_services(job: dict[str, Any], probe: Callable[[int], bool]) -> dict[int, str]:
    """Declared service containers with nothing listening on their port here."""
    return {port: name for port, name in host_ports(job).items() if not probe(port)}


def _withhold(env: dict[str, str], absent: dict[int, str]) -> tuple[dict[str, str], str | None]:
    """Split a step's env into what still means something locally, and what cannot.

    A variable is tied to a service when it carries that service's port. The match
    is on the port alone, not on the host beside it: CI writes these as
    `127.0.0.1:6379`, but a value pointing somewhere else that happens to use the
    same port would also be withheld. That direction is the safe one — the name is
    printed every time, so a wrong guess is visible rather than silent.
    """
    kept, lost = {}, {}
    for name, value in env.items():
        # The literal `:` already rules out a longer number ending in these digits
        # (`:16379` has no colon before `6379`); the trailing guard rules out one
        # starting with them, so `:63790` is not read as `:6379`.
        port = next((p for p in absent if re.search(rf":{p}(?!\d)", value)), None)
        if port is None:
            kept[name] = value
        else:
            lost[name] = absent[port]
    if not lost:
        return env, None
    named = ", ".join(f"{n} (service `{s}`)" for n, s in sorted(lost.items()))
    return kept, (
        f"{named} withheld — nothing is listening on the port the job publishes for it, "
        "so the tests that need it will skip themselves rather than fail on a refused connection"
    )


def plan(
    workflow: dict[str, Any],
    jobs: tuple[str, ...],
    base: str,
    temp: str | None = None,
    probe: Callable[[int], bool] | None = None,
) -> list[dict[str, Any]]:
    """Turn the chosen jobs' steps into entries to run, or to skip with a reason.

    Every step appears in the result exactly once. A preflight that drops one is
    the same kind of lie as a harness reporting green while the tests are red.

    **A step's `env:` is part of the command, not decoration.** While it was being
    ignored, a step measuring coverage of one directory overwrote the coverage data
    of another on the developer's machine — CI sets `COVERAGE_FILE` outside the
    workspace precisely to stop that. Running the same command in a different
    environment answers a different question from the one CI asked.

    **The exception is env that names a service container.** A job may declare
    `services:`, and CI then hands its steps an address like
    `TEST_REDIS_URL=redis://127.0.0.1:6379/0`. That address means nothing on a
    machine with no such service: passing it on makes the suite dial a port nobody
    is answering and report a failure that says nothing about the change under
    test. Withholding the variable instead puts the suite into the reduced state it
    already declares for itself — the tests behind it are guarded by their own
    skip, because a test that skips when it cannot connect would never run in CI
    either. The alternative, skipping the whole step, throws away the entire local
    signal to protect a fraction of it, which is the gap preflight exists to close.
    Reduced entries are reported apart from clean ones so the two cannot be
    confused, and a service that *is* running locally is used exactly as CI uses it.
    """
    temp = tempfile.gettempdir() if temp is None else temp
    # Resolved here rather than as a default, so the name is looked up when the
    # plan is made — a default binds the function object at import and a test
    # replacing it would be patching something nobody reads.
    probe = listening if probe is None else probe
    made: list[dict[str, Any]] = []
    for job in jobs:
        absent = _absent_services(workflow["jobs"][job], probe)
        for step in workflow["jobs"][job]["steps"]:
            entry = {"job": job, "label": _label(step)}
            command = step.get("run")
            if command is None:
                uses = step.get("uses", "?")
                made.append({**entry, "skip": f"an action ({uses}) — the version in CI decides"})
                continue
            head = command.strip()
            skip = next((why for prefix, why in SKIP_RUNS if head.startswith(prefix)), None)
            if skip:
                made.append({**entry, "skip": skip})
                continue
            resolved = _substitute(command, base, temp)
            left = EXPRESSION.search(resolved)
            if left:
                made.append(
                    {**entry, "skip": f"a CI expression with no local value: {left.group(0)}"}
                )
                continue
            declared = (step.get("env") or {}).items()
            env = {str(k): _substitute(str(v), base, temp) for k, v in declared}
            unresolved = next((m for v in env.values() if (m := EXPRESSION.search(v))), None)
            if unresolved:
                where = unresolved.group(0)
                made.append(
                    {**entry, "skip": f"env holds a CI expression with no local value: {where}"}
                )
                continue
            env, reduced = _withhold(env, absent)
            planned = {**entry, "run": resolved, "env": env}
            made.append(planned if reduced is None else {**planned, "reduced": reduced})
    return made


def environment(
    command: str, declared: dict[str, str], base: dict[str, str] | None = None
) -> tuple[dict[str, str], list[str]]:
    """The environment one step runs in, and which variables it borrowed by name.

    Three layers, narrowest wins: the baseline every tool needs, then whatever the
    step's own text or its `env:` values name (`$GH_TOKEN`) if the shell has it,
    then the `env:` the workflow declares. A name the shell does not have is not
    invented — the step sees it unset, exactly as CI would without a secret.
    """
    shell = os.environ if base is None else base
    lent = {
        key: value
        for key, value in shell.items()
        if key in BASELINE_ENV or key.startswith(BASELINE_PREFIXES)
    }
    mentioned = set(NAMED_VARIABLE.findall(command))
    for value in declared.values():
        mentioned.update(NAMED_VARIABLE.findall(value))
    borrowed = sorted(
        name for name in mentioned if name in shell and name not in lent and name not in declared
    )
    lent.update({name: shell[name] for name in borrowed})
    return {**lent, **declared}, borrowed


def execute(entries: list[dict[str, Any]], root: pathlib.Path) -> int:
    """Run the plan, printing as it goes. Returns how many steps failed.

    A reduced step prints what was withheld *before* it runs, so the reason is on
    screen while the command is working rather than buried above its output — and
    a step that borrows a variable by name prints which, for the same reason.
    """
    # GitHub's runner executes a step with `bash -e {0}`, so this needs real bash —
    # not the `/bin/sh` that `shell=True` would give, since the commands in a
    # workflow are written to bash's rules.
    bash = shutil.which("bash")
    if not bash:
        message = "no bash on this machine — workflow steps are written for it"
        raise RuntimeError(message)

    failed = 0
    for entry in entries:
        head = f"[{entry['job']}] {entry['label']}"
        if "skip" in entry:
            print(f"-  {head}\n   skipped: {entry['skip']}")
            continue
        if "reduced" in entry:
            print(f"~  {head}\n   reduced: {entry['reduced']}")
        env, borrowed = environment(entry["run"], entry.get("env", {}))
        if borrowed:
            print(f"   lent from your shell, because the step names it: {', '.join(borrowed)}")
        result = subprocess.run(  # noqa: S603 — the command comes from the workflow under --root
            [bash, "-e", "-c", entry["run"]],
            cwd=root,
            check=False,
            timeout=STEP_TIMEOUT_SECONDS,
            env=env,
        )
        if result.returncode == 0:
            print(f"{'~~' if 'reduced' in entry else 'OK'}  {head}")
        else:
            failed += 1
            print(f"XX  {head}  (exit {result.returncode})")
    return failed


# The hook types a contributing guide usually asks for. The file names under
# `.git/hooks/` match the type names, and `pre-commit` leaves its own signature.
HOOK_TYPES = ("pre-commit", "commit-msg", "pre-push")
HOOK_MARK = "pre-commit"


def missing_hooks(root: pathlib.Path) -> list[str]:
    """Which hook types are not installed — read from `.git/hooks/`, not from belief.

    **From a real event, 2026-08-20**: an outside contributor's pull request arrived
    with unsorted imports and trailing whitespace on blank lines — two things the
    commit hook fixes by itself. That they travelled at all means the `pre-commit
    install` line in the setup instructions had never been run. An instruction that
    lives only in a document is an instruction that gets skipped.

    This warns rather than fails. Someone who skips hooks deliberately has their
    reasons, and the real gate is CI regardless. What is wrong is not knowing which
    state you are in.
    """
    hooks = root / ".git" / "hooks"
    if not hooks.is_dir():
        return []
    absent = []
    for kind in HOOK_TYPES:
        path = hooks / kind
        if not path.is_file() or HOOK_MARK not in path.read_text(
            encoding="utf-8", errors="replace"
        ):
            absent.append(kind)
    return absent


def main(argv: list[str] | None = None) -> int:
    """Read the workflows, plan, run, summarise. Exit 1 if anything failed."""
    parser = argparse.ArgumentParser(description="Walk the CI gates locally.")
    parser.add_argument("--root", default=".", help="the tree to check")
    parser.add_argument("--base", default="main", help="base branch for diff coverage")
    parser.add_argument(
        "--only", action="append", default=[], help="walk just this job (repeatable)"
    )
    args = parser.parse_args(argv)

    root = pathlib.Path(args.root).resolve()
    try:
        workflow = {"jobs": jobs_on_disk(root)}
        jobs = wanted_jobs(root, args.only)
    except ValueError as unreadable:
        print(f"cannot read {unreadable}", file=sys.stderr)
        return 2
    unknown = [j for j in jobs if j not in workflow["jobs"]]
    if unknown:
        print(f"no job {unknown} under {WORKFLOW_DIR}/", file=sys.stderr)
        return 2

    absent = missing_hooks(root)
    if absent:
        print(
            f"!  hooks not installed: {', '.join(absent)}\n"
            "   install with: pre-commit install "
            + " ".join(f"--hook-type {kind}" for kind in HOOK_TYPES)
            + "\n   (not a failure — but what the hooks fix will surface in CI instead)\n"
        )

    entries = plan(workflow, jobs, args.base)
    failed = execute(entries, root)
    skipped = sum(1 for e in entries if "skip" in e)
    reduced = sum(1 for e in entries if "reduced" in e)
    passed = len(entries) - skipped - failed
    tail = f" · {reduced} ran without a service CI provides" if reduced else ""
    print(f"\n{passed} passed · {failed} failed · {skipped} skipped with a reason{tail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
