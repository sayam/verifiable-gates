# verifiable-gates

A gate registry that is enforced two ways against the tests and CI jobs behind
it, gates that must carry evidence of having gone red on a real defect, and a
portable rule set that lets an AI coding agent work under the same rules in
another project.

**Status: extraction in progress (stage 1 of 6).** The tooling still lives in
the reference implementation,
[`sayam/flask-todolist`](https://github.com/sayam/flask-todolist), and moves here
in stages — the decision, what moves and what stays, is
[ADR 0075 §6](https://github.com/sayam/flask-todolist/blob/main/docs/adr/0075-thesis-track-freeze-effort-and-ceilings.md)
and the file-by-file census is
[`extraction.yaml`](https://github.com/sayam/flask-todolist/blob/main/extraction.yaml)
there. **Do not depend on this package yet.**

| Stage | What lands | Status |
|---|---|---|
| 1 | Package skeleton · CI · hash-pinned tools · registry schema | **here** |
| 2 | The nine checks · the doctor · preflight · the skill generator | next |
| 3 | The governance checkers (ratchets, censuses, pending page) | |
| 4 | The supply-chain checkers | |
| 5 | The measurement instruments and the comparison data | |
| 6 | Registry handover · citation · DOI | |

## What is here today

```python
from verifiable_gates import registry

gates = registry.load("gates.yaml")
for problem in registry.problems(gates):
    print(problem)
```

The schema encodes four rules that came from real traps, not from theory:

- a rule whose `layer` is `internal` **cannot** be `portable` — a rule tied to one
  project's architecture, exported as universal, is an overclaim;
- anything exported must name the trap that created it (`born_from`), because a
  rule with no origin is a rule nobody knows when to remove;
- `proved_by` entries must say what they caught and when — a gate nobody has seen
  go red is indistinguishable from a gate that checks nothing;
- the vocabularies for `kind`, `severity`, `layer`, and `pillar` are closed.

## Licence

- Code: [Apache-2.0](LICENSE). Contributors sign [`CLA.md`](CLA.md) — one line in
  the pull request; you keep your copyright.
- Rules and documentation: [CC BY 4.0](LICENSE-docs).

The application this was extracted from stays AGPL-3.0-or-later. The two differ
on purpose: a CI tool is not a network service, and a rule meant to be adopted
inside an organisation's internal handbook must not require share-alike.

---

## ภาษาไทย

ทะเบียน gate ที่ถูกบังคับให้ตรงกับความจริงสองทิศ · gate ที่ต้องพกหลักฐานว่าเคยแดง
ตอนของเสียจริง · และชุดกฎที่ส่งออกไปให้ AI agent ทำงานใต้กติกาเดียวกันในโปรเจกต์อื่นได้

**สถานะ: กำลังถอด (ขั้น 1 จาก 6)** — เครื่องมือยังอยู่ที่
[`flask-todolist`](https://github.com/sayam/flask-todolist) และทยอยย้ายมาตาม
ADR 0075 ข้อ 6 ที่นั่น · **ยังอย่าเพิ่งพึ่งแพ็กเกจนี้**

วันนี้มีแค่ **schema ของทะเบียน** (`verifiable_gates.registry`) ซึ่งเป็นสิ่งที่ทุกขั้น
ถัดไปต้องอ่าน · `gates.yaml` ของ repo นี้ยังว่างโดยตั้งใจ — **จะไม่มีแถวใดถูกเพิ่ม
ก่อนที่ตัวบังคับของมันจะมีอยู่จริง**

โค้ด: Apache-2.0 (ผู้ร่วมพัฒนาลงนาม `CLA.md`) · กฎและเอกสาร: CC BY 4.0
