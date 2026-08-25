"""schema ของทะเบียน gate — สิ่งเดียวที่ทุกขั้นถัดไปต้องพึ่ง

ทะเบียนคือ *ดัชนี* ไม่ใช่ *แหล่ง* — ตัวบังคับจริงคือเทสต์กับ job ใน CI · หน้าที่ของ
โมดูลนี้จึงมีข้อเดียว: **ตอบว่าไฟล์ทะเบียนมีรูปที่เครื่องอ่านได้ไหม** ส่วนคำถามว่า
"แถวนี้ตรงกับความจริงหรือเปล่า" เป็นงานของตัวตรวจในขั้น 2–3 ซึ่งอ่านจากที่นี่

กติกาที่ทำให้ schema นี้ไม่ใช่แค่การจัดรูป (ทุกข้อมาจากกับดักจริงใน reference
implementation ไม่ใช่จากทฤษฎี):

- **`layer` กับ `portable` ต้องไม่ขัดกัน** — กฎชั้น `internal` คือกฎที่ผูกกับ
  สถาปัตยกรรมของ repo หนึ่ง ๆ · ส่งออกมันไปบังคับที่อื่นคือการอ้างว่าเป็นสากล
  ทั้งที่ไม่ใช่ (ADR 0042 · วัดได้จริงในรอบ audit ที่ 23: 5 ข้อติดป้ายผิด)
- **กฎที่ส่งออกต้องบอกกับดักที่ให้กำเนิดมัน (`born_from`)** — กฎที่ไม่มีที่มา
  คือกฎที่ไม่มีใครรู้ว่าเมื่อไหร่ควรถอด
- **`proved_by` เก็บหลักฐานว่าด่านเคยแดงตอนของเสียจริง** — ด่านที่ไม่เคยมีใคร
  เห็นแดง แยกไม่ออกจากด่านที่ไม่ได้ตรวจอะไร (ADR 0059)

`problems()` คืน *รายการปัญหา* ไม่ใช่ raise — เพราะผู้เรียกทุกตัวอยากเห็นทุกข้อ
พร้อมกัน ไม่ใช่ข้อแรกแล้วหยุด (หลักเดียวกับตัวตรวจ ratchet ของ reference)
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
    """อ่านทะเบียนจากไฟล์ — raise ถ้าอ่านไม่ได้เลย คืนรายการ gate ถ้าอ่านได้

    "อ่านไม่ได้เลย" กับ "อ่านได้แต่มีแถวผิด" เป็นคนละเรื่อง: อย่างแรกคือไฟล์ที่ใช้
    ไม่ได้ (raise ทันที) อย่างหลังคือรายงานที่ `problems()` มีหน้าที่บอกทีละข้อ
    """
    raw = yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"{path}: ทะเบียนต้องเป็น mapping ที่มีคีย์ version กับ gates")
    if raw.get("version") != SCHEMA_VERSION:
        raise ValueError(f"{path}: version ต้องเป็น {SCHEMA_VERSION} ได้ {raw.get('version')!r}")
    gates = raw.get("gates")
    if gates is None:
        gates = []
    if not isinstance(gates, list):
        raise TypeError(f"{path}: gates ต้องเป็นรายการ ได้ {type(gates).__name__}")
    return [gate for gate in gates if isinstance(gate, dict)]


def _proof_problems(where: str, proofs: Any) -> list[str]:  # noqa: ANN401 — รับของที่ยังไม่รู้รูป
    if not isinstance(proofs, list):
        return [f"{where}: proved_by ต้องเป็นรายการ"]
    found: list[str] = []
    for index, proof in enumerate(proofs):
        at = f"{where}: proved_by[{index}]"
        if not isinstance(proof, dict):
            found.append(f"{at} ต้องเป็น mapping")
            continue
        if proof.get("kind") not in PROOF_KINDS:
            found.append(f"{at} kind {proof.get('kind')!r} ไม่อยู่ใน {sorted(PROOF_KINDS)}")
        if not str(proof.get("ref", "")).strip():
            found.append(f"{at} ไม่มี ref — หลักฐานที่ชี้ไปไหนไม่ได้ ไม่ใช่หลักฐาน")
        if not ISO_DATE.match(str(proof.get("date", ""))):
            found.append(f"{at} date ต้องเป็น YYYY-MM-DD ได้ {proof.get('date')!r}")
        if not str(proof.get("caught", "")).strip():
            found.append(f"{at} caught ว่าง — หลักฐานที่ไม่บอกว่าพิสูจน์อะไร ใช้ไม่ได้")
    return found


def _vocabulary_problems(gate_id: str, gate: dict[str, Any]) -> list[str]:
    """คำศัพท์ปิดทุกชุด — ค่าที่ไม่อยู่ในชุดคือค่าที่ไม่มีใครเคยตัดสินว่าแปลว่าอะไร"""
    closed = (("kind", KINDS), ("severity", SEVERITIES), ("layer", LAYERS), ("pillar", PILLARS))
    return [
        f"{gate_id}: {field} {gate.get(field)!r} ไม่อยู่ใน {sorted(allowed)}"
        for field, allowed in closed
        if gate.get(field) not in allowed
    ]


def _export_problems(gate_id: str, gate: dict[str, Any]) -> list[str]:
    """กฎที่อ้างว่าเป็นสากล ต้องเป็นสากลจริงและบอกที่มาของตัวเอง"""
    if not gate.get("portable"):
        return []
    found = []
    if gate.get("layer") == "internal":
        found.append(
            f"{gate_id}: ชั้น internal ส่งออกไม่ได้ — กฎที่ผูกกับสถาปัตยกรรมของ repo "
            "หนึ่ง ๆ ถูกส่งไปบังคับที่อื่นในฐานะกฎสากล คือการอ้างเกินจริง (ADR 0042)"
        )
    if not str(gate.get("born_from", "")).strip():
        found.append(f"{gate_id}: กฎที่ส่งออกต้องมี born_from — กฎที่ไม่มีที่มา คือกฎที่ไม่มีใครรู้ว่าเมื่อไหร่ควรถอด")
    return found


def problems(gates: list[dict[str, Any]]) -> list[str]:
    """รายการปัญหาของทะเบียน — ว่าง = รูปถูกต้อง (ไม่ได้แปลว่าตรงกับความจริง)"""
    found: list[str] = []
    seen: set[str] = set()

    for gate in gates:
        gate_id = str(gate.get("id", "?"))
        missing = [field for field in REQUIRED if not gate.get(field)]
        if missing:
            found.append(f"{gate_id}: ขาดฟิลด์ {missing}")
        if gate_id in seen:
            found.append(f"{gate_id}: id ซ้ำ — ดัชนีที่มี id ซ้ำชี้ไปสองที่พร้อมกัน")
        seen.add(gate_id)
        if not GATE_ID.match(gate_id):
            found.append(f"{gate_id}: id ต้องเป็น kebab-case")

        found.extend(_vocabulary_problems(gate_id, gate))
        found.extend(_export_problems(gate_id, gate))
        if "proved_by" in gate:
            found.extend(_proof_problems(gate_id, gate["proved_by"]))

    return found
