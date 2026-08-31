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
        return {"status": "pass", "seconds": seconds}

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

    log_path = root / ROUND_LOG
    previous = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    record = {"round": len(previous) + 1, "counts": counts, "failed": [r["gate"] for r in failed]}
    log_path.write_text("\n".join([*previous, json.dumps(record, ensure_ascii=False)]) + "\n")

    if args.output:
        args.output.write_text(
            json.dumps({"round": record["round"], "results": results}, ensure_ascii=False, indent=1)
        )

    summary = f"{counts['pass']} pass · {counts['fail']} fail · {counts['skip']} skip"
    print(f"round {record['round']}: {summary}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
