"""Counting CI failures **including the ones a rerun erased from the record**.

The platform reports the conclusion of the **latest attempt only**. Press rerun
until it goes green and the original failure leaves the results at once, its only
trace an attempt nobody opens. Measured on a real repository: eleven visible
failures, **three more hidden underneath**.

The direction of that error matters more than its size. A rerun can turn a job
that *was* red back into one that was **never** red — and "never red" is what
decides both whether a gate carries evidence and whether a flaky-test review has
anything to look at.

**Classify by the failure's *message*, not by the step's name.** An early version
read only step names, and on a day the platform was genuinely down, a scanning
action failed four times inside its own setup step — where the real cause was the
platform answering 503. The counter read all four as ours. **A step name says
where it broke, not who broke it**; the signal that can say is the check run's
annotations.

Three classes, not two:

- `platform` — a clear trace of the world breaking (429/503, "no server is
  currently available", and the like), or a failure in the runner's own steps.
  Not ours to fix, so it must not ripen a flake threshold.
- `ours` — a failure in a step that is our own command, with a message that is
  not the platform's.
- `unclassified` — **everything else**: no annotation to read, or a failure
  inside somebody else's action with no trace of which side broke. This class
  exists so that what cannot be classified does not fall quietly into `ours`.
  Guessing in that direction ripens a flake threshold with things we cannot fix,
  which is the mistake the first version actually made.

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
import json
import pathlib
import re
import sys
from typing import TYPE_CHECKING, Any

import yaml

from verifiable_gates import gh, history, workflows

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "MESSAGES",
    "OURS",
    "PLATFORM",
    "UNKNOWN",
    "census",
    "classify",
    "collect",
    "evidence_proposals",
    "failing_tests",
    "gates_by_test_file",
    "harvest",
    "job_identity",
    "jobs_never_red",
    "main",
    "report",
    "report_evidence",
    "startup_failure",
    "unresolved_labels",
]

PLATFORM = "platform"
OURS = "ours"
UNKNOWN = "unclassified"

#: A job's log can be very large, so it gets a ceiling of its own rather than
#: sharing the one every other call to the API uses.
LOG_TIMEOUT_SECONDS = 180

#: Steps that belong to the runner rather than to any gate — failing in one of
#: these means the platform had trouble.
PLATFORM_STEPS = frozenset({"Set up job", "Set up runners", "Complete job"})

# Traces of the world breaking, collected from a real outage. **A status code
# always needs its HTTP context**, never a bare number: a project's own tests
# assert on 503 for a health endpoint, and a bare number would read our failure
# as the platform's — the same direction of error described at the top of this
# file.
PLATFORM_MESSAGES = re.compile(
    r"""(?ix)
      \bhttp/?[\d.]*\s* (?:error\s*)? (?:429|50[234])\b
    | \b(?:status|code)\b [^\n]{0,20} \b(?:429|50[234])\b
    | \b(?:429|50[234])\b \s* [:-]? \s*
      (?:too\ many\ requests|bad\ gateway|service\ unavailable|gateway\ time-?out)
    | too\ many\ requests
    | bad\ gateway
    | service\ unavailable
    | server\ error
    | no\ server\ is\ currently\ available
    | (?:api\ )?rate\ limit\ exceeded
    | you\ have\ exceeded\ a\ secondary\ rate\ limit
    """
)

# A step running somebody else's action — the name begins "Run <owner>/<name>@".
# Failing there without a platform message means it cannot be decided whether
# their server or our configuration broke, so a person has to read it.
THIRD_PARTY_STEP = re.compile(r"^Run [\w.-]+/[\w./-]+@")

#: The report is the whole product of this tool, so its wording is an input: a
#: project prints in the language its people read.
MESSAGES = {
    "class_platform": "platform",
    "class_ours": "ours",
    "class_unclassified": "needs reading",
    "no_jobs": "workflow file issue — this run created no jobs at all",
    "not_started": "{workflow} — never started",
    "unknown_workflow": "(unknown workflow)",
    "examined": "examined {count} runs",
    "visible": "  failed the way a run listing shows : {count}",
    "hidden": "  failed, then a rerun erased it      : {count}",
    "by_class": "  failures of kind {kind}: {count}",
    "unread": (
        "  ↳ {count} could not be classified by machine — read them before any of "
        "them counts toward a flake threshold"
    ),
    "hidden_mark": "  (hidden {count})",
    "strange_labels": (
        "\n**names that could not be resolved back to a job id** — their counts will "
        'not reach the "never red" side: {names}'
    ),
    "never_red": "\njobs that never went red in this window ({count}): {names}",
    "never_red_note": (
        "  note: {names} never went red on their own, but their workflow failed before "
        "creating a job {count} times — a different thing from 'nothing broke'"
    ),
    "never_red_footer": (
        "read this beside each gate's `guards:` before deciding a check should move to a schedule"
    ),
    "no_proposals": "\nno gate lacking evidence actually went red in this window",
    "proposals": "\ngates that went red in this window and still carry no evidence ({count}):",
    "proposal_date": "        date: <the date of that run>",
    "proposal_caught": (
        "        caught: <what it caught — write it yourself, do not paste a test name>"
    ),
    "proposals_footer": (
        "\n**read the log before accepting any row** — a test red because a fixture "
        "broke does not mean the gate caught a defect"
    ),
    "over_ceiling": (
        "\n{count} failures were erased by a rerun (ceiling {ceiling}) — read what went "
        "red before calling any of it flake"
    ),
    "cannot_read": (
        "cannot read the run history: {problem}\n**This must never become a silent "
        "skip** — a census that goes quiet when it cannot see reports a clean window "
        "on the day it can see nothing at all."
    ),
}


def _text(messages: Mapping[str, str] | None) -> dict[str, str]:
    return {**MESSAGES, **(messages or {})}


def classify(failure: Mapping[str, Any]) -> str:
    """Whose failure this one is — **read the message first, then where it fell**.

    The order matters: the message is evidence, the step name only context. What
    has neither must always leave through `unclassified`.
    """
    message = str(failure.get("message") or "").strip()
    if message and PLATFORM_MESSAGES.search(message):
        return PLATFORM
    if failure.get("step") in PLATFORM_STEPS:
        return PLATFORM
    if not message:
        return UNKNOWN
    if THIRD_PARTY_STEP.match(str(failure.get("step") or "")):
        return UNKNOWN
    return OURS


def _annotations(job: Mapping[str, Any]) -> str:
    """The failure messages from a job's check run — the evidence of who broke.

    **Unreadable must return empty, never raise** (scope too small, annotations
    expired, or the API itself down), letting that failure fall to
    `unclassified`. A census that dies because one job cannot be read is a census
    that cannot run while the platform is having trouble, which is exactly when
    it is wanted.
    """
    url = str(job.get("check_run_url") or "")
    if not url:
        return ""
    try:
        rows = gh.api(f"{url}/annotations")
    except (PermissionError, RuntimeError, json.JSONDecodeError) as problem:
        # Empty, never raised — but said: a ceiling reached here fell to
        # `unclassified` with no trace that it had (review, 2026-08-30).
        print(f"could not read annotations at {url}: {problem}", file=sys.stderr)
        return ""
    return " · ".join(
        str(row.get("message") or "")
        for row in rows
        if isinstance(row, dict) and row.get("annotation_level") == "failure"
    ).strip()


def startup_failure(
    run: Mapping[str, Any],
    failures: list[dict[str, Any]],
    *,
    messages: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """A run that failed **with no job failing at all** never started.

    A census walking failures job by job cannot see a run the platform rejected
    before creating any: it has zero jobs and **disappears from the count
    entirely**. What hid under that blind spot in practice: one workflow failing
    on every run for days, so a job that verifies the platform's own settings had
    never run once.

    Counted as ours, because the workflow file is ours.
    """
    if failures or run.get("conclusion") != "failure":
        return failures
    text = _text(messages)
    name = run.get("name") or text["unknown_workflow"]
    return [
        {
            "attempt": run.get("run_attempt", 1),
            "job": text["not_started"].format(workflow=name),
            "step": "",
            "message": text["no_jobs"],
        }
    ]


# The page ceiling lives with the wrapper now — one loop, not three.
PAGE_SIZE = gh.PAGE_SIZE


def _recent_runs(limit: int) -> list[dict[str, Any]]:
    """The most recent runs — paged by the wrapper, trimmed to `limit`."""
    return gh.api_pages("repos/:owner/:repo/actions/runs", limit=limit, key="workflow_runs")


def collect(limit: int, *, messages: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    """Recent runs with **every attempt a rerun replaced** — the part that needs the network."""
    records = []
    for run in _recent_runs(limit):
        attempt = run.get("run_attempt", 1)
        base = f"repos/:owner/:repo/actions/runs/{run['id']}"
        failures: list[dict[str, Any]] = []
        for n in range(1, attempt + 1):
            # The last attempt is read from /jobs; the replaced ones live under
            # /attempts/<n>/jobs, which is the only place they survive.
            jobs = gh.api(f"{base}/jobs" if n == attempt else f"{base}/attempts/{n}/jobs")
            for job in jobs["jobs"]:
                if job.get("conclusion") != "failure":
                    continue
                steps = [
                    s["name"] for s in job.get("steps", []) if s.get("conclusion") == "failure"
                ]
                failures.append(
                    {
                        "attempt": n,
                        "job": job["name"],
                        "step": steps[0] if steps else "",
                        "message": _annotations(job),
                        "job_id": job.get("id"),
                    }
                )
        records.append(
            {
                "id": run["id"],
                "attempt": attempt,
                "failures": startup_failure(run, failures, messages=messages),
            }
        )
    return records


def job_identity(
    directory: pathlib.Path,
) -> tuple[set[str], dict[str, str], dict[str, list[str]]]:
    """Every job id · a map from **check name** back to id · and the ids per file.

    **Why the map is needed**: the API returns the *check name*, which is the
    value of `name:` when a job declares one. A job declaring
    `name: dialect (${{ matrix.db.name }})` comes back as `dialect (mysql-8)`,
    while the side asking "which job never went red" reads ids from the workflow
    file. The two can never match, and the result is **one report saying
    `dialect` failed ten times and `dialects` never went red**.
    """
    ids: set[str] = set()
    by_name: dict[str, str] = {}
    by_path: dict[str, list[str]] = {}
    for name, workflow in workflows.all_workflows(directory).items():
        jobs = workflow.get("jobs") or {}
        ids |= set(jobs)
        by_path[f".github/workflows/{name}"] = sorted(jobs)
        for job_id, body in jobs.items():
            by_name[job_id] = job_id
            declared = (body or {}).get("name")
            if not declared:
                continue
            # Cut off the templated part of a matrix name, keeping what is fixed.
            static = str(declared).split("${{")[0].strip().rstrip("(").strip()
            if static:
                by_name[static] = job_id
    return ids, by_name, by_path


def census(
    records: list[dict[str, Any]], by_name: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """What really failed — what a rerun erased still counts.

    `visible` failed in the last attempt, which is what a run listing shows;
    `hidden` failed in an earlier one and was rerun into green, which is what
    disappears.

    `by_name` turns the **check name** the API returns back into a **job id**,
    and must always be passed in real use, or this side keys on something else
    than the "never red" side does.
    """
    by_job: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    runs = {"visible": 0, "hidden": 0}
    classes: collections.Counter[str] = collections.Counter()

    for record in records:
        last = record.get("attempt", 1)
        seen = set()
        for failure in record.get("failures", []):
            where = "visible" if failure.get("attempt", 1) >= last else "hidden"
            label = str(failure.get("job", "?")).split(" (")[0]
            job = (by_name or {}).get(label, label)
            by_job[job][where] += 1
            classes[classify(failure)] += 1
            seen.add(where)
        for where in seen:
            runs[where] += 1

    return {
        "runs_examined": len(records),
        "runs_failed_visible": runs["visible"],
        "runs_failed_hidden": runs["hidden"],
        "failures_by_class": dict(classes),
        "jobs": {job: dict(counts) for job, counts in sorted(by_job.items())},
    }


def unresolved_labels(
    summary: Mapping[str, Any],
    ids: set[str],
    *,
    messages: Mapping[str, str] | None = None,
) -> list[str]:
    """Names that carry a count but resolve to no job id.

    Such a name falls quietly onto the "never red" side. A run that never started
    is named after its workflow, so it does not count as a strange name.
    """
    marker = _text(messages)["not_started"].format(workflow="")
    return sorted(
        label for label in summary["jobs"] if label not in ids and marker.strip() not in label
    )


def jobs_never_red(summary: Mapping[str, Any], defined: set[str]) -> list[str]:
    """Jobs that never went red in this window — half of "is this check still worth it".

    The other half is what each gate declares it guards: **never red because
    nobody touched what it guards** is a different answer from **never red though
    that code changes every week**.
    """
    return sorted(defined - set(summary["jobs"]))


# The line a test runner prints in its summary: "FAILED tests/test_x.py::test_y".
PYTEST_FAILED = re.compile(r"^FAILED\s+(tests/[\w/]+\.py)::", re.MULTILINE)


def failing_tests(log: str) -> set[str]:
    """The test files that went red in one log — **evidence a gate just caught something**.

    A gate is supposed to carry proof it once went red on a real defect. That
    proof is created every time CI goes red, and then leaves with the log. This
    picks it up before it goes.
    """
    return set(PYTEST_FAILED.findall(log))


def gates_by_test_file(gates: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Test file → the gate it enforces."""
    return {path: gate for gate in gates for path in gate.get("enforced_by", {}).get("tests", [])}


def evidence_proposals(
    records: list[dict[str, Any]], gates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Proposed evidence rows drawn from real redness — **proposed, not written**.

    Deciding whether a failure *proves* anything is a person's work: a test can
    go red because a fixture broke rather than because the gate caught a defect.
    So the tool stops at proposing, and only for gates that carry no evidence
    yet, since the ones that do need no more.
    """
    owners = gates_by_test_file(gates)
    found: dict[str, dict[str, Any]] = {}
    for record in records:
        for failure in record.get("failures", []):
            if classify(failure) != OURS:
                continue
            for path in sorted(failure.get("tests", [])):
                gate = owners.get(path)
                if gate is None or gate.get("proved_by"):
                    continue
                entry = found.setdefault(
                    gate["id"], {"gate": gate["id"], "run": record["id"], "tests": set()}
                )
                entry["tests"].add(path)
    return [
        {**entry, "tests": sorted(entry["tests"])}
        for entry in sorted(found.values(), key=lambda e: str(e["gate"]))
    ]


def _job_log(job_id: object) -> str:
    """One job's log — expired or unreadable returns empty rather than killing the census."""
    if not job_id:
        return ""
    try:
        return gh.run(
            [
                "api",
                "--allow-escape-sequences",
                f"repos/:owner/:repo/actions/jobs/{job_id}/logs",
            ],
            timeout=LOG_TIMEOUT_SECONDS,
        )
    except (PermissionError, RuntimeError) as problem:
        print(f"could not read the log of job {job_id}: {problem}", file=sys.stderr)
        return ""


def harvest(records: list[dict[str, Any]]) -> None:
    """Fill in which test files went red for each failure (the part that needs the network)."""
    for record in records:
        for failure in record.get("failures", []):
            if classify(failure) == OURS and "tests" not in failure:
                failure["tests"] = sorted(failing_tests(_job_log(failure.get("job_id"))))


def report_evidence(
    proposals: list[dict[str, Any]], *, messages: Mapping[str, str] | None = None
) -> None:
    """Print rows ready to drop into the registry — a person decides whether to take them."""
    text = _text(messages)
    if not proposals:
        print(text["no_proposals"])
        return
    print(text["proposals"].format(count=len(proposals)))
    for proposal in proposals:
        print(f"\n  # {proposal['gate']} — from {', '.join(proposal['tests'])}")
        print("    proved_by:")
        print("      - kind: ci-red")
        print(f"        ref: run/{proposal['run']}")
        print(text["proposal_date"])
        print(text["proposal_caught"])
    print(text["proposals_footer"])


def report(summary: Mapping[str, Any], *, messages: Mapping[str, str] | None = None) -> None:
    """Print for a person — what was hidden has to stand out more than what everyone sees."""
    text = _text(messages)
    print(text["examined"].format(count=summary["runs_examined"]))
    print(text["visible"].format(count=summary["runs_failed_visible"]))
    print(text["hidden"].format(count=summary["runs_failed_hidden"]))
    for kind, count in sorted(summary["failures_by_class"].items()):
        print(text["by_class"].format(kind=text.get(f"class_{kind}", kind), count=count))
    unread = summary["failures_by_class"].get(UNKNOWN, 0)
    if unread:
        print(text["unread"].format(count=unread))
    for job, counts in summary["jobs"].items():
        hidden = counts.get("hidden", 0)
        mark = text["hidden_mark"].format(count=hidden) if hidden else ""
        print(f"    {job}: {counts.get('visible', 0)}{mark}")


def _never_red(
    summary: Mapping[str, Any],
    ids: set[str],
    by_path: Mapping[str, list[str]],
    text: Mapping[str, str],
) -> None:
    """The "never red" tail of the report, including runs that failed before any job."""
    # No guard against a job appearing in both lists, because there cannot be
    # one: `jobs_never_red` is set subtraction against the very dictionary
    # printed above. An earlier version asserted it anyway, and no input could
    # reach that assertion — a check nothing can trigger is not a check, it is a
    # line that makes a reader believe something is being watched.
    never = jobs_never_red(summary, ids)
    print(text["never_red"].format(count=len(never), names=", ".join(never)))
    for label, count in sorted(summary["jobs"].items()):
        owned = by_path.get(label.split(" — ")[0], [])
        silent = [job for job in owned if job in never]
        if silent:
            print(text["never_red_note"].format(names=", ".join(silent), count=sum(count.values())))
    print(text["never_red_footer"])


def main(argv: list[str] | None = None, *, messages: Mapping[str, str] | None = None) -> int:
    """Fetch (or read a file) → summarise → print · returns 1 over the ceiling."""
    parser = argparse.ArgumentParser(description="Census of CI failures, reruns included.")
    parser.add_argument("--root", default=".", help="the project to read (default: here)")
    parser.add_argument(
        "--registry", default=None, help="the gate registry (default: <root>/gates.yaml)"
    )
    parser.add_argument("--limit", type=int, default=100, help="how many runs to examine")
    parser.add_argument("--input", help="a JSON file of records (offline)")
    parser.add_argument("--json", action="store_true", help="print the summary as JSON")
    parser.add_argument(
        "--never-red", action="store_true", help="end with the jobs that never went red"
    )
    parser.add_argument(
        "--evidence", action="store_true", help="propose evidence rows for gates that went red"
    )
    parser.add_argument(
        "--max-hidden",
        type=int,
        default=None,
        help="ceiling on failures a rerun erased — over it, exit 1",
    )
    args = parser.parse_args(argv)

    text = _text(messages)
    root = pathlib.Path(args.root)
    registry = pathlib.Path(args.registry) if args.registry else root / "gates.yaml"

    try:
        # Zero runs is not a clean window — it is a window nobody looked through.
        records = history.read(
            args.input,
            lambda: collect(args.limit, messages=messages),
            shape=list,
            must_hold_something=True,
            fields={"id": (int, str), "failures": (list,), "?attempt": (int,)},
        )
    except (PermissionError, RuntimeError) as problem:
        print(text["cannot_read"].format(problem=problem), file=sys.stderr)
        return 2

    if args.evidence:
        if not args.input:
            harvest(records)
        gates = yaml.safe_load(registry.read_text(encoding="utf-8"))["gates"]
        report_evidence(evidence_proposals(records, gates), messages=messages)

    ids, by_name, by_path = job_identity(workflows.workflow_dir(root))
    summary = census(records, by_name)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        report(summary, messages=messages)

    strange = unresolved_labels(summary, ids, messages=messages)
    if strange:
        print(text["strange_labels"].format(names=strange), file=sys.stderr)

    if args.never_red:
        _never_red(summary, ids, by_path, text)

    if args.max_hidden is not None and summary["runs_failed_hidden"] > args.max_hidden:
        print(
            text["over_ceiling"].format(
                count=summary["runs_failed_hidden"], ceiling=args.max_hidden
            ),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
