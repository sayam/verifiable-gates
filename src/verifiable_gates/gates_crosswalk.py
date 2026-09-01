"""A crosswalk between gates and the standard's requirements they *actually* back.

Linking two registries (the gate index and the assessment worksheet) by writing
both sides by hand creates a third place for them to drift. So this is
**derived one way from the evidence that already exists**: a worksheet row whose
evidence cites a test file or a `ci:job` is mapped back to the gate that owns
that file or job, through the registry's partition — every test file belongs to
exactly one gate, so the mapping cannot be ambiguous.

The deliberate by-product: it is plain which rows **pass by a gate that runs on
every push** and which **pass by an argument or a document** (evidence is an
ADR or a source file; nothing runs). Those are two levels of confidence, and a
reader should see the difference without walking the rows.

Role: generator — the evidence is that the committed file equals the render.
"""

from __future__ import annotations

import dataclasses
import re
import sys
from typing import Any

from verifiable_gates.asvs_worksheet import CELLS, ROW, assessment_part

__all__ = ["JOB_REF", "ROW", "TEST_REF", "Words", "crosswalk", "gate_lookups", "passed_rows"]

# Evidence conventions of the worksheet: a test file, optionally `::name`, and a job.
TEST_REF = re.compile(r"`(tests/test_\w+\.py)(?:::\w+)?`")
JOB_REF = re.compile(r"`ci:([a-z0-9-]+)`")


@dataclasses.dataclass(frozen=True)
class Words:
    """The rendered document's own wording — supplied by the project, not invented here."""

    header: str
    """Everything above the summary line, including the trailing newline."""
    summary: str
    """Format string with `{rows}`, `{backed}` and `{unbacked}`."""
    backed_title: str
    table_head: str
    unbacked_title: str
    unbacked_note: str


def passed_rows(text: str, *, marker: str, passed: str) -> dict[str, str]:
    """Rows judged as passing → their raw evidence cell.

    Raises `ValueError` when the document has no marker (its shape changed) or
    when no row passes at all (the reader is broken, or the document is) — both
    are cases where an empty crosswalk would read as "nothing is backed".
    """
    if marker not in text:
        raise ValueError("the worksheet has no assessment marker — its shape has changed")
    found: dict[str, str] = {}
    for line in assessment_part(text, marker).splitlines():
        if not ROW.match(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == CELLS and cells[3] == passed:
            found[cells[0]] = cells[4]
    if not found:
        raise ValueError("no passing row at all — is the reader broken?")
    return found


def gate_lookups(gates: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, list[str]]]:
    """(test file → gate id, job → gate ids of kind job/step on that job).

    Gates of kind `test` are not counted on the job side: every one of them sits
    on the `test` job, and mapping `ci:test` to all of them would make the
    crosswalk noise rather than information.
    """
    by_file: dict[str, str] = {}
    by_job: dict[str, list[str]] = {}
    for gate in gates:
        for path in gate["enforced_by"].get("tests") or []:
            by_file[path] = gate["id"]
        if gate["kind"] in ("job", "step"):
            by_job.setdefault(gate["enforced_by"]["job"], []).append(gate["id"])
    return by_file, {job: sorted(ids) for job, ids in by_job.items()}


def _version_key(requirement_id: str) -> tuple[int, ...]:
    return tuple(int(part) for part in requirement_id[1:].split("."))


def crosswalk(
    rows: dict[str, str],
    by_file: dict[str, str],
    by_job: dict[str, list[str]],
    *,
    words: Words,
) -> str:
    """The whole document — every list sorted, so the render repeats byte for byte."""
    gate_rows: dict[str, set[str]] = {}
    unbacked: list[str] = []
    for requirement_id, evidence in rows.items():
        supported = {by_file[f] for f in TEST_REF.findall(evidence) if f in by_file}
        for job in JOB_REF.findall(evidence):
            supported.update(by_job.get(job, []))
        if supported:
            for gate_id in supported:
                gate_rows.setdefault(gate_id, set()).add(requirement_id)
        else:
            unbacked.append(requirement_id)

    lines = [words.header]
    lines.append(
        words.summary.format(
            rows=len(rows), backed=len(rows) - len(unbacked), unbacked=len(unbacked)
        )
    )
    lines.append(words.backed_title)
    lines.append(words.table_head)
    lines.append("|---|---|")
    lines.extend(
        f"| `{gate_id}` | {' · '.join(sorted(gate_rows[gate_id], key=_version_key))} |"
        for gate_id in sorted(gate_rows)
    )
    lines.append("")
    lines.append(words.unbacked_title)
    lines.append(words.unbacked_note)
    lines.append(" · ".join(sorted(unbacked, key=_version_key)))
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    # A helper is not a command. Run as one, these modules imported cleanly and exited 0
    # with nothing done — a wrong call that looked like a pass, which `gates.yaml` forbids
    # in as many words ("A misuse must exit 2, never 0"). Round 11 gave seven modules this
    # guard from a list written by hand, and the list was seven short (self-audit round 12,
    # 2026-09-01); the test now reads the package instead of remembering it.
    sys.stderr.write(
        "verifiable_gates.gates_crosswalk is a helper, not a command — it has no entry point of\n"
        "its own; the readers that answer for themselves are listed in CONTRIBUTING.\n"
    )
    sys.exit(2)
