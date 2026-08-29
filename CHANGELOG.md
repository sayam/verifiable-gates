# Changelog

Notable changes to this project. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **The platform's posture is read on a schedule and held to a register.**
  `posture` gains a `--settings` mode: branch protection and the repository
  switches, read with an administrator's token, held to
  `pins/dev/posture-declared.json` (twelve switches, each with its why, and the
  checks excused from being required, each with who sees it). `posture.yml`
  runs it weekly and on every push to `main` with the `POSTURE_TOKEN` secret and
  exits 2 without it. That is this repository's first cron, so the schedule
  census now runs in the `test` job over a full clone, and treats a workflow
  the platform has not met yet as "never fired" rather than "cannot see". The
  platform was changed to match the register: the four newer jobs became
  required checks, squash and merge-commit buttons went off, branches delete
  on merge, and web commits require a sign-off.

## [0.1.2] - 2026-08-29

The release that keeps at home the rest of what the 2026-08-29 practise audit
found published from here and kept only by others: SAST and secret scanning as
jobs, a release that carries its SBOM and provenance, and a record of what was
deliberately not done.

### Added

- **`DECISIONS.md`, and a shrink-only list of gates without evidence.** Twelve
  deliberate choices an outside audit had read as gaps — the reasons lived in
  comments and commit messages — now sit in one table with a reason, an expiry
  condition and, where one makes sense, a revisit date that keeps the suite red
  once passed. Every gate now carries `proved_by`, and the names allowed to lack
  it are an empty list in `tests/test_gate_evidence.py` that a commit has to
  grow on purpose.
- **A release carries its SBOM and provenance.** `release.yml` builds the wheel
  and the sdist from the tag, takes a CycloneDX SBOM from a clean environment
  holding exactly that wheel, attests all of it keyless through GitHub's
  attestation service, verifies in both directions — the real wheel accepted,
  a copy with one byte appended refused — and only then attaches the assets.
  `v0.1.0` and `v0.1.1` had shipped with neither, while the rule
  `release-signed-and-attested` was published from the same tree; `v0.1.1`
  gained its assets retroactively by a dispatch of the same workflow.
- **SAST and secret scanning run as jobs.** `codeql` (Python and Actions,
  security-extended) ends with a decider — `python -m verifiable_gates.posture`
  gains a command line for the alert half of the posture — that refuses any open
  alert on the ref neither in `pins/dev/code-scanning-accepted.txt` nor dismissed
  with a reason. `secret-scan` runs a checksum-verified gitleaks release over the
  whole history on every push and pull request. The rules `codeql-sast` and
  `push-secret-scan` had been published from here and kept only by others.

## [0.1.1] - 2026-08-29

Everything in this release answers an outside zero-trust audit of `v0.1.0`
(2026-08-29), which reproduced each gap it reported before reporting it — and
the practise audit that followed it, which asked which of the rules published
here were not kept here.

### Fixed

- **This repository's inline `commit-lint` job is the same gate as the module.**
  It accepted a subject by *prefix* (`feature:`, `fixup!`, `testing:` all began
  with a type) and included merge commits, while `lint_commits` refused the first
  and skipped the second — one rule, two verdicts. The job now carries the
  module's type list and subject shape and skips merges, and a test runs the
  job's regex through bash against the subjects the module judges, so the copy
  cannot drift from the original again.
- **The Dockerfile scanner judges the image, not the spelling.** A lowercase
  `from`, an unpinned `COPY --from=<image>`, and `FROM --platform=… <image>` all
  passed a scanner that read only uppercase `FROM` and took the first token after
  it. Instructions are now matched in any case, flags are stepped over, and
  `COPY --from=` is held to the same digest rule; stage aliases and indices stay
  exempt.
- **Both licences reach the citation card, the archive and the wheel.**
  `CITATION.cff`, `.zenodo.json` and `license-files` declared Apache-2.0 for the
  whole, while the README and `LICENSE-docs` say the rules are CC BY 4.0 — and
  the archived copy is the one that cannot be corrected. The citation card now
  lists both, the shared abstract says which is which (Zenodo's field takes one
  licence, the code's), and the wheel carries `LICENSE-docs`.
- **`.gate-rounds.jsonl` is in `.gitignore`**, as the harness had said it should
  be since the file was named; a test now holds the two together.

- **A census over nothing counts nothing.** `red_streak_census` and
  `rerun_census` fed a valid, empty run history reported a pass — "every promise
  holds (0 watched)", "examined 0 runs" — while a file that was not there or was
  not JSON was a traceback; the exit-2 path each carried was reachable only
  through the exceptions somebody had thought of. One reader (`history.read`)
  now serves all three censuses: unreadable, malformed, the wrong shape, or
  empty while a promise exists all come out as exit 2, the third answer. The
  red-streak census says "nothing to measure" and exits 0 only when no gate
  declares a watcher; the schedule census keeps `{}` as a real answer, since it
  already closes on it.
- **Why the censuses name no token is written down** in the wrapper: a step's
  `GH_TOKEN` is the platform's own scoping, and `token_env` exists for the one
  caller that needs two tokens inside one process.

- **The shipped issue-handoff gate talks to `gh` under the wrapper's contract.**
  It cannot import `verifiable_gates.gh` — it is copied into a project's
  `tools/` and run under a bare `python3` — so it carries a copy, and the copy
  had drifted: the binary was assumed rather than found, a failure was a
  `CalledProcessError` with the return code and none of `gh`'s words, and the
  gate died with a traceback instead of saying it could not look. The copy now
  finds the binary, says so when there is none, raises `PermissionError` with
  stderr attached, and the gate exits 2 when the platform cannot be asked; a
  test holds the copy's time budget to the wrapper's.
- **`import verifiable_gates` reaches `rules` and `registry`.** `__all__` held
  only the version; the README example worked by accident of `from … import`
  reaching a submodule. The example now passes `package_dir`, so it checks that
  every `script:` exists rather than only the shape of the path, and a test
  executes the README's block as written.

- **preflight lends a step only what it names.** Every `run:` line read from a
  workflow used to execute with `os.environ` whole — every token in the
  developer's shell — which made any workflow file under `--root` a shell with
  those tokens in it. A step now gets a fixed baseline a tool needs to start
  (`PATH`, `HOME`, locale, temp directory), the `env:` the workflow declares for
  it, and any variable its own text or env values name (`$GH_TOKEN`); what it
  borrows by name is printed before it runs.

- **This repository's own advertised numbers are held to what it measures** —
  the version in four files, the release date in three, the rule count in both
  languages, the checker count as a word in three places, and the About field on
  GitHub, which CI now reads live every run. `advertised` had been proved only on
  temporary files while the tree it lives in typed these by hand — the rule
  `contributor-docs-truthful` taught to others and not kept here.
  `python -m verifiable_gates.own_numbers --write` fixes the tree,
  `--about --write` patches the platform's field in place. CONTRIBUTING gains a
  Releasing section in which every step names the test that reads it.

- **Dependabot's commits fit the commit gate.** Its default subject ("Bump x
  from a to b") is not a Conventional Commit, so every bump would have been red
  at `commit-lint` — the rule `dependabot-fits-the-gates` this repository
  publishes, unkept here until 2026-08-29, before the first bump ever opened.
  Prefixes are `build(deps)` for pip and `ci(deps)` for actions; a test holds
  each to the module's type list. The bot signs its commits, so the DCO half
  needed nothing.

- **The deciders this bundle ships run on this repository.** `advisories`,
  `check_issue_handoff`, `preflight` and the harness were tested on fakes and
  pointed at nobody. Now: an `advisories` job audits the forty hash-pinned
  tools with `pip-audit` and holds every finding to
  `pins/dev/advisories-accepted.txt` both ways (the scanner writes, the decider
  decides — `advisories` gained a command line for it); a `handoff` job runs the
  issue-handoff gate on every pull request; `scaffold.json` names `lint` and
  `test` for `preflight`, and the dogfood suite walks preflight's plan and one
  gate through the harness on this tree. Three new gates record it.

- **Four more published rules are kept at home.** `SECURITY.md` (one set of
  timeframes, no address, private vulnerability reporting switched on and
  named); a `Role:` line in every module, held by a test — ten had none; a
  declared, two-way line ceiling on each rule sheet; and `xenon` + `interrogate`
  in the `lint` battery at floors set where reality stood (complexity C/C/B,
  docstrings 84%), every step carrying `!cancelled()` so the first red does not
  hide the next.

### Changed

- **Intent that lived in comments is written where a reader looks.** The README
  says that the bundle decides 9 of the 92 rules and that a doctor reporting
  every rule `NA` has measured nothing; that `evidence-freeze-1` and `v0.1.0`
  are different commits on purpose; CONTRIBUTING says why `strict` is off, why
  `commit-lint` is inline, that a `proved_by.ref` may point at the reference
  implementation, and that `preflight --root` trusts the tree it is given.

### Added

- **The commit gate refuses `Co-authored-by:` and `Claude-Session:` trailers**,
  in the module and in this repository's own inline check alike. A trailer
  hands authorship credit — and a contributor entry on the platform — to an
  address that signed nothing; under the DCO the signer is the author. The rule
  had lived only in a maintainer's notes, and four commits on 2026-08-28 carried
  the trailer anyway (rewritten out before the first release, which is why
  `v0.1.0` sits on new hashes for those four).

## [0.1.0] - 2026-08-28

The first release, cut at the point where this repository and the reference
implementation separate. Everything below it landed during the extraction
(2026-08-25 to 2026-08-28) under a single unreleased heading; it is kept in the
order it happened.

### Added

- **The extraction is closed.** The reference implementation's census
  (`extraction.yaml`) records nothing outstanding — 0 to move, 58 that stayed,
  13 split — after three of the last five candidates were re-decided as `stay`
  on 2026-08-28 and the other two arrived in the entry below.
- **Development moves to this repository's own checkout.** `CONTRIBUTING.md`
  says where the work happens: a consumer's `vendor/verifiable-gates` is a
  read-only pin, a change lands here first, and no consumer pins a commit that
  is not on `main`.

- **The ASVS worksheet and the gate↔requirement crosswalk move in (extraction
  stage 5, last part).** `asvs_worksheet` refreshes a worksheet from a standard
  pinned in the repository — the digest moves only when a requirement does —
  and never writes a verdict: every status a person wrote survives, a dropped
  requirement leaves, a new one arrives unassessed. `gates_crosswalk` derives
  which gates back which passing rows from the rows' own evidence through the
  registry's partition, so no hand-written mapping exists to drift. The words
  of the document (its marker, its header, its status for an unjudged row) and
  the levels in scope are inputs — a worksheet in another language is still a
  worksheet.
- **The `gh` wrapper pages, and lends a token per call.** `api_pages()` walks a
  list endpoint until the first empty page, unwraps by `key` when the endpoint
  wraps its rows, and trims to `limit` — the loop the reference implementation
  carried in three places (two censuses here and a posture checker there), one of
  which stopped at page one on the endpoint whose whole point was the 101st row.
  `token_env` names the variable holding the token for *that question*: branch
  protection wants a PAT, code-scanning alerts want the job's own, and a wrapper
  that only knows one forces the broader scope onto both.
- **The two censuses that watch what CI cannot (extraction stage 3b, second
  part).** `schedule_census` asks when each declared cron last actually fired —
  a workflow never triggered counts zero runs, and "no runs" looks exactly like
  "no failures" in every tool there is. `red_streak_census` measures how long
  redness stood on the default branch and holds each `watched_by` promise against
  it, because checking the *shape* of a promised number is not checking the
  promise.
- **Both take the project root and the registry as inputs**, and both answer
  "cannot see" as a third outcome distinct from pass and fail: a watcher that
  goes quiet when it cannot read reports everything as healthy at exactly the
  wrong moment.

- **The surface reader, the `gh` wrapper and the workflow reader move in
  (extraction stage 3b, first part).** All three are helpers the reference
  implementation had already collapsed from copies: the `on:` idiom had been
  duplicated in five places and three were broken the same way, and the `gh` call
  in five more, each with its own suppression for the same command.
- **The workflow directory is an input.** Baking one project's layout in would
  make the reader usable only from a checkout of that project.

### Changed

- **`rerun_census` and `red_streak_census` page through the wrapper** instead of
  each carrying its own copy of the loop. Their `PAGE_SIZE` now aliases
  `gh.PAGE_SIZE`; the URLs they ask for are byte-for-byte what they were.

### Fixed

- **A shallow clone cannot say when a file was added.** The cron allowance reads
  the commit that introduced a workflow to tell "added on Thursday, fires on
  Monday" from "the platform refused this". A `--depth 1` clone reports *every*
  file as added by the graft commit, so every workflow looked newborn and every
  silent cron was excused — the free pass the function exists to refuse, handed
  out by the code meant to withhold it. `actions/checkout` clones depth 1 by
  default, so that was the normal state of a CI run, not a corner case.
  `first_seen` now asks `git rev-parse --is-shallow-repository` first and returns
  unknown birthdays for everything when the answer is yes; a caller that wants the
  allowance has to fetch the history it rests on.

- **A service container is not on the developer's machine.** A job may declare
  `services:`, and CI then hands its steps an address for a container it started.
  preflight passed that address on verbatim — correct as a rule, and itself a
  past fix — so on a machine with no such service the suite dialled a refused port
  and reported failures that said nothing about the change under test. Published
  service ports are now probed: something answering means the env is used exactly
  as CI uses it; nothing answering means only the variables carrying that port are
  withheld and **the step still runs**. Skipping it would throw away a whole suite
  to protect the two tests that need the service, and the tests behind a withheld
  address take the skip they already declare for themselves. Such runs are
  reported apart from clean ones, because a run missing what CI provides must not
  read like a run that had everything.

- **The workflow reader's declared types no longer say something untrue.** They
  claimed `dict[str, Any]`, while the whole reason the reader exists is that YAML
  1.1 turns an unquoted `on:` into the boolean `True` — so a real workflow's
  top-level mapping has a non-string key in it. The type checker had been
  reporting that contradiction; the type was wrong, not the code.

- **Two CI deciders moved in from the reference implementation (extraction stage
  3a): the commit gate and the newcomer-issue gate.** Both are stdlib-only and
  shipped, so a project gets them in `tools/`.
- **A third kind of shipped file is now named for what it is.** `gates_doctor.py`,
  `preflight.py` and these two are tools a project runs with context only its CI
  has — a commit range, a pull request number — so they take flags rather than a
  project root, and the doctor does not run them. Registering the new pair as
  scanners made the doctor report findings that were only the wrong argument
  shape; the manifest now says which files are which and why.

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
  there was nothing to cite them with. The DOI came with `evidence-freeze-1`,
  recorded above.

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
  92 rules this project publishes (93 at the time; one was unpublished below), each with the incident that produced it, and
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

[Unreleased]: https://github.com/sayam/verifiable-gates/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.2
[0.1.1]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.1
[0.1.0]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.0
