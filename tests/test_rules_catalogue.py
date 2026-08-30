"""The catalogue's schema, proved in both directions.

Every check here exists because the opposite mistake is easy to make and silent
once made. So each one is tested twice: a clean rule must produce no complaint,
and a rule with the defect planted in it must produce exactly that complaint. A
validator only tested on broken input passes just as happily on everything.
"""

from __future__ import annotations

import json
import os
import pathlib
from typing import Any

import pytest

from verifiable_gates import rules

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "src" / "verifiable_gates"


def a_rule(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401 — field values are of mixed type
    base: dict[str, Any] = {
        "id": "a-rule",
        "layer": "baseline",
        "pillar": "security",
        "title": "A rule that holds",
        "title_th": "กฎที่ยังยืนอยู่",
        "born_from": "the trap that produced it",
        "born_from_th": "กับดักที่ให้กำเนิดมัน",
        "reference": {"kind": "test", "job": "test", "tests": ["tests/test_a.py"]},
    }
    base.update(overrides)
    return base


def complaints(*rule_list: dict[str, Any], package_dir: pathlib.Path | None = None) -> str:
    return " ".join(rules.problems(list(rule_list), package_dir))


# ---------------------------------------------------------------- the clean side


def test_every_script_the_catalogue_names_is_a_scan_the_manifest_ships_and_back() -> None:
    """A rule's `script:` and the manifest's `scan` entry are two statements of one fact —
    "the bundle decides this rule" — in two files. Nothing held them together: on 2026-08-30
    the re-audit deleted a rule's `script:` line in a worktree and the suite stayed green,
    so a published rule could lose its checker with no diff anyone reads."""
    catalogue = rules.load(ROOT / "rules.yaml")
    manifest = json.loads((ROOT / "src" / "verifiable_gates" / "overlay.json").read_text("utf-8"))
    scripted = {rule["id"]: rule["script"] for rule in catalogue if rule.get("script")}
    shipped = {
        gate_id: entry["script"]
        for gate_id, entry in manifest["gates"].items()
        if isinstance(entry, dict) and entry.get("kind") == "scan"
    }

    moved = sorted(k for k in scripted if shipped.get(k, scripted[k]) != scripted[k])
    assert scripted == shipped, (
        f"only in rules.yaml: {sorted(set(scripted) - set(shipped))} · "
        f"only in overlay.json: {sorted(set(shipped) - set(scripted))} · different path: {moved}"
    )


def test_a_well_formed_rule_draws_no_complaint() -> None:
    assert rules.problems([a_rule()]) == []


def test_the_published_catalogue_passes_its_own_schema() -> None:
    """The file this repository ships is held to the rules it publishes."""
    assert rules.problems(rules.load(ROOT / "rules.yaml"), PACKAGE) == []


# ---------------------------------------------------------------- required fields


@pytest.mark.parametrize("field", rules.REQUIRED)
def test_every_required_field_is_required(field: str) -> None:
    assert f"missing {field}" in complaints(a_rule(**{field: None}))


def test_a_rule_without_an_origin_is_refused() -> None:
    """A rule with no incident behind it is a preference, and preferences get no gate."""
    assert "missing born_from" in complaints(a_rule(born_from=""))


def test_the_original_wording_is_required_too() -> None:
    """Losing the original turns the record into a retelling of itself."""
    assert "missing born_from_th" in complaints(a_rule(born_from_th=""))


# ---------------------------------------------------------------- vocabularies


def test_an_internal_rule_cannot_be_published() -> None:
    """An internal rule is tied to one architecture; publishing it is an overclaim."""
    said = complaints(a_rule(layer="internal"))
    assert "layer 'internal' is outside" in said
    assert "never published" in said


def test_portable_on_a_rule_is_refused_as_a_gates_field() -> None:
    """A rule here is published whole; which gates are portable is a registry's call."""
    assert "portable is a gate's field" in complaints(a_rule(portable=True))


def test_a_key_nobody_defined_is_refused() -> None:
    """`born_frm` is a rule with no origin that looks like one with — refused, not skipped."""
    assert "'whatever' is not a field of a rule" in complaints(a_rule(whatever="hello"))


def test_a_layer_nobody_defined_is_refused() -> None:
    assert "layer 'weekly' is outside" in complaints(a_rule(layer="weekly"))


def test_a_pillar_nobody_defined_is_refused() -> None:
    assert "pillar 'vibes' is outside" in complaints(a_rule(pillar="vibes"))


@pytest.mark.parametrize("layer", sorted(rules.LAYERS))
def test_every_published_layer_is_accepted(layer: str) -> None:
    assert rules.problems([a_rule(layer=layer)]) == []


@pytest.mark.parametrize("pillar", sorted(rules.PILLARS))
def test_every_pillar_is_accepted(pillar: str) -> None:
    assert rules.problems([a_rule(pillar=pillar)]) == []


# ---------------------------------------------------------------- identity


def test_an_id_that_is_not_kebab_case_is_refused() -> None:
    assert "lowercase words joined by hyphens" in complaints(a_rule(id="Bad_Id"))


def test_a_repeated_id_is_refused() -> None:
    """Two rules under one id means one of them is unreachable by anything."""
    assert "listed more than once" in complaints(a_rule(), a_rule())


def test_two_different_ids_are_fine() -> None:
    assert rules.problems([a_rule(), a_rule(id="another-rule")]) == []


# ---------------------------------------------------------------- the reference block


def test_a_reference_kind_nobody_defined_is_refused() -> None:
    assert "reference kind 'ritual' is outside" in complaints(
        a_rule(reference={"kind": "ritual", "job": "test"})
    )


def test_a_reference_that_names_no_job_is_refused() -> None:
    assert "names no job" in complaints(
        a_rule(reference={"kind": "test", "tests": ["tests/test_a.py"]})
    )


def test_a_test_reference_must_name_a_test_file() -> None:
    assert "names no test file" in complaints(a_rule(reference={"kind": "test", "job": "test"}))


def test_a_step_reference_must_name_a_step() -> None:
    assert "names no step" in complaints(a_rule(reference={"kind": "step", "job": "scans"}))


def test_a_job_reference_needs_nothing_but_a_job() -> None:
    assert rules.problems([a_rule(reference={"kind": "job", "job": "scans"})]) == []


def test_a_reference_that_is_not_a_mapping_is_refused() -> None:
    assert "must be a mapping" in complaints(a_rule(reference="tests/test_a.py"))


# ---------------------------------------------------------------- universality


@pytest.mark.parametrize("field", ["title", "born_from", "title_th", "born_from_th"])
def test_a_framework_library_name_makes_a_rule_not_universal(field: str) -> None:
    """In either language: a rule naming one stack's library means nothing on another."""
    said = complaints(a_rule(**{field: "always call SQLAlchemy first"}))
    assert "'sqlalchemy'" in said
    assert "not universal" in said


def test_the_reference_block_may_name_the_reference_implementation() -> None:
    """Naming that project's own files is what makes the reference evidence."""
    rule = a_rule(reference={"kind": "test", "job": "test", "tests": ["tests/test_flask_app.py"]})
    assert rules.problems([rule]) == []


def test_the_name_of_an_external_system_is_not_a_framework_name() -> None:
    """redis and mysql are things any stack talks to, not the stack itself."""
    assert rules.problems([a_rule(born_from="the redis counter was per-process")]) == []


# ---------------------------------------------------------------- shipped checkers


def test_a_script_that_climbs_out_of_the_bundle_is_refused() -> None:
    assert "inside the bundle" in complaints(a_rule(script="../../etc/passwd"))


def test_an_absolute_script_path_is_refused() -> None:
    assert "inside the bundle" in complaints(a_rule(script="/usr/bin/true"))


def test_a_script_this_bundle_does_not_carry_is_refused() -> None:
    """Otherwise the rule reports pending forever while looking answered."""
    said = complaints(a_rule(script="checks/scan_nothing.py"), package_dir=PACKAGE)
    assert "is not shipped by this bundle" in said


def test_a_script_this_bundle_carries_is_accepted() -> None:
    rule = a_rule(script="checks/scan_adr_index.py")
    assert rules.problems([rule], PACKAGE) == []


def test_without_a_package_directory_only_the_shape_is_checked() -> None:
    """A caller who has no bundle on disk still gets the shape check."""
    assert rules.problems([a_rule(script="checks/scan_nothing.py")]) == []


# ---------------------------------------------------------------- reading the file


def test_a_rule_that_is_not_a_mapping_is_refused() -> None:
    not_a_rule: Any = "a-rule"  # the point of the test is that this is the wrong type
    assert "must be a mapping" in " ".join(rules.problems([not_a_rule]))


def test_a_catalogue_of_another_version_is_refused(tmp_path: pathlib.Path) -> None:
    """A reader that guesses at an unknown version reads it wrong in silence."""
    path = tmp_path / "rules.yaml"
    path.write_text("version: 99\nrules: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="this reader speaks"):
        rules.load(path)


def test_a_catalogue_that_is_not_a_mapping_is_refused(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(TypeError, match="must be a mapping"):
        rules.load(path)


def test_rules_must_be_a_list(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text("version: 1\nrules: {a: b}\n", encoding="utf-8")
    with pytest.raises(TypeError, match="must be a list"):
        rules.load(path)


def test_the_order_of_the_file_survives_loading(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text(
        "version: 1\nrules:\n  - id: zeta\n  - id: alpha\n",
        encoding="utf-8",
    )
    assert [r["id"] for r in rules.load(path)] == ["zeta", "alpha"]


# ---------------------------------------------------------------- the surface the README shows


def test_the_catalogue_reader_is_on_the_package_surface() -> None:
    """`import verifiable_gates` must reach `rules` — the README shows exactly that.

    It did not, until an outside audit (2026-08-29) found `__all__` holding only
    the version; the example worked by accident of `from … import` reaching a
    submodule. A name that is documented is a name that is exported.
    """
    import verifiable_gates  # noqa: PLC0415 — the point is what the bare import brings

    assert "rules" in verifiable_gates.__all__
    assert verifiable_gates.rules is rules


def test_the_readme_example_runs_as_written(capsys: pytest.CaptureFixture[str]) -> None:
    """The python block in the README is executed, in the checkout, and prints nothing.

    Nothing, because the shipped catalogue has no problems — and the example
    passing `package_dir` is what makes that a claim about the scripts too.
    """
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    start = readme.index("```python\n") + len("```python\n")
    block = readme[start : readme.index("```", start)]
    assert "package_dir=" in block, "the example must check the scripts, not only the shape"

    previous = pathlib.Path.cwd()
    os.chdir(ROOT)
    try:
        exec(compile(block, "README.md", "exec"), {})  # noqa: S102 — the README's own code, from disk
    finally:
        os.chdir(previous)

    assert capsys.readouterr().out == ""
