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
"""

from __future__ import annotations

import pathlib
import re
from typing import Any

import yaml

__all__ = [
    "KINDS",
    "LAYERS",
    "PILLARS",
    "PROOF_KINDS",
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
GATE_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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
    if gates is None:
        gates = []
    if not isinstance(gates, list):
        raise TypeError(f"{path}: 'gates' must be a list, got {type(gates).__name__}")
    return [gate for gate in gates if isinstance(gate, dict)]


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
        if not str(proof.get("ref", "")).strip():
            found.append(f"{at} has no ref — evidence that points nowhere is not evidence")
        if not ISO_DATE.match(str(proof.get("date", ""))):
            found.append(f"{at} date must be YYYY-MM-DD, got {proof.get('date')!r}")
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

        found.extend(_vocabulary_problems(gate_id, gate))
        found.extend(_export_problems(gate_id, gate))
        if "proved_by" in gate:
            found.extend(_proof_problems(gate_id, gate["proved_by"]))

    return found
