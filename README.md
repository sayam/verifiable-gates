# verifiable-gates

A gate registry that is enforced two ways against the tests and CI jobs behind
it, gates that must carry evidence of having gone red on a real defect, and a
portable rule set that lets an AI coding agent work under the same rules in
another project.

**Status: extraction in progress (stages 1, 2 and 6 done).** Some tooling still lives in
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
| 2 | The nine checks · the doctor · preflight · the skill generator | **here** |
| 3 | The governance checkers (ratchets, censuses, pending page) | |
| 4 | The supply-chain checkers | |
| 5 | The measurement instruments and the comparison data | |
| 6 | Registry handover · citation · DOI | **here** |

Stage 6 was taken out of order on purpose. The rules are what this project *is*;
stages 3 to 5 move the machinery that happens to enforce some of them, and a
bundle that shipped the machinery before the rules would have had nothing to say
about the ones it cannot enforce. What remains of stage 6 is a DOI, which needs
a release rather than a commit.

## What is here today

**[`rules.yaml`](rules.yaml) — 92 rules, each carrying the incident that produced
it.** They are rendered into two sheets an agent can be handed:
[`SKILL.md`](SKILL.md), the baseline layer, where deviating is a defect; and
[`SKILL-BUSINESS.md`](SKILL-BUSINESS.md), agreements an application of a given
kind may legitimately decide differently.

A rule and its enforcement live in separate files, because they have separate
lifetimes. `rules.yaml` is what this project publishes; `gates.yaml` is what this
project is itself held to.

```python
from verifiable_gates import rules

catalogue = rules.load("rules.yaml")
for problem in rules.problems(catalogue):
    print(problem)
```

Also here: the nine stdlib-only checkers, the installer and the doctor that runs
them in a project that has installed nothing, preflight, the sheet renderer, and
the fail-fix harness.

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

**สถานะ: กำลังถอด (ขั้น 1, 2 และ 6 เสร็จแล้ว)** — เครื่องมือบางส่วนยังอยู่ที่
[`flask-todolist`](https://github.com/sayam/flask-todolist) และทยอยย้ายมาตาม
ADR 0075 ข้อ 6 ที่นั่น · **ยังอย่าเพิ่งพึ่งแพ็กเกจนี้**

วันนี้มี **คลังกฎ 92 ข้อ** (`rules.yaml`) ที่แต่ละข้อพกกับดักจริงที่ให้กำเนิดมันมาด้วย
· ตัวตรวจ stdlib ล้วนเก้าตัว · ตัวติดตั้งกับ doctor · preflight · ตัวเรนเดอร์แผ่นกฎ
· และ harness ของ fail-fix loop

**กฎกับตัวบังคับอยู่คนละไฟล์โดยตั้งใจ** เพราะอายุไม่เท่ากัน — `rules.yaml` คือสิ่งที่
repo นี้เผยแพร่ ส่วน `gates.yaml` คือสิ่งที่ repo นี้ถูกบังคับด้วยตัวเอง

**คลังเก็บสองภาษา**: อังกฤษเป็นข้อความที่เผยแพร่ ส่วนถ้อยคำไทยต้นฉบับอยู่ในฟิลด์
`*_th` คู่กัน เพราะคำแปลของบันทึกเหตุการณ์คือการเล่าใหม่ และการเล่าใหม่ไม่ใช่ตัวบันทึก

โค้ด: Apache-2.0 (ผู้ร่วมพัฒนาลงนาม `CLA.md`) · กฎและเอกสาร: CC BY 4.0
