# verifiable-gates

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22103110.svg)](https://doi.org/10.5281/zenodo.22103110)

A gate registry that is enforced two ways against the tests and CI jobs behind
it, gates that must carry evidence of having gone red on a real defect, and a
portable rule set that lets an AI coding agent work under the same rules in
another project.

**Archived under a DOI.** The state the claims point at is tagged
[`evidence-freeze-1`](https://github.com/sayam/verifiable-gates/releases/tag/evidence-freeze-1)
in both this repository and the reference implementation, and archived at
[doi:10.5281/zenodo.22103110](https://doi.org/10.5281/zenodo.22103110). That DOI resolves to the
latest version; each release also gets one of its own. `evidence-freeze-1` and
`v0.1.0` are **different commits** on purpose: the freeze is the state the
measurements were taken on, the release is the state the package first shipped in.

**Status: the extraction is complete (2026-08-28).** Every stage has landed. What
remains in the reference implementation,
[`sayam/flask-todolist`](https://github.com/sayam/flask-todolist), is the
*registers* — which test, which job, which threshold — read by thin adapters on
the paths its hooks and jobs already called. The decision, what moved and what
stayed, is
[ADR 0075 §6](https://github.com/sayam/flask-todolist/blob/main/docs/adr/0075-thesis-track-freeze-effort-and-ceilings.md)
and the file-by-file census is
[`extraction.yaml`](https://github.com/sayam/flask-todolist/blob/main/extraction.yaml)
there, which now records nothing outstanding: 0 to move, 58 that stayed, 13
split between the two. **First release: `v0.1.0` (2026-08-28)** — the point at
which this repository and the reference implementation separate. Consume it as
a pinned submodule or a versioned dependency, never from `main`.

| Stage | What lands | Status |
|---|---|---|
| 1 | Package skeleton · CI · hash-pinned tools · registry schema | **here** |
| 2 | The nine checks · the doctor · preflight · the skill generator | **here** |
| 3 | The governance checkers (ratchets, censuses, platform posture) | **here** |
| 4 | The supply-chain checkers | **here** |
| 5 | The measurement instruments and the comparison data | **here** |
| 6 | Registry handover · citation · DOI | **here** |
| — | Extraction closed — census at move 0 / stay 58 / split 13 · `v0.1.0` | **2026-08-28** |

Stage 6 was taken out of order on purpose. The rules are what this project *is*;
stages 3 to 5 move the machinery that happens to enforce some of them, and a
bundle that shipped the machinery before the rules would have had nothing to say
about the ones it cannot enforce.

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
import verifiable_gates

catalogue = verifiable_gates.rules.load("rules.yaml")
# `package_dir` is where a rule's `script:` is looked for; without it, only the
# shape of the path is checked — a checker that is not there would go unnoticed.
for problem in verifiable_gates.rules.problems(catalogue, package_dir="src/verifiable_gates"):
    print(problem)
```

`rules.yaml` ships with the checkout, not with the wheel — it is the published
artefact (CC BY 4.0), and the package is the machinery that reads it.

Also here: the nine stdlib-only checkers, the installer and the doctor that runs
them in a project that has installed nothing, preflight, the sheet renderer, and
the fail-fix harness.

**What the bundle decides, and what it does not.** Of the 92 rules, **nine** have a
checker in the bundle (`script:` in `rules.yaml`); the doctor and the installer
decide those and nothing else. The other 83 are the rule sheets — an agent is held
to them by reading, and the *Enforced in the reference* line on each says how one
project turned it into a test. `rules.yaml` and the sheets are not installed by
`install()` either; they come with the checkout. Two consequences worth knowing
before trusting a green: the doctor reports a rule it cannot decide as `NA`, and a
project where every rule is `NA` exits 0 — that is "nothing was measured", not "the
project passed" (a path that `scaffold.json` *names* and the project does not have is
never `NA`, though: that is a broken configuration, and it is a finding; and a
`Dockerfile*` the project has but never named is a finding too, not "no
Dockerfile"; and a scan that crashes, hangs past its timeout, or answers half a verdict
before crashing is `[error]` with its stderr passed through, never `[found]` — red,
but no verdict); and `rules.problems()` only checks that a `script:` exists when it is
given the package directory (`package_dir=`), as the doctor does. On a fresh
install the only `pass` is the shipped index (`gates-registry-total`), which has
to be true about itself; the starting workflow the installer wrote is `NA` to the
two pinning checkers until a line of it changes — a green on the bundle's own
file says nothing about the project.

**What the two pinning checkers read.** `ci-tools-hash-pinned` and
`actions-sha-pinned` read every workflow, every composite action a workflow names
with `uses: ./<path>` wherever it lives, folded or not, and — for installs — every
shell script a `run:` line hands off to, known by its `.sh` name or by its shebang,
quoted or not, from wherever the shell stands (a `cd dir &&` before it, or the
step's `working-directory:`), with comments stripped first — a `#` inside a word
(`$#`, `${#PKGS}`, `\#`) is not one. In a workflow only what `run:` executes is judged —
a `name:` or an `env:` that quotes the command is prose — and `--require-hashes`
counts only as an argument of the install itself. A command inside `$( )`,
backticks, a `( )` subshell, an `sh -c` string (`-c` folded into other flags
too — `bash -lc`), a string `python -c` hands to `os.system`, or after a lone `&`
executes and is judged; a bare `echo` of the words is prose — unless a shell is
handed the words, by a pipe (`echo … | bash`), a here-string or `eval`, and a
`${PIP:-pip}` default is read as the word. The YAML shapes `uses :` and `- {uses: …}` are
read the way the platform reads them — and so are a quoted key (`"run":`), an
alias of an anchor set anywhere in the file (`run: *cmd`, `uses: *co`, with the
anchor's version comment), a tagged value (`!!str`), and a plain, quoted or
folded (`>`) scalar that continues onto the next line, which YAML joins with a
space before the shell sees it; only a literal block (`|`) keeps its lines
apart, and a `uses` under `with:` is an input, not a step. An install is judged
whether it says `pip`, `pipx`, `uv tool install`, `uv add`, `uvx`, `poetry add`,
`pdm add` or `pipenv install`; `uv run --locked`, `uv sync --locked` and `uv build`
install from a lock and are left alone. A `uses:` folded onto the next line is
read from that line. `actions-sha-pinned` judges both halves of its title: a
floating tag is a finding, and so is a commit SHA with no version comment beside
it — a pin nobody can read or move (a `docker://` digest needs none). Of the
other checkers, `adr-index-complete` reports two records sharing a number as
well as a gap, and `csp-no-inline` reads `ONCLICK=`, `STYLE=` and a `<style>`
element the way a browser does — in any case, split over lines or not, with
comments blanked first.

Since the extraction finished, so are the deciders that used to live in the
reference implementation: ratchets and the measurements that feed them, the
removal census, the synchroniser for numbers a project advertises about itself,
the platform-posture reader, the advisory deciders for pip, npm, and container
images, the scanner-coverage check, the two censuses that watch what CI cannot see
(when a schedule last fired, how long redness stood), the `gh` wrapper, and the
ASVS worksheet builder with the gate-to-ASVS crosswalk — and the research
instruments, the ASVS
probe and the battery that runs it over a directory of generated applications,
together with [the experiment](docs/comparison/) they measured. Each arrives with
its messages as an input, so a project can keep printing in its own language.

The two schemas — `rules.py` for this catalogue, `registry.py` for a project's
`gates.yaml` — encode five rules that came from real traps, not from theory:

- a gate whose `layer` is `internal` **cannot** be `portable` — a rule tied to one
  project's architecture, exported as universal, is an overclaim; that hold is in
  the gate schema, and the rule schema refuses `internal` outright, since a rule
  in this catalogue is published whole (`portable` on a rule is refused as a
  gate's field);
- a key neither schema knows is refused, not skipped — a misspelt `born_frm` is a
  rule with no origin that looks like one with;
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

**เก็บถาวรใต้ DOI แล้ว** — สถานะที่ข้ออ้างชี้ถึงถูกตรึงไว้ที่ tag `evidence-freeze-1`
ทั้ง repo นี้และ reference implementation · archive อยู่ที่
[doi:10.5281/zenodo.22103110](https://doi.org/10.5281/zenodo.22103110) ซึ่งชี้รุ่นล่าสุดเสมอ
(แต่ละ release มี DOI ของตัวเองด้วย) · `evidence-freeze-1` กับ `v0.1.0` เป็น**คนละคอมมิต**โดยตั้งใจ —
tag แรกคือสถานะตอนวัด tag หลังคือสถานะตอนแพ็กเกจออกครั้งแรก

**สถานะ: ถอดครบทุกขั้นแล้ว (2026-08-28)** — ที่
[`flask-todolist`](https://github.com/sayam/flask-todolist) เหลือ *ทะเบียน*
(เทสต์ไหน · job ไหน · พื้นเท่าไหร่) กับ adapter บาง ๆ บนพาธเดิม ตาม ADR 0075
ข้อ 6 และ `extraction.yaml` ที่นั่น ซึ่งไม่เหลืออะไรค้างแล้ว (move 0 · stay 58 · split 13) ·
**รุ่นแรก `v0.1.0` (2026-08-28)** คือจุดที่สอง repo แยกทางกัน — ใช้ผ่าน submodule
ที่ pin ไว้หรือ dependency ที่ระบุรุ่น ไม่ใช่จาก `main`

วันนี้มี **คลังกฎ 92 ข้อ** (`rules.yaml`) ที่แต่ละข้อพกกับดักจริงที่ให้กำเนิดมันมาด้วย
· ตัวตรวจ stdlib ล้วนเก้าตัว · ตัวติดตั้งกับ doctor · preflight · ตัวเรนเดอร์แผ่นกฎ
· harness ของ fail-fix loop · **ตัวตัดสินฝั่ง governance กับ supply chain**
(ratchet · สำมะโนของที่ถอด · ตัวซิงก์เลขที่โฆษณา · ท่าทีแพลตฟอร์ม · advisory ของ
pip/npm/image · ขอบเขตของตัวสแกน · สำมะโนตารางเวลากับสายแดงที่ CI มองไม่เห็น ·
แผ่นงาน ASVS กับ crosswalk) · และ **เครื่องมือวิจัย** (ASVS probe + battery)
พร้อม[การทดลอง](docs/comparison/)ที่มันวัด — ทุกตัวรับถ้อยคำเป็น input
โปรเจกต์ปลายทางจึงพิมพ์ภาษาของตัวเองได้

**กฎกับตัวบังคับอยู่คนละไฟล์โดยตั้งใจ** เพราะอายุไม่เท่ากัน — `rules.yaml` คือสิ่งที่
repo นี้เผยแพร่ ส่วน `gates.yaml` คือสิ่งที่ repo นี้ถูกบังคับด้วยตัวเอง

**บันเดิลตัดสินได้ 9 จาก 92** — เฉพาะกฎที่มี `script:` เท่านั้นที่ doctor กับ installer
ตัดสินให้ อีก 83 ข้อคือแผ่นกฎที่ agent ถูกบังคับด้วยการอ่าน · doctor รายงานกฎที่ตัดสินไม่ได้เป็น `NA`
และโปรเจกต์ที่ทุกข้อเป็น `NA` ออก 0 แปลว่า "ไม่ได้วัดอะไร" ไม่ใช่ "ผ่าน" · สแกนที่ล่ม ค้างเกินเวลา หรือพิมพ์คำตัดสินได้ครึ่งเดียวแล้วพัง
รายงานเป็น `[error]` พร้อมส่ง stderr ต่อ ไม่ใช่ `[found]` · หลังติดตั้งใหม่
ด่านเดียวที่ `pass` คือทะเบียนที่ส่งมากับบันเดิล (`gates-registry-total`) ส่วน workflow
ตั้งต้นที่ตัวติดตั้งเขียนให้เป็น `NA` สำหรับตัวตรวจ pin ทั้งสองจนกว่าจะมีบรรทัดถูกแก้ —
เขียวบนไฟล์ของบันเดิลเองไม่ได้บอกอะไรเกี่ยวกับโปรเจกต์ · ตัวตรวจ pin อ่าน workflow ทุกไฟล์
composite action ที่ `uses: ./<path>` ชี้ไม่ว่าอยู่ที่ไหนหรือพับบรรทัดอย่างไร และเชลล์สคริปต์ที่ `run:`
เรียกต่อ ไม่ว่าจะรู้จากชื่อ `.sh` หรือจาก shebang ใส่เครื่องหมายคำพูดหรือไม่ก็ตาม จากที่ที่เชลล์ยืนอยู่ (`cd dir &&` ก่อนหน้า หรือ `working-directory:` ของ step) โดยตัดคอมเมนต์ก่อน — `#` ที่อยู่ในคำ (`$#`, `${#PKGS}`, `\#`) ไม่ใช่คอมเมนต์ · ใน workflow ตัดสินเฉพาะสิ่งที่
`run:` รันจริง (`name:` หรือ `env:` ที่ยกคำสั่งมาพูดถึงเป็นแค่ข้อความ) และ `--require-hashes` นับเมื่อเป็น
อาร์กิวเมนต์ของคำสั่งติดตั้งเองเท่านั้น · คำสั่งใน `$( )` backtick subshell สตริงของ `sh -c` (รวม `-c` ที่พับกับ flag อื่นเช่น `bash -lc`) สตริงที่ `python -c` ส่งให้ `os.system` หรือหลัง `&` เดี่ยว รันจริงจึงถูกตัดสิน
ส่วน `echo` ที่แค่พูดคำนั้นเป็นข้อความ — เว้นแต่คำนั้นถูกส่งให้เชลล์ผ่าน pipe (`echo … | bash`) here-string หรือ `eval` และค่าเริ่มต้นของ `${PIP:-pip}` ถูกอ่านเป็นคำนั้น · รูป YAML `uses :` และ `- {uses: …}` ถูกอ่านแบบเดียวกับที่แพลตฟอร์มอ่าน — เช่นเดียวกับคีย์ในเครื่องหมายคำพูด (`"run":`) alias ของ anchor ที่ตั้งไว้ที่ใดก็ได้ในไฟล์ (`run: *cmd`, `uses: *co` พร้อม comment เวอร์ชันของ anchor) ค่าที่มี tag (`!!str`) และ scalar แบบ plain quoted หรือ folded (`>`) ที่ต่อลงบรรทัดถัดไป ซึ่ง YAML เชื่อมด้วยช่องว่างก่อนถึงเชลล์ · มีแต่ literal block (`|`) ที่คงบรรทัดแยกกัน และ `uses` ใต้ `with:` เป็น input ไม่ใช่ step · `actions-sha-pinned` ตัดสินทั้งสองครึ่งของชื่อกฎ: tag ลอยเป็น finding และ
commit SHA ที่ไม่มี comment บอกเวอร์ชันข้าง ๆ ก็เป็น finding (digest ของ `docker://` ไม่ต้องมี) ·
`adr-index-complete` รายงานบันทึกสองฉบับที่ใช้เลขเดียวกันเช่นเดียวกับเลขที่ขาด · `csp-no-inline` อ่าน
`ONCLICK=` `STYLE=` และ `<style>` แบบไม่สนตัวพิมพ์และไม่สนการตัดบรรทัด เหมือนที่เบราว์เซอร์อ่าน
โดยลบคอมเมนต์ก่อน · `Dockerfile*` ที่มีอยู่แต่ไม่ได้ตั้งชื่อไว้ใน `scaffold.json` ถือเป็น
finding ไม่ใช่ "ไม่มี Dockerfile"

**คลังเก็บสองภาษา**: อังกฤษเป็นข้อความที่เผยแพร่ ส่วนถ้อยคำไทยต้นฉบับอยู่ในฟิลด์
`*_th` คู่กัน เพราะคำแปลของบันทึกเหตุการณ์คือการเล่าใหม่ และการเล่าใหม่ไม่ใช่ตัวบันทึก

โค้ด: Apache-2.0 (ผู้ร่วมพัฒนาลงนาม `CLA.md`) · กฎและเอกสาร: CC BY 4.0
