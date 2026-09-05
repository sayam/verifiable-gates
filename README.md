# verifiable-gates

[![CI](https://img.shields.io/github/actions/workflow/status/sayam/verifiable-gates/ci.yml?branch=main&label=CI)](https://github.com/sayam/verifiable-gates/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/verifiable-gates)](https://pypi.org/project/verifiable-gates/)
[![Python](https://img.shields.io/pypi/pyversions/verifiable-gates)](https://pypi.org/project/verifiable-gates/)
[![Code: Apache-2.0](https://img.shields.io/badge/code-Apache--2.0-blue)](https://github.com/sayam/verifiable-gates/blob/main/LICENSE)
[![Rules: CC BY 4.0](https://img.shields.io/badge/rules-CC_BY_4.0-blue)](https://github.com/sayam/verifiable-gates/blob/main/LICENSE-docs)
[![DOI 10.5281/zenodo.22103110](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.22103110-blue)](https://doi.org/10.5281/zenodo.22103110)

Thai: [`README.th.md`](https://github.com/sayam/verifiable-gates/blob/main/README.th.md).

A registry of CI gates for projects built with or without AI coding agents. Every
gate carries evidence of having gone red on a real defect, and the same rules ship
as an agent skill, so the agent works under the constraints CI will later enforce.
Of the 92 rules, **nine** have a checker in this package;
the other 83 are written for an agent to read.

**What this is not.** Not a linter and not a SAST replacement. It decides
configuration and process posture — pinning, CSP, ADR bookkeeping, supply chain —
not code correctness. A green run means the nine checks it can decide found nothing;
it says nothing about the 83 it cannot.

## Quickstart

```sh
pip install verifiable-gates
cd your-project
python -m verifiable_gates.install .     # writes tools/, scaffold.json, gates.yaml, a starting workflow
python3 tools/gates_doctor.py            # runs the checkers the project now holds
```

What the two commands printed, in an empty git repository (2026-09-05, v0.3.0; the
install line's absolute path is shortened to `<your-project>`):

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

On a fresh install the only `pass` is the registry index, which has to be true
about itself. Everything else is `NA` until the project has something to check.
**Exit 0 here means nothing was measured, not that the project passed.**

Add one workflow with a floating tag and an unpinned install, and the same command
answers with two findings and exits 1 (the full transcript, with the third finding
the new job itself causes, is in [`docs/output-semantics.md`](https://github.com/sayam/verifiable-gates/blob/main/docs/output-semantics.md)):

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

## Reading the output

| Verdict   | Means                                                                 | Does not mean                                              |
|-----------|-----------------------------------------------------------------------|------------------------------------------------------------|
| `pass`    | The checker looked and the rule holds.                                | Any rule without a checker holds.                          |
| `[found]` | The checker looked and the rule is broken; the doctor exits 1.        | The build is unsafe in ways this checker does not read.    |
| `NA`      | Nothing of the kind this checker reads is here; it says what it looked for. | The rule passed.                                     |
| `[error]` | The checker could not answer: crash, timeout, undecodable or oversize file, unreadable directory, malformed `scaffold.json`. Its stderr is passed through; the doctor exits 1. | "Looked and found nothing." It is red without a verdict. |

Two consequences to know before trusting a green:

- **A project where every rule is `NA` exits 0. That is an unmeasured project**, not
  a passed one (`DECISIONS.md` `doctor-all-na-exits-zero`).
- A path that `scaffold.json` names and the project does not have is a finding, not
  `NA`: a broken configuration is a defect, not an absence.

The full taxonomy — every `NA` and `[error]` case, the `--installed` record, `--rules`
off an edited bundle, the SARIF mapping — is in
[`docs/output-semantics.md`](https://github.com/sayam/verifiable-gates/blob/main/docs/output-semantics.md).

## Three ways to run it

| Entry point           | Runs                         | Config                                                                                                                      | Default                     |
|-----------------------|------------------------------|-----------------------------------------------------------------------------------------------------------------------------|-----------------------------|
| GitHub Action         | on push / pull request       | `uses: sayam/verifiable-gates@<commit-sha> # vX.Y.Z` · optional `with: sarif: gates.sarif` ([`action.yml`](https://github.com/sayam/verifiable-gates/blob/main/action.yml))  | —                           |
| pre-commit            | before each commit           | `repo: https://github.com/sayam/verifiable-gates` · hook `gates-doctor`, or one hook per rule id ([`.pre-commit-hooks.yaml`](https://github.com/sayam/verifiable-gates/blob/main/.pre-commit-hooks.yaml)) | —                    |
| Claude Code edit hook | after every `Edit` / `Write` | plugin installed (below) · `"env": {"VERIFIABLE_GATES_AT_EDIT": "1"}` in `.claude/settings.json` ([`hooks/hooks.json`](https://github.com/sayam/verifiable-gates/blob/main/hooks/hooks.json)) | off; reports, never refuses |

All three run `tools/` as the project has it, and none carries a copy of the
checkers. Moving the SHA, the `rev` or the plugin version changes nothing about what
the project is held to (`DECISIONS.md` `ci-runs-the-bundle-the-project-installed`).

The action is listed on the
[GitHub Marketplace](https://github.com/marketplace/actions/verifiable-gates) as
`verifiable-gates` — pin the SHA, not the tag the listing offers. The edit hook
hands a finding back to the agent while it still holds the file, and refuses nothing
(`DECISIONS.md` `the-edit-hook-reports-and-does-not-refuse`).

## What the nine checkers decide

Each of the nine stdlib-only checkers is one Python file under `tools/checks/`, run by
the doctor or on its own; the bundle opens no network. `python3 tools/gates_doctor.py --rules` prints
this list off the installed bundle, with each rule's incident.

| Rule id | What it catches | What it reads |
|---|---|---|
| [`gates-registry-total`](https://github.com/sayam/verifiable-gates/blob/main/docs/checker-reference.md#gates-registry-total) | A CI job with no row in the gate index, a row nothing can fail, a test file no gate claims | `gates.yaml`, every workflow under `.github/workflows`, the test files |
| [`actions-sha-pinned`](https://github.com/sayam/verifiable-gates/blob/main/docs/checker-reference.md#actions-sha-pinned) | A `uses:` on a floating tag, or on a SHA with no version comment beside it | `uses:` steps of workflows and composite actions under `.github` |
| [`ci-tools-hash-pinned`](https://github.com/sayam/verifiable-gates/blob/main/docs/checker-reference.md#ci-tools-hash-pinned) | A tool CI installs for itself without hashes or a lock | pip, pipx, uv, poetry, pdm, pipenv, npm, npx, yarn, pnpm and `python -m build` lines in workflows, the scripts they run, the root Dockerfile |
| [`image-digest-pinned`](https://github.com/sayam/verifiable-gates/blob/main/docs/checker-reference.md#image-digest-pinned) | A base image not pinned to a manifest-index digest, or pinned with nobody to move it | `FROM` lines of the root Dockerfile, `.github/dependabot.yml` |
| [`csp-no-inline`](https://github.com/sayam/verifiable-gates/blob/main/docs/checker-reference.md#csp-no-inline) | Inline script, style or handler in a template | `.html`, `.htm`, `.jinja`, `.jinja2`, `.j2` under the templates path |
| [`no-debug-entrypoint`](https://github.com/sayam/verifiable-gates/blob/main/docs/checker-reference.md#no-debug-entrypoint) | An entrypoint that can open a debug console | `run.py`, `wsgi.py`, `app.py`, `main.py`, as an AST |
| [`logic-knows-no-http`](https://github.com/sayam/verifiable-gates/blob/main/docs/checker-reference.md#logic-knows-no-http) | A service module importing from the request side | Python modules under the services path, their imports |
| [`delete-means-soft-delete`](https://github.com/sayam/verifiable-gates/blob/main/docs/checker-reference.md#delete-means-soft-delete) | A `session.delete` outside the one purge path (layer `business`) | Python modules under the source path |
| [`adr-index-complete`](https://github.com/sayam/verifiable-gates/blob/main/docs/checker-reference.md#adr-index-complete) | An ADR missing from the index, a repeated or skipped number, a supersession recorded one way | `.md` records and the `README.md` index under the ADR path |

The paths are the defaults `scaffold.json` carries; the project moves them there.

## The 92 rules

[`rules.yaml`](https://github.com/sayam/verifiable-gates/blob/main/rules.yaml) — 92 rules, each carrying the incident that produced it
(`born_from`), because a rule with no origin is a rule nobody knows when to remove.
They are rendered into an agent skill in the layout of the
[Agent Skills specification](https://agentskills.io/specification):
[`skills/verifiable-gates/SKILL.md`](https://github.com/sayam/verifiable-gates/blob/main/skills/verifiable-gates/SKILL.md) is the front
page, and the full entries sit beside it in `references/`.

Two pipes this repository does not own install the skill without cloning:

| Pipe | Command | What lands |
|---|---|---|
| Skills CLI | `npx skills add sayam/verifiable-gates` | lands the **four** files under `skills/verifiable-gates/` and nothing else; the pipe sends the repository and skill identifiers as telemetry, off with `DISABLE_TELEMETRY=1` |
| Claude Code | `claude plugin marketplace add sayam/verifiable-gates`, then `claude plugin install verifiable-gates@verifiable-gates` | the whole repository, as a plugin |

The nine rules with a checker (`script:` in `rules.yaml`) are the ones the doctor and
the installer decide, and nothing else. The other 83 are the rule sheets an agent is held to by
reading, and the *Enforced in the reference* line on each says how one project turned
it into a test. What each pipe sends and fetches, and why there is no registry of this
project's own, is in [`docs/history.md`](https://github.com/sayam/verifiable-gates/blob/main/docs/history.md#the-two-pipes) and
`DECISIONS.md` `distribution-is-two-pipes-nobody-here-owns`.

A rule that turns out to be wrong is **withdrawn in place**, never deleted: `retracted:`
keeps it in the catalogue and on its sheet with the date and the reason, marked and out of
every count, so a reader who followed it can find out that they should stop. Nothing is
withdrawn today.

A rule may also say where it sits in a vocabulary somebody else already speaks:
`maps_to:` names items of [OpenSSF Scorecard](https://github.com/ossf/scorecard/blob/main/docs/checks.md),
[SLSA v1.0](https://slsa.dev/spec/v1.0/levels) and
[NIST SSDF](https://csrc.nist.gov/pubs/sp/800/218/final) — 35 of them name where they sit,
and the rest deliberately name nothing, because no item of those three covers them. A
mapping says the rule would satisfy or contribute to that item, never that the two are
equal; the item names are a closed set read off the publications, so a misspelling is
refused rather than published as a map to nothing.

`rules.yaml` and the sheets come with the checkout, not with the wheel. The package
is the machinery that reads the catalogue:

```python
import verifiable_gates

catalogue = verifiable_gates.rules.load("rules.yaml")
# `package_dir` is where a rule's `script:` is looked for; without it, only the
# shape of the path is checked — a checker that is not there would go unnoticed.
for problem in verifiable_gates.rules.problems(catalogue, package_dir="src/verifiable_gates"):
    print(problem)
```

## Design constraints

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

A rule and its enforcement live in separate files, because they have separate
lifetimes: `rules.yaml` is what this project publishes; `gates.yaml` is what this
project is itself held to. What was deliberately not done, each with the condition
that would expire it, is [`DECISIONS.md`](https://github.com/sayam/verifiable-gates/blob/main/DECISIONS.md).

## Provenance and status

Archived at [doi:10.5281/zenodo.22103110](https://doi.org/10.5281/zenodo.22103110),
which resolves to the latest version; each release also gets a DOI of its own. The
tag `evidence-freeze-1` is the state the measurements were taken on and `v0.1.0`
(2026-08-28) the state the package first shipped in — different commits on purpose.
The extraction from the reference implementation,
[`sayam/flask-todolist`](https://github.com/sayam/flask-todolist), is complete;
the stage table, the census and what stayed behind are in
[`docs/history.md`](https://github.com/sayam/verifiable-gates/blob/main/docs/history.md). Consume a pinned submodule or a versioned
dependency, never `main`.

None of this has to be taken on trust. [`docs/auditing.md`](https://github.com/sayam/verifiable-gates/blob/main/docs/auditing.md) is the
hour: the eleven rules this repository states about itself, the command that decides each
one, and — said plainly — what no command here can answer.

## Licence

- Code: [Apache-2.0](https://github.com/sayam/verifiable-gates/blob/main/LICENSE). Contributors sign [`CLA.md`](https://github.com/sayam/verifiable-gates/blob/main/CLA.md) — one line in
  the pull request; you keep your copyright.
- Rules and documentation: [CC BY 4.0](https://github.com/sayam/verifiable-gates/blob/main/LICENSE-docs).

The application this was extracted from stays AGPL-3.0-or-later. The two differ
on purpose: a CI tool is not a network service, and a rule meant to be adopted
inside an organisation's internal handbook must not require share-alike.

---

[`README.th.md`](https://github.com/sayam/verifiable-gates/blob/main/README.th.md) · [`docs/`](https://github.com/sayam/verifiable-gates/tree/main/docs) · [`CONTRIBUTING.md`](https://github.com/sayam/verifiable-gates/blob/main/CONTRIBUTING.md) ·
[`SECURITY.md`](https://github.com/sayam/verifiable-gates/blob/main/SECURITY.md) · [`CHANGELOG.md`](https://github.com/sayam/verifiable-gates/blob/main/CHANGELOG.md) · [the experiment](https://github.com/sayam/verifiable-gates/tree/main/docs/comparison)
