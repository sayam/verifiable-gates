# verifiable-gates (ภาษาไทย)

ฉบับภาษาอังกฤษคือ [`README.md`](https://github.com/sayam/verifiable-gates/blob/main/README.md) — ไฟล์นี้เป็นคำแปลที่วางไว้ข้างกัน หัวข้อตรงกันหนึ่งต่อหนึ่ง
(`DECISIONS.md` `the-thai-readme-is-a-file-beside-it`)

ทะเบียน gate ของ CI สำหรับโปรเจกต์ที่สร้างด้วยหรือไม่ด้วย AI coding agent · gate ทุกด่านต้องพกหลักฐานว่าเคยแดง
ตอนของเสียจริง · และชุดกฎเดียวกันส่งออกเป็น agent skill ให้ agent ทำงานใต้กติกาที่ CI จะบังคับในภายหลัง ·
**บันเดิลตัดสินได้ 9 จาก 92** — เฉพาะกฎที่มี `script:` เท่านั้นที่ doctor กับ installer ตัดสินให้
อีก 83 ข้อคือแผ่นกฎที่ agent ถูกบังคับด้วยการอ่าน

**สิ่งที่มันไม่ใช่** — ไม่ใช่ linter และไม่ใช่ของแทน SAST · มันตัดสินท่าทีของคอนฟิกกับกระบวนการ (การ pin · CSP ·
บัญชี ADR · supply chain) ไม่ใช่ความถูกต้องของโค้ด · เขียวแปลว่ากฎที่มันตัดสินได้ไม่พบอะไร
และไม่ได้บอกอะไรเลยเกี่ยวกับกฎที่มันตัดสินไม่ได้

## เริ่มใช้

```sh
pip install verifiable-gates
cd your-project
python -m verifiable_gates.install .     # เขียน tools/, scaffold.json, gates.yaml และ workflow ตั้งต้น
python3 tools/gates_doctor.py            # รันตัวตรวจที่โปรเจกต์ถือไว้ตอนนี้
```

สองคำสั่งนั้นพิมพ์อะไรใน git repository เปล่า (2026-09-05, v0.3.0 · พาธเต็มในบรรทัด install ย่อเป็น `<your-project>`):

```text
$ python -m verifiable_gates.install .
installed into <your-project> — 9 gates (9 scan) · check with: python3 tools/gates_doctor.py
for the instruction file your agents read (AGENTS.md, CLAUDE.md), add one line: `run python3 tools/gates_doctor.py --rules before editing`
this bundle also carries the working: 10 practices, each with the lesson behind it and the pull requests it held on — off here; read `python3 tools/gates_doctor.py --working`, turn on with `install <dest> --working`
$ python3 tools/gates_doctor.py
[   NA] actions-sha-pinned — only the bundle's own starting workflow, untouched — nothing of yours to read
[   NA] adr-index-complete — no docs/adr — this rule reads the .md records and the README.md index under docs/adr (scaffold.json adr_path)
[   NA] ci-tools-hash-pinned — only the bundle's own starting workflow, untouched — nothing of yours to read
[   NA] csp-no-inline — no app/templates — this rule reads .html, .htm, .jinja, .jinja2 and .j2 templates under app/templates (scaffold.json templates_path)
[   NA] delete-means-soft-delete — no app — this rule reads Python modules under app (scaffold.json src_path) — session.delete calls outside the purge_paths
[ pass] gates-registry-total
[   NA] image-digest-pinned — no Dockerfile — this rule reads the FROM lines of the root Dockerfile (scaffold.json dockerfiles), and .github/dependabot.yml for a docker ecosystem
[   NA] logic-knows-no-http — no app/services — this rule reads Python modules under app/services (scaffold.json services_path) — their imports, for request-side symbols
[   NA] no-debug-entrypoint — no entrypoint — this rule reads the Python entrypoints run.py, wsgi.py, app.py and main.py (scaffold.json entrypoints), as an AST

waiting on this project's own tests: 0 gates
[exit 0]
```

หลังติดตั้งใหม่ ด่านเดียวที่ `pass` คือทะเบียนที่ส่งมากับบันเดิล ซึ่งต้องจริงเกี่ยวกับตัวมันเอง · ที่เหลือเป็น `NA`
จนกว่าโปรเจกต์จะมีอะไรให้ตรวจ · **exit 0 ตรงนี้แปลว่า "ไม่ได้วัดอะไร" ไม่ใช่ "โปรเจกต์ผ่าน"**

เพิ่ม workflow หนึ่งไฟล์ที่มี tag ลอยกับคำสั่งติดตั้งที่ไม่ได้ pin แล้วคำสั่งเดิมตอบด้วย finding สองข้อและ exit 1
(transcript เต็ม รวม finding ข้อที่สามที่ job ใหม่นั้นเองก่อขึ้น อยู่ใน [`docs/output-semantics.md`](https://github.com/sayam/verifiable-gates/blob/main/docs/output-semantics.md)):

```text
[found] actions-sha-pinned — Every action is pinned to a commit SHA with the version in a comment
  born from: Tags move, commits do not — upload-artifact once sat on @v4 at a single call site for ten days with CI green throughout.
actions-sha-pinned: .github/workflows/lint.yml: actions/checkout@v4
…
[found] ci-tools-hash-pinned — Tools CI installs for itself are pinned by hash, on both the Python and the Node side
  born from: An unpinned install command takes whatever is newest at the second the job runs, and it runs with our workflow's privileges · pinning one package at a time pins only that package while the rest of the tree still floats.
ci-tools-hash-pinned: .github/workflows/lint.yml: pip install ruff
…
** scans found problems in 3 gates: actions-sha-pinned, ci-tools-hash-pinned, gates-registry-total
[exit 1]
```

## อ่านผลอย่างไร

| คำตัดสิน | หมายความว่า | ไม่ได้หมายความว่า |
|-----------|-------------|-------------------|
| `pass`    | ตัวตรวจดูแล้ว และกฎข้อนั้นเป็นจริง | กฎที่ไม่มีตัวตรวจก็เป็นจริงด้วย |
| `[found]` | ตัวตรวจดูแล้ว และกฎข้อนั้นถูกละเมิด · doctor ออก 1 | build ไม่ปลอดภัยในแบบที่ตัวตรวจนี้ไม่ได้อ่าน |
| `NA`      | ไม่มีของชนิดที่ตัวตรวจนี้อ่านอยู่ที่นี่เลย · มันบอกว่าไปหาอะไร | กฎข้อนั้นผ่าน |
| `[error]` | ตัวตรวจตอบไม่ได้: ล่ม · ค้างเกินเวลา · ไฟล์ถอดรหัสไม่ได้หรือใหญ่เกิน · ไดเรกทอรีเข้าไม่ได้ · `scaffold.json` ผิดรูป · ส่ง stderr ต่อ · doctor ออก 1 | "ดูแล้วไม่เจอ" · มันแดงโดยไม่มีคำตัดสิน |

สองเรื่องที่ต้องรู้ก่อนเชื่อสีเขียว:

- **โปรเจกต์ที่ทุกข้อเป็น `NA` ออก 0 นั่นคือโปรเจกต์ที่ยังไม่ได้วัด** ไม่ใช่โปรเจกต์ที่ผ่าน
  (`DECISIONS.md` `doctor-all-na-exits-zero`)
- พาธที่ `scaffold.json` *ตั้งชื่อไว้* แต่โปรเจกต์ไม่มี เป็น finding ไม่ใช่ `NA` — คอนฟิกที่พังคือของเสีย ไม่ใช่ของที่ไม่มี

อนุกรมวิธานเต็ม — ทุกกรณีของ `NA` กับ `[error]` · record ของ `--installed` · `--rules` บนบันเดิลที่ถูกแก้ ·
การแมปเป็น SARIF — อยู่ใน [`docs/output-semantics.md`](https://github.com/sayam/verifiable-gates/blob/main/docs/output-semantics.md) (ภาษาอังกฤษ)

## สามทางที่จะรันมัน

| ประตู | รันเมื่อ | คอนฟิก | ค่าเริ่มต้น |
|-------|---------|--------|-------------|
| GitHub Action | ทุก push / pull request | `uses: sayam/verifiable-gates@<commit-sha> # vX.Y.Z` · เลือกใส่ `with: sarif: gates.sarif` ได้ ([`action.yml`](https://github.com/sayam/verifiable-gates/blob/main/action.yml)) | — |
| pre-commit | ก่อนทุก commit | `repo: https://github.com/sayam/verifiable-gates` · hook `gates-doctor` หรือ hook ต่อ id ของกฎ ([`.pre-commit-hooks.yaml`](https://github.com/sayam/verifiable-gates/blob/main/.pre-commit-hooks.yaml)) | — |
| hook ตอน edit ใน Claude Code | หลังทุก `Edit` / `Write` | ติดตั้ง plugin (ข้างล่าง) · `"env": {"VERIFIABLE_GATES_AT_EDIT": "1"}` ใน `.claude/settings.json` ([`hooks/hooks.json`](https://github.com/sayam/verifiable-gates/blob/main/hooks/hooks.json)) | ปิด · รายงาน ไม่ปฏิเสธ |

ทั้งสามประตูรัน `tools/` ตามที่โปรเจกต์มี **และไม่พกสำเนาเลย** — SHA · `rev` · หรือ plugin ขยับ
จึงไม่เปลี่ยนสิ่งที่โปรเจกต์ถูกบังคับ (`DECISIONS.md` `ci-runs-the-bundle-the-project-installed`)

action อยู่บน [GitHub Marketplace](https://github.com/marketplace/actions/verifiable-gates) ในชื่อ `verifiable-gates`
— pin ด้วย SHA ไม่ใช่ tag ที่หน้า listing เสนอ · hook ตอน edit ส่ง finding กลับให้ agent ตอนที่ยังถือไฟล์อยู่
และไม่ปฏิเสธอะไร (`DECISIONS.md` `the-edit-hook-reports-and-does-not-refuse`)

## ตัวตรวจแต่ละตัวตัดสินอะไร

ตัวตรวจ stdlib ล้วนเก้าตัว แต่ละตัวเป็นไฟล์ Python ไฟล์เดียวใต้ `tools/checks/` รันโดย doctor หรือรันเองก็ได้ ·
ตัว bundle เองไม่เปิดเครือข่าย · `python3 tools/gates_doctor.py --rules` พิมพ์รายการนี้จากบันเดิลที่ติดตั้งอยู่
พร้อมเหตุการณ์ที่ให้กำเนิดแต่ละข้อ

| id ของกฎ | จับอะไร | อ่านอะไร |
|---|---|---|
| [`gates-registry-total`](https://github.com/sayam/verifiable-gates/blob/main/docs/checker-reference.md#gates-registry-total) | job ใน CI ที่ไม่มีแถวในทะเบียน · แถวที่ไม่มีอะไรทำให้ล้มได้ · ไฟล์เทสต์ที่ไม่มี gate ไหนอ้าง | `gates.yaml` · ทุก workflow ใต้ `.github/workflows` · ไฟล์เทสต์ |
| [`actions-sha-pinned`](https://github.com/sayam/verifiable-gates/blob/main/docs/checker-reference.md#actions-sha-pinned) | `uses:` บน tag ลอย หรือบน SHA ที่ไม่มี comment บอกเวอร์ชันข้าง ๆ | step `uses:` ของ workflow และ composite action ใต้ `.github` |
| [`ci-tools-hash-pinned`](https://github.com/sayam/verifiable-gates/blob/main/docs/checker-reference.md#ci-tools-hash-pinned) | เครื่องมือที่ CI ติดตั้งให้ตัวเองโดยไม่มี hash หรือ lock | บรรทัด pip · pipx · uv · poetry · pdm · pipenv · npm · npx · yarn · pnpm · `python -m build` ใน workflow สคริปต์ที่มันเรียก และ Dockerfile ที่ราก |
| [`image-digest-pinned`](https://github.com/sayam/verifiable-gates/blob/main/docs/checker-reference.md#image-digest-pinned) | base image ที่ไม่ได้ pin ด้วย manifest-index digest หรือ pin ไว้โดยไม่มีใครขยับให้ | บรรทัด `FROM` ของ Dockerfile ที่ราก · `.github/dependabot.yml` |
| [`csp-no-inline`](https://github.com/sayam/verifiable-gates/blob/main/docs/checker-reference.md#csp-no-inline) | script · style · handler แบบ inline ใน template | `.html` `.htm` `.jinja` `.jinja2` `.j2` ใต้พาธ template |
| [`no-debug-entrypoint`](https://github.com/sayam/verifiable-gates/blob/main/docs/checker-reference.md#no-debug-entrypoint) | entrypoint ที่เปิด debug console ได้ | `run.py` `wsgi.py` `app.py` `main.py` อ่านเป็น AST |
| [`logic-knows-no-http`](https://github.com/sayam/verifiable-gates/blob/main/docs/checker-reference.md#logic-knows-no-http) | โมดูล service ที่ import จากฝั่ง request | โมดูล Python ใต้พาธ services · import ของมัน |
| [`delete-means-soft-delete`](https://github.com/sayam/verifiable-gates/blob/main/docs/checker-reference.md#delete-means-soft-delete) | `session.delete` นอกทาง purge ทางเดียว (layer `business`) | โมดูล Python ใต้พาธ source |
| [`adr-index-complete`](https://github.com/sayam/verifiable-gates/blob/main/docs/checker-reference.md#adr-index-complete) | ADR ที่หายจาก index · เลขซ้ำหรือขาด · supersession ที่จดทางเดียว | บันทึก `.md` และ index `README.md` ใต้พาธ ADR |

พาธในตารางคือค่าเริ่มต้นที่ `scaffold.json` พกมา โปรเจกต์ย้ายมันได้ที่นั่น

## กฎ 92 ข้อ

**คลังกฎ 92 ข้อ** (`rules.yaml`) ที่แต่ละข้อพกกับดักจริงที่ให้กำเนิดมันมาด้วย (`born_from`) เพราะกฎที่ไม่มีที่มา
คือกฎที่ไม่มีใครรู้ว่าควรเอาออกเมื่อไร · **แผ่นกฎเป็น Agent Skill ตาม spec แล้ว** อยู่ที่ `skills/verifiable-gates/`
(หน้าแรก [`SKILL.md`](https://github.com/sayam/verifiable-gates/blob/main/skills/verifiable-gates/SKILL.md) + entry เต็มใน `references/`)

ติดตั้ง skill โดยไม่ต้อง clone ได้สองทางผ่านท่อที่ repo นี้ไม่ได้เป็นเจ้าของ:

| ท่อ | คำสั่ง | ลงอะไร |
|---|---|---|
| Skills CLI | `npx skills add sayam/verifiable-gates` | ท่อ `npx` ลง **สี่** ไฟล์ใต้ `skills/verifiable-gates/` (แผ่นกฎกับ references) และไม่มีอะไรอื่น · ท่อส่ง identifier ของ repo และ skill เป็น telemetry ปิดได้ด้วย `DISABLE_TELEMETRY=1` |
| Claude Code | `claude plugin marketplace add sayam/verifiable-gates` แล้ว `claude plugin install verifiable-gates@verifiable-gates` | ทั้ง repo เป็น plugin |

กฎที่มีตัวตรวจ (`script:` ใน `rules.yaml`) คือกฎที่ doctor กับ installer ตัดสิน และไม่ตัดสินอะไรมากกว่านั้น ·
กฎที่เหลือคือแผ่นกฎที่ agent ถูกบังคับด้วยการอ่าน และบรรทัด *Enforced in the reference* ของแต่ละข้อบอกว่าโปรเจกต์หนึ่ง
เปลี่ยนมันเป็นเทสต์อย่างไร · ท่อแต่ละท่อส่งอะไร ดึงอะไร และทำไมไม่มี registry ของ repo นี้เอง อยู่ใน
[`docs/history.md`](https://github.com/sayam/verifiable-gates/blob/main/docs/history.md#the-two-pipes) และ `DECISIONS.md` `distribution-is-two-pipes-nobody-here-owns`

กฎที่ปรากฏภายหลังว่าผิด จะถูก**ถอนคาที่** ไม่ถูกลบ: `retracted:` เก็บมันไว้ในคลังกฎและบนแผ่นกฎพร้อมวันที่กับเหตุผล
ทำเครื่องหมายไว้และไม่ถูกนับในตัวเลขใด ๆ เพื่อให้คนที่เคยทำตามกฎข้อนั้นรู้ได้ว่าควรหยุด · วันนี้ยังไม่มีข้อไหนถูกถอน

กฎหนึ่งข้อบอกได้ด้วยว่ามันอยู่ตรงไหนในคำศัพท์ที่คนอื่นใช้กันอยู่แล้ว: `maps_to:` อ้างรายการของ
[OpenSSF Scorecard](https://github.com/ossf/scorecard/blob/main/docs/checks.md) ·
[SLSA v1.0](https://slsa.dev/spec/v1.0/levels) · [NIST SSDF](https://csrc.nist.gov/pubs/sp/800/218/final)
— 35 ข้อที่มี `maps_to:` และที่เหลือตั้งใจไม่อ้างอะไรเลย เพราะไม่มีรายการไหนในสามชุดนั้นครอบมัน ·
การแมปแปลว่ากฎข้อนี้**ทำให้รายการนั้นสำเร็จหรือช่วยให้สำเร็จ** ไม่ใช่ว่าเท่ากัน · ชื่อรายการเป็นชุดปิดที่อ่านมาจาก
เอกสารต้นทาง สะกดผิดจึงถูกปฏิเสธ แทนที่จะถูกเผยแพร่เป็นแผนที่ที่ชี้ไปที่ไม่มีอะไร

`rules.yaml` กับแผ่นกฎมากับ checkout ไม่ได้มากับ wheel — แพ็กเกจคือเครื่องจักรที่อ่านคลังกฎ:

```python
import verifiable_gates

catalogue = verifiable_gates.rules.load("rules.yaml")
# `package_dir` คือที่ที่ `script:` ของกฎถูกมองหา ถ้าไม่ให้ จะเช็คแค่รูปร่างของพาธ
# — ตัวตรวจที่ไม่มีอยู่จริงจะหลุดไปเงียบ ๆ
for problem in verifiable_gates.rules.problems(catalogue, package_dir="src/verifiable_gates"):
    print(problem)
```

## ข้อจำกัดในการออกแบบ

สคีมาสองตัว — `rules.py` สำหรับคลังกฎนี้ · `registry.py` สำหรับ `gates.yaml` ของโปรเจกต์ — เข้ารหัสกฎห้าข้อ
ที่มาจากกับดักจริง ไม่ใช่จากทฤษฎี:

- gate ที่ `layer` เป็น `internal` **ห้าม** เป็น `portable` — กฎที่ผูกกับสถาปัตยกรรมของโปรเจกต์เดียวแล้วส่งออกว่าเป็นสากล
  คือการอ้างเกินจริง · ข้อนี้ถือไว้ในสคีมาของ gate ส่วนสคีมาของกฎปฏิเสธ `internal` ตั้งแต่ต้น เพราะกฎในคลังนี้
  เผยแพร่ทั้งก้อน (`portable` บนกฎถูกปฏิเสธว่าเป็นฟิลด์ของ gate)
- คีย์ที่สคีมาไม่รู้จักถูกปฏิเสธ ไม่ใช่ข้าม — `born_frm` ที่สะกดผิดคือกฎไม่มีที่มาที่หน้าตาเหมือนมีที่มา
- ทุกอย่างที่ส่งออกต้องบอกชื่อกับดักที่สร้างมัน (`born_from`) เพราะกฎที่ไม่มีที่มาคือกฎที่ไม่มีใครรู้ว่าควรเอาออกเมื่อไร
- รายการ `proved_by` ต้องบอกว่าจับอะไรได้และเมื่อไร — gate ที่ไม่มีใครเคยเห็นแดง แยกไม่ออกจาก gate ที่ไม่ได้ตรวจอะไร
- คำศัพท์ของ `kind` `severity` `layer` และ `pillar` เป็นเซตปิด

**กฎกับตัวบังคับอยู่คนละไฟล์โดยตั้งใจ** เพราะอายุไม่เท่ากัน — `rules.yaml` คือสิ่งที่ repo นี้เผยแพร่
ส่วน `gates.yaml` คือสิ่งที่ repo นี้ถูกบังคับด้วยตัวเอง · สิ่งที่ตั้งใจไม่ทำ พร้อมเงื่อนไขที่จะทำให้ข้อตัดสินนั้นหมดอายุ
อยู่ใน [`DECISIONS.md`](https://github.com/sayam/verifiable-gates/blob/main/DECISIONS.md)

## ที่มาและสถานะ

เก็บถาวรที่ [doi:10.5281/zenodo.22103110](https://doi.org/10.5281/zenodo.22103110) ซึ่งชี้รุ่นล่าสุดเสมอ
(แต่ละ release มี DOI ของตัวเองด้วย) · tag `evidence-freeze-1` คือสถานะตอนวัด และ `v0.1.0` (2026-08-28)
คือสถานะตอนแพ็กเกจออกครั้งแรก — เป็น**คนละคอมมิต**โดยตั้งใจ · การถอดออกจาก reference implementation
[`flask-todolist`](https://github.com/sayam/flask-todolist) ครบทุกขั้นแล้ว · ตารางเวที สำมะโน และสิ่งที่ยังอยู่ที่นั่น
อยู่ใน [`docs/history.md`](https://github.com/sayam/verifiable-gates/blob/main/docs/history.md) (ภาษาอังกฤษ) · ใช้ผ่าน submodule ที่ pin ไว้หรือ dependency ที่ระบุรุ่น ไม่ใช่จาก `main`

ทั้งหมดนี้ไม่ต้องเชื่อเอาเอง — [`docs/auditing.md`](https://github.com/sayam/verifiable-gates/blob/main/docs/auditing.md) (ภาษาอังกฤษ) คือหนึ่งชั่วโมงนั้น:
กฎ 11 ข้อที่ repo นี้ประกาศกับตัวเอง คำสั่งที่ตัดสินแต่ละข้อ และสิ่งที่ไม่มีคำสั่งไหนที่นี่ตอบได้ เขียนไว้ตรง ๆ

**คลังเก็บสองภาษา**: อังกฤษเป็นข้อความที่เผยแพร่ ส่วนถ้อยคำไทยต้นฉบับอยู่ในฟิลด์
`*_th` คู่กัน เพราะคำแปลของบันทึกเหตุการณ์คือการเล่าใหม่ และการเล่าใหม่ไม่ใช่ตัวบันทึก

## สัญญาอนุญาต

- โค้ด: [Apache-2.0](https://github.com/sayam/verifiable-gates/blob/main/LICENSE) · ผู้ร่วมพัฒนาลงนาม [`CLA.md`](https://github.com/sayam/verifiable-gates/blob/main/CLA.md) — หนึ่งบรรทัดใน pull request · คุณยังถือลิขสิทธิ์ของคุณ
- กฎและเอกสาร: [CC BY 4.0](https://github.com/sayam/verifiable-gates/blob/main/LICENSE-docs)

แอปพลิเคชันที่ถอดมายังเป็น AGPL-3.0-or-later · ต่างกันโดยตั้งใจ: เครื่องมือ CI ไม่ใช่ network service
และกฎที่ตั้งใจให้เอาไปใช้ในคู่มือภายในองค์กรต้องไม่บังคับ share-alike

---

[`README.md`](https://github.com/sayam/verifiable-gates/blob/main/README.md) · [`docs/`](https://github.com/sayam/verifiable-gates/tree/main/docs) · [`CONTRIBUTING.md`](https://github.com/sayam/verifiable-gates/blob/main/CONTRIBUTING.md) ·
[`SECURITY.md`](https://github.com/sayam/verifiable-gates/blob/main/SECURITY.md) · [`CHANGELOG.md`](https://github.com/sayam/verifiable-gates/blob/main/CHANGELOG.md) · [การทดลอง](https://github.com/sayam/verifiable-gates/tree/main/docs/comparison)
