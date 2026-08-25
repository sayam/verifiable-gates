"""The schema has to separate a good registry from a bad one — one rule at a time.

A test that feeds in only valid input and sees "no problems" proves the code
runs, not that it checks anything. So every rule in `registry.problems()` has a
counterpart here: a registry that breaks *that rule alone* must produce a problem
naming it, while the valid registry beside it stays silent.

This repository's own `gates.yaml` is read here too. The house that produces
registries has to pass its own schema — starting from when it is still empty.
"""

from __future__ import annotations

import pathlib
from typing import Any

import pytest

from verifiable_gates import registry

ROOT = pathlib.Path(__file__).resolve().parent.parent


def a_gate(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401 — field values are deliberately of mixed type
    """One valid gate. Each test breaks exactly one field of it."""
    base: dict[str, Any] = {
        "id": "example-rule",
        "title": "An example of a well-formed rule",
        "kind": "test",
        "severity": "blocking",
        "enforced_by": {"job": "test", "tests": ["tests/test_example.py"]},
        "layer": "baseline",
        "pillar": "security",
        "portable": True,
        "born_from": "the real trap that produced this rule",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------- reading the file


def test_a_wellformed_file_loads(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "gates.yaml"
    path.write_text("version: 1\ngates:\n  - id: a\n", encoding="utf-8")
    assert registry.load(path) == [{"id": "a"}]


def test_missing_gates_key_is_an_empty_registry(tmp_path: pathlib.Path) -> None:
    """An empty registry is a correct state — a repository with no enforcer yet lives here."""
    path = tmp_path / "gates.yaml"
    path.write_text("version: 1\n", encoding="utf-8")
    assert registry.load(path) == []


def test_non_mapping_entries_are_ignored(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "gates.yaml"
    path.write_text("version: 1\ngates:\n  - id: a\n  - 'a stray string'\n", encoding="utf-8")
    assert registry.load(path) == [{"id": "a"}]


def test_a_file_that_is_not_a_mapping_is_refused(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "gates.yaml"
    path.write_text("- not a mapping\n", encoding="utf-8")
    with pytest.raises(TypeError, match="mapping"):
        registry.load(path)


def test_a_wrong_schema_version_is_refused(tmp_path: pathlib.Path) -> None:
    """An unknown version is a file whose rules changed underfoot; reading on would be guessing."""
    path = tmp_path / "gates.yaml"
    path.write_text("version: 2\ngates: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        registry.load(path)


def test_gates_that_is_not_a_list_is_refused(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "gates.yaml"
    path.write_text("version: 1\ngates:\n  a: b\n", encoding="utf-8")
    with pytest.raises(TypeError, match="list"):
        registry.load(path)


# ---------------------------------------------------------------- checking each row


def test_an_empty_registry_has_no_problems() -> None:
    assert registry.problems([]) == []


def test_a_valid_gate_is_silent() -> None:
    assert registry.problems([a_gate()]) == []


@pytest.mark.parametrize("field", registry.REQUIRED)
def test_every_required_field_is_required(field: str) -> None:
    gate = a_gate()
    del gate[field]
    found = registry.problems([gate])
    assert any(field in problem for problem in found), f"removing {field} was silent"


def test_duplicate_ids_are_caught() -> None:
    found = registry.problems([a_gate(), a_gate()])
    assert any("duplicate" in problem for problem in found)


@pytest.mark.parametrize("bad", ["Example-Rule", "example_rule", "example rule", "-example"])
def test_ids_must_be_kebab_case(bad: str) -> None:
    found = registry.problems([a_gate(id=bad)])
    assert any("kebab" in problem for problem in found)


@pytest.mark.parametrize(
    ("field", "bad"),
    [("kind", "check"), ("severity", "critical"), ("layer", "shared"), ("pillar", "quality")],
)
def test_closed_vocabularies_are_closed(field: str, bad: str) -> None:
    found = registry.problems([a_gate(**{field: bad})])
    assert any(field in problem and bad in problem for problem in found)


def test_an_internal_rule_cannot_be_exported() -> None:
    """ADR 0042 — a rule tied to one project's architecture cannot ship as universal."""
    found = registry.problems([a_gate(layer="internal", portable=True)])
    assert any("internal" in problem for problem in found)


def test_an_internal_rule_that_stays_home_is_fine() -> None:
    """The other direction — `internal` is not a fault, as long as it claims nothing more."""
    assert registry.problems([a_gate(layer="internal", portable=False, born_from="")]) == []


def test_an_exported_rule_must_name_the_trap_that_created_it() -> None:
    found = registry.problems([a_gate(born_from="   ")])
    assert any("born_from" in problem for problem in found)


# ---------------------------------------------------------------- proved_by


def test_a_wellformed_proof_is_silent() -> None:
    gate = a_gate(
        proved_by=[
            {
                "kind": "mutation",
                "ref": "pr/1",
                "date": "2026-08-25",
                "caught": "broke the code and it went red",
            }
        ]
    )
    assert registry.problems([gate]) == []


def test_proved_by_must_be_a_list() -> None:
    found = registry.problems([a_gate(proved_by={"kind": "mutation"})])
    assert any("proved_by" in problem for problem in found)


def test_a_proof_that_is_not_a_mapping_is_caught() -> None:
    found = registry.problems([a_gate(proved_by=["it passed"])])
    assert any("mapping" in problem for problem in found)


@pytest.mark.parametrize(
    ("field", "value", "needle"),
    [
        ("kind", "vibes", "kind"),
        ("ref", "", "ref"),
        ("date", "25/08/2026", "date"),
        ("caught", "  ", "caught"),
    ],
)
def test_each_field_of_a_proof_is_checked(field: str, value: str, needle: str) -> None:
    proof = {"kind": "ci-red", "ref": "run/1", "date": "2026-08-25", "caught": "it really went red"}
    proof[field] = value
    found = registry.problems([a_gate(proved_by=[proof])])
    assert any(needle in problem for problem in found), f"a bad {field} was silent"


# ---------------------------------------------------------------- dogfood


def test_this_repos_own_registry_passes_its_own_schema() -> None:
    """The house that produces registries passes its own — starting from when it is empty."""
    assert registry.problems(registry.load(ROOT / "gates.yaml")) == []
