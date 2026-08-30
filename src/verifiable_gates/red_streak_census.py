"""Does a declared `within_days` hold up in practice?

A gate that cannot block anything is supposed to declare **who sees it within how
many days**. The usual check is on the *shape* of that number — is it an integer,
is it under some cap — which is no check at all: a promise with no instrument
behind it expires in silence.

This measures the one thing the available data can answer: **how long redness
stood on the default branch before going green again**, by pairing each "first
failure" with the next success for the same workflow.

**Call it what it is: an upper bound on notice-plus-fix, not MTTA.** It does not
know when a person saw anything, only how long the condition stood. A measurable
upper bound is worth more than a precise figure nobody collects, and it answers
the question the promise actually makes.

Two things this gets wrong if done naively:

- **Group by `path`, not by `name`.** A run the platform rejected outright is
  named after the workflow's *path* rather than its declared `name`, so grouping
  by name splits one history into two silently. The first attempt at this
  measurement reported 2.2 hours where the truth was 14.6.
- **The platform's resolution is the file, not the job.** A run's conclusion
  belongs to the whole workflow, so a file mixing blocking and watched jobs
  cannot measure the watched one: its figure is dominated by the blocking job's
  redness, which is fixed fast precisely because it stops merges. So only files
  with **no job running on `pull_request`** are judged. The rest are printed to
  be read but never decide anything — a green that means nothing is worse than
  no measurement.

Role: decider — it answers pass or fail with an exit code (1 when a promise the
registry makes is broken, 2 when it cannot see), and a job can block on it —
`schedule_census` blocks ci.yml's `test` job; the other two run by hand. It was
labelled a reader until 2026-08-30, when the re-audit read its `return 1` beside
the label; the evidence is still that the numbers printed match the source and
that nothing is dropped in silence.
"""

from __future__ import annotations

import argparse
import collections
import datetime
import pathlib
import sys
from typing import Any

import yaml

from verifiable_gates import gh, history, workflows

__all__ = ["longest_red_hours", "main", "problems", "promised_days"]

# The page ceiling lives with the wrapper now — one loop, not three.
PAGE_SIZE = gh.PAGE_SIZE
HOURS_PER_DAY = 24


def promised_days(registry: pathlib.Path, workflow_directory: pathlib.Path) -> dict[str, int]:
    """Workflow path → the **shortest** number of days any gate in it promises.

    Shortest because one file can hold several gates, and the narrowest promise
    is the one that breaks first: satisfy it and the others follow.
    """
    owner: dict[str, str] = {}
    for path in sorted(workflow_directory.glob("*.y*ml")):
        workflow = workflows.load(path)
        # A file that runs on pull_request has blocking jobs mixed in. The run's
        # conclusion belongs to the whole file, so its figure cannot answer for
        # the watched job — see the module docstring.
        if workflows.runs_on(workflow, "pull_request"):
            continue
        for job in workflows.jobs(workflow):
            owner[job] = f".github/workflows/{path.name}"

    promised: dict[str, int] = {}
    for gate in yaml.safe_load(registry.read_text(encoding="utf-8"))["gates"]:
        watcher = gate.get("watched_by")
        watched = (gate.get("enforced_by") or {}).get("job")
        if not watcher or watched not in owner:
            continue
        days = int(watcher["within_days"])
        promised[owner[watched]] = min(promised.get(owner[watched], days), days)
    return promised


def blocking_paths(workflow_directory: pathlib.Path) -> set[str]:
    """Workflow paths whose jobs run on pull_request — the ones a merge can block on."""
    return {
        f".github/workflows/{path.name}"
        for path in sorted(workflow_directory.glob("*.y*ml"))
        if workflows.runs_on(workflows.load(path), "pull_request")
    }


def standing(path: str, promised: dict[str, int], blocking: set[str]) -> tuple[str, bool]:
    """What holds this workflow, in words — and whether nothing does.

    Three states, told apart: a `watched_by` promise, a pull_request trigger (it
    blocks), or neither — the worst of the three, which an outside audit on
    2026-08-30 found printed as "it blocks" for the platform's own Dependabot
    runs and for release.yml. A path outside `.github/workflows/` is the
    platform's, not this repository's, and is named as such rather than judged.
    """
    if path in promised:
        return f"promised {promised[path]} days", False
    if path in blocking:
        return "runs on pull_request (it blocks)", False
    if not path.startswith(".github/workflows/"):
        return "the platform's own run, not a workflow here", False
    return "nobody watches it and nothing blocks on it", True


def longest_red_hours(runs: list[dict[str, Any]]) -> dict[str, float]:
    """Workflow path → its longest unbroken stretch of red, in hours.

    Redness **still standing now** is counted up to the newest run seen rather
    than dropped: an unfinished stretch is always the longest one from here.
    """
    grouped: dict[str, list[tuple[str, str | None]]] = collections.defaultdict(list)
    for run in runs:
        grouped[str(run.get("path") or "?")].append((str(run["created_at"]), run.get("conclusion")))

    newest = max((run["created_at"] for run in runs), default=None)
    longest: dict[str, float] = {}
    for path, rows in grouped.items():
        rows.sort()
        started: datetime.datetime | None = None
        worst = 0.0
        for stamp, conclusion in rows:
            moment = datetime.datetime.fromisoformat(stamp)
            if conclusion == "failure" and started is None:
                started = moment
            elif conclusion == "success" and started is not None:
                worst = max(worst, (moment - started).total_seconds() / 3600)
                started = None
        if started is not None and newest:
            still = (datetime.datetime.fromisoformat(newest) - started).total_seconds() / 3600
            worst = max(worst, still)
        longest[path] = round(worst, 1)
    return longest


def problems(promised: dict[str, int], measured: dict[str, float]) -> list[str]:
    """How many days were promised, and did reality stand longer than that?"""
    found = []
    for path, days in sorted(promised.items()):
        hours = measured.get(path)
        if hours is None:
            continue  # no runs in the fetched window — that is the schedule census's question
        if hours > days * HOURS_PER_DAY:
            found.append(
                f"{path}: redness once stood for {hours / HOURS_PER_DAY:.1f} days, "
                f"but `watched_by` promises somebody sees it within {days} — "
                "fix one side or the other: see it sooner, or stop promising what is not done"
            )
    return found


def _fetch(limit: int) -> list[dict[str, Any]]:
    """Runs on the default branch, newest first — paged by the wrapper up to the limit."""
    return gh.api_pages(
        "repos/:owner/:repo/actions/runs?branch=main", limit=limit, key="workflow_runs"
    )


def main(argv: list[str] | None = None) -> int:
    """Measure how long red stood, compare it with what was promised."""
    parser = argparse.ArgumentParser(description="Census of watcher promises against reality.")
    parser.add_argument("--root", default=".", help="the project to read (default: here)")
    parser.add_argument(
        "--registry", default=None, help="the gate registry (default: <root>/gates.yaml)"
    )
    parser.add_argument("--input", help="a JSON file of runs (offline)")
    parser.add_argument("--limit", type=int, default=200, help="how many runs to fetch")
    args = parser.parse_args(argv)

    root = pathlib.Path(args.root)
    registry = pathlib.Path(args.registry) if args.registry else root / "gates.yaml"

    promised = promised_days(registry, workflows.workflow_dir(root))
    if not promised:
        # Nothing to hold to anything: no gate declares a watcher. Said out loud,
        # because a green that means "nothing was measured" must read as such.
        print("no gate declares a `watched_by` promise — there is nothing to measure")
        return 0

    try:
        # A promise exists, so an empty history is not an answer — it is the
        # census being unable to see, and that must not round to "kept".
        runs = history.read(
            args.input, lambda: _fetch(args.limit), shape=list, must_hold_something=True
        )
    except (PermissionError, RuntimeError) as problem:
        print(
            f"cannot read the run history: {problem}\n"
            "**This must never become a silent skip** — a measurement that goes quiet "
            "when it cannot see reports every promise as kept on the day it can see "
            "nothing at all.",
            file=sys.stderr,
        )
        return 2

    measured = longest_red_hours(runs)
    blocking = blocking_paths(workflows.workflow_dir(root))
    found = problems(promised, measured)
    for path, hours in sorted(measured.items()):
        note, unheld = standing(path, promised, blocking)
        print(f"  {path:35s} longest red {hours:6.1f} h · {note}")
        if unheld:
            found.append(f"{path}: {note} — declare `watched_by` on a gate, or let it block")

    if found:
        print("promises that are not being kept:", file=sys.stderr)
        for line in found:
            print(f"  - {line}", file=sys.stderr)
        return 1

    print(f"every `watched_by` promise still holds ({len(promised)} watched workflows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
