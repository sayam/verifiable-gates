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
   `I have read and agree to CLA.md v1. — <name> <email>` — for example
   `I have read and agree to CLA.md v1. — Ada Lovelace <ada@example.org>`. The angle
   brackets around the address are part of the line (the sign-off's shape), not
   placeholders: the first pull request of the 2026-08-30 re-audit wrote the
   address bare and was red at `cla` for it.
   You keep your copyright; the grant is what makes it possible to publish this
   work under a commercial licence alongside Apache-2.0 later. The `cla` job
   reads the line (name and address both, like the sign-off); Dependabot is
   skipped, since a version bump carries no copyright — and it opens nothing
   here any more (`DECISIONS.md` `dependabot-runs-nowhere-here`). **The owner's
   own pull requests are held to one address**, the
   `<id>+<owner>@users.noreply.github.com` their commits are signed with: a
   private address pasted in from an editor's context attributes the acceptance
   to an identity that has nothing to do with this work, and correcting the body
   afterwards does not take it back, because GitHub keeps the edit history (four
   merged pull requests carried one, found 2026-09-01). Every other
   contributor's line is untouched — the CLA wants a real identity from them,
   and only the owner's address is fixed by this repository.

If this is your first pull request here, its workflows do not start until a
maintainer approves them — the repository's policy is `first_time_contributors`,
so the eight required checks show as *expected* until then. That wait is the
maintainer, not a red. Editing the description re-runs the checks (the `cla`
job reads it, so a fixed line gets its own run).

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
  ref nobody can look up is not evidence. The ref is the pull request or run
  where the red *was seen*, not the one that added the job: the two security
  proofs cited the pull request that added `codeql` and `secret-scan`, whose
  every check is green, while the red sat on a throwaway pull request and its
  run — an outside reader followed the ref and called the proof unverifiable
  (2026-08-30). Prefer `run/N` when the run is what went red. `proved_by` itself is optional for exactly one reason: the
  list of gates that have never gone red can only shrink, and a gate that has not
  yet had its defect is still a gate.
- **`preflight --root` runs the workflow's `run:` steps in a local bash**, because
  that is what the runner will do — so point it only at a checkout you would run
  CI on. A step is lent a fixed baseline (`PATH`, `HOME`, locale, temp), the
  `env:` the workflow declares, and any variable its own text names; a borrowed
  variable is printed before the step runs. Nothing else from your shell reaches
  it.
- **Thresholds move one way, and a test holds each one.** Coverage starts at 100
  here because the repository started empty; lowering it is a decision someone
  signs, not a convenience. `tests/test_own_ratchets.py` holds the `interrogate`
  floor to `DECISIONS.md` `interrogate-at-84`, and the three `xenon` ranks on
  ci.yml's line to the row `xenon-floor-at-reality` *and* to where reality sits
  (measured with `radon`) — a ceiling reality has dropped below is red until the
  line and the row move up together.
- **A register is held by a copy in a test, two-way.** The switches in
  `pins/dev/posture-declared.json` and what each wants (`HELD` in
  `tests/test_posture.py`), the row ids of `DECISIONS.md` in order (`HELD` in
  `tests/test_decisions.py`), the gates one named step enforces and the step
  each names (`HELD_STEP_GATES` in `tests/test_instruments_dogfood.py`), the
  shipped overlay's scan-gate ids and titles held to `rules.yaml`
  (`tests/test_manifest.py`), and the
  number of suppression lines under `src/` and `tests/` (`SUPPRESSED_LINES` in
  the same file). A switch turned, a row or a step gate removed or added, a
  suppression added: red until the same
  pull request changes the copy too, where a reviewer sees both. Every
  suppression carries a reason on its line; every job in every workflow declares
  `timeout-minutes`.
- **A proof is dated no later than today** — anywhere on Earth (UTC+14), so a
  proof written here at 02:00 and dated tomorrow-in-UTC is not "from the
  future"; `2099-01-01` is.
- **Both schemas refuse a key they do not know.** `rules.py` and `registry.py`
  each carry the set of keys they read; a misspelt `born_frm` is refused, not
  skipped. **`layer: internal` can never be `portable: true`** — a rule tied to
  one project's architecture, exported as universal, is an overclaim. That hold
  is in the gate schema; the rule schema refuses `internal` outright, and
  `portable` on a rule as a gate's field.
- **A finding's fix can contradict a gate that already decided the behaviour.**
  Before changing what a decider answers, grep `tests/` and `DECISIONS.md` for
  that answer, and run the full suite before the mutation proofs: making every
  scan `NA` on a fresh install would have undone `tests/test_box_opens_true.py`,
  which holds the shipped index to *pass*, never `NA` (2026-08-30).

## Where the work happens

Since the extraction closed (2026-08-28) this repository is developed in its
own checkout, never inside a consumer's `vendor/verifiable-gates` submodule.
That directory is a read-only pin: a change lands here first, merges to `main`,
and reaches the reference implementation through its Dependabot `gitsubmodule`
bump (or a manual `git submodule update --remote` opened as a pull request).
A consumer must never pin a commit that is not on this `main` — the extraction
period, when both moved in one day, is the exception that has ended.

An agent working in this checkout reads `AGENTS.md`, which points at this file
and the tests rather than restating them; `CLAUDE.md` imports it. Both are held
by `tests/test_identity_cards.py` to name only things that exist.

## Releasing

Every step below has a test or a CI step reading alongside it — the rule
`contributor-docs-truthful` this repository publishes says a checklist item with
none goes stale exactly like a number with none, and this repository's own About
field was one release away from proving it (2026-08-29).

0. **Bring every document up to date first, in its own pull request** — README (the
   English and `README.th.md`), CONTRIBUTING, DECISIONS.md, and any docstring or `_comment` that
   describes a behaviour the `[Unreleased]` entries changed. The numbers half is
   held by `tests/test_own_numbers.py`; the prose half is not, and it is the
   half an outside reader audits: on 2026-08-30 seventeen fixes were green and
   merged while README still described the scanners as they were before them.
   A cut whose documents lag its code archives the lag under a DOI, where it
   cannot be corrected. Only then:
1. Move the `[Unreleased]` entries in `CHANGELOG.md` under `## [x.y.z] - YYYY-MM-DD`,
   add its `[x.y.z]: …/releases/tag/vx.y.z` line at the foot (the test holds the
   two sets to each other), and set `__version__` in `src/verifiable_gates/__init__.py`. Those two are the
   *sources*: the version is what the package reports, the date is the newest
   released heading (`tests/test_own_numbers.py` holds the heading to the version).
2. `python -m verifiable_gates.own_numbers --write` — fixes every other place that
   quotes the version, the date, or a count (`pyproject.toml`, `CITATION.cff`,
   `.zenodo.json`, `.claude-plugin/plugin.json`, `README.md` and `README.th.md`),
   touching nothing else. The same
   test holds every place to its fact on every run, so a place missed here is red.
   If a place cannot be written, the report names the ones that did land before
   it names what stopped it: a half-corrected checkout is a different thing from
   an untouched one, and the operator has to be able to tell them apart.
3. `python -m verifiable_gates.own_numbers --about --write` — patches the claims
   in the About field on GitHub in place, **before the pull request can merge**:
   CI reads that field on every run (gate `the-about-field-is-read-not-remembered`),
   so a release pull request whose About still says the old version is red. The
   first release cut under this checklist (`v0.1.1`) found that out — this step
   used to sit after the merge, where it could never have been reached.
4. Merge; tag `vx.y.z` on the merged commit and publish the GitHub release —
   on the release form, with **Publish this Action to the GitHub Marketplace**
   ticked, so the listing at `github.com/marketplace/actions/verifiable-gates`
   moves to the new version (`action.yml` carries the name, description and
   branding the form validates; a release cut from the CLI does not tick the
   box — edit it afterwards). Zenodo reads `.zenodo.json` from the release and
   mints the version's DOI under the concept DOI already in the README.
5. Publishing the release starts `release.yml`: it builds the wheel and the sdist
   from the tag, generates the SBOM, attests all three keyless, verifies them in
   both directions and only then attaches them to the release — and then, last,
   publishes the same wheel and sdist to PyPI by trusted publishing (an OIDC
   exchange; no token is stored anywhere, and `skip-existing` makes a
   re-dispatch against a version already on the index a no-op rather than a red
   last step). Watch it go green; a downloader gets it with
   `pip install verifiable-gates==x.y.z` and verifies the same bytes with
   `gh attestation verify <wheel> --repo sayam/verifiable-gates`. The
   publisher is registered once, by the owner, on PyPI (workflow `release.yml`,
   this repository, no environment).
6. `python -m verifiable_gates.zenodo` — reads the archive back and holds its
   version count to the release count; the cut is done when it exits 0, not
   when the tag exists.

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

- The skill under `skills/verifiable-gates/` is read by an agent every session —
  the front page when the skill activates, a reference sheet for the rule at hand —
  so each of its three files has a declared line ceiling in `tests/test_sheets.py`,
  two-way: the file may not pass it, and it may not sit more than 40 lines above the
  file. Raise one only in the change that adds the content. The front page has a
  second, fixed ceiling it cannot negotiate: the 500 lines the Agent Skills
  specification recommends, held by the same test beside the frontmatter's shape.
- `lint` also runs `xenon` (complexity) and `interrogate` (docstring coverage)
  at floors set where reality stood when they arrived. They move up only.
- Every module declares a `Role:` (decider · generator · reader · helper) in
  its docstring; `tests/test_roles.py` holds it.
- Vulnerabilities: see [`SECURITY.md`](SECURITY.md).

## Running everything locally

```bash
python -m venv .venv && . .venv/bin/activate
pip install --require-hashes -r pins/dev/requirements.txt
pip install --no-deps --no-build-isolation -e .
ruff check . && ruff format --check . && mypy src tests && pytest -q --cov
```

**This repository is written in English** — comments, docstrings, commit
messages, changelog entries, and anything the tools print. One exception is
[`CLA.md`](CLA.md), bilingual with English first and Thai below, and any future
file of that kind: a licence, a notice, or anything else that binds someone
legally is kept in the maintainer's first language as well, so that what was
agreed to is what was understood. The other is [`README.th.md`](README.th.md),
the Thai README kept as its own file beside the English one — `README.md` is what
PyPI renders and the wheel embeds, so the Thai the maintainer thinks in stays in
this repository rather than travelling to everyone who installs
(`DECISIONS.md` `the-thai-readme-is-a-file-beside-it`). (The
reference implementation is the other way round, in Thai; that is deliberate —
it is one project's record, this is a tool other people are meant to pick up.)

Issues and reviews in Thai or English are both fine.
