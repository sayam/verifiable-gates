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

**A pin nobody moves is a vulnerability kept on ice** — worse than no pin at all.
Every directory here is watched by Dependabot in `.github/dependabot.yml`.
