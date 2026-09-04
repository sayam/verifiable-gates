# verifiable-gates

[![DOI 10.5281/zenodo.22103110](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.22103110-blue)](https://doi.org/10.5281/zenodo.22103110)

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
it.** They are rendered into an agent skill in the layout of the
[Agent Skills specification](https://agentskills.io/specification), so any of the
products that read that layout can be handed it unchanged:
[`skills/verifiable-gates/SKILL.md`](skills/verifiable-gates/SKILL.md) is the front
page — how to read the rules, the five practices underneath them, and one line per
rule — and the full entries sit beside it in
[`references/baseline.md`](skills/verifiable-gates/references/baseline.md), the
baseline layer, where deviating is a defect, and
[`references/business.md`](skills/verifiable-gates/references/business.md),
agreements an application of a given kind may legitimately decide differently. (The
two sheets lived at the repository root as `SKILL.md` and `SKILL-BUSINESS.md` until
v0.1.12; `DECISIONS.md` `the-sheets-live-under-skills` says why they moved and why
no copy stayed.)

**Two ways to take the skill without cloning**, through pipes this repository does
not own: `npx skills add sayam/verifiable-gates` puts it into whichever agent you use
(the Skills CLI reads the `skills/` directory), and in Claude Code
`claude plugin marketplace add sayam/verifiable-gates` then
`claude plugin install verifiable-gates@verifiable-gates` (the one-entry marketplace
in `.claude-plugin/`). Both install the same three files and nothing else — a skill
is instructions. The scanners are still `pip install verifiable-gates` and
`python -m verifiable_gates.install`, because a checker is not something to be
handed an agent as prose. `DECISIONS.md` `distribution-is-two-pipes-nobody-here-owns`
says why there is no marketplace or registry of this project's own.

**Three front doors for a project that has installed the bundle.** In CI,
`uses: sayam/verifiable-gates@<commit-sha>` runs the doctor the project installed —
[`action.yml`](action.yml) is `run:` steps only, with nothing inside it to pin, and an
optional `sarif:` input. With pre-commit, `repo: https://github.com/sayam/verifiable-gates`
offers [`gates-doctor`](.pre-commit-hooks.yaml) and one hook per scanner, by the id of
the rule it decides. **All three run `tools/` as the project has it and none carries a
copy**, so a SHA, a `rev` or a plugin update moving changes nothing about what the project
is held to (`DECISIONS.md` `ci-runs-the-bundle-the-project-installed`). The third opens at
edit time: with the plugin enabled in Claude Code and `VERIFIABLE_GATES_AT_EDIT=1` in
the project's `.claude/settings.json` under `env`, a [hook](hooks/hooks.json) runs the
installed doctor after every `Edit` or `Write` and hands a finding back to the agent
while it still holds the file. Off by default; it reports and refuses nothing
(`DECISIONS.md` `the-edit-hook-reports-and-does-not-refuse`).

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
never `NA`, though: that is a broken configuration, and it is a finding — and so are a
value of the wrong shape, a list where one path goes or a string where a list of names
goes, and a path that leads outside the project, each naming the key it came from; and a
`Dockerfile*` the project has but never named is a finding too, not "no
Dockerfile"; a directory that is *there* and holds no file of the kind a checker reads
— an `app/` of Go, a templates directory of `.ejs` — is `NA` naming what it looked for,
not a pass, because a rule the tool cannot check must not look like a rule it checked;
and a scan that crashes, hangs past its timeout, answers half a verdict
before crashing, meets a file it cannot decode, may not open, or that is larger than the
8 MiB a scanner reads whole, cannot read `scaffold.json` as a configuration at all, or
cannot walk the whole tree it was pointed at — a directory closed to it is *not* the
answer a directory that is not there gets, which stays `NA` — is `[error]` with its
stderr passed through, never `[found]` — red,
but no verdict); and `rules.problems()` only checks that a `script:` exists when it is
given the package directory (`package_dir=`), as the doctor does. On a fresh
install the only `pass` is the shipped index (`gates-registry-total`), which has
to be true about itself; the starting workflow the installer wrote is `NA` to the
two pinning checkers until a line of it changes — a green on the bundle's own
file says nothing about the project. That index check reads its own direction too: a
gate whose job cannot turn the build red — a workflow with no trigger, `if: false`, or
`continue-on-error: true` — is a finding, because a row nothing can fail is a row and
nothing else; and each of its findings names the file to open and the row to add or
change, so the first line a stranger reads points at the second. And the bundle keeps a
record of what it installed: `gates_doctor
--installed` holds every file it wrote to the contents it wrote, not merely to being
present — and writes nothing into the tree it checks, not even bytecode — and an upgrade names what this version no longer ships and leaves it in place,
because a file in your repository is yours to remove. An install that stopped partway is
read as one: the doctor leads with *the last install into this tree did not finish*
rather than reporting the files that did land as files somebody edited — and one still
under way is read as one too, because the record is written before the first file and
names what each file is about to become. And
`gates_doctor --rules` prints the rules the bundle decides — each with where it came
from and which scanner reads it — for the instruction file a project keeps for its
agents (`AGENTS.md`, `CLAUDE.md`) to point at: read at run time from the installed
manifest, so an upgrade cannot leave an agent on yesterday's rule, and only the rules a
scanner here can decide, so no instruction stands without a gate behind it. It prints
them only off a bundle the installed record still vouches for: an edited manifest, an
edited scanner, or no record at all prints no rules and exits 2, because the file it
reads lives inside the project it holds to account (`DECISIONS.md`
`the-rules-are-read-off-a-bundle-that-is-still-intact`). A finding in the report
carries the same two lines — `[found] <gate> — <rule>` and `born from: <incident>` above
the scanner's own — and off a bundle the record no longer vouches for it carries the gate
alone and one line saying why, the findings printed either way. And
`gates_doctor --sarif FILE` writes the same run as SARIF 2.1.0 for code scanning,
reviewdog or an IDE — a finding is a result, while `NA` and a scan that did not answer
are notifications on the invocation, never results, so a reader counting results cannot
mistake "could not look" for "looked and found nothing". A file already at that path is
replaced only if it is this doctor's run over the same root; another tree's run, or
anything else, is left where it is and named — two trees given one path lose no answer.

**What the two pinning checkers read.** `ci-tools-hash-pinned` and
`actions-sha-pinned` read every workflow, every composite action a workflow names
with `uses: ./<path>` wherever it lives, folded or not, and — for installs — every
shell script a `run:` line hands off to, known by its `.sh` name or by its shebang,
quoted or not, from wherever the shell stands (a `cd dir &&` before it, or the
step's `working-directory:`), with comments stripped first — a `#` inside a word
(`$#`, `${#PKGS}`, `\#`) is not one. In a workflow only what `run:` executes is judged —
a `name:` or an `env:` that quotes the command is prose — and `--require-hashes`
counts only as an argument of the install itself, quoted or not; so do
`PIP_REQUIRE_HASHES=1` on the command or in the step's own `env:`, and a
requirements file whose every line carries a `--hash=`, because pip requires
hashes in each of those cases on its own; `--no-index`, and a wheel installed
with `--no-deps`, fetch nothing and are left alone. A command inside `$( )`,
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
whether it says `pip`, `pipx`, `uv tool install`, `uv tool run`, `uv add`, `uvx`,
`uv run --with`, `poetry add`, `pdm add` or `pipenv install`, and on the Node side
`npm install`, `npm exec`, `npx`, `yarn add`, `pnpm add` or `pnpm dlx`; `pip wheel`
builds in an isolated environment like `python -m build` and is held to
`--no-build-isolation`; `uv run --locked`, `uv sync --locked`, `uv build`, `npm ci`,
`yarn install --immutable` and `pnpm install --frozen-lockfile` install from a lock
and are left alone, as are `npx --no`, `npm exec --no` and `pnpm exec`, which run the
installed copy and refuse to fetch. A Node finding says what replaces that line —
`npm ci` for `npm install`, `npx --no <tool>` for `npx <tool>` — and names the lock it
needs, or says to commit one when it is not there. A `uses:` folded onto the next line is
read from that line. `actions-sha-pinned` judges both halves of its title: a
floating tag is a finding, and so is a commit SHA with no version comment beside
it — a pin nobody can read or move (a `docker://` digest needs none). Of the
other checkers, `adr-index-complete` reports two records sharing a number as
well as a gap, and `csp-no-inline` reads `ONCLICK=`, `STYLE=` and a `<style>`
element the way a browser does — in any case, split over lines or not (the `=`
on the line after the name too), with comments blanked first (one that never
closes runs to the end of the file), entities inside an attribute value decoded
before the scheme is read (`&#106;avascript:`), and `.htm`, `.jinja`, `.jinja2`
and `.j2` templates read like `.html`.

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

**แผ่นกฎเป็น Agent Skill ตาม spec แล้ว** อยู่ที่ `skills/verifiable-gates/` (หน้าแรก `SKILL.md` + entry เต็มใน `references/`)
· ติดตั้งโดยไม่ต้อง clone ได้สองทางผ่านท่อที่ repo นี้ไม่ได้เป็นเจ้าของ: `npx skills add sayam/verifiable-gates`
(Skills CLI ลงให้ agent ที่คุณใช้) หรือใน Claude Code `claude plugin marketplace add sayam/verifiable-gates` แล้ว
`claude plugin install verifiable-gates@verifiable-gates` · ทั้งสองทางลงไฟล์สามไฟล์เดียวกันและไม่มีอะไรอื่น —
skill คือคำสั่ง ส่วนตัวสแกนยังเป็น `pip install verifiable-gates` + `python -m verifiable_gates.install`
เพราะตัวตรวจไม่ใช่ของที่จะยื่นให้ agent เป็นร้อยแก้ว

**สามประตูหน้าสำหรับโปรเจกต์ที่ติดตั้ง bundle แล้ว** — ใน CI `uses: sayam/verifiable-gates@<commit-sha>` รัน doctor
ที่โปรเจกต์ติดตั้งไว้ (`action.yml` เป็น `run:` ล้วน ไม่มีอะไรข้างในให้ pin · มี input `sarif:` ให้เลือก) · ใน pre-commit
`repo: https://github.com/sayam/verifiable-gates` มี hook `gates-doctor` กับ hook ต่อ scanner ตาม id ของกฎ · ทั้งสองรัน `tools/`
ตามที่โปรเจกต์มี **ทั้งสามประตูไม่พกสำเนาเลย** — SHA · `rev` · หรือ plugin ขยับ จึงไม่เปลี่ยนสิ่งที่โปรเจกต์ถูกบังคับ · ประตูที่สามเปิดตอน edit: เปิด plugin
ใน Claude Code แล้วตั้ง `VERIFIABLE_GATES_AT_EDIT=1` ใน `.claude/settings.json` ของโปรเจกต์ใต้ `env` — hook (`hooks/hooks.json`)
จะรัน doctor ที่ติดตั้งไว้หลังทุก `Edit`/`Write` แล้วส่ง finding กลับให้ agent ตอนที่ยังถือไฟล์อยู่ · ปิดเป็นค่าเริ่มต้น · รายงาน ไม่ปฏิเสธ
(`DECISIONS.md` `the-edit-hook-reports-and-does-not-refuse`)

**บันเดิลตัดสินได้ 9 จาก 92** — เฉพาะกฎที่มี `script:` เท่านั้นที่ doctor กับ installer
ตัดสินให้ อีก 83 ข้อคือแผ่นกฎที่ agent ถูกบังคับด้วยการอ่าน · doctor รายงานกฎที่ตัดสินไม่ได้เป็น `NA`
และโปรเจกต์ที่ทุกข้อเป็น `NA` ออก 0 แปลว่า "ไม่ได้วัดอะไร" ไม่ใช่ "ผ่าน" · ไดเรกทอรีที่ *มีอยู่* แต่ไม่มีไฟล์ชนิดที่ตัวตรวจอ่านเลย
— `app/` ที่มีแต่ Go หรือไดเรกทอรี template ที่มีแต่ `.ejs` — เป็น `NA` พร้อมบอกว่าไปหาอะไร ไม่ใช่ `pass`
เพราะกฎที่เครื่องมือตรวจไม่ได้ต้องไม่หน้าตาเหมือนกฎที่ตรวจแล้ว · สแกนที่ล่ม ค้างเกินเวลา พิมพ์คำตัดสินได้ครึ่งเดียวแล้วพัง
เจอไฟล์ที่ถอดรหัสไม่ได้ ไม่มีสิทธิ์เปิด หรือใหญ่เกิน 8 MiB ที่ตัวสแกนอ่านทั้งไฟล์ อ่าน `scaffold.json` เป็นคอนฟิกไม่ได้เลย
หรือเดินต้นไม้ที่ถูกชี้ให้ดูไม่ทั่ว — ไดเรกทอรีที่ปิดไม่ให้เข้าไม่ใช่คำตอบเดียวกับไดเรกทอรีที่ *ไม่มีอยู่* ซึ่งยังเป็น `NA` —
รายงานเป็น `[error]` พร้อมส่ง stderr ต่อ ไม่ใช่ `[found]` · หลังติดตั้งใหม่
ด่านเดียวที่ `pass` คือทะเบียนที่ส่งมากับบันเดิล (`gates-registry-total`) ส่วน workflow
ตั้งต้นที่ตัวติดตั้งเขียนให้เป็น `NA` สำหรับตัวตรวจ pin ทั้งสองจนกว่าจะมีบรรทัดถูกแก้ —
เขียวบนไฟล์ของบันเดิลเองไม่ได้บอกอะไรเกี่ยวกับโปรเจกต์ · ตัวตรวจทะเบียนอ่านทิศของตัวเองด้วย: gate ที่งานของมัน
ทำให้ build แดงไม่ได้ — workflow ที่ไม่มี trigger, `if: false`, หรือ `continue-on-error: true` — เป็น finding
เพราะแถวที่ไม่มีอะไรทำให้ล้มได้คือแถวเปล่า ๆ · และ finding แต่ละข้อของมันบอกชื่อไฟล์ที่ต้องเปิดกับแถวที่ต้องเพิ่มหรือแก้
บรรทัดแรกที่คนแปลกหน้าอ่านจึงชี้ไปที่บรรทัดถัดไป · และบันเดิลจดสิ่งที่มันติดตั้งไว้: `gates_doctor --installed`
ถือทุกไฟล์ที่มันเขียนไว้กับ *เนื้อ* ที่มันเขียน ไม่ใช่แค่ว่ามีไฟล์อยู่ — และไม่เขียนอะไรลงต้นไม้ที่มันตรวจ แม้แต่ bytecode · และตอนอัปเกรด มันบอกว่ารุ่นนี้เลิกส่งอะไร
แล้วปล่อยไฟล์นั้นไว้ เพราะไฟล์ในรีโปของคุณเป็นสิทธิ์ของคุณที่จะลบ · การติดตั้งที่หยุดกลางทางถูกอ่านว่าอย่างนั้น —
doctor ขึ้นต้นด้วย *การติดตั้งครั้งล่าสุดลงในต้นไม้นี้ยังไม่จบ* แทนที่จะรายงานไฟล์ที่ลงไปแล้วว่าเป็นไฟล์ที่ถูกใครแก้ · และ `gates_doctor --rules` พิมพ์กฎที่บันเดิล
ตัดสินได้ — แต่ละข้อพร้อมที่มาและตัวสแกนที่อ่านมัน — ให้ไฟล์คำสั่งที่โปรเจกต์เก็บไว้ให้ agent (`AGENTS.md`, `CLAUDE.md`)
ชี้มาหา: อ่านตอนรันจาก manifest ที่ติดตั้งอยู่ การอัปเกรดจึงทิ้ง agent ไว้กับกฎเมื่อวานไม่ได้ และมีเฉพาะกฎที่ตัวสแกน
ตรงนี้ตัดสินได้ จึงไม่มีคำสั่งข้อไหนยืนอยู่โดยไม่มีด่านหนุนหลัง · และมันพิมพ์กฎเฉพาะจากบันเดิลที่ record ยังรับรอง —
manifest ถูกแก้ · scanner ถูกแก้ · หรือไม่มี record เลย = ไม่พิมพ์กฎสักข้อ exit 2 เพราะไฟล์ที่มันอ่านอยู่ในโปรเจกต์ที่มันกำลังตรวจเอง
(`DECISIONS.md` `the-rules-are-read-off-a-bundle-that-is-still-intact`) · finding ในรายงานพกสองบรรทัดเดียวกัน —
`[found] <gate> — <กฎ>` และ `born from: <เหตุการณ์>` เหนือบรรทัดของตัวสแกน — และจากบันเดิลที่ record ไม่รับรองแล้ว
พิมพ์แค่ชื่อ gate กับหนึ่งบรรทัดบอกว่าทำไม ส่วน finding พิมพ์ทั้งสองกรณี · และ `gates_doctor --sarif FILE` เขียนผลรอบเดียวกันเป็น SARIF 2.1.0
ให้ code scanning, reviewdog หรือ IDE — finding เป็น result ส่วน `NA` กับสแกนที่ตอบไม่ได้เป็น notification บน invocation ไม่ใช่ result
คนที่นับ result จึงเข้าใจ "ดูไม่ได้" เป็น "ดูแล้วไม่เจอ" ไม่ได้ · ไฟล์ที่มีอยู่แล้วที่ path นั้นจะถูกแทนที่ก็ต่อเมื่อเป็นผลรอบของ doctor
ตัวนี้บน root เดียวกัน ถ้าเป็นผลของต้นไม้อื่นหรืออย่างอื่นจะถูกทิ้งไว้และบอกชื่อ — สองต้นไม้ที่ใช้ path เดียวกันไม่เสียคำตอบ · ตัวตรวจ pin อ่าน workflow ทุกไฟล์
composite action ที่ `uses: ./<path>` ชี้ไม่ว่าอยู่ที่ไหนหรือพับบรรทัดอย่างไร และเชลล์สคริปต์ที่ `run:`
เรียกต่อ ไม่ว่าจะรู้จากชื่อ `.sh` หรือจาก shebang ใส่เครื่องหมายคำพูดหรือไม่ก็ตาม จากที่ที่เชลล์ยืนอยู่ (`cd dir &&` ก่อนหน้า หรือ `working-directory:` ของ step) โดยตัดคอมเมนต์ก่อน — `#` ที่อยู่ในคำ (`$#`, `${#PKGS}`, `\#`) ไม่ใช่คอมเมนต์ · ใน workflow ตัดสินเฉพาะสิ่งที่
`run:` รันจริง (`name:` หรือ `env:` ที่ยกคำสั่งมาพูดถึงเป็นแค่ข้อความ) และ `--require-hashes` นับเมื่อเป็น
อาร์กิวเมนต์ของคำสั่งติดตั้งเองเท่านั้น (จะอยู่ในเครื่องหมายคำพูดหรือไม่ก็ตาม) · `PIP_REQUIRE_HASHES=1` บนคำสั่งหรือใน `env:` ของ step และไฟล์ requirements ที่ทุกบรรทัดมี `--hash=` ก็นับ เพราะ pip บังคับ hash เองในกรณีเหล่านั้น · `--no-index` และ wheel ที่ติดตั้งด้วย `--no-deps` ไม่ดึงอะไรจาก index จึงไม่ถูกตัดสิน · คำสั่งใน `$( )` backtick subshell สตริงของ `sh -c` (รวม `-c` ที่พับกับ flag อื่นเช่น `bash -lc`) สตริงที่ `python -c` ส่งให้ `os.system` หรือหลัง `&` เดี่ยว รันจริงจึงถูกตัดสิน
ส่วน `echo` ที่แค่พูดคำนั้นเป็นข้อความ — เว้นแต่คำนั้นถูกส่งให้เชลล์ผ่าน pipe (`echo … | bash`) here-string หรือ `eval` และค่าเริ่มต้นของ `${PIP:-pip}` ถูกอ่านเป็นคำนั้น · รูป YAML `uses :` และ `- {uses: …}` ถูกอ่านแบบเดียวกับที่แพลตฟอร์มอ่าน — เช่นเดียวกับคีย์ในเครื่องหมายคำพูด (`"run":`) alias ของ anchor ที่ตั้งไว้ที่ใดก็ได้ในไฟล์ (`run: *cmd`, `uses: *co` พร้อม comment เวอร์ชันของ anchor) ค่าที่มี tag (`!!str`) และ scalar แบบ plain quoted หรือ folded (`>`) ที่ต่อลงบรรทัดถัดไป ซึ่ง YAML เชื่อมด้วยช่องว่างก่อนถึงเชลล์ · มีแต่ literal block (`|`) ที่คงบรรทัดแยกกัน และ `uses` ใต้ `with:` เป็น input ไม่ใช่ step · `actions-sha-pinned` ตัดสินทั้งสองครึ่งของชื่อกฎ: tag ลอยเป็น finding และ
commit SHA ที่ไม่มี comment บอกเวอร์ชันข้าง ๆ ก็เป็น finding (digest ของ `docker://` ไม่ต้องมี) ·
`adr-index-complete` รายงานบันทึกสองฉบับที่ใช้เลขเดียวกันเช่นเดียวกับเลขที่ขาด · `csp-no-inline` อ่าน
`ONCLICK=` `STYLE=` และ `<style>` แบบไม่สนตัวพิมพ์และไม่สนการตัดบรรทัด (รวม `=` ที่อยู่บรรทัดถัดจากชื่อ) เหมือนที่เบราว์เซอร์อ่าน
โดยลบคอมเมนต์ก่อน (คอมเมนต์ที่ไม่ปิดกินถึงท้ายไฟล์) ถอด entity ในค่าของ attribute ก่อนอ่าน scheme (`&#106;avascript:`) และอ่าน `.htm` `.jinja` `.jinja2` `.j2` เหมือน `.html` · `Dockerfile*` ที่มีอยู่แต่ไม่ได้ตั้งชื่อไว้ใน `scaffold.json` ถือเป็น
finding ไม่ใช่ "ไม่มี Dockerfile" · ค่าใน `scaffold.json` ที่ผิดรูป — ลิสต์ในที่ที่ต้องเป็นพาธเดียว หรือสตริงในที่ที่ต้อง
เป็นลิสต์ของชื่อ — และพาธที่พาออกไปนอกโปรเจกต์ เป็น finding ที่บอกชื่อคีย์ เช่นเดียวกับพาธที่ตั้งชื่อไว้แต่ไม่มีอยู่จริง

**คลังเก็บสองภาษา**: อังกฤษเป็นข้อความที่เผยแพร่ ส่วนถ้อยคำไทยต้นฉบับอยู่ในฟิลด์
`*_th` คู่กัน เพราะคำแปลของบันทึกเหตุการณ์คือการเล่าใหม่ และการเล่าใหม่ไม่ใช่ตัวบันทึก

โค้ด: Apache-2.0 (ผู้ร่วมพัฒนาลงนาม `CLA.md`) · กฎและเอกสาร: CC BY 4.0
