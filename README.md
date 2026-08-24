# verifiable-gates

**Status: placeholder — no code here yet.** (2026-08-25)

This repository reserves the name and the licence for the governance core that is
being extracted from [`sayam/flask-todolist`](https://github.com/sayam/flask-todolist):
a gate registry that is enforced two ways against the tests and CI jobs that
back it, gates that must carry evidence of having gone red on a real defect,
a portable skill/overlay that lets an AI coding agent work under the same rules
in another project, and the instruments used to measure whether any of that
changes the code an agent writes.

The decision to extract, what moves and what stays, and why this licence, are in
[ADR 0075 §6](https://github.com/sayam/flask-todolist/blob/main/docs/adr/0075-thesis-track-freeze-effort-and-ceilings.md)
of the source repository. Until the extraction lands, **the source repository is
the only place the tooling exists** — do not depend on this one yet.

## Licence

- Code: [Apache-2.0](LICENSE). Contributors sign [`CLA.md`](CLA.md) (a one-line
  grant in the pull request; you keep your copyright).
- Rules and documentation: [CC BY 4.0](LICENSE-docs).

The application this was extracted from stays AGPL-3.0-or-later; the two are
deliberately different — a CI tool is not a network service, and a rule you want
adopted inside an organisation's internal handbook must not require share-alike.

---

## ภาษาไทย

**สถานะ: จองชื่อไว้ ยังไม่มีโค้ด** (2026-08-25) · แกน governance ของ
[`flask-todolist`](https://github.com/sayam/flask-todolist) — ทะเบียน gate ที่ตรวจสองทิศ ·
gate ที่ต้องพกหลักฐานว่าเคยแดง · skill/overlay สำหรับ AI agent · เครื่องมือวัดผล —
กำลังถูกถอดมาที่นี่ตาม ADR 0075 ข้อ 6 ของ repo ต้นทาง · จนกว่าจะถอดเสร็จ
**เครื่องมือทั้งหมดยังอยู่ที่ต้นทางเท่านั้น**

โค้ด: Apache-2.0 (ผู้ร่วมพัฒนาลงนาม `CLA.md`) · กฎและเอกสาร: CC BY 4.0
