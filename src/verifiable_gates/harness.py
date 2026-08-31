"""A fail-fix harness — run the gates and answer in something a machine can read.

This is what turns a checklist into a loop: change the code, run the harness, get
back `(gate id, cause, hint)`, fix, repeat until it passes. Rounds are counted, so
which gate keeps failing is a fact rather than an impression.

**The scope is stated rather than implied.** The harness runs gates of kind
`test`, which is what a code-editing loop collides with most. Gates of kind `job`
or `step` are reported as **skipped with a reason** — never silently — because
their commands live in the workflow, and copying them here would create the second
copy that drifts. Those are decided in CI, which every pull request goes through
anyway.

The `hint` on a failure is the gate's `born_from`: the trap that produced the
rule. A loop that knows only *what* broke will satisfy the letter of a check; one
that knows *what the rule was protecting* has a chance of fixing the cause.

Role: reader — it runs gates and reports their answers machine-readably. It
decides nothing itself; the gates it runs do.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import time
from typing import Any

import yaml

from verifiable_gates import registry

__all__ = ["ROUND_LOG", "main", "run_all", "run_test_gate"]

# **A ceiling on anything we launch.** `subprocess.run` without a timeout waits
# forever, which in CI is a job that never ends.
GATE_TIMEOUT_SECONDS = 1800  # one gate is a subset of the suite, not the whole of it

ROUND_LOG = ".gate-rounds.jsonl"  # per-machine notes; belongs in .gitignore
CAUSE_LINES = 12  # enough to point at the failure without carrying the whole log


RAN = re.compile(r"(?<![\w.])(\d+) (?:passed|failed)(?![\w.])")


def _ran_or_not(output: str, seconds: float) -> dict[str, Any]:
    """A pass, or the third answer when pytest ran nothing it collected.

    pytest exits 0 when every test it collected was skipped, so a gate whose tests
    are all `pytest.mark.skip` came back `pass` — enforcement that did not happen,
    reported as enforcement that held. The whole suite and the coverage floor stayed
    green beside it, because the lines those tests cover are reached by others
    (self-audit round 4, 2026-09-01; observed and unfiled in round 1, ledger L-0036).
    A file with no test in it at all is already a fail: pytest exits 5 for that.
    """
    if any(int(count) for count in RAN.findall(output)):
        return {"status": "pass", "seconds": seconds}
    tail = [line for line in output.splitlines() if line.strip()][-1:]
    return {
        "status": "fail",
        "seconds": seconds,
        "cause": "no test ran — every test this gate names was skipped: " + " ".join(tail),
    }


def run_test_gate(gate: dict[str, Any], root: pathlib.Path) -> dict[str, Any]:
    """Run one gate's tests in the given tree, and say why if it failed."""
    files = gate["enforced_by"]["tests"]
    started = time.monotonic()
    try:
        result = subprocess.run(  # noqa: S603 — same interpreter, paths from a checked registry
            [sys.executable, "-m", "pytest", "-q", "--no-header", *files],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=GATE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        # A hung gate is a red answer, not a traceback — the loop can act on a
        # cause; it cannot act on `TimeoutExpired` (outside audit, 2026-08-31).
        seconds = round(time.monotonic() - started, 2)
        cause = f"timed out after {GATE_TIMEOUT_SECONDS}s — the gate never answered"
        return {"status": "fail", "seconds": seconds, "cause": cause}
    seconds = round(time.monotonic() - started, 2)
    if result.returncode == 0:
        return _ran_or_not(result.stdout, seconds)

    # The cause is the tail of pytest's own output — the summary and the last
    # assertion. Enough for the loop to know where to look, without a report that
    # nobody reads because it carries everything.
    tail = [line for line in result.stdout.splitlines() if line.strip()][-CAUSE_LINES:]
    return {"status": "fail", "seconds": seconds, "cause": "\n".join(tail)}


def run_all(
    gates: list[dict[str, Any]], root: pathlib.Path, only: set[str]
) -> list[dict[str, Any]]:
    """Walk the gates in registry order. Skips are reported, never silent."""
    results = []
    for gate in gates:
        if only and gate["id"] not in only:
            continue
        entry: dict[str, Any] = {"gate": gate["id"], "kind": gate["kind"]}
        if gate["kind"] != "test":
            requires = ", ".join(gate.get("requires") or []) or "a CI environment"
            entry |= {
                "status": "skip",
                "cause": f"enforced by CI job `{gate['enforced_by']['job']}` — needs {requires}",
            }
        else:
            entry |= run_test_gate(gate, root)
            if entry["status"] == "fail":
                entry["hint"] = " ".join(str(gate.get("born_from", "")).split())
        results.append(entry)
    return results


def _note_the_round(
    root: pathlib.Path, counts: dict[str, int], failed: list[dict[str, Any]]
) -> dict[str, Any]:
    """Add this round to the per-machine notes, and never let the notes decide the verdict.

    The notes were written without a guard, so a checkout mounted read-only — or a
    `.gate-rounds.jsonl` that is a directory — ended the run with a raw `PermissionError`
    and exit 1 *after every gate had passed*: a red that reads as a broken gate and sends
    the next person hunting for one (self-audit round 5, 2026-09-01). The gates' answer
    is the gates' answer; a failure to keep notes about it is said out loud and changes
    nothing.
    """
    log_path = root / ROUND_LOG
    try:
        previous = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    except OSError:
        previous = []
    record = {"round": len(previous) + 1, "counts": counts, "failed": [r["gate"] for r in failed]}
    try:
        log_path.write_text("\n".join([*previous, json.dumps(record, ensure_ascii=False)]) + "\n")
    except OSError as problem:
        print(f"could not write the round notes: {problem}", file=sys.stderr)
    return record


def _write_report(output: pathlib.Path, round_number: int, results: list[dict[str, Any]]) -> bool:
    """The report the caller asked for, or a misuse said plainly.

    Unlike the notes, this file was asked for by name: not producing it is a call that
    could not be answered, which is exit 2 — not exit 1, which would say the gates failed.
    """
    try:
        output.write_text(
            json.dumps({"round": round_number, "results": results}, ensure_ascii=False, indent=1)
        )
    except OSError as problem:
        print(f"cannot write the report: {output}: {problem}", file=sys.stderr)
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    """One round: run, print, record, and exit according to the result."""
    parser = argparse.ArgumentParser(description="Run the gates and report machine-readably.")
    parser.add_argument("--registry", type=pathlib.Path, default=pathlib.Path("gates.yaml"))
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path())
    parser.add_argument("--only", action="append", default=[], metavar="GATE_ID")
    parser.add_argument("--output", type=pathlib.Path, help="write the full report here as JSON")
    args = parser.parse_args(argv)

    try:
        gates = registry.load(args.registry)
    except (TypeError, ValueError, OSError, yaml.YAMLError) as error:
        # …and YAML the parser rejects, or a file that is not there, are the same
        # misuse — each was a traceback with exit 1 before (self-audit, 2026-08-31).
        # An index the harness cannot read is a misuse (exit 2) — not a pass, and
        # not a traceback whose exit code is whatever the interpreter made of it.
        print(f"cannot read the registry: {error}", file=sys.stderr)
        return 2
    known = {gate["id"] for gate in gates}
    unknown = sorted(set(args.only) - known)
    if unknown:
        print(f"no such gate: {unknown}", file=sys.stderr)
        return 2

    root = args.root.resolve()
    results = run_all(gates, root, set(args.only))

    counts = {
        status: sum(1 for r in results if r["status"] == status)
        for status in ("pass", "fail", "skip")
    }
    failed = [r for r in results if r["status"] == "fail"]
    for entry in failed:
        print(f"[FAIL] {entry['gate']}")
        print("   " + entry["cause"].replace("\n", "\n   "))
        if entry.get("hint"):
            print(f"   hint: {entry['hint']}")

    record = _note_the_round(root, counts, failed)

    if args.output and not _write_report(args.output, record["round"], results):
        return 2

    summary = f"{counts['pass']} pass · {counts['fail']} fail · {counts['skip']} skip"
    print(f"round {record['round']}: {summary}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
