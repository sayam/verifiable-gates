# Auditing this repository in an hour

This project publishes rules about how software should be built, and holds itself to them.
That is a circular claim until somebody outside checks it, so this page is the checking
list: **eleven rules this repository states about itself, the command that decides each
one, and what a red looks like** — plus the parts no command here can answer, said plainly.

You need `git`, `python3` (3.11 or later) and about an hour, most of it waiting. Nothing on
this page asks you to trust a sentence: every claim has something to run.

## What you are auditing, and where each layer stops

1. **What the repository says about itself, checked by machine.** The battery, the
   registers held two ways, the ratchets. This ends at a test suite the same hand wrote —
   it gives integrity, not truth. The way out of that circle is the mutation proof, check
   1 below: a test that goes red on a defect *you* plant is red whoever wrote it.
2. **What you can reproduce without us.** Every gate's evidence is a public record we
   cannot rewrite: a pull request, a workflow run, a Zenodo DOI, a Sigstore entry. Checks
   5 and 12 walk them.
3. **What only you can decide.** Whether the rules are worth holding, whether a
   `DECISIONS.md` row is a decision or an excuse. No command answers that, and this page
   does not pretend one does.

## Before you start

```bash
git clone https://github.com/sayam/verifiable-gates.git && cd verifiable-gates
python3 -m venv .venv
.venv/bin/pip install --require-hashes -r pins/dev/requirements.txt   # ~4 minutes
.venv/bin/pip install --no-deps --no-build-isolation -e .
```

Then, once — this is the claim everything else rests on:

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check . \
  && .venv/bin/mypy src tests && .venv/bin/python -m pytest -q --cov
```

Coverage is a floor of 100% and `pytest` fails below it, so a green run is also the
coverage claim. Everything below runs with `.venv/bin/python`; the prompt is dropped from
here on.

## The eleven, one at a time

Each heading is a rule from [`CONTRIBUTING.md` § "The rules this repository holds itself
to"](../CONTRIBUTING.md), word for word. A test in this repository holds that this page
names all eleven and no twelfth.

### 1. A new test must be proven to catch something.

The one check that does not depend on us. Pick any gate in `gates.yaml`, read the file it
names, break the behaviour that file tests, and watch it go red:

```bash
python -m verifiable_gates.harness --only the-cards-still-say-what-the-repo-says
# round 1: 1 pass · 0 fail · 0 skip
# now plant a defect the gate claims to catch, e.g. the DOI in README.md, and run it again
git diff            # and check you restored all of it
```

Every `proved_by` row in `gates.yaml` says which defect was planted and where the red was
seen. **What is still ours is which defect somebody chose to plant** — so plant a different
one.

### 2. A gate only enters `gates.yaml` when the thing that enforces it exists.

```bash
python src/verifiable_gates/checks/scan_gates_registry.py .   # silence and exit 0 is clean
```

A test file with no gate, or a gate naming a test file that is not there, is a finding and
exit 1.

### 3. A gate arrives with `proved_by`.

```bash
python -m pytest -q tests/test_gate_evidence.py
```

The list of gates allowed to lack evidence is inside that file, empty since 2026-08-29 and
shrink-only.

### 4. A deliberate "we do not do this" goes in `DECISIONS.md`.

```bash
python -m pytest -q tests/test_decisions.py
```

Every row has a reason and an expiry condition; the row ids are copied into the test, so a
row added or removed without touching the test is red. A `revisit` date that has passed
turns the suite red until somebody re-decides the row.

### 5. `proved_by.ref` names where the red was seen, which may be the reference implementation

```bash
python -m verifiable_gates.proved_by_refs      # needs the network and a GitHub token
```

It resolves every ref against GitHub: a 404, a shape it cannot ask about, or a run whose
log has expired is red. Then do it by hand, once — `gh pr view 274` — and read whether the
pull request really shows the red the row claims.

### 6. `preflight --root` runs the workflow's `run:` steps in a local bash.

```bash
python -m verifiable_gates.preflight
```

It runs the lint and test jobs the way the runner will, from `.github/workflows/ci.yml`,
with the `env:` the workflow declares and nothing else from your shell.

### 7. Thresholds move one way, and a test holds each one.

```bash
python -m pytest -q tests/test_own_ratchets.py
```

The `xenon` ranks and the `interrogate` floor on `ci.yml`'s command line are held to the
`DECISIONS.md` rows that set them **and** to where reality sits, measured with `radon`: a
ceiling reality has dropped below is red until the line and the row move together.

### 8. A register is held by a copy in a test, two-way.

```bash
python -m pytest -q tests/test_posture.py tests/test_decisions.py \
  tests/test_instruments_dogfood.py tests/test_manifest.py
```

Branch-protection switches, decision ids, the gates a named step enforces, the shipped
overlay against `rules.yaml`, the number of lint suppressions. Each is a copy a reviewer
sees change in the same diff.

### 9. A proof is dated no later than today.

```bash
python -m pytest -q tests/test_registry.py
```

"Today" is the date it already is anywhere on Earth (UTC+14), because a proof written in
Bangkok at 02:00 is dated tomorrow in UTC and is not from the future. `2099-01-01` is.

### 10. Both schemas refuse a key they do not know.

```bash
python -m pytest -q tests/test_rules_catalogue.py tests/test_registry.py
```

A misspelt `born_frm` is refused, not skipped. `layer: internal` can never be
`portable: true`.

### 11. A finding's fix can contradict a gate that already decided the behaviour.

This one is a habit, not a command: before changing what a decider answers, grep `tests/`
and `DECISIONS.md` for that answer. What you can audit is whether it was kept — pick a
decider, grep, and see whether the answer it gives is written down somewhere as decided.

## Four more, because they are cheap

```bash
python -m verifiable_gates.own_numbers    # every number the documents advertise, measured
python -m verifiable_gates.skill --check --index --preamble preambles/skill.md \
  --practices working.yaml --out skills/verifiable-gates/SKILL.md   # generated, not written
python -m verifiable_gates.zenodo --root .            # the archive, read back (network)
python -m verifiable_gates.install /tmp/a-project     # the bundle, into an empty project
python /tmp/a-project/tools/gates_doctor.py /tmp/a-project
```

## What you cannot check from here

- **Which defect was planted.** Mutation proofs show a test can go red; the choice of
  defect is ours. Check 1 is where you take that choice away from us.
- **That a `proved_by` pull request went red *for the reason claimed*.** The ref resolves
  and the pull request is public — the reading is yours.
- **The Thai fields.** `*_th` carries the original wording of each rule. If you do not read
  Thai, that half is not audited by you, and no test here can be.
- **Anything the platform decides.** Branch protection, the release attestation, the
  archive: `posture.yml` reads them weekly with a token you do not have. Its runs are
  public; read one.
- **Whether the rules are any good.** That is the judgment this page exists to make
  possible, and it is not a command.

## When you find something

Open an issue or a pull request. A finding that turns out to be a decision already recorded
is still worth filing — a decision an outside reader cannot find is a decision that is not
written where readers look, and that has been a finding here before.
