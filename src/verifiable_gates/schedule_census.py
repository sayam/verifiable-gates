"""Anything that runs on a schedule has to be provably still firing.

A workflow that never started counts zero jobs, and that layer is closable. The
layer above it is not: **a workflow that was never triggered counts zero runs**,
and "no runs at all" looks exactly like "no run went red" in every tool there is,
including any census that counts what *happened* rather than what *should have*.

This answers one question: **when did each declared schedule last actually fire,
and how far past its own period is that?**

Two criteria:

- Every workflow declaring `on.schedule` must have at least one run of type
  `schedule`. A cron declared but never fired is the shape of a workflow the
  platform rejected outright, or of a repository whose schedules were disabled
  for inactivity — GitHub does that after 60 days, and announces that it does.
- The most recent run must not be older than the declared period times
  `--tolerance` (2 by default), because platform crons drift by tens of minutes
  in busy hours.

**Things that cannot be checked by machine are reported as exactly that**, never
guessed either way. Dependabot is the standing example: there is no public
endpoint saying when it last ran, and "no pull requests appeared" is correct
whenever nothing needed updating. Such rows are printed with a label and do not
make the census red.

Role: reader — it reports. Its evidence is that the numbers printed match the
source, and that nothing is dropped in silence.
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys
from typing import Any

import yaml

from verifiable_gates import gh, workflows

__all__ = [
    "declared_schedules",
    "fetch",
    "main",
    "period_hours",
    "problems",
    "unverifiable_schedules",
]

HOUR = 1
DAY = 24
WEEK = 7 * DAY
MONTH = 30 * DAY

# A cron's period is judged from the coarsest field that is *not* `*`. That is
# enough for "how often should this fire" without dragging in a cron library —
# and a dependency here would have to be installed by every project that runs it.
CRON_FIELDS = ("minute", "hour", "dom", "month", "dow")


def period_hours(cron: str) -> int:
    """Roughly how often one cron line fires, in hours.

    Read from the coarsest field that is pinned: a pinned day-of-week means
    weekly, a pinned day-of-month means monthly, a pinned hour means daily, and
    anything else means hourly.
    """
    fields = dict(zip(CRON_FIELDS, cron.split(), strict=False))
    if fields.get("dow", "*") != "*":
        return WEEK
    if fields.get("dom", "*") != "*":
        return MONTH
    if fields.get("hour", "*") != "*":
        return DAY
    return HOUR


def declared_schedules(directory: pathlib.Path) -> dict[str, int]:
    """Workflow filename → the shortest period it declares, in hours."""
    found: dict[str, int] = {}
    for path in sorted(directory.glob("*.y*ml")):
        crons = workflows.schedules(workflows.load(path))
        if crons:
            found[path.name] = min(period_hours(cron) for cron in crons)
    return found


def unverifiable_schedules(root: pathlib.Path) -> list[str]:
    """Schedules declared to a service that will not say when it last ran.

    Dependabot is the standing example: no public endpoint reports its last run,
    and "no pull requests appeared" is correct whenever nothing needed updating.
    So these are named and printed with a label rather than guessed either way —
    a thing that cannot be classified by machine has to be called that, not
    quietly rounded to pass or to fail.
    """
    config_path = root / ".github" / "dependabot.yml"
    if not config_path.is_file():
        return []
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return [
        f"dependabot {entry.get('package-ecosystem')} "
        f"({(entry.get('schedule') or {}).get('interval')})"
        for entry in config.get("updates", [])
    ]


def fetch(files: list[str]) -> dict[str, dict[str, str | None]]:
    """When each file's most recent `schedule` run happened — None means never."""
    last: dict[str, str | None] = {}
    for name in files:
        runs = gh.api(f"repos/:owner/:repo/actions/workflows/{name}/runs?event=schedule&per_page=1")
        rows = runs.get("workflow_runs") or []
        last[name] = rows[0]["created_at"] if rows else None
    return {"last_scheduled_run": last}


def problems(
    schedules: dict[str, int],
    last: dict[str, Any],
    now: str,
    tolerance: int,
) -> list[str]:
    """A schedule that stopped firing must be louder than one that never existed."""
    moment = datetime.datetime.fromisoformat(now)
    found = []
    for name, hours in sorted(schedules.items()):
        stamp = last.get(name)
        if stamp is None:
            found.append(
                f"{name}: declares a cron but has **never had a run of type schedule** — "
                "a workflow the platform rejected outright and a repository whose "
                "schedules were disabled for inactivity look identical from here"
            )
            continue
        age = (moment - datetime.datetime.fromisoformat(stamp)).total_seconds() / 3600
        if age > hours * tolerance:
            found.append(
                f"{name}: last scheduled run was {age / 24:.1f} days ago, but it "
                f"declares every {hours / 24:.1f} days ({tolerance}x tolerance already "
                "allowed) — a schedule that stopped firing is silence shaped like success"
            )
    return found


def main(argv: list[str] | None = None) -> int:
    """Read what is declared, ask when it last fired, return 1 if it has gone quiet."""
    parser = argparse.ArgumentParser(description="Census of declared schedules against reality.")
    parser.add_argument("--root", default=".", help="the project to read (default: here)")
    parser.add_argument("--input", help="a JSON file of already-fetched results (offline)")
    parser.add_argument("--tolerance", type=int, default=2, help="how many periods late is allowed")
    parser.add_argument("--now", help="reference time in ISO format (for tests)")
    args = parser.parse_args(argv)

    directory = workflows.workflow_dir(pathlib.Path(args.root))
    schedules = declared_schedules(directory)
    if not schedules:
        print("no workflow declares a cron — there is nothing to watch")
        return 0

    try:
        state = (
            json.loads(pathlib.Path(args.input).read_text(encoding="utf-8"))
            if args.input
            else fetch(list(schedules))
        )
    except (PermissionError, RuntimeError) as problem:
        print(
            f"cannot read the run history: {problem}\n"
            "**This must never become a silent skip** — a watcher that goes quiet when "
            "it cannot see is one that reports every schedule as firing on the day it "
            "can see nothing at all.",
            file=sys.stderr,
        )
        return 2

    now = args.now or datetime.datetime.now(datetime.UTC).isoformat()
    found = problems(schedules, state.get("last_scheduled_run") or {}, now, args.tolerance)

    for line in unverifiable_schedules(pathlib.Path(args.root)):
        print(f"  not checkable by machine (no public endpoint): {line}")

    if found:
        print("declared schedules disagree with what actually fired:", file=sys.stderr)
        for line in found:
            print(f"  - {line}", file=sys.stderr)
        return 1

    print(f"every declared schedule is still firing within its period ({len(schedules)} workflows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
