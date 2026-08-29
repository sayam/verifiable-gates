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
   work under a commercial licence alongside Apache-2.0 later.

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
- **`proved_by.ref` names where the red was seen, which may be the reference
  implementation** (`pr/151` on `flask-todolist`, for an instrument that was
  proved there before it moved here). The schema does not bind `ref` to this
  repository, so a row that cannot be found here is a row to look up there —
  not a missing one. `proved_by` itself is optional for exactly one reason: the
  list of gates that have never gone red can only shrink, and a gate that has not
  yet had its defect is still a gate.
- **`preflight --root` trusts the tree it is pointed at.** It runs the workflow's
  `run:` steps in a local bash with the caller's environment, because that is
  what the runner will do; point it only at a checkout you would run CI on.
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
