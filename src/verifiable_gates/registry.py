"""The gate-registry schema — the one thing every later stage depends on.

A registry is an *index*, not a *source*: the things that actually enforce
anything are the tests and CI jobs it points at. So this module has exactly one
job — **say whether a registry file has a shape a machine can read**. Whether a
row still matches reality is the job of the checkers that arrive in stages 2–3,
and they read from here.

The four rules below are not tidiness. Each came from a trap that was paid for
in the reference implementation:

- **`layer` and `portable` must not contradict each other.** A rule at layer
  `internal` is tied to one project's architecture; exporting it as universal is
  an overclaim (ADR 0042 — governance audit round 23 measured five rules
  carrying the wrong label).
- **An exported rule must name the trap that created it (`born_from`).** A rule
  with no origin is a rule nobody knows when to remove.
- **`proved_by` records that a gate has gone red on a real defect** (ADR 0059).
  A gate nobody has seen fail is indistinguishable from a gate that checks
  nothing.
- **The vocabularies are closed.** A value outside the set is a value nobody has
  ever decided the meaning of.

`problems()` returns a *list of problems* rather than raising, because every
caller wants to see all of them at once instead of the first one and a stop.

Role: decider — it answers whether a registry has a shape a machine can read.
Its evidence is a planted defect per rule, in `tests/test_registry.py`.
"""

from __future__ import annotations

import datetime
import pathlib
import re
from typing import Any

import yaml

__all__ = [
    "KINDS",
    "LAYERS",
    "PILLARS",
    "PROOF_KINDS",
    "PROOF_REF",
    "SCHEMA_VERSION",
    "SEVERITIES",
    "load",
    "problems",
]

SCHEMA_VERSION = 1

KINDS = frozenset({"test", "job", "step"})
SEVERITIES = frozenset({"blocking", "watched", "warning"})
LAYERS = frozenset({"baseline", "business", "internal"})
PILLARS = frozenset({"security", "performance", "manageability", "devx"})
PROOF_KINDS = frozenset({"ci-red", "mutation"})

REQUIRED = ("id", "title", "kind", "severity", "enforced_by", "layer", "pillar")
# Every key a gate may carry; one outside this set is refused, not skipped — a
# misspelt `proved_yb` is a gate with no evidence that looks like one with
# (outside audit, 2026-08-30: an unknown key drew no complaint).
KEYS = frozenset({*REQUIRED, "portable", "born_from", "proved_by", "watched_by"})
GATE_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# The shape of a `proved_by.ref`: `pr/N`, `run/N` or `commit/<hex>`, optionally
# prefixed with `owner/repo#` when the red was seen in another repository. A
# ref is the one thing that makes a proof checkable, so its shape is closed —
# an outside audit on 2026-08-29 wrote `ref: trust me` and `date: 9999-99-99`
# into a row and both passed a schema that read only "non-empty" and "ten
# characters with dashes". The repository prefix exists for the same reader:
# a bare `pr/151` that is not here has nothing in it saying where to look.
PROOF_REF = re.compile(
    r"^(?:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#)?(?:(?:pr|run)/[1-9][0-9]*|commit/[0-9a-f]{7,40})$"
)


def load(path: str | pathlib.Path) -> list[dict[str, Any]]:
    """Read a registry file: raise if it is unusable, return its gates if it is.

    "Unusable" and "usable but with bad rows" are different failures. The first
    means the file cannot be worked with at all, so it raises. The second is a
    report, and that is what `problems()` is for.
    """
    raw = yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"{path}: a registry must be a mapping with 'version' and 'gates'")
    if raw.get("version") != SCHEMA_VERSION:
        raise ValueError(f"{path}: version must be {SCHEMA_VERSION}, got {raw.get('version')!r}")
    gates = raw.get("gates")
    # `gates: []` is the empty registry, and a correct state. A file with no
    # `gates` key at all is not — `rules.load` and the shipped registry scanner
    # both refuse it, and this reader used to hand back `[]` for it, so an index
    # that had lost its list looked like one that was empty on purpose. A row
    # that is not a mapping used to be dropped on the floor for the same reason:
    # `problems()` never saw it (outside audit, 2026-08-29).
    if not isinstance(gates, list):
        raise TypeError(f"{path}: 'gates' must be a list, got {type(gates).__name__}")
    for index, gate in enumerate(gates):
        if not isinstance(gate, dict):
            raise TypeError(f"{path}: gates[{index}] must be a mapping, got {type(gate).__name__}")
    return gates


def _as_date(value: object) -> datetime.date | None:
    """A real calendar date written YYYY-MM-DD — `9999-99-99` has the shape and is not one.

    PyYAML already turns an unquoted `2026-08-29` into a `datetime.date`, so a
    date object is one that parsed; what arrives as a string did not.
    """
    if isinstance(value, datetime.date):
        return value
    if not isinstance(value, str) or len(value) != len("YYYY-MM-DD"):
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def _latest_today(now: datetime.datetime | None = None) -> datetime.date:
    """The date it already is somewhere on Earth (UTC+14) — a proof written today in
    Bangkok at 02:00 is dated tomorrow in UTC, and that is not a proof from the future.
    """
    now = now or datetime.datetime.now(datetime.UTC)
    return (now + datetime.timedelta(hours=14)).date()


def _proof_problems(where: str, proofs: Any) -> list[str]:  # noqa: ANN401 — shape is what we check
    if not isinstance(proofs, list):
        return [f"{where}: proved_by must be a list"]
    found: list[str] = []
    for index, proof in enumerate(proofs):
        at = f"{where}: proved_by[{index}]"
        if not isinstance(proof, dict):
            found.append(f"{at} must be a mapping")
            continue
        if proof.get("kind") not in PROOF_KINDS:
            found.append(f"{at} kind {proof.get('kind')!r} is not one of {sorted(PROOF_KINDS)}")
        ref = str(proof.get("ref", "")).strip()
        if not ref:
            found.append(f"{at} has no ref — evidence that points nowhere is not evidence")
        elif not PROOF_REF.match(ref):
            found.append(
                f"{at} ref {ref!r} is not pr/N, run/N or commit/<sha>, optionally "
                "behind owner/repo# — a ref nobody can look up is not evidence"
            )
        date = _as_date(proof.get("date"))
        if date is None:
            found.append(f"{at} date must be a real YYYY-MM-DD date, got {proof.get('date')!r}")
        elif date > _latest_today():
            # An outside audit on 2026-08-30 wrote `date: 2099-01-01` and the
            # schema took it: evidence that has not happened yet is not evidence.
            found.append(f"{at} date {date.isoformat()} has not happened yet")
        if not str(proof.get("caught", "")).strip():
            found.append(
                f"{at} caught is empty — evidence that does not say what it proved is unusable"
            )
    return found


def _vocabulary_problems(gate_id: str, gate: dict[str, Any]) -> list[str]:
    """Every closed vocabulary — a value outside the set has no agreed meaning."""
    closed = (("kind", KINDS), ("severity", SEVERITIES), ("layer", LAYERS), ("pillar", PILLARS))
    return [
        f"{gate_id}: {field} {gate.get(field)!r} is not one of {sorted(allowed)}"
        for field, allowed in closed
        if gate.get(field) not in allowed
    ]


def _enforcement_problems(gate_id: str, gate: dict[str, Any]) -> list[str]:
    """`kind` and `enforced_by` have to describe the same enforcement.

    `kind` is not a label: the harness runs a gate only while it reads `test`, and
    the shipped scanner checks that the named files exist only for the same value.
    A gate that lists `tests:` under any other kind is one whose test files nothing
    runs and nothing looks for — the harness reported it as "skip, needs CI" and
    every reader stayed green (self-audit round 2, 2026-08-31: one word changed on
    one row took the harness from 43 pass · 11 skip to 42 · 12, exit 0 throughout).
    """
    enforced = gate.get("enforced_by")
    if not isinstance(enforced, dict) or gate.get("kind") not in KINDS:
        return []  # already said by another check
    if enforced.get("tests") and gate.get("kind") != "test":
        return [
            (
                f"{gate_id}: kind {gate['kind']!r} lists tests — a gate the harness does "
                "not run, whose test files nothing checks for, while the index counts it"
            )
        ]
    return []


def _export_problems(gate_id: str, gate: dict[str, Any]) -> list[str]:
    """A rule that claims to be universal has to be one, and has to say where it came from."""
    if not gate.get("portable"):
        return []
    found = []
    if gate.get("layer") == "internal":
        found.append(
            f"{gate_id}: an internal rule cannot be exported — a rule tied to one project's "
            "architecture, shipped elsewhere as universal, is an overclaim (ADR 0042)"
        )
    if not str(gate.get("born_from", "")).strip():
        found.append(
            f"{gate_id}: an exported rule needs born_from — a rule with no origin "
            "is a rule nobody knows when to remove"
        )
    return found


def problems(gates: list[dict[str, Any]]) -> list[str]:
    """Everything wrong with a registry. Empty means well-formed, not accurate."""
    found: list[str] = []
    seen: set[str] = set()

    for gate in gates:
        gate_id = str(gate.get("id", "?"))
        missing = [field for field in REQUIRED if not gate.get(field)]
        if missing:
            found.append(f"{gate_id}: missing {missing}")
        if gate_id in seen:
            found.append(f"{gate_id}: duplicate id — an index with a repeated id points two ways")
        seen.add(gate_id)
        if not GATE_ID.match(gate_id):
            found.append(f"{gate_id}: id must be kebab-case")

        found.extend(
            f"{gate_id}: {key!r} is not a field of a gate — nothing reads it"
            for key in sorted(set(gate) - KEYS)
        )
        found.extend(_vocabulary_problems(gate_id, gate))
        found.extend(_export_problems(gate_id, gate))
        found.extend(_enforcement_problems(gate_id, gate))
        if "proved_by" in gate:
            found.extend(_proof_problems(gate_id, gate["proved_by"]))

    return found
