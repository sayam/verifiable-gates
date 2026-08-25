# Changelog

Notable changes to this project. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **A DOI: [10.5281/zenodo.22103110](https://doi.org/10.5281/zenodo.22103110).**
  The `evidence-freeze-1` release is archived on Zenodo, which read `.zenodo.json`
  rather than guessing — the tag was moved onto the commit carrying that file
  before the release, while nothing yet cited it. The concept DOI resolves to the
  latest version; each release also gets one of its own.
- **The advertised DOI is held to the citation card.** Every occurrence in the
  README is compared, not just the first: nothing about a stale DOI looks wrong —
  it resolves, it renders, and it points at somebody's work, just not necessarily
  at the state being claimed. The reference implementation had four such numbers
  stale at once before anything read them.

- **`.zenodo.json`, and a check holding it to `CITATION.cff`.** Zenodo reads it when
  archiving a release and publishes the result under a permanent DOI, which by the
  definition of archiving cannot be corrected afterwards. The reference
  implementation measured what happens without such a check: its two cards and its
  own register once gave three different numbers for one fact, and the value
  published under the DOI was the oldest of the three. The licence is held against
  `LICENSE` rather than only across the two cards, because two cards agreeing with
  each other and both being wrong is exactly what a cross-check between them cannot
  see.

- **`CITATION.cff`.** The rules are the artefact somebody would cite, and until now
  there was nothing to cite them with. No DOI yet — that needs a release rather
  than a commit.

### Removed

- **`skill-mirrors-portable-gates` is no longer published.** It said an exported
  rule sheet must be generated rather than written alongside — true, and nobody
  enforces it any more. The reference implementation stopped rendering a sheet
  when the rules moved here, so the catalogue was publishing a rule with no
  enforcement behind it, which is what the reference implementation's two-way
  agreement check caught on its first run. The idea is not lost: this repository
  holds itself to it through `the-sheets-match-the-catalogue`. It can return to
  the catalogue the day a project renders a sheet of its own and can cite real
  enforcement for it.

### Fixed

- **A scanner no longer crashes on a project that configured nothing.** Six of the
  seven scanners that read `scaffold.json` read it unguarded, so pointing one at a
  project without that file raised `FileNotFoundError` out of `main()`. A traceback
  is the worst of the three answers, because it is neither a finding, nor N/A, nor
  a pass. Missing configuration now falls back to the defaults, which report N/A.
- **This repository keeps `gates-registry-total`, a rule it publishes.** It had
  five findings against itself: two jobs with no gate, one unregistered test file,
  and two test files each claimed by two gates. The test files are split so every
  gate owns one, and the three missing gates are registered.

### Changed

- **The dogfood list is computed rather than written.** It used to name the two
  scanners that applied here, and its docstring said "only two apply today" — true
  when `gates.yaml` was empty, false from its first row, and unnoticed for four
  stages. Every shipped scanner now runs, each answering for itself whether it had
  anything to check, with a floor on how many must find real work so an all-N/A
  suite cannot pass as a clean one.

### Added

- **The rule catalogue (extraction stage 6, first part).** `rules.yaml` holds the
  93 rules this project publishes, each with the incident that produced it, and
  `verifiable_gates.rules` reads and checks it. A rule and a gate now live in
  separate files because they have separate lifetimes: enforcement moves whenever
  a project reorganises its tests and is written in that project's framework,
  while a rule changes only when reality teaches something new. One file worked
  while there was one project; it breaks the moment a second adopts a rule, since
  its `enforced_by` would point at files that project does not have.
- **Two rendered sheets, `SKILL.md` and `SKILL-BUSINESS.md`**, generated from the
  catalogue and compared against a fresh render on every test run.
- **The catalogue carries two languages.** English is the published text; each
  rule's original wording sits beside it in a `*_th` field, because a translation
  of an incident report is a retelling, and the retelling is not the record. The
  renderer can produce either, so the second language is reachable rather than
  dead weight.

### Changed

- **The sheet renderer reads a catalogue rather than a registry**, and the
  language is now an input alongside the catalogue and the preamble.
- **The language rule is enforced by position, not by file.** Thai is allowed in a
  `*_th` value, in a cited CI step name, and inside a string literal in the code
  that renders those fields — and nowhere else, in any file. A Thai comment, key
  or identifier still fails everywhere, which is the leak the check was built for.
  A cited step name is kept in its own language on purpose: translating it would
  point the evidence at a step that does not exist.

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

- **The language check now reads tracked *and* new files.** Reading only what git
  tracks let a new file with Thai in it pass locally and fail in CI — which is what
  happened while stage 2e was being written. Untracked-but-not-ignored is the set a
  developer is one `git add` away from committing, so that is the set it judges.
  Ignored files stay out, which is what the earlier fix was for.
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
