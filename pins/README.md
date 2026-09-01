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

**Dependabot does compile from inside the directory**, so every bump it opens rewrites those
annotations. Restore them in the same pull request — the version and the hashes it computed
are correct, only the path is not (measured on #201, ruff 0.16.4 → 0.16.5, 2026-09-01).

Since the change is partly ours by then anyway, **the bump lands as a commit the owner
authored**, crediting Dependabot in the body rather than in the author field: the author is
what the platform counts as a contributor, and it survives a rebase merge. The decision, and
what would end it, is `bumps-land-as-the-owners-commit` in `DECISIONS.md`.

**A pin nobody moves is a vulnerability kept on ice** — worse than no pin at all.
Every directory here is watched by Dependabot in `.github/dependabot.yml`.
