"""verifiable-gates — ทะเบียน gate ที่ถูกบังคับให้ตรงกับความจริงสองทิศ

แกน governance ที่ถอดมาจาก reference implementation (`sayam/flask-todolist`)
ตาม ADR 0075 ข้อ 6 ของที่นั่น · **ขั้น 1: มีแค่ schema ของทะเบียน** — ตัวบังคับ
(checks · doctor · preflight) ย้ายเข้ามาในขั้น 2 และตัวตรวจ governance ในขั้น 3
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.0.1"
