# Changelog

Notable changes to this project. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **The rule-sheet renderer and the fail-fix harness (extraction stage 2e).**
  `verifiable_gates.skill` renders a sheet from a registry; `verifiable_gates.harness`
  runs the gates and answers with `(gate id, cause, hint)` so a loop can act on it.
- **Three things that were constants are now inputs**: the registry, the preamble,
  and the field headings. A tool that hard-codes one project's opening prose makes
  every other project ship that project's story — and one that hard-codes English
  headings forces a language on projects that do not write in it.
- **preflight arrived, and the bundle now declares what its files need
  (extraction stage 2d, part two).** preflight walks the CI gates locally by
  reading the commands out of the workflow, so no second copy of them exists to
  drift. Every step reaches the plan exactly once — run, or skipped with its
  reason printed.
- **A shipped file is stdlib-only, or says what it needs.** The scans and the
  doctor run on a bare runner and may import nothing else; preflight needs a YAML
  reader for whole workflows and runs on a developer's machine, so its dependency
  is declared in the manifest under `requires`. A test holds that declaration to
  what the files actually import, in **both** directions — an undeclared import
  surprises someone else's project, and a declaration nothing imports is a
  requirement carried forever for a reason that expired. The reference
  implementation shipped this file with the dependency undeclared.
- **The registry scanner arrived (extraction stage 2d)** — the gate that holds a
  project's index to reality in four directions, and the hand-written YAML reader
  underneath it. The reader is the riskiest code in the bundle: it cannot use
  PyYAML, because it runs where nothing is installed. Two defences — anything
  outside its subset raises, and on this repository's own files it must agree with
  PyYAML value for value, with the one accepted divergence (block scalar bodies)
  measured rather than assumed.
- **A fresh install's registry now has to pass its own check** and must not be
  skipped as not-applicable.

### Fixed

- **The reader was quietly more permissive than YAML in two places.** An anchor or
  an unclosed quote in *value* position was read as ordinary text, because the
  guard only looked at the start of a line. And `portable: false` came back as the
  string `"false"` — which is truthy, so any rule reading a boolean would have read
  it backwards and said nothing. Both found by writing the agreement test.
- **The shipped defaults disagreed with each other.** `gates.yaml.default`
  declared its rows as `kind: step`, naming steps that `ci-template.yml` does not
  have. A project that installed the bundle and changed nothing would have failed
  its own registry check on the first run.
- **The machinery arrived (extraction stage 2c)** — `gates_doctor.py`,
  `install.py`, a manifest module, and the three files a project starts from
  (`scaffold.json.default`, `gates.yaml.default`, `ci-template.yml`). Installing
  into an empty directory and running the doctor there is now covered end to end,
  including the parts that decay quietly: a second install keeps the files that
  hold decisions, an incomplete bundle refuses to install, and a scan that exists
  but does not compile is an incomplete install rather than a finding.

### Changed

- **The manifest is an input, not a constant.** The reference implementation's
  doctor read `overlay.json` from the directory beside it — right while one tool
  serves one registry, wrong the moment the tool is a package several projects
  install. `--manifest` is the seam that lets one doctor answer for many
  catalogues.
- **`NA` and `pass` are reported separately**, and gates of kind `suite` are
  counted as waiting rather than folded into the pass count. A rule the bundle
  cannot decide must not look like one it decided.
- **The nine scanners landed (extraction stage 2b)** — ADR index, base-image
  digest, debug entrypoint, CI tool pinning, service-layer isolation, inline
  handlers in templates, delete discipline, and action SHA pinning. Each is a
  single stdlib-only file with `main(root) -> int`, because `install.py` copies
  one into a project that has installed nothing and runs it under a bare
  `python3`. `tests/test_checks_are_standalone.py` enforces that property from
  the AST *and* by copying each scanner somewhere the package cannot be imported
  and running it there.
- **Every scanner is proven against a pair** — one tree that breaks its rule, one
  that keeps it — plus a not-applicable case, because a scanner that finds nothing
  to check must say so rather than read as a pass. Nine mutations, one per
  scanner, red every time.
- **This repository now runs the scanners that apply to it** (`tests/test_dogfood.py`).

### Changed

- **`ci-tools-hash-pinned` no longer flags installing the checkout itself.**
  `pip install --no-deps -e .` resolves nothing from an index, so there is no hash
  to pin. **This is a behaviour change from the reference implementation's copy of
  the scanner**, which never met the case because it uses pipenv. The exemption
  needs both halves and has a test for each: `--no-deps` alone still reaches the
  index, and `-e .` alone drags the whole dependency tree in unpinned.
  Found by the dogfood test failing on its first run, here.
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
