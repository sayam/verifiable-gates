# Changelog

Notable changes to this project. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **A trailing comment cannot pin an install.** `scan_install_pinning` checked
  for `--require-hashes` on the whole line, so `pip install ruff  # TODO: use
  --require-hashes one day` was green while the same line without its comment
  was red (outside audit, 2026-08-30, reproduced). Everything after a `#`
  outside quotes is dropped before the line is judged; a `#` inside quotes
  stays text. Proved by mutation both ways (#109).

## [0.1.7] - 2026-08-30

The owner's decisions after the 2026-08-30 re-audit, each carried in by its
own pull request with the mutation that proves it and, where the platform is
involved, a live flip on the platform's own job: the two clocks and the
archive read on the cron, four more switches and their detail in the posture
register, the gitleaks pin with a mover, the ratchet module on this
repository's own floors, and a batch of four smaller items run as parallel
worktree agents. A review of the whole `v0.1.6..main` diff before this cut
found seven more, closed in #103–#107.

### Added

- **The ratchet module is pointed at this repository's own floors.** It
  shipped from here, proved on fakes, while the docstring and coverage floors
  in `pyproject.toml` were "moved up only" by a comment and a DECISIONS row —
  the rule `ratchets-do-not-drift-below-reality` with no machine behind it
  (re-audit rounds 14 and 23). `tests/test_own_ratchets.py` measures
  `interrogate` live and holds the floor with the slack the row
  `interrogate-at-84` names — six points, so the test and the row go red on
  the same day coverage reaches 90 — and holds `fail_under` at 100, the top
  of its scale. Gate `our-own-floors-sit-against-reality`. Owner's decision,
  2026-08-30.
- **The archive is read back.** Nothing read Zenodo: the cards in the tree
  are held to each other and the About field is read live, but the archived
  copy — the one that cannot be corrected — was compared with the releases
  by hand (re-audit round 24: 7 and 7). `verifiable_gates.zenodo` now reads
  every version under the concept DOI the citation card advertises and holds
  the list to the release tags both ways, and refuses a record under another
  concept; `posture.yml` runs it on the cron and on every push to main. The
  archive turned out to refuse a page above 25 on the first live call, so the
  reader pages. Live: "8 versions under 10.5281/zenodo.22103110, 8 releases".
  Gate `the-archive-is-read-back`. Owner's decision, 2026-08-30.

### Fixed

- **"selected" actions are read, not assumed.** The register held
  `allowed_actions` to the word `selected` while its why promised "GitHub-owned
  allowed"; the detail behind the word — `github_owned_allowed`,
  `verified_allowed`, `patterns_allowed` — was read by nothing, so a pattern
  `*` under "selected" would have been "all" with a different word and a
  green census (pre-cut review). `posture` reads the detail when the policy is
  "selected", and the register declares it: GitHub-owned only, no marketplace,
  no patterns. Seventeen switches now; proved live both ways on the platform's
  own job — a pattern `*` added → red printing both details (run 33289361339),
  removed → green.
- **The gitleaks mover says what it could not read.** Its `grep | head | sed`
  ran under `set -euo pipefail`, so a download line that changed shape aborted
  the step with no words at all (pre-cut review, reproduced: exit 1, empty).
  It now prints which file it could not read the pin from and where the
  decision lives; the test runs that tree through the block too. Also from
  the review: the posture gate's `born_from` said "twelve switches" beside a
  proof that says sixteen, and `posture.yml`'s header still placed the
  schedule census in ci.yml alone — both say what is true now.
- **The archive reader refuses what its map cannot count.** `versions()`
  keyed the records by version, so two records under `0.1.6` and one with no
  version at all collapsed to "1 version — the archive says what the releases
  say" (pre-cut review of `v0.1.6..main`, reproduced). Both shapes are named
  and red now. Also from that review: the reader shares `gh`'s time budget
  instead of copying the number, spells a tag one way, and its gate says where
  the live read runs (posture's watched cron, seven days) rather than implying
  the `test` job reads the archive; and `posture`'s alerts switch reads "off"
  only from the platform's own `HTTP 404`, not from any 404 in the message.

### Changed

- **Four baseline titles say the mechanism, not one stack's tool.** The
  re-audit (round 23) read eight baseline rules as architecture-bound; on a
  full reading four name a tool or one project's choice in the universal
  sentence itself — `purge-timer-real-systemd` ("here systemd"),
  `alerts-fire-for-real` ("the Loki ruler"), `dialect-discipline`
  ("UTCDateTime", "three brands"), `a11y-real-browser` ("pa11y with a real
  Chromium … and Thai") — and are reworded in both languages to what any
  stack must keep: a real scheduler whose failures a person sees; alert rules
  that fire when their events are fired at the stack; time in UTC at full
  precision on every brand the project targets; accessibility in a real
  browser in every theme and language shipped. The tool stays in
  `born_from` and `reference`, where it is evidence. Ids are unchanged, so
  nothing reads as a removal. The other four (`n-minus-one-served`,
  `backup-restore-drilled-every-push`, the two TLS rules) are universal as
  written — expand–contract, a rehearsed restore and a refusing server are
  not one stack's choices — and stay. Owner's decision, 2026-08-30.
- **`github/codeql-action` is pinned to a release tag.** The SHA it sat on
  (`486fec2a`, a 2026-08-21 merge) carried only the bundle tag
  `codeql-bundle-v2.26.4` — no `v4.x.y` release pointed at it, which the
  version-comment test from the same day could only record. Both `init` and
  `analyze` now sit on `cdf488f5`, the commit release `v4.37.9` names
  (2026-08-26), and the comment says so. (The first pull request for this,
  #98, carried this entry and not the change — a `sed` with `#` as its
  delimiter and a `#` in the pattern; the pin moved in the next.) Owner's
  decision, 2026-08-30.
- **The gitleaks pin has a mover.** The binary is fetched by URL and held to a
  sha256 written in `security.yml`, so Dependabot never sees it and nothing
  said when to bump it (re-audit round 15). The upstream signs nothing —
  release v8.30.1 carries no `.sig` or `.pem`, `gh attestation verify --owner
  gitleaks` is 404, and its workflows name no cosign — so a signature step
  would verify nothing. Instead `posture.yml`'s cron compares the pinned
  version with the latest release and is red the week it falls behind; a test
  runs the block through bash on a tree pinning 8.0.0 and sees the red.
  `DECISIONS.md` records the checksum-in-our-tree as the strongest control
  available, expiring when gitleaks ships signatures (revisit 2027-02-28).
  Owner's decision, 2026-08-30.
- **`tools/gates_doctor.py` takes `--root DIR` as well as the positional
  root.** Every other tool here takes `--root`; the re-audit's operator typed
  it at the doctor and got a usage error (round 18, 2026-08-30). The two
  spellings answer identically, the no-argument default is unchanged, and
  naming the project both ways is a misuse (exit 2, with a message). The file
  stays stdlib-only. Proved by tests that point `--root` at a directory the
  default cannot reach, so an ignored flag cannot hide behind the default
  (#95). Owner's decision, 2026-08-30.
- **A pull request body edit now re-runs the checks.** The `cla` job reads the
  description, but `on.pull_request` in `ci.yml` used the default event types,
  so a contributor who fixed the line saw no new run and the 2026-08-30
  re-audit had to close and reopen a pull request. `ci.yml` declares `types:
  [opened, synchronize, reopened, edited]`; the reader still yields the same
  eight pull-request checks, a test in `tests/test_instruments_dogfood.py`
  holds the four types (mutation-proved), and the live check was PR #93's own
  second CI run from one body edit. CONTRIBUTING also tells a first-time
  contributor that the wait is a maintainer's approval
  (`first_time_contributors`), not a red. Owner's decision, 2026-08-30.

- **Every action pin names its version in a trailing comment, and a test keeps
  it so.** The published rule `actions-sha-pinned` says "pinned to a commit
  SHA with the version in a comment"; on 2026-08-30 all 6 distinct pins were
  SHAs and 0 carried the comment, so a reader saw forty hex digits and
  Dependabot had no version to rewrite. Each of the 20 `uses:` lines now ends
  with the tag the GitHub API resolves for its SHA (`v7.0.1`, `v7.0.0`,
  `v4.2.2`, `v4.1.0`; the codeql-action commit carries only `codeql-
  bundle-v2.26.4`, so that is what it says), and a test reads the workflows as
  text and refuses a pin with no version behind it, per occurrence. Owner's
  decision, 2026-08-30.
- **Every suppression carries its reason.** The rule
  `exception-registers-are-reasoned` asks each switched-off checker to say
  why; eleven `# noqa` lines and six `# type: ignore[...]` lines said nothing.
  Each now names the fact that makes the suppression right at that line — a
  fixed git argv, a binary from `shutil.which`, a `None` that is what GitHub
  sends for an empty body. For `type: ignore` the reason is a second `#`
  comment on the same line, since mypy does not read an em dash after the
  bracket. No behaviour changed; no new gate. Owner's decision, 2026-08-30.
- **The two excused jobs declare their watcher, and the promise is measured.**
  `posture` and `release-sign` are not required checks; the register excused
  them with "the maintainer sees a red within 7 days / 1 day" in prose, and no
  gate carried `watched_by`, so `red_streak_census` — shipped from here since
  the extraction — had nothing to measure on this repository (re-audit round
  7). Both gates now say `severity: watched` with a `watched_by` block holding
  the same number, a test holds the prose to the block, and the census runs on
  posture's cron over the last 200 runs: "every `watched_by` promise still
  holds (2 watched workflows)". Owner's decision, 2026-08-30.
- **The `cla` job skips by the pull request's author, not the run's actor.**
  `github.actor` is whoever triggered the run, so a maintainer re-running a
  Dependabot pull request's checks would become the actor, the job would run,
  and the bot's body has no line — a red on a bump for the wrong reason
  (re-audit round 22). The condition reads `pull_request.user.login`; a test
  holds it. Owner's decision, 2026-08-30.
- **Four more switches in the platform register.** The re-audit's first
  round read four live switches the rule `platform-posture-verified` names
  and the register did not: `sha_pinning_required` off (the rule's own
  incident had found it off in the reference implementation too),
  `allowed_actions` all, Dependabot alerts off, `required_signatures` off.
  `posture` now reads the Actions policy and the alerts switch (204 on, 404
  off, anything else the third answer) beside branch protection; the first
  three were turned on/narrowed on the platform on 2026-08-30 — SHA pins
  required, GitHub-owned actions only, alerts on — and the fourth is declared
  off with its reason (DECISIONS.md `git-signing-not-required`). The first
  live run of the wider reader caught the reader itself: `required_signatures`
  was declared and not read, and `blind` said so. Proved live both ways on
  the platform's own job: `sha_pinning_required` off → red naming it (run
  33282261202); on → green, 16 switches holding. Owner's decision, 2026-08-30.
- **The two clocks tick on the platform's cron, not only on a push.** The
  schedule census and the DECISIONS revisit check ran in ci.yml's `test` job
  alone — on push and pull request — so with nobody pushing they stopped, and
  GitHub's 60-day cron disable, the silence the census exists to report, would
  have gone unreported by it (re-audit round 26: the first silent point of an
  absent owner was day 60). `posture.yml` now carries both steps on its weekly
  cron over a full clone; the push-time copies stay. The day that cron stops,
  the platform's own e-mail is the notice. Owner's decision, 2026-08-30.

## [0.1.6] - 2026-08-30

### Fixed

- **`pyproject.toml`'s requirements are held to the pins.** The release job
  installs the wheel with `--no-deps` and its dependencies from
  `pins/runtime`, so a dependency added to `[project].dependencies` and not
  to the pins would be missing from the attested SBOM in silence, and a
  backend switched in `[build-system].requires` without `pins/dev` would fail
  at tag time inside the signing job. A test holds the first pair equal and
  the second contained; the `.in` readers take the name before any specifier.
  Found by the pre-cut review (2026-08-30).
- **A reached ceiling is never silent.** After the wrapper started raising
  `RuntimeError` for a hung `gh` (`[Unreleased]` above), the rerun census's
  annotation and log readers — which return empty on purpose so one unreadable
  job cannot kill a census — swallowed it with no trace, and
  `own_numbers --about`, a CI step, called `gh` bare and would have ended in a
  traceback. Both readers now print one line to stderr naming what could not
  be read; `--about` exits 2 with the reason. The Role paragraph the three
  censuses gained above said "a job blocks on it" of all three — only
  `schedule_census` is run by a job; the sentence says so. Found by the
  pre-cut review (2026-08-30).
- **A duplicate link reference at the changelog's foot is red.** The test
  from `[Unreleased]` above read the references into a `dict`, which keeps the
  last line, while Markdown renders the first — a stray `[0.1.5]:` pointing at
  `v0.1.3` inserted before the right one passed. Found by the pre-cut review.
- **The `cla` job's failure line prints.** The example added in 0.1.6's
  `[Unreleased]` was quoted so that `<ada@example.org>` became a shell
  redirection: the job was red for the right reason and the contributor saw
  "No such file or directory" instead of the line to write. The test now runs
  the block's FAIL branch through bash on an empty body and holds the example
  to stdout and stderr to nothing. Found by the pre-cut review (2026-08-30).
- **Installing the checkout is exempt only without build isolation.** The
  exemption for `pip install --no-deps -e .` said "nothing is fetched", and
  the same release said `python -m build` fetches its backend from the index —
  pip builds an editable install the same way, in a fresh environment, with
  `setuptools` arriving unhashed; this repository's own four lines in three
  workflows had it, in the jobs that hold `GH_TOKEN`. The exemption now needs
  `--no-build-isolation` as its third half, and the four lines (and the SBOM
  environment's wheel install, and CONTRIBUTING) carry it; the backend comes
  from `pins/dev`. Found by the pre-cut review (2026-08-30).
- **Four defects in the install scanner's widened regex**, found by a review
  of the `v0.1.5..main` diff before the cut (2026-08-30): the option shape
  `-{1,2}[\w-]+` parsed `--x` two ways, so a `pip` line with twenty long
  flags and no `install` took a second and forty took minutes — a shipped
  check that a hostile line could hang until the job's timeout; `pip3.13`
  and `python3.13`, the spellings runners ship, were not matched; `_targets`
  cut the line at the first substring `install`, so `--python
  /opt/installer/bin/python install --no-deps .` was reported; and `build`'s
  documented short flag `-n` was told to add `--no-isolation`. The option
  name now starts with a letter, a minor version is allowed, the targets are
  sliced after the matched subcommand, `-n` is accepted, and `install` must be
  a whole token (`cp installer/pip install.log` was a finding). Eight lines
  added; four mutations red; 80 flags parse in 0.06 ms.
Everything below answers the 2026-08-30 re-audit of `v0.1.5` — twenty-five
rounds, each asking one question the round before could not (what is still
missing · what has rotted · who proves the provers · has every gate caught
something real · can the instruments be trusted · who sees what is removed ·
what we teach, do we do), every number counted from the tree or the platform
before it was written, and every fix carried in by its own pull request with
the mutation that proves it (#68–#79). Before the cut, a review of the whole
`v0.1.5..main` diff found six more (#81–#86), each reproduced first. Seventeen
pull requests, one live flip, no new gate, rule or badge; what needed a new
one is a proposal for the owner in the round's report, not a change.

### Fixed

- **The release job installs nothing it has not pinned.** `python -m build`
  created an isolated environment and `pip install`ed the backend from the
  index — `setuptools==84.0.0` arrived unhashed on 2026-08-30 — inside the job
  that holds `id-token: write`, and the SBOM environment fetched PyYAML the
  same way, so the SBOM recorded whatever the index served that minute. The
  rule `ci-tools-hash-pinned` is published from this tree; `scan_install_pinning`
  did not see either line (`pip --python … install` puts an option before
  `install`, and `build`'s fetch is not a `pip` line at all), so the dogfood
  suite was green. The backend is now in `pins/dev` and `build` runs
  `--no-isolation`; the SBOM environment takes PyYAML by hash from a new
  `pins/runtime/requirements.txt` that Dependabot moves, and the wheel with
  `--no-deps`. Three tests hold the two steps and the pins↔Dependabot pairing
  both ways. Found by the 2026-08-30 re-audit (round 1: what is still missing).
- **`scan_install_pinning` sees every shape that reaches an index.** It read
  `pip install` only side by side, so `pip --python <interpreter> install` — the
  release job's own line, for five releases — was never judged; `python -m
  build` without `--no-isolation`, which pip-installs the backend from the
  index with no `pip` on the line, and `pipx install`/`pipx run` were not
  shapes it knew. All three are findings now, with the fix in the message;
  a global option before `install` no longer hides the subcommand. Fourteen
  lines hold it, and four mutations (the old regex back, each of the two new
  findings switched off, `--no-isolation` ignored) were red.
- **The changelog's foot is held to its headings.** `[0.1.4]` and `[0.1.5]`
  had no link reference and `[Unreleased]` compared against `v0.1.3`, so the
  "pending" link showed two shipped releases — the rule `changelog-tracks-version`
  read only the headings. `own_numbers` now measures the compare link (and
  `--write` fixes it), and a test holds the set of link references to the set
  of released headings both ways. Found by the 2026-08-30 re-audit (round 2:
  what has rotted, and who guards it).

- **A `gh` that reaches its ceiling is "could not look", not a traceback.**
  The wrapper declared a 60-second budget on every call and mapped a non-zero
  exit to `PermissionError`, but `subprocess.TimeoutExpired` walked past every
  caller's `except (PermissionError, RuntimeError)`: `rerun_census`, run over
  this repository's own 300 runs on 2026-08-30, died with a traceback on one
  annotations call that sat for 60 seconds — the worst of the three answers,
  from the instrument that exists to say "cannot see". The wrapper, and the
  copy the issue-handoff gate ships, now raise `RuntimeError` naming the
  budget, so every census and the posture reader exit 2 as they already do
  for a refused call. Re-audit round 7 (can the instruments be trusted).

- **The CLA line's example has real brackets in it.** CONTRIBUTING and the
  `cla` job's failure text showed `— <name> <email>`, which reads as two
  placeholders; the brackets around the address are literal, and the first
  pull request of the 2026-08-30 re-audit was red at `cla` for writing the
  address bare. Both now show `— Ada Lovelace <ada@example.org>`, a test runs
  that example through the job's own grep, and the bare-address body is in the
  job's test list as a refusal. Re-audit round 8 (does the new machinery
  survive contact with a real contributor).

- **The DECISIONS row that states the split is measured, not typed.**
  `rules-vs-bundle` said "92 rules … the bundle decides 9 … the other 83" by
  hand, while the README's copies of the first two were held by
  `own_numbers` — so a tenth checker would have moved the README and left the
  decision saying 9 and 83. All three are places now, the third as its own
  fact (rules minus scripted). Re-audit round 13 (do the audit's own artefacts
  contradict each other yet).

- **A rule's `script:` is held to the manifest both ways.** `rules.yaml` says
  which nine rules the bundle decides and `overlay.json` says which nine scans
  it ships — the same fact in two files, and nothing compared them: the
  re-audit deleted a rule's `script:` line in a worktree and 1121 tests stayed
  green. A test now holds the two maps equal, id for id and path for path.
  Re-audit round 16 (who sees what is *removed*).

- **`requirements.in` and `requirements.txt` are held to each other.** The
  source list and its hash-pinned compilation are one list twice, and nothing
  compared them: a name dropped from the source stayed pinned, audited and
  installed forever, a name added was not installed until somebody ran
  pip-compile. The re-audit dropped `interrogate` from the source and 1121
  tests stayed green. A test now holds the packages the compiled file marks
  `via -r requirements.in` equal to the source's names, for every `pins/*`.
  Re-audit round 16.

### Changed

- **The three censuses say what they are: deciders.** Each declared
  `Role: reader — it reports` while returning 1 on a broken promise and 2
  when it cannot see, and `schedule_census` blocks the `test` job on that
  exit. `test_roles` holds that a module names one of the four kinds, not
  that the kind is true; the re-audit read the `return 1` beside the label.
  Re-audit round 17 (what checks the tools that check everything).
- **The `advisories` job has been seen red on the platform.** A census of all
  266 runs since 2026-08-25 found it the one job never red live — 67 of 67
  green, with an empty register, which from the outside is the same as a job
  that reads nothing. A throwaway pull request (#71) planted an exemption no
  finding matched; the job refused it for that reason, and the run is recorded
  in `proved_by`. Re-audit round 6 (has every gate caught something real).

## [0.1.5] - 2026-08-29

One test: the last item the five-model outside audit left open, the list of
required checks in CONTRIBUTING, is derived and held rather than written.

### Added

- **CONTRIBUTING's list of required checks is held to the register.** The
  sentence was prose, and had drifted once — at `v0.1.0` it named three checks
  while the platform required seven — which one of the five outside auditors
  read as a fixed list that goes stale silently. A test now derives what a
  pull request must show (the checks the workflows produce on a pull request,
  minus those `posture-declared.json` excuses) and holds the sentence to that
  set, both ways.

## [0.1.4] - 2026-08-29

Everything in this release answers the five-model outside audit of `v0.1.0`
(2026-08-29) — five reports on the same commit, re-planted on `v0.1.3` before
anything was changed, so only what was still open was touched: six false
greens closed, one promise given its job, and three deliberate zeros given a
record.

### Added

- **The CLA line is read by a job.** CONTRIBUTING has asked every pull request
  for `I have read and agree to CLA.md v1. — <name> <email>` since the first
  one, and nothing read it. The `cla` job now does, with the sign-off's own
  name-and-address shape; Dependabot's pull requests are skipped, since a
  bump carries no copyright, and a skipped required check passes. Listed by
  the five-model outside audit of `v0.1.0` (2026-08-29) as a promise with no
  enforcer.

### Changed

- **Three deliberate zeros have a record.** The five-model outside audit of
  `v0.1.0` (2026-08-29) read three exit codes as false greens: the doctor
  exiting 0 with every scan `NA`, the harness exiting 0 with every gate
  skipped, and `manifest.problems()` having no caller in `src/`. Each was a
  choice with its reason in a comment or a docstring — the place an outside
  reader does not look — so each now has a row in `DECISIONS.md` with its
  reason, the condition that expires it, and a revisit date for the two that
  should not stand forever.

### Fixed

- **A quoted `uses:` is judged without its quotes.** `uses:
  "actions/checkout@<sha>"` — pinned, and quoted as YAML allows — was reported
  as unpinned because the closing quote sat where the last digit had to be; a
  wrong answer on a correct file. Noted by two of the five outside auditors
  beside the folded-scalar case.
- **`checks/__init__.py` names the test that holds its property**
  (`tests/test_checks_are_standalone.py`; it named a file that does not exist).
- **A proof's `ref` has a shape somebody can look up, and its `date` is a real
  one.** The schema asked only that `ref` be non-empty and that `date` be ten
  characters with two dashes, so `ref: trust me` and `date: 9999-99-99` passed
  — in the field `registry.py` calls the reason a gate is distinguishable from
  one that checks nothing. A ref is now `pr/N`, `run/N` or `commit/<sha>`,
  with `owner/repo#` in front when the red was seen elsewhere; a date has to
  parse as a calendar date (an unquoted one already reaches the schema as a
  `datetime.date`, and is accepted as such). `pr/151` is written
  `sayam/flask-todolist#pr/151`, so the one row that is not this repository's
  says so in the row — the outside audit that found it got a 404 here with
  nothing in the file pointing elsewhere. Found by the five-model outside
  audit of `v0.1.0` (2026-08-29).
- **A registry that has lost its list is refused, not read as empty.**
  `registry.load` answered `[]` for a file with no `gates` key and silently
  dropped any row that was not a mapping — so an index that had lost its list
  looked like one that was empty on purpose, and a stray row vanished before
  `problems()` could report it — while `rules.load` and the shipped registry
  scanner refuse the same files. Both are now a `TypeError` naming the file
  and, for a row, its index; `gates: []` remains the explicit empty state. The
  harness, the one caller, turns that into exit 2 with the reader's words
  instead of a traceback. Found by the five-model outside audit of `v0.1.0`
  (2026-08-29), which planted `version: 1` alone.
- **An exemption covers only the case it was written for.** Two read wider.
  `ci-tools-hash-pinned` excused a `pip install` that had `--no-deps` *and* a
  local target anywhere on the line, so `pip install --no-deps requests .`
  — both halves present, and a package fetched from the index anyway — passed;
  now every target has to be local, values of options such as `--index-url`
  are not targets, and a line chaining several commands is judged one command
  at a time, or the second hides behind the first's exemption.
  `actions-sha-pinned` excused the whole `docker://` prefix, so
  `uses: docker://alpine:latest` — an image with the job's permissions, on a
  tag that can be re-pointed — passed; a `docker://` step is now held to a
  `@sha256:` digest, and only `./` stays local. Both lines were planted by the
  five-model outside audit of `v0.1.0` (2026-08-29).
- **The inline `commit-lint` job's sign-off shape is the module's.** `v0.1.1`
  made the job carry the module's type list and subject shape and bound them
  with a test — but only the subject half. The sign-off half stayed
  `grep '^Signed-off-by: .* <.*@.*>$'`, which accepts `Signed-off-by:  <@>` —
  no name, no address — while `lint_commits.SIGN_OFF` requires both, because a
  DCO line nobody can follow up on certifies nothing. The five-model outside
  audit of `v0.1.0` (2026-08-29) fed that line through both gates and got two
  verdicts. The job now carries the module's shape as `SIGNOFF`, and
  `tests/test_lint_commits.py` runs it through bash against the bodies the
  module judges, the way it already did for subjects.
- **A composite action is judged like the workflow that calls it.** Both
  pinning scanners read `.github/workflows/` and nothing else, so a step moved
  into `.github/actions/<name>/action.yml` — which runs with the calling
  workflow's permissions — moved out of sight: the five-model outside audit of
  `v0.1.0` (2026-08-29) planted `uses: actions/checkout@v4` and
  `pip install requests` there and got exit 0 from each, while the workflow
  calling the action was clean on its own. `actions-sha-pinned` and
  `ci-tools-hash-pinned` now read `.github/actions/**/action.y*ml` too, and a
  project with an action file and no workflows is something to check, not NA.
- **A configured path that is missing is a finding, not "nothing to check".**
  Every scanner that reads `scaffold.json` answered `NA` and exited 0 when the
  path it was pointed at did not exist — the same answer for a project that has
  no Dockerfile and for a project whose `scaffold.json` names a Dockerfile it
  does not have. A five-model outside audit of `v0.1.0` (2026-08-29) planted
  `"dockerfiles": ["docker/Dockerfile"]` beside an unpinned `Dockerfile` at the
  root and got `NA: no Dockerfile`: one wrong line of configuration had turned
  "checked and clean" into "nothing to check" with the same exit code. The seven
  scaffold-driven scanners now tell the two apart: a *default* path that is not
  there is still NA, a path the project *named* and does not have is a finding
  that says which key and which path. `scaffold.json.default` no longer spells
  every default out as a key — that made "configured" and "default" the same
  thing on every install — it documents the defaults in its comment and carries
  only `preflight_jobs`; a project names a path only to move it.

## [0.1.3] - 2026-08-29

The platform's posture, read on a schedule and held to a register — the last
item of the 2026-08-29 practise audit, and the one that produced a false green
of its own before it was proved red and green live.

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
- **A readable switch that comes back empty is red, not "holds".** The first
  dispatch with the secret reported all twelve switches holding; a switch was
  then flipped on the platform and the job still said so — the token could not
  see the repository switches, and a `None` fell between `setting_problems`
  (which skips it) and `unreadable` (which covers only switches declared
  unreadable). `blind` reports it by name with the value it should hold. Four
  merge switches turned out unreadable by any fine-grained token; they are
  declared so, printed with their declared value on every run for a person to
  check, and judged from the maintainer's session (DECISIONS.md).

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

[Unreleased]: https://github.com/sayam/verifiable-gates/compare/v0.1.7...HEAD
[0.1.7]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.7
[0.1.6]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.6
[0.1.5]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.5
[0.1.4]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.4
[0.1.3]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.3
[0.1.2]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.2
[0.1.1]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.1
[0.1.0]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.0
