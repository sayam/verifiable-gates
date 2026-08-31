"""The schema has to separate a good registry from a bad one — one rule at a time.

A test that feeds in only valid input and sees "no problems" proves the code
runs, not that it checks anything. So every rule in `registry.problems()` has a
counterpart here: a registry that breaks *that rule alone* must produce a problem
naming it, while the valid registry beside it stays silent.

This repository's own `gates.yaml` is read here too. The house that produces
registries has to pass its own schema — starting from when it is still empty.
"""

from __future__ import annotations

import datetime
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


def test_an_explicitly_empty_registry_is_a_correct_state(tmp_path: pathlib.Path) -> None:
    """`gates: []` — a repository with no enforcer yet lives here, and says so."""
    path = tmp_path / "gates.yaml"
    path.write_text("version: 1\ngates: []\n", encoding="utf-8")
    assert registry.load(path) == []


def test_a_missing_gates_key_is_refused_not_read_as_empty(tmp_path: pathlib.Path) -> None:
    """A file with no `gates` list is not an empty index — it is a broken one.

    This reader used to answer `[]`, so an index that had lost its list looked
    like one that was empty on purpose, while `rules.load` and the shipped
    registry scanner both refuse the same file (outside audit, 2026-08-29).
    """
    path = tmp_path / "gates.yaml"
    path.write_text("version: 1\n", encoding="utf-8")
    with pytest.raises(TypeError, match="'gates' must be a list"):
        registry.load(path)


@pytest.mark.parametrize(
    ("row", "kind"),
    [("  - 'a stray string'", "str"), ("  - 42", "int"), ("  - [a, list]", "list")],
)
def test_a_row_that_is_not_a_mapping_is_refused_not_dropped(
    tmp_path: pathlib.Path, row: str, kind: str
) -> None:
    """A stray row used to vanish before `problems()` could see it."""
    path = tmp_path / "gates.yaml"
    path.write_text(f"version: 1\ngates:\n  - id: a\n{row}\n", encoding="utf-8")
    with pytest.raises(TypeError, match=rf"gates\[1\] must be a mapping, got {kind}"):
        registry.load(path)


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


@pytest.mark.parametrize(
    "ref",
    [
        "pr/1",
        "pr/151",
        "run/33259458732",
        "commit/9ff00d2c",
        "commit/" + "9ff00d2c" * 5,
        "sayam/flask-todolist#pr/151",
        "org/repo.name#run/7",
    ],
)
def test_a_ref_somebody_can_look_up_is_accepted(ref: str) -> None:
    proof = {"kind": "mutation", "ref": ref, "date": "2026-08-25", "caught": "it went red"}
    assert registry.problems([a_gate(proved_by=[proof])]) == []


@pytest.mark.parametrize(
    "ref",
    [
        "trust me",
        "pr/",
        "pr/0",
        "pr/abc",
        "PR/1",
        "issue/1",
        "commit/xyz",
        "commit/9ff00d",
        "#pr/1",
        "sayam/#pr/1",
        "https://github.com/sayam/verifiable-gates/pull/1",
    ],
)
def test_a_ref_nobody_can_look_up_is_refused(ref: str) -> None:
    """`ref: trust me` passed a schema that read only "non-empty" (outside audit, 2026-08-29)."""
    proof = {"kind": "mutation", "ref": ref, "date": "2026-08-25", "caught": "it went red"}
    found = registry.problems([a_gate(proved_by=[proof])])
    assert any("ref" in problem and "look up" in problem for problem in found), ref


def test_a_date_yaml_already_parsed_is_a_real_one() -> None:
    """An unquoted `2026-08-25` reaches the schema as a `datetime.date`, not a string."""
    proof = {"kind": "mutation", "ref": "pr/1", "date": datetime.date(2026, 8, 25), "caught": "red"}
    assert registry.problems([a_gate(proved_by=[proof])]) == []


@pytest.mark.parametrize("date", ["9999-99-99", "2026-02-30", "2026-13-01", "2026-8-5", "20260825"])
def test_a_date_that_is_not_a_calendar_date_is_refused(date: str) -> None:
    """`9999-99-99` has ten characters and two dashes; the old check asked nothing more."""
    proof = {"kind": "mutation", "ref": "pr/1", "date": date, "caught": "it went red"}
    found = registry.problems([a_gate(proved_by=[proof])])
    assert any("real YYYY-MM-DD" in problem for problem in found), date


def test_a_key_nobody_defined_is_refused() -> None:
    """`proved_yb` is a gate with no evidence that looks like one with — refused, not skipped."""
    found = registry.problems([a_gate(whatever="hello")])
    assert any("'whatever' is not a field of a gate" in problem for problem in found)


@pytest.mark.parametrize("key", ["portable", "born_from", "proved_by", "watched_by"])
def test_every_optional_key_the_registry_uses_is_known(key: str) -> None:
    """The other direction: the keys this repository's registry really carries draw nothing."""
    assert not any(
        "is not a field of a gate" in p for p in registry.problems([a_gate(**{key: None})])
    )


@pytest.mark.parametrize("date", ["2099-01-01", datetime.date(2099, 1, 1)])
def test_a_date_that_has_not_happened_yet_is_refused(date: str | datetime.date) -> None:
    """Evidence that has not happened yet is not evidence — the old check took `2099-01-01`."""
    proof = {"kind": "mutation", "ref": "pr/1", "date": date, "caught": "it went red"}
    found = registry.problems([a_gate(proved_by=[proof])])
    assert any("has not happened yet" in problem for problem in found), date


def test_a_date_that_is_today_anywhere_on_earth_is_not_in_the_future() -> None:
    """A proof written today in Bangkok at 02:00 is dated tomorrow in UTC; it is still today."""
    noon_utc = datetime.datetime(2026, 8, 30, 12, 0, tzinfo=datetime.UTC)
    assert registry.latest_today(noon_utc) == datetime.date(2026, 8, 31)
    assert registry.latest_today() >= datetime.datetime.now(datetime.UTC).date()


# ---------------------------------------------------------------- dogfood


def test_this_repos_own_registry_passes_its_own_schema() -> None:
    """The house that produces registries passes its own — starting from when it is empty."""
    assert registry.problems(registry.load(ROOT / "gates.yaml")) == []


def test_a_gate_that_lists_tests_under_another_kind_is_refused() -> None:
    """`kind` is not a label: the harness runs a gate only while it reads `test`, and the
    shipped scanner looks for the named files only for the same value. One word changed on
    one row took the harness from 43 pass · 11 skip to 42 · 12 with every reader still
    green (self-audit round 2, 2026-08-31)."""
    gate = {
        "id": "a-gate",
        "title": "A gate",
        "kind": "job",
        "severity": "blocking",
        "enforced_by": {"job": "test", "tests": ["tests/test_a.py"]},
        "layer": "internal",
        "pillar": "devx",
    }

    found = registry.problems([gate])

    assert any("lists tests" in problem for problem in found), found


def test_a_job_gate_with_no_tests_is_still_well_formed() -> None:
    """The other direction — the nine job gates and two step gates of this repository
    name no test files, and must not be caught by the rule above."""
    gate = {
        "id": "a-gate",
        "title": "A gate",
        "kind": "job",
        "severity": "blocking",
        "enforced_by": {"job": "test"},
        "layer": "internal",
        "pillar": "devx",
    }

    assert registry.problems([gate]) == []
