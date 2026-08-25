# Contributing

This repository is the governance core extracted from
[`sayam/flask-todolist`](https://github.com/sayam/flask-todolist) (its
[ADR 0075 §6](https://github.com/sayam/flask-todolist/blob/main/docs/adr/0075-thesis-track-freeze-effort-and-ceilings.md)).
The extraction is in progress; see the README for what has landed.

## `main` only accepts pull requests

Including from the maintainer — branch protection has `enforce_admins` on, so
there is no path that skips the checks. `lint`, `test`, and `commit-lint` are all
required, history is linear (rebase, not merge commits), and force-pushing or
deleting `main` is refused. Required approving reviews are 0, which is honest
rather than aspirational: a single maintainer cannot review their own work.

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
- **Thresholds move one way.** Coverage starts at 100 here because the repository
  started empty; lowering it is a decision someone signs, not a convenience.
- **`layer: internal` can never be `portable: true`** — a rule tied to one
  project's architecture, exported as universal, is an overclaim. The schema
  refuses it.

## Running everything locally

```bash
python -m venv .venv && . .venv/bin/activate
pip install --require-hashes -r pins/dev/requirements.txt
pip install --no-deps -e .
ruff check . && ruff format --check . && mypy src tests && pytest -q --cov
```

Documentation and comments in this repository are in Thai, matching the
reference implementation; issues and reviews in Thai or English are both fine.
