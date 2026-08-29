# Contributing

This repository is the governance core extracted from
[`sayam/flask-todolist`](https://github.com/sayam/flask-todolist) (its
[ADR 0075 §6](https://github.com/sayam/flask-todolist/blob/main/docs/adr/0075-thesis-track-freeze-effort-and-ceilings.md)).
The extraction finished on 2026-08-28; the README says what landed and what the
reference implementation kept.

## `main` only accepts pull requests

Including from the maintainer — branch protection has `enforce_admins` on, so
there is no path that skips the checks. `lint`, `test`, and `commit-lint` are all
required, history is linear (rebase, not merge commits), and force-pushing or
deleting `main` is refused. Required approving reviews are 0, which is honest
rather than aspirational: a single maintainer cannot review their own work.
`required_status_checks.strict` is off, also on purpose: with linear history
required, a branch is rebased before it merges anyway, and a strict flag would
only add a second "Update branch" click that the rebase already implies.

The `commit-lint` job is a shell block rather than a call to
`verifiable_gates.lint_commits`, so that the gate guarding the package never
depends on importing the package. It is held to the module by
`tests/test_lint_commits.py`, which runs the block's regex against the subjects
the module judges — the two accepting different histories is a defect, not a
style difference.

## Two things every pull request needs

1. **`git commit -s` on every commit** — the DCO sign-off. Job `commit-lint`
   checks each commit a pull request adds, along with Conventional Commits and a
   72-character subject limit.
2. **A line in the pull request description accepting [`CLA.md`](CLA.md):**
   `I have read and agree to CLA.md v1. — <name> <email>`
   You keep your copyright; the grant is what makes it possible to publish this
   work under a commercial licence alongside Apache-2.0 later. The `cla` job
   reads the line (name and address both, like the sign-off); Dependabot is
   skipped, since a version bump carries no copyright.

## The rules this repository holds itself to

They are the rules it exists to export, so it has to pass them first — audit
round 23 of the reference implementation measured what happens when a project
teaches rules it does not follow, and the answer was 2.7%.

- **A new test must be proven to catch something.** Break the code it claims to
  cover, watch it go red, restore the code from a copy, and check with
  `git diff` that you restored all of it. A test that stays green when you delete
  the behaviour it names is not a weak test — it is not a test.
- **A gate only enters `gates.yaml` when the thing that enforces it exists.**
  A registry row with nothing behind it is exactly what this project is against.
- **A gate arrives with `proved_by`.** The names allowed to lack it are the list
  in `tests/test_gate_evidence.py` — empty since 2026-08-29 and shrink-only.
- **A deliberate "we do not do this" goes in [`DECISIONS.md`](DECISIONS.md)**
  with its reason and the condition that expires it; a `revisit` date that has
  passed turns the suite red until the row is re-decided.
- **`proved_by.ref` names where the red was seen, which may be the reference
  implementation** (`sayam/flask-todolist#pr/151`, for an instrument that was
  proved there before it moved here). A ref is `pr/N`, `run/N` or
  `commit/<sha>`, with `owner/repo#` in front when it is not this repository —
  the schema holds the shape, and a real calendar date beside it, because a
  ref nobody can look up is not evidence. `proved_by` itself is optional for exactly one reason: the
  list of gates that have never gone red can only shrink, and a gate that has not
  yet had its defect is still a gate.
- **`preflight --root` runs the workflow's `run:` steps in a local bash**, because
  that is what the runner will do — so point it only at a checkout you would run
  CI on. A step is lent a fixed baseline (`PATH`, `HOME`, locale, temp), the
  `env:` the workflow declares, and any variable its own text names; a borrowed
  variable is printed before the step runs. Nothing else from your shell reaches
  it.
- **Thresholds move one way.** Coverage starts at 100 here because the repository
  started empty; lowering it is a decision someone signs, not a convenience.
- **`layer: internal` can never be `portable: true`** — a rule tied to one
  project's architecture, exported as universal, is an overclaim. The schema
  refuses it.

## Where the work happens

Since the extraction closed (2026-08-28) this repository is developed in its
own checkout, never inside a consumer's `vendor/verifiable-gates` submodule.
That directory is a read-only pin: a change lands here first, merges to `main`,
and reaches the reference implementation through its Dependabot `gitsubmodule`
bump (or a manual `git submodule update --remote` opened as a pull request).
A consumer must never pin a commit that is not on this `main` — the extraction
period, when both moved in one day, is the exception that has ended.

## Releasing

Every step below has a test or a CI step reading alongside it — the rule
`contributor-docs-truthful` this repository publishes says a checklist item with
none goes stale exactly like a number with none, and this repository's own About
field was one release away from proving it (2026-08-29).

1. Move the `[Unreleased]` entries in `CHANGELOG.md` under `## [x.y.z] - YYYY-MM-DD`
   and set `__version__` in `src/verifiable_gates/__init__.py`. Those two are the
   *sources*: the version is what the package reports, the date is the newest
   released heading (`tests/test_own_numbers.py` holds the heading to the version).
2. `python -m verifiable_gates.own_numbers --write` — fixes every other place that
   quotes the version, the date, or a count (`pyproject.toml`, `CITATION.cff`,
   `.zenodo.json`, the README in both languages), touching nothing else. The same
   test holds every place to its fact on every run, so a place missed here is red.
3. `python -m verifiable_gates.own_numbers --about --write` — patches the claims
   in the About field on GitHub in place, **before the pull request can merge**:
   CI reads that field on every run (gate `the-about-field-is-read-not-remembered`),
   so a release pull request whose About still says the old version is red. The
   first release cut under this checklist (`v0.1.1`) found that out — this step
   used to sit after the merge, where it could never have been reached.
4. Merge; tag `vx.y.z` on the merged commit and publish the GitHub release —
   Zenodo reads `.zenodo.json` from it and mints the version's DOI under the
   concept DOI already in the README.
5. Publishing the release starts `release.yml`: it builds the wheel and the sdist
   from the tag, generates the SBOM, attests all three keyless, verifies them in
   both directions and only then attaches them to the release. Watch it go
   green; a downloader verifies with
   `gh attestation verify <wheel> --repo sayam/verifiable-gates`.

## What runs on this repository's own pull requests

`lint`, `test`, `commit-lint`, `advisories`, `handoff`, `codeql`, `secret-scan` and
`cla` are required (`pins/dev/posture-declared.json` says so, and `posture.yml` — weekly, and on
every push to `main`, with the `POSTURE_TOKEN` secret — holds the platform to it). `advisories` audits the pinned
tools and holds every finding to `pins/dev/advisories-accepted.txt` — an
advisory you cannot act on goes there with a reason, not into a silenced job.
`handoff` refuses a pull request that closes an issue still labelled
`good first issue` without saying so. `codeql` and `secret-scan` (in
`security.yml`) refuse an unjudged code-scanning alert on the ref and any secret
anywhere in the history; a CodeQL finding you cannot act on goes into
`pins/dev/code-scanning-accepted.txt` with a reason. Locally, `python -m verifiable_gates.preflight`
walks `lint` and `test` as CI would, and `python -m verifiable_gates.harness
--only <gate-id>` runs one gate and answers in something a loop can read.

## Ceilings and floors this repository keeps on itself

- `SKILL.md` and `SKILL-BUSINESS.md` are read in full by an agent every session,
  so each has a declared line ceiling in `tests/test_sheets.py` — two-way: the
  sheet may not pass it, and it may not sit more than 40 lines above the sheet.
  Raise it only in the change that adds the content.
- `lint` also runs `xenon` (complexity) and `interrogate` (docstring coverage)
  at floors set where reality stood when they arrived. They move up only.
- Every module declares a `Role:` (decider · generator · reader · helper) in
  its docstring; `tests/test_roles.py` holds it.
- Vulnerabilities: see [`SECURITY.md`](SECURITY.md).

## Running everything locally

```bash
python -m venv .venv && . .venv/bin/activate
pip install --require-hashes -r pins/dev/requirements.txt
pip install --no-deps -e .
ruff check . && ruff format --check . && mypy src tests && pytest -q --cov
```

**This repository is written in English** — comments, docstrings, commit
messages, changelog entries, and anything the tools print. The two exceptions are
[`README.md`](README.md) and [`CLA.md`](CLA.md), which are bilingual with English
first and Thai below, and any future file of that kind: a licence, a notice, or
anything else that binds someone legally is kept in the maintainer's first
language as well, so that what was agreed to is what was understood. (The
reference implementation is the other way round, in Thai; that is deliberate —
it is one project's record, this is a tool other people are meant to pick up.)

Issues and reviews in Thai or English are both fine.
