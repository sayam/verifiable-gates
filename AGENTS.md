# AGENTS.md

Read by any coding agent working in this repository (the agents.md convention);
`CLAUDE.md` imports this file. It points at where things are and at what checks
them. It copies nothing: a copy is a register nobody holds, and the file you are
reading would be the one to go stale (`DECISIONS.md`
`agent-instructions-point-and-do-not-copy`).

## What this is

`verifiable-gates` — a gate registry held to reality in both directions, gates
that carry evidence of having gone red on a real defect, and a rule catalogue
rendered into an agent skill. Start with `README.md`. The skill is
`skills/verifiable-gates/SKILL.md`; its full entries are under
`skills/verifiable-gates/references/`.

## Before changing anything

- The rules this repository holds itself to: `CONTRIBUTING.md`
  § "The rules this repository holds itself to". Every one of them has a test.
- What was deliberately not done, each with the condition that would expire it:
  `DECISIONS.md`. A row is changed together with its copy in
  `tests/test_decisions.py`, never worked around in code.
- Every module states its role in its docstring (`Role:`). A tool that decides
  answers 0 = clean, 1 = findings, 2 = could not answer — a rule the tool cannot
  check must never look like a rule it checked.

## Run what CI runs

```bash
pip install --require-hashes -r pins/dev/requirements.txt
pip install --no-deps --no-build-isolation -e .
ruff check . && ruff format --check . && mypy src tests && pytest -q --cov
python -m verifiable_gates.preflight                  # the lint and test jobs, as CI would
python -m verifiable_gates.harness --only <gate-id>   # one gate, in a shape a loop can read
```

Coverage is 100% and stays there, `mypy` is strict, `ruff` selects every rule;
each is a one-way ratchet (`CONTRIBUTING.md` § "Ceilings and floors this
repository keeps on itself").

## Conventions a job or a test enforces

- English in every file; `README.md` and `CLA.md` are bilingual
  (`tests/test_language_policy.py`).
- Commits: Conventional Commits, a subject of at most 72 characters,
  `git commit -s`, and no `Co-authored-by:` or `Claude-Session:` trailer
  (`src/verifiable_gates/lint_commits.py`, job `commit-lint`).
- A pull request body carries the CLA line — `CONTRIBUTING.md` § "Two things
  every pull request needs", job `cla`.
- One gate per test file and every test file claimed by exactly one gate: a new
  test file needs a row in `gates.yaml`, and a row needs `proved_by`
  (`src/verifiable_gates/checks/scan_gates_registry.py`).
- A new test is proved by mutation before it is believed: break the code it
  covers, watch it go red, restore, and check with `git diff` that the tree is
  back.
- Registers are held by a copy in a test, two-way — the list is in
  `CONTRIBUTING.md` § "The rules this repository holds itself to"; a register and
  its copy change in one pull request.
- Generated, never edited by hand: everything under `skills/verifiable-gates/`
  (`python -m verifiable_gates.skill`, source `rules.yaml`). Numbers the
  documents quote are written by `python -m verifiable_gates.own_numbers --write`.
- Stage files by name. Never `git add -A`.

## Releasing

`CONTRIBUTING.md` § "Releasing": documents first, in their own pull request, then
the cut. Merging a green pull request is routine. A tag, a GitHub release or a
Zenodo record is published by the owner, never by an agent on its own.
