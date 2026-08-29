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
  **A file younger than one allowance is the third case**: a weekly cron added on
  a Thursday has not been rejected, it has not come round yet, and calling that
  red teaches the reader that this census cries wolf whenever a schedule is
  added. It is named and printed, and it turns red on its own once the wait
  passes `period x tolerance` measured from the commit that added the file.
- The most recent run must not be older than the declared period times
  `--tolerance` (2 by default), because platform crons drift by tens of minutes
  in busy hours.

**Things that cannot be checked by machine are reported as exactly that**, never
guessed either way. Dependabot is the standing example: there is no public
endpoint saying when it last ran, and "no pull requests appeared" is correct
whenever nothing needed updating. Such rows are printed with a label and do not
make the census red.

Role: decider — it answers pass or fail with an exit code (1 when a promise the
registry makes is broken, 2 when it cannot see), and a job can block on it —
`schedule_census` blocks ci.yml's `test` job; the other two run by hand. It was
labelled a reader until 2026-08-30, when the re-audit read its `return 1` beside
the label; the evidence is still that the numbers printed match the source and
that nothing is dropped in silence.
"""

from __future__ import annotations

import argparse
import datetime
import pathlib
import sys
from typing import Any

import yaml

from verifiable_gates import gh, history, removals, workflows

__all__ = [
    "declared_schedules",
    "fetch",
    "first_seen",
    "main",
    "not_due_yet",
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
    """When each file's most recent `schedule` run happened — None means never.

    **A workflow the platform does not know yet answers 404, and that is "never",
    not "cannot see".** A cron fires only from the default branch, so a file that
    exists on a branch and not yet on `main` has genuinely never run and cannot
    have; its birthday keeps it excused until it is due. Every other refusal is
    let through as the third answer — a 404 on a file that *is* on `main` would
    be the platform losing a workflow, and that surfaces as a cron that never
    fires past its allowance, which is the red this census exists for.
    """
    last: dict[str, str | None] = {}
    for name in files:
        try:
            runs = gh.api(
                f"repos/:owner/:repo/actions/workflows/{name}/runs?event=schedule&per_page=1"
            )
        except PermissionError as problem:
            if "HTTP 404" not in str(problem):
                raise
            last[name] = None
            continue
        rows = runs.get("workflow_runs") or []
        last[name] = rows[0]["created_at"] if rows else None
    return {"last_scheduled_run": last}


def first_seen(root: pathlib.Path, files: list[str]) -> dict[str, str | None]:
    """When each workflow file first appeared in history — `None` when git cannot say.

    A file that has never had a scheduled run is ambiguous, and the history is the
    only thing on this machine that can separate "the platform refused it" from
    "it was added on Thursday and fires on Monday". When git is unavailable, the
    file is not committed yet, **or the clone is shallow**, this returns `None`
    and the caller stays strict — an unknown birthday must not become a free pass.

    The shallow case is the dangerous one: it fails in the generous direction
    without looking like a failure. A `--depth 1` clone reports every file as
    added by the graft commit, so *every* workflow reads as newborn and every
    silent cron gets excused — and `actions/checkout` clones depth 1 by default,
    so that is the normal state of a CI run rather than a corner case.
    """
    born: dict[str, str | None] = {}
    try:
        shallow = removals._git(  # noqa: SLF001 — one git caller in the package, reused
            root, "rev-parse", "--is-shallow-repository"
        )
        if shallow.strip() == "true":
            # A shallow clone shows every file as added by the graft commit, so
            # every workflow would look newborn and the allowance would excuse all
            # of them — the free pass this function exists to refuse.
            # `actions/checkout` clones depth 1 by default, which is exactly where
            # that would go unnoticed.
            return dict.fromkeys(files)
        for name in files:
            raw = removals._git(  # noqa: SLF001 — the same one, for the same reason
                root,
                "log",
                "--diff-filter=A",
                "--format=%aI",
                "--",
                f".github/workflows/{name}",
            )
            stamps = [line.strip() for line in raw.splitlines() if line.strip()]
            born[name] = stamps[-1] if stamps else None
    except RuntimeError:
        return dict.fromkeys(files)
    return born


def _waited_hours(born: dict[str, Any], name: str, moment: datetime.datetime) -> float | None:
    """How long since the file was added — `None` when its birthday is unknown."""
    birth = born.get(name)
    if birth is None:
        return None
    return (moment - datetime.datetime.fromisoformat(birth)).total_seconds() / 3600


def not_due_yet(
    schedules: dict[str, int],
    last: dict[str, Any],
    born: dict[str, Any],
    now: str,
    tolerance: int,
) -> list[str]:
    """Crons that have never fired *and* are too young to have been expected to.

    These are printed rather than counted, next to the rows no machine can check:
    a reader has to be able to see that the census knows about them, and the line
    says the date they stop being excused so nobody has to work it out later.
    """
    moment = datetime.datetime.fromisoformat(now)
    rows = []
    for name, hours in sorted(schedules.items()):
        if last.get(name) is not None:
            continue
        waited = _waited_hours(born, name, moment)
        if waited is None or waited > hours * tolerance:
            continue
        deadline = datetime.datetime.fromisoformat(born[name]) + datetime.timedelta(
            hours=hours * tolerance
        )
        rows.append(
            f"{name}: declared {waited / 24:.1f} days ago and has not come round yet — "
            f"red from {deadline:%Y-%m-%d %H:%M %Z} if it still has not fired by then"
        )
    return rows


def problems(
    schedules: dict[str, int],
    last: dict[str, Any],
    now: str,
    tolerance: int,
    born: dict[str, Any] | None = None,
) -> list[str]:
    """A schedule that stopped firing must be louder than one that never existed."""
    moment = datetime.datetime.fromisoformat(now)
    found = []
    for name, hours in sorted(schedules.items()):
        stamp = last.get(name)
        if stamp is None:
            waited = _waited_hours(born or {}, name, moment)
            if waited is not None and waited <= hours * tolerance:
                continue
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
        # An empty object is a usable answer here — "no scheduled run ever" —
        # and `problems()` already closes on it, so only the shape is held.
        state = history.read(
            args.input, lambda: fetch(list(schedules)), shape=dict, must_hold_something=False
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
    last = state.get("last_scheduled_run") or {}
    born = first_seen(pathlib.Path(args.root), list(schedules))
    found = problems(schedules, last, now, args.tolerance, born)

    for line in not_due_yet(schedules, last, born, now, args.tolerance):
        print(f"  declared but not due yet: {line}")

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
