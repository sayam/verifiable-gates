# Where this came from

The README used to open with this. It is the provenance of the project: what was
extracted from where, in what order, and what the two pipes that distribute the skill
do on the way. Nothing here is needed to install or run the bundle.

## The extraction

`verifiable-gates` was extracted from a reference implementation,
[`sayam/flask-todolist`](https://github.com/sayam/flask-todolist), where every rule
was learned from a real failure. **The extraction is complete (2026-08-28).** Every
stage has landed. What remains in the reference implementation is the *registers* —
which test, which job, which threshold — read by thin adapters on the paths its hooks
and jobs already called. The decision, what moved and what stayed, is
[ADR 0075 §6](https://github.com/sayam/flask-todolist/blob/main/docs/adr/0075-thesis-track-freeze-effort-and-ceilings.md)
and the file-by-file census is
[`extraction.yaml`](https://github.com/sayam/flask-todolist/blob/main/extraction.yaml)
there, which now records nothing outstanding: 0 to move, 58 that stayed, 13 split
between the two.

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
stages 3 to 5 move the machinery that happens to enforce some of them, and a bundle
that shipped the machinery before the rules would have had nothing to say about the
ones it cannot enforce.

**First release: `v0.1.0` (2026-08-28)** — the point at which this repository and the
reference implementation separate. Consume it as a pinned submodule or a versioned
dependency, never from `main`.

## The freeze and the DOI

The state the claims point at is tagged
[`evidence-freeze-1`](https://github.com/sayam/verifiable-gates/releases/tag/evidence-freeze-1)
in both this repository and the reference implementation, and archived at
[doi:10.5281/zenodo.22103110](https://doi.org/10.5281/zenodo.22103110). That DOI
resolves to the latest version; each release also gets one of its own.
`evidence-freeze-1` and `v0.1.0` are **different commits** on purpose: the freeze is
the state the measurements were taken on, the release is the state the package first
shipped in (`DECISIONS.md` `freeze-tag-vs-release`).

## What else came across

Since the extraction finished, so did the deciders that used to live in the reference
implementation: ratchets and the measurements that feed them, the removal census, the
synchroniser for numbers a project advertises about itself, the platform-posture
reader, the advisory deciders for pip, npm, and container images, the
scanner-coverage check, the two censuses that watch what CI cannot see (when a
schedule last fired, how long redness stood), the `gh` wrapper, and the ASVS worksheet
builder with the gate-to-ASVS crosswalk — and the research instruments, the ASVS probe
and the battery that runs it over a directory of generated applications, together with
[the experiment](comparison/) they measured. Each arrives with its messages as an
input, so a project can keep printing in its own language.

Also in the package: the nine stdlib-only checkers, the installer and the doctor that
runs them in a project that has installed nothing, preflight, the sheet renderer, and
the fail-fix harness.

## The sheets

The rules are rendered into an agent skill in the layout of the
[Agent Skills specification](https://agentskills.io/specification), so any of the
products that read that layout can be handed it unchanged:
[`skills/verifiable-gates/SKILL.md`](../skills/verifiable-gates/SKILL.md) is the front
page — how to read the rules, the five practices underneath them, and one line per
rule — and the full entries sit beside it in
[`references/baseline.md`](../skills/verifiable-gates/references/baseline.md), the
baseline layer, where deviating is a defect, and
[`references/business.md`](../skills/verifiable-gates/references/business.md),
agreements an application of a given kind may legitimately decide differently. The
two sheets lived at the repository root as `SKILL.md` and `SKILL-BUSINESS.md` until
v0.1.12; `DECISIONS.md` `the-sheets-live-under-skills` says why they moved and why no
copy stayed.

## The two pipes

Two ways to take the skill without cloning, through pipes this repository does not
own: `npx skills add sayam/verifiable-gates` puts it into whichever agent you use (the
Skills CLI reads the `skills/` directory), and in Claude Code
`claude plugin marketplace add sayam/verifiable-gates` then
`claude plugin install verifiable-gates@verifiable-gates` (the one-entry marketplace in
`.claude-plugin/`). `DECISIONS.md` `distribution-is-two-pipes-nobody-here-owns` says
why there is no marketplace or registry of this project's own.

| | `npx skills add` | `claude plugin install` |
|---|---|---|
| What lands | the files under `skills/verifiable-gates/` — the sheet and its references — copied, not linked, and nothing else | the whole repository: its plugin is the root (`"source": "./"`) because the hook runs `src/verifiable_gates/edit_hook.py`; a git clone of the marketplace plus a copy per version in Claude Code's plugin cache (measured on 2.1.261, 2026-09-05), so its manifest declares both licences, `Apache-2.0 AND CC-BY-4.0` |
| What it sends | the Skills CLI's own README (at `435076e`) says an install sends the repository and skill identifiers as telemetry, off with `DISABLE_TELEMETRY=1` or `DO_NOT_TRACK=1` | not measured here |
| What it pins | nothing: it fetches the default branch at the moment of the command and takes no ref (`@<sha>` is read as a skill name); its `skills-lock.json` records a content hash it does not enforce, and `skills update` re-fetches and moves the copy to `.agents/skills/` with a symlink in its place (measured on Skills CLI 1.5.23, 2026-09-05) | the plugin version |

Through the `npx` pipe you get `main` of that moment; the pinned routes are the
submodule and the versioned dependency. A skill is instructions. The scanners are
still `pip install verifiable-gates` and `python -m verifiable_gates.install`,
because a checker is not something to be handed an agent as prose. Neither pipe is
this repository's, so what each does on the way is the pipe's to say. The bundle
itself opens no network — no shipped file imports one, and
`tests/test_checks_are_standalone.py` holds it.
