"""Every advisory has been judged, and every judgement still describes something real.

A vulnerability scanner that fails on anything it finds gets switched off. Some
findings genuinely cannot be acted on — a pinned transitive dependency the
upstream has not moved, a distribution patch that does not exist yet — and a
check that is red from its first day and red forever is a check somebody silences
inside a fortnight, taking the real findings with it.

So the rule is not "no findings". It is **every finding has been decided about**,
and a register of accepted ones is what makes a decision something a reader can
check.

That register has to be held **both ways**, and the second way is the one that
gets forgotten:

- **A finding nobody has entered** is the obvious direction.
- **An entry describing a finding that no longer appears** is the quiet one. The
  tools themselves are silent about it — `--ignore-vuln` never mentions an id it
  did not need — so an entry outlives its subject and sits there excusing
  nothing, until the day it silently excuses something real. The reference
  implementation found exactly that: entries kept for a scanner's pinned
  dependency, still listed long after the pin moved.

**Where the findings come from is a format, not a project.** The readers here
turn each tool's report into the same shape — id → one line a person can read —
so a project chooses its scanners and this decides the same way about all of them.

Two of those readers carry a lesson worth keeping:

- **A package audit groups by affected package, not by advisory.** Counting the
  headlines gives six where the cause is one, and a register then grows with the
  number of packages that happen to depend on each other rather than with the
  number of things anybody decided.
- **The advisory id has to be the public one**, never a registry's internal
  number: a reader of the register must be able to look the entry up.

Role: decider — it answers pass or fail. Running the scanners belongs to the
caller; this is handed their reports.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

__all__ = [
    "MESSAGES",
    "accepted",
    "from_npm_audit",
    "from_pip_audit",
    "from_trivy",
    "main",
    "problems",
]

MESSAGES = {
    "unjudged": (
        "{id} — {detail} · nobody has decided about this yet: upgrade it if you can, "
        "otherwise enter it in the register with the reason"
    ),
    "stale": (
        "{id} — the register accepts this and no scan reports it any more · take the line "
        "out: a register nobody prunes becomes one that silences something real"
    ),
}


def accepted(path: pathlib.Path) -> dict[str, str]:
    """Advisory id → the reason it was accepted, from a register on disk.

    One id per line, with the reason after a `#`. Blank lines and whole-line
    comments are skipped, so the file can carry its own preamble.
    """
    entries = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        body = line.strip()
        if not body or body.startswith("#"):
            continue
        name, _, why = body.partition("#")
        entries[name.strip()] = why.strip()
    return entries


def problems(
    found: dict[str, str],
    register: dict[str, str],
    messages: dict[str, str] | None = None,
) -> list[str]:
    """Both directions at once — unjudged findings, and entries with nothing left to excuse."""
    text = {**MESSAGES, **(messages or {})}
    lines = [
        text["unjudged"].format(id=name, detail=found[name])
        for name in sorted(found.keys() - register.keys())
    ]
    lines += [text["stale"].format(id=name) for name in sorted(register.keys() - found.keys())]
    return lines


def _fix_versions(vuln: dict[str, Any]) -> str:
    """**"none yet" and "one exists but we cannot take it" are different facts.**

    The first is waiting on somebody else; the second means the way out is here
    and something on this side is in the way. Collapsing them hides which.
    """
    return ", ".join(vuln.get("fix_versions") or []) or "none yet"


def from_pip_audit(report: dict[str, Any]) -> dict[str, str]:
    """Findings from a `pip-audit --format json` report.

    **Run the tool without its own ignore list.** Everything it found has to be
    visible here, or the register cannot be checked in the second direction at
    all — the tool would hide exactly the entries that have gone stale.

    **Strict about the id, forgiving about the rest.** The id is what the register
    is keyed on and a missing one is a finding lost; the package name and version
    are a line for a person to read, and a report that omits one should not stop
    the check that would have caught the finding.
    """
    return {
        vuln["id"]: (
            f"{dep.get('name', '?')}=={dep.get('version', '?')} (fix: {_fix_versions(vuln)})"
        )
        for dep in report.get("dependencies") or []
        for vuln in dep.get("vulns") or []
    }


def _advisory_id(via: dict[str, Any]) -> str:
    """The public advisory id, taken from its URL.

    **Never the registry's numeric `source`.** That is an internal identifier
    nobody can look up, and a register full of them cannot be read by the person
    who has to decide whether an entry still makes sense.
    """
    url = str(via.get("url") or "")
    _, marker, tail = url.partition("/advisories/")
    return tail if marker and tail else (url or str(via.get("name")))


def from_npm_audit(report: dict[str, Any]) -> dict[str, str]:
    """Findings from an `npm audit --json` report.

    The report is grouped **by affected package, not by advisory**: an entry's
    `via` holds objects for the advisories themselves and plain strings for "this
    came in through that one". Counting the headline entries gives six where the
    cause is one, and the register then tracks how packages happen to depend on
    each other rather than what anybody decided.
    """
    return {
        _advisory_id(via): f"{via.get('name')}{via.get('range', '')} ({via.get('severity', '?')})"
        for entry in (report.get("vulnerabilities") or {}).values()
        for via in entry.get("via") or []
        if isinstance(via, dict)
    }


def from_trivy(report: dict[str, Any]) -> dict[str, str]:
    """Findings from a `trivy --format json` report.

    **Every row in the report counts**, with no filtering here. Severity and
    whether a fix exists are decided once, where the scanner is invoked — a filter
    in two places is a filter that will one day disagree with itself.
    """
    rows = {}
    for result in report.get("Results") or []:
        for vuln in result.get("Vulnerabilities") or []:
            severity = vuln.get("Severity", "?")
            fixed = vuln.get("FixedVersion") or "?"
            rows[vuln["VulnerabilityID"]] = f"{vuln.get('PkgName', '?')} ({severity}, fix: {fixed})"
    return rows


READERS = {"pip-audit": from_pip_audit, "npm-audit": from_npm_audit, "trivy": from_trivy}


def main(argv: list[str] | None = None) -> int:
    """Decide one report against one register — exit 1 on anything unjudged or stale.

    This repository shipped the decider for others and audited nothing of its own
    (found 2026-08-29). The command reads a report a scanner already wrote, so
    the scanner's own exit code never decides: `pip-audit` red on a finding that
    has been judged is the check somebody silences.
    """
    parser = argparse.ArgumentParser(description="Every advisory judged, every judgement real.")
    parser.add_argument("--report", required=True, help="the scanner's JSON report")
    parser.add_argument("--kind", choices=sorted(READERS), required=True, help="which scanner")
    parser.add_argument("--register", required=True, help="accepted advisories, one id per line")
    args = parser.parse_args(argv)

    report = json.loads(pathlib.Path(args.report).read_text(encoding="utf-8"))
    found = READERS[args.kind](report)
    register = accepted(pathlib.Path(args.register))
    lines = problems(found, register)
    for line in lines:
        print(line, file=sys.stderr)
    if lines:
        return 1
    print(f"{len(found)} finding(s), every one judged; {len(register)} accepted, none stale")
    return 0


if __name__ == "__main__":
    sys.exit(main())
