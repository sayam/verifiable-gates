# Changelog

Notable changes to this project. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
