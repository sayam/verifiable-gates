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
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

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


def _substitute(text: str, base: str, temp: str) -> str:
    """Replace the CI expressions that have a local equivalent; the caller skips the rest."""
    return text.replace("${{ github.base_ref }}", base).replace("${{ runner.temp }}", temp)


def _label(step: dict[str, Any]) -> str:
    """What a person sees: the step's name, or the first line of its command."""
    if step.get("name"):
        return str(step["name"])
    lines = str(step.get("run") or step.get("uses") or "?").strip().splitlines()
    return lines[0][:70] if lines else "?"


def jobs_on_disk(root: pathlib.Path) -> dict[str, Any]:
    """job → its definition, from **every** workflow file; job names are unique across them."""
    found: dict[str, Any] = {}
    for path in sorted((root / WORKFLOW_DIR).glob("*.y*ml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        found.update(workflow.get("jobs") or {})
    return found


def wanted_jobs(root: pathlib.Path, chosen: list[str]) -> tuple[str, ...]:
    """Which jobs to walk: the command line beats the config, the config beats the default."""
    if chosen:
        return tuple(chosen)
    config = root / CONFIG
    if config.is_file():
        declared = json.loads(config.read_text(encoding="utf-8")).get("preflight_jobs")
        if declared:
            return tuple(declared)
    return DEFAULT_JOBS


def plan(
    workflow: dict[str, Any], jobs: tuple[str, ...], base: str, temp: str | None = None
) -> list[dict[str, Any]]:
    """Turn the chosen jobs' steps into entries to run, or to skip with a reason.

    Every step appears in the result exactly once. A preflight that drops one is
    the same kind of lie as a harness reporting green while the tests are red.

    **A step's `env:` is part of the command, not decoration.** While it was being
    ignored, a step measuring coverage of one directory overwrote the coverage data
    of another on the developer's machine — CI sets `COVERAGE_FILE` outside the
    workspace precisely to stop that. Running the same command in a different
    environment answers a different question from the one CI asked.
    """
    temp = tempfile.gettempdir() if temp is None else temp
    made: list[dict[str, Any]] = []
    for job in jobs:
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
            made.append({**entry, "run": resolved, "env": env})
    return made


def execute(entries: list[dict[str, Any]], root: pathlib.Path) -> int:
    """Run the plan, printing as it goes. Returns how many steps failed."""
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
        result = subprocess.run(  # noqa: S603 — the command comes from this repo's own workflow
            [bash, "-e", "-c", entry["run"]],
            cwd=root,
            check=False,
            timeout=STEP_TIMEOUT_SECONDS,
            env={**os.environ, **entry.get("env", {})},
        )
        if result.returncode == 0:
            print(f"OK  {head}")
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
    workflow = {"jobs": jobs_on_disk(root)}
    jobs = wanted_jobs(root, args.only)
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
    passed = len(entries) - skipped - failed
    print(f"\n{passed} passed · {failed} failed · {skipped} skipped with a reason")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
