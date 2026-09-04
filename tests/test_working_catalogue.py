"""The working catalogue's schema, proved in both directions.

`working.yaml` is where a habit goes once it has held — not once it sounds right. Every
check here exists because the opposite mistake is easy to make and silent once made, so
each is tested twice: a clean practice must produce no complaint, and one with the
defect planted must produce exactly that complaint. A validator only ever shown broken
input passes just as happily on everything (the same discipline as
`tests/test_rules_catalogue.py`, for the same reason).

What the file may not do, in one line each: carry a practice with no ledger entry
behind it; call something `tool` or `file` without naming what; name a file the bundle
does not ship; grow on fewer than three pull requests; or carry a Thai column or a
pillar, which a practice does not have.
"""

from __future__ import annotations

import pathlib
from typing import Any

import pytest

from verifiable_gates import rules

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "src" / "verifiable_gates"
CATALOGUE = ROOT / "working.yaml"


def a_practice(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401 — field values are of mixed type
    base: dict[str, Any] = {
        "id": "a-practice",
        "layer": "working",
        "title": "A habit that held",
        "born_from": "L-0001 · 2026-08-30 · what it cost, in one sentence",
        "held_by": "reading",
        "held_on": ["pr/227", "pr/231", "pr/235"],
        "apply": "what to do, in the imperative",
    }
    base.update(overrides)
    return base


def complaints(*entries: dict[str, Any], package_dir: pathlib.Path | None = PACKAGE) -> str:
    return " ".join(rules.problems(list(entries), package_dir))


# ------------------------------------------------------------------ the file as shipped


def test_the_catalogue_loads_under_its_own_name() -> None:
    """The list is called `practices`, because a file of practices that called them
    rules would be the one place this repository let a name lie."""
    practices = rules.load(CATALOGUE, key="practices")
    assert len(practices) >= 1
    with pytest.raises(TypeError, match="'rules' must be a list"):
        rules.load(CATALOGUE)


def test_every_practice_in_the_catalogue_is_well_formed() -> None:
    practices = rules.load(CATALOGUE, key="practices")
    assert rules.problems(practices, PACKAGE) == []
    assert all(p["layer"] == rules.WORKING for p in practices)


def test_the_published_catalogue_carries_no_practice() -> None:
    """A practice is never a rule: `gates_doctor --rules` prints what a scanner decides,
    and the sheets a project is held to by reading are the 92 — not these."""
    assert all(r.get("layer") != rules.WORKING for r in rules.load(ROOT / "rules.yaml"))


def test_held_by_says_what_is_true_today() -> None:
    """Every holder names something the bundle ships **on the day it is claimed**.

    Two of these said `reading` when the catalogue was written and became `file` in the
    change that shipped the templates they name — the flip and the templates in one
    breath. That is the only way a holder is checked when it is claimed rather than
    promised, so the check is the general one: whatever a practice says holds it, the
    bundle has it now.
    """
    practices = rules.load(CATALOGUE, key="practices")
    assert {p["held_by"] for p in practices} <= rules.HELD_BY
    named = [
        (p["id"], p["held_by"], p[p["held_by"]]) for p in practices if p["held_by"] != "reading"
    ]
    assert named, "no practice names a holder — the check below would be vacuous"
    for practice_id, held_by, name in named:
        assert (PACKAGE / name).is_file(), f"{practice_id}: {held_by} {name} is not shipped"
    assert {p["id"] for p in practices if p["held_by"] == "file"} == {
        "keep-a-ledger-of-the-working",
        "work-products-live-where-they-survive",
    }


# ------------------------------------------------------ each defect, planted and refused


def test_a_clean_practice_produces_no_complaint() -> None:
    assert complaints(a_practice()) == ""


@pytest.mark.parametrize("field", rules.WORKING_REQUIRED)
def test_a_missing_field_is_named(field: str) -> None:
    entry = a_practice()
    del entry[field]
    assert f"missing {field}" in complaints(entry)


@pytest.mark.parametrize(
    "born",
    [
        "the trap that produced it",
        "L-124 · 2026-09-03 · too short an id",
        "L-0124 · 3 Sep 2026 · a date in the wrong shape",
        "L-0124 · 2026-09-03 ·",
        "2026-09-03 · L-0124 · the two swapped",
    ],
)
def test_a_born_from_that_is_not_a_ledger_entry_is_refused(born: str) -> None:
    """A practice with no lesson behind it is a preference, exactly as a rule with no
    incident is — the same field, held to the ledger's shape instead of prose."""
    assert "born_from must be a ledger entry" in complaints(a_practice(born_from=born))


def test_a_born_from_folded_across_lines_still_matches() -> None:
    """YAML folds `>-` scalars; the check reads the sentence, not the line breaks."""
    folded = "L-0124 · 2026-09-03 · a sentence\n  that continues on the next line"
    assert complaints(a_practice(born_from=folded)) == ""


def test_held_by_outside_the_three_is_refused() -> None:
    assert "held_by 'hope' is outside" in complaints(a_practice(held_by="hope"))


@pytest.mark.parametrize("kind", ["tool", "file"])
def test_a_named_holder_must_say_which(kind: str) -> None:
    assert f"held_by {kind!r} must say which" in complaints(a_practice(held_by=kind))


@pytest.mark.parametrize("kind", ["tool", "file"])
def test_a_name_given_for_the_wrong_holder_is_refused(kind: str) -> None:
    entry = a_practice(held_by="reading", **{kind: "lint_commits.py"})
    assert f"`{kind}:` is given but held_by is 'reading'" in complaints(entry)


def test_a_tool_the_bundle_does_not_ship_is_refused() -> None:
    entry = a_practice(held_by="tool", tool="checks/scan_nothing.py")
    assert "is not shipped by this bundle" in complaints(entry)
    assert complaints(a_practice(held_by="tool", tool="lint_commits.py")) == ""
    # Without a package_dir only the shape is checked — the same contract as `script`.
    assert complaints(entry, package_dir=None) == ""


@pytest.mark.parametrize("named", ["/etc/passwd", "../outside.py"])
def test_a_holder_outside_the_bundle_is_refused_before_it_is_looked_for(named: str) -> None:
    assert "must be a path inside the bundle" in complaints(a_practice(held_by="tool", tool=named))


@pytest.mark.parametrize("held_on", [[], ["pr/1"], ["pr/1", "pr/2"]])
def test_fewer_than_three_pull_requests_is_refused(held_on: list[str]) -> None:
    """The floor is what keeps a good idea out of the file. Three is the owner's number,
    re-decided in DECISIONS.md and never here."""
    assert "needs at least 3 pull requests" in complaints(a_practice(held_on=held_on))


def test_the_floor_is_the_one_the_decision_names() -> None:
    assert rules.HELD_ON_FLOOR == 3


@pytest.mark.parametrize("ref", ["227", "#227", "pull/227", "pr/abc", 227])
def test_a_ref_nobody_can_look_up_is_refused(ref: object) -> None:
    entry = a_practice(held_on=["pr/1", "pr/2", ref])
    assert "is not `pr/N` or `run/N`" in complaints(entry)


def test_held_on_that_is_not_a_list_is_refused() -> None:
    assert "held_on must be a list" in complaints(a_practice(held_on="pr/1, pr/2, pr/3"))


@pytest.mark.parametrize("key", ["pillar", "title_th", "born_from_th", "reference", "script"])
def test_a_rules_field_on_a_practice_is_refused(key: str) -> None:
    """English only and no pillar: a Thai column would be a retelling of a record, and
    the pillars describe what a rule protects in a product. A `reference` or a `script`
    is a rule's evidence, not a practice's."""
    assert f"{key!r} is not a field of a practice" in complaints(a_practice(**{key: "x"}))


def test_a_practice_listed_twice_is_refused() -> None:
    assert "listed more than once" in complaints(a_practice(), a_practice())


def test_a_bad_id_is_refused() -> None:
    assert "id must be lowercase words" in complaints(a_practice(id="A_Practice"))


def test_the_published_rules_still_pass_untouched() -> None:
    """The second catalogue must not have moved the first: every rule of the 92 is held
    to exactly the checks it was held to before."""
    assert rules.problems(rules.load(ROOT / "rules.yaml"), PACKAGE) == []
