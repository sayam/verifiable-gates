# `pins/` — the tools CI installs are pinned by hash

`pip install ruff` takes whatever is newest at the second the job runs. Two runs
an hour apart can therefore use different tools with nothing in the repository
having changed — and these tools run with our workflow's permissions, reading the
source and whatever token the job holds.

**Pinning a version is not enough.** `--require-hashes` enforces two things a
version number does not: the file must be the same bytes, **and every dependency
in the tree must be listed**. A lockfile with a gap becomes an error at install
time instead of a hole that stays quiet until the day someone walks through it.

| Directory | Used by |
|---|---|
| `dev/` | jobs `lint` and `test` (ruff · mypy · pytest · pytest-cov · pyyaml) |

## Regenerating

```bash
pip install pip-tools
pip-compile --allow-unsafe --generate-hashes --strip-extras \
  --output-file=pins/dev/requirements.txt pins/dev/requirements.in
```

**Run it from the repository root, as written.** The `# via -r pins/dev/requirements.in`
annotation in the compiled file carries the path pip-compile was given, and
`test_the_compiled_pins_are_compiled_from_the_source_beside_them` reads exactly that string
to check that the source and the lockfile are one list twice. Compiling from inside
`pins/dev/` writes `# via -r requirements.in` instead, the test finds no roots at all, and
the gate goes red with nothing wrong with the pins themselves.

`pins/bump.sh` does exactly that, from the right directory, and checks afterwards that the
annotations still carry the path:

```bash
bash pins/bump.sh --check    # what would move, writing nothing
bash pins/bump.sh            # move it, check it, print the commit to make
```

It finds the directories rather than listing them, so a new `pins/<name>/requirements.in` is
covered the day it arrives, and `tests/test_instruments_dogfood.py` asks the script itself
what it moves and what commit subject it writes — the two facts that have to be true before a
bump can land.

**Nothing here is moved by a machine.** Dependabot opened pull requests against these files
until 2026-09-01; it does not any more — `DECISIONS.md` `dependabot-runs-nowhere-here` says
why, and what would bring it back. Dependabot **alerts** stay on: being told about a
vulnerability costs nobody an authorship line, and the `advisories` job audits these pins on
every run besides.

**A pin nobody moves is a vulnerability kept on ice** — worse than no pin at all. The mover
is `pins/bump.sh`, and the person who runs it is the one watching.
