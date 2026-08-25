"""schema ของทะเบียนต้องแยกทะเบียนที่ถูกออกจากทะเบียนที่ผิดได้ — ทีละข้อ

เทสต์ที่ป้อนแต่ของถูกแล้วเห็นว่า "ไม่มีปัญหา" พิสูจน์แค่ว่าโค้ดรันผ่าน ไม่ได้พิสูจน์
ว่ามันตรวจอะไร · ทุกกฎใน `registry.problems()` จึงมีคู่ของมันที่นี่: ทะเบียนที่
ละเมิด*ข้อนั้นข้อเดียว* ต้องได้ปัญหาที่ชี้ข้อนั้น และทะเบียนที่ถูกต้องข้างเคียงต้องเงียบ

`gates.yaml` ของ repo นี้เองก็ถูกอ่านที่นี่ด้วย — ทะเบียนของบ้านที่ผลิตทะเบียน
ต้องผ่าน schema ของตัวเอง ตั้งแต่ตอนที่มันยังว่าง
"""

from __future__ import annotations

import pathlib
from typing import Any

import pytest

from verifiable_gates import registry

ROOT = pathlib.Path(__file__).resolve().parent.parent


def a_gate(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401 — ค่าของฟิลด์เป็นได้หลายชนิดโดยตั้งใจ
    """gate ที่ถูกต้องหนึ่งใบ — เทสต์แต่ละตัวทำให้ผิดทีละฟิลด์จากตรงนี้"""
    base: dict[str, Any] = {
        "id": "example-rule",
        "title": "ตัวอย่างกฎที่ถูกต้อง",
        "kind": "test",
        "severity": "blocking",
        "enforced_by": {"job": "test", "tests": ["tests/test_example.py"]},
        "layer": "baseline",
        "pillar": "security",
        "portable": True,
        "born_from": "กับดักจริงที่ให้กำเนิดกฎข้อนี้",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------- อ่านไฟล์


def test_a_wellformed_file_loads(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "gates.yaml"
    path.write_text("version: 1\ngates:\n  - id: a\n", encoding="utf-8")
    assert registry.load(path) == [{"id": "a"}]


def test_missing_gates_key_is_an_empty_registry(tmp_path: pathlib.Path) -> None:
    """ทะเบียนว่างเป็นสถานะที่ถูกต้อง — repo ที่ยังไม่มีตัวบังคับตัวแรกอยู่ตรงนี้"""
    path = tmp_path / "gates.yaml"
    path.write_text("version: 1\n", encoding="utf-8")
    assert registry.load(path) == []


def test_non_mapping_entries_are_ignored(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "gates.yaml"
    path.write_text("version: 1\ngates:\n  - id: a\n  - 'ข้อความลอย'\n", encoding="utf-8")
    assert registry.load(path) == [{"id": "a"}]


def test_a_file_that_is_not_a_mapping_is_refused(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "gates.yaml"
    path.write_text("- ไม่ใช่ mapping\n", encoding="utf-8")
    with pytest.raises(TypeError, match="mapping"):
        registry.load(path)


def test_a_wrong_schema_version_is_refused(tmp_path: pathlib.Path) -> None:
    """เวอร์ชันที่ไม่รู้จักคือไฟล์ที่กติกาเปลี่ยนใต้เท้า — อ่านต่อคือการเดา"""
    path = tmp_path / "gates.yaml"
    path.write_text("version: 2\ngates: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        registry.load(path)


def test_gates_that_is_not_a_list_is_refused(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "gates.yaml"
    path.write_text("version: 1\ngates:\n  a: b\n", encoding="utf-8")
    with pytest.raises(TypeError, match="รายการ"):
        registry.load(path)


# ---------------------------------------------------------------- ตรวจรูปของแถว


def test_an_empty_registry_has_no_problems() -> None:
    assert registry.problems([]) == []


def test_a_valid_gate_is_silent() -> None:
    assert registry.problems([a_gate()]) == []


@pytest.mark.parametrize("field", registry.REQUIRED)
def test_every_required_field_is_required(field: str) -> None:
    gate = a_gate()
    del gate[field]
    found = registry.problems([gate])
    assert any(field in problem for problem in found), f"ถอด {field} ออกแล้วเงียบ"


def test_duplicate_ids_are_caught() -> None:
    found = registry.problems([a_gate(), a_gate()])
    assert any("ซ้ำ" in problem for problem in found)


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
    """ADR 0042 — กฎที่ผูกกับสถาปัตยกรรมของ repo หนึ่ง ๆ ส่งออกเป็นกฎสากลไม่ได้"""
    found = registry.problems([a_gate(layer="internal", portable=True)])
    assert any("internal" in problem for problem in found)


def test_an_internal_rule_that_stays_home_is_fine() -> None:
    """ทิศกลับ — ชั้น internal ไม่ใช่ความผิด ตราบใดที่ไม่อ้างว่าเป็นสากล"""
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
                "caught": "ทำให้โค้ดผิดแล้วมันแดง",
            }
        ]
    )
    assert registry.problems([gate]) == []


def test_proved_by_must_be_a_list() -> None:
    found = registry.problems([a_gate(proved_by={"kind": "mutation"})])
    assert any("proved_by" in problem for problem in found)


def test_a_proof_that_is_not_a_mapping_is_caught() -> None:
    found = registry.problems([a_gate(proved_by=["ผ่านแล้ว"])])
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
    proof = {"kind": "ci-red", "ref": "run/1", "date": "2026-08-25", "caught": "แดงจริง"}
    proof[field] = value
    found = registry.problems([a_gate(proved_by=[proof])])
    assert any(needle in problem for problem in found), f"{field} ผิดแล้วเงียบ"


# ---------------------------------------------------------------- dogfood


def test_this_repos_own_registry_passes_its_own_schema() -> None:
    """บ้านที่ผลิตทะเบียน ต้องผ่านทะเบียนของตัวเอง — ตั้งแต่ตอนที่มันยังว่าง"""
    assert registry.problems(registry.load(ROOT / "gates.yaml")) == []
