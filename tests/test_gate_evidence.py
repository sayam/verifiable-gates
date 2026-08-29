"""Every gate carries evidence of going red — and the list of ones that do not only shrinks.

The rule `gates-carry-red-evidence` this repository publishes: a gate nobody has
seen fail is indistinguishable from a gate that checks nothing. The schema keeps
`proved_by` optional on purpose — a gate that has not yet met its defect is still
a gate — so the ratchet lives here instead: the names allowed to lack evidence are
written down, the file on disk must match that list exactly in both directions,
and the list may only lose names. Adding one is a diff on this file that somebody
signs, with the reason in the commit.

On 2026-08-29 the list reached zero and started being enforced.
"""

from __future__ import annotations

import pathlib
from typing import Any

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Gates allowed to carry no `proved_by` yet. **Shrink only.** Empty since 2026-08-29.
UNPROVED: frozenset[str] = frozenset()


def gates() -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = yaml.safe_load(
        (ROOT / "gates.yaml").read_text(encoding="utf-8")
    )["gates"]
    return loaded


def test_every_gate_without_evidence_is_on_the_list_and_the_list_names_only_those() -> None:
    """Both directions: a new gate with no evidence is red, and a stale name on the list is red."""
    without = {str(g["id"]) for g in gates() if not g.get("proved_by")}

    assert without == set(UNPROVED), (
        f"gates lacking proved_by: {sorted(without - UNPROVED)} — add evidence, or add the name "
        f"to UNPROVED in a commit that says why; names on the list that now carry evidence: "
        f"{sorted(UNPROVED - without)} — remove them, the list only shrinks"
    )


def test_the_list_is_empty() -> None:
    """The ceiling. Raise it only in the same change that adds the name, and say why."""
    assert len(UNPROVED) == 0


def test_every_proof_says_what_it_caught_and_when() -> None:
    """A proof row that names a pull request and nothing else is a citation, not evidence."""
    for gate in gates():
        for proof in gate.get("proved_by") or []:
            assert isinstance(proof, dict)
            assert str(proof.get("caught", "")).strip(), f"{gate['id']}: a proof with no `caught`"
            assert str(proof.get("date", "")).strip(), f"{gate['id']}: a proof with no date"
            assert str(proof.get("ref", "")).strip(), f"{gate['id']}: a proof with no ref"
