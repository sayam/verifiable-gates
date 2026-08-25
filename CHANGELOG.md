# Changelog

Notable changes to this project. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **This repository is now in English, and a test says so.** Comments,
  docstrings, commit messages, and anything the tools print — with `README.md`
  and `CLA.md` kept bilingual, English first and Thai below, because a document
  that binds someone has to be understood by the person bound. Any future licence
  or notice follows the same shape.
  `tests/test_language_policy.py` checks both directions: Thai outside the
  allowlist fails, and so does an allowlisted file with no Thai left in it — an
  exception that no longer excuses anything is a hole with a label on it.
- **The registry has its first row**, `english-except-where-it-binds`, which is
  also the first time the promise in `gates.yaml` holds in practice: the row
  arrived with the thing that enforces it, not before.
- **`main` only accepts pull requests, and that now includes the owner.** Branch
  protection matches the reference implementation's posture: the three CI jobs
  are required, admins are not exempt, history stays linear, force-pushes and
  deletions are refused, and conversations must be resolved. Required approving
  reviews are **0** on purpose — one maintainer cannot review their own work, and
  pretending otherwise would make the number a formality rather than a control
  (the compensating controls are in the reference implementation's ADR 0053).
  Verified by trying: a direct push to `main` is rejected with `GH006`.
- **The repository has a skeleton and a schema (extraction stage 1).** A
  `src/verifiable_gates/` package, `pyproject.toml` with ruff · mypy `strict` ·
  pytest · coverage at 100%, hash-pinned CI tools under `pins/dev/` with
  Dependabot watching them, and a CI that runs lint, tests, and a commit check
  (Conventional Commits + DCO).
- **`verifiable_gates.registry`** — the gate-registry schema every later stage
  reads: closed vocabularies for `kind` / `severity` / `layer` / `pillar`, a
  refusal to export a rule whose layer is `internal`, `born_from` required on
  anything exported, and `proved_by` entries that must name what they caught and
  when. Mutation-tested seven ways.
- **`gates.yaml`, deliberately empty.** This repository will not list a gate
  before the thing that enforces it exists.

### Not here yet

- The checks, the doctor, and the preflight tool arrive in stage 2 — which is
  also when a `dogfood` job can run the doctor against this repository. There is
  no such job today, because a job with nothing to run is a job that is green
  for no reason.
