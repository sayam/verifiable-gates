# Changelog

Notable changes to this project. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **The checks switched off in pyproject are a register too.** Ruff's `ignore`
  list and `per-file-ignores` relax whole classes of check for the tree or a
  directory — what `exception-registers-are-reasoned` is about — and the
  suppression census counted `# noqa` lines only, so a code added to either
  list was seen by nothing (self-audit, 2026-08-31). Both lists are now a copy
  in `tests/test_instruments_dogfood.py`, held two-way like `SUPPRESSED_LINES`,
  and every group of entries has to sit under a reason. Proved by mutation: a
  code added to `ignore` is red against the copy (#170).

- **The words beside two registers are held.** CONTRIBUTING's "the eight
  required checks" sat beside a list a test holds to the register, and the
  word could go to "seven" alone; CLA.md's `v1` appears in its title, its
  signing line, CONTRIBUTING's example and the `cla` job's grep, and a new
  CLA.md v2 would have left the job accepting v1 (self-audit, 2026-08-31, both
  reproduced on v0.1.10). The count is now read against the register, and the
  four places carry one version. Proved by mutation: each drift is red (#169).

- **A DECISIONS row is held by its clock and its words, not only its id.** A
  `revisit` date could be removed from a row, an `expires when` could be
  rewritten to "Never", and the `interrogate-at-84` row could say "floor is
  80%" — all green, because the copy in `tests/test_decisions.py` held ids
  alone (self-audit, 2026-08-31, each reproduced on v0.1.10). The copy now
  carries each row's revisit date, the set of rows that never expire is
  named, and the interrogate row's two numbers are read against the floor
  pyproject declares and the move point the ratchet test uses. Proved by
  mutation: three planted drifts red (#168).

- **The steps two gates promise are held.** `the-archive-is-read-back` says
  "posture's cron runs it live", and `our-own-floors-sit-against-reality`
  holds the docstring floor — yet the `python -m verifiable_gates.zenodo
  --root .` step could leave `posture.yml`, and `interrogate src` could leave
  the lint job, with every test green (self-audit, 2026-08-31, both reproduced
  on v0.1.10). Two dogfood tests now read the workflows for those steps.
  Proved by mutation: each step removed is red (#167).

- **The default registry says of each rule exactly what the catalogue says.**
  `gates.yaml.default` — the index every installed project receives as its own
  — described the nine scan gates in words of its own ("pinned by hash" with
  no Node side, "without gaps" with no repeats or supersessions), a third
  register held by nothing while the overlay was held to `rules.yaml`
  (self-audit, 2026-08-31). Its titles are now the catalogue's, held two-way
  by a test like the overlay's. Proved by mutation: one title edited by hand is
  red (#166).

- **`image-digest-pinned` judges both halves of its title.** The title says
  "pinned to a manifest-index digest and Dependabot moves it"; the scanner
  checked the digest and delegated the mover to a gate that does not check it,
  so a pinned image with no `docker` ecosystem in `.github/dependabot.yml` —
  a digest nobody moves — was clean; and `FROM scratch`, the empty image with
  nothing to pin, was a finding (self-audit, 2026-08-31, both reproduced on
  v0.1.10). A judged Dockerfile now needs a `docker` entry in
  `.github/dependabot.yml`, and `scratch` is not an image. Proved by mutation:
  three cases red on the old scanner (#165).

- **`adr-index-complete` reads supersessions, and every common index shape.**
  The title's last clause — "supersessions are recorded in both directions" —
  had no code behind it: a record saying `Supersedes: 0001` while 0001 said
  nothing was clean; an index link with a title in its text
  (`[0001: Use X](…)`) or a table row (`| 0001 | [Use X](…) |`) was "missing
  from the index"; and a record named in capitals was not a record at all
  (self-audit, 2026-08-31, each reproduced on v0.1.10). `Supersedes:` and
  `Superseded by:` (plain, bold or hyphenated, with or without `ADR-`) are read
  from both records and each side has to name the other; both link shapes
  count; file names match in any case. Proved by mutation: six cases red on the
  old scanner (#164).

- **Every installer that reaches an index is read — the Node side too.**
  `uv tool run` (`uvx` spelled out), `uv run --with <pkg>` (resolved before it
  runs), `pip wheel` (an isolated build fetching its backend like `python -m
  build`), and on the Node side `npx`, `npm exec`, `yarn add`, `pnpm add` and
  `pnpm dlx` each fetch from a registry unpinned and each exited 0 — the
  title promises "both the Python and the Node side" and the scanner read
  `npm install` alone (self-audit, 2026-08-31, proved against uv 0.12.7 and
  npm 11.14.1). `pip wheel` is held to `--no-build-isolation` as `build` is;
  `yarn install --immutable` and `pnpm install --frozen-lockfile` install from
  a lock and are left alone with `npm ci`. Proved by mutation: nine cases red
  on the old scanner (#163).

- **An install pip itself holds to hashes, or fetches nothing for, is not a
  finding.** `pip install "--require-hashes" -r …` (the flag in quotes),
  `PIP_REQUIRE_HASHES=1 pip install -r …` and the same variable in the step's
  own `env:`, `pip install -r requirements.txt` where every requirement carries
  a `--hash=` (pip then requires hashes on its own — `pip-compile`'s shape),
  `pip install --no-index …` and `pip install --no-deps ./dist/*.whl` (a wheel
  is copied, never built) were each a finding of `ci-tools-hash-pinned` — a
  scanner repeating what pip already enforces sent a project that did the
  right thing back to rewrite it (self-audit, 2026-08-31, each proved against
  pip 26.2.1). The install's arguments are read the way the shell splits them,
  the step's `env:` is read for the one variable pip reads, and a named
  requirements file is opened from where the shell stands. An unhashed line, a
  file that is not there, the variable set to `0`, an sdist, or a wheel with
  its dependencies stay findings. Proved by mutation: seven cases red on the
  old scanner (#162).

- **The template's checkout pin moves with ours.** `ci-template.yml` — the
  workflow the installer writes into every project — pins `actions/checkout`
  by SHA, and Dependabot, which moves the pins under `.github/workflows/`,
  never reads it: a pin nobody moves, the thing `dependabot.yml` here calls a
  vulnerability kept on ice (self-audit, 2026-08-31). A test now holds the
  template's pin to the one our own workflows carry, so a Dependabot bump of
  `ci.yml` is red until the template follows in the same pull request. Proved
  by mutation: the template's pin moved alone is red (#161).

- **The archive's time budget is held by a test.** `zenodo._page` asks
  `urlopen` with `timeout=`, and every other network call here is held to its
  budget by a test — this one was not: the argument dropped left the suite
  green, and a socket that never answers would have held the posture cron
  forever (self-audit, 2026-08-31, reproduced on v0.1.10). Proved by mutation:
  the test is red with the argument gone (#160).

- **A name is not whitespace.** `Signed-off-by:    <a@b.co>` and
  `I have read and agree to CLA.md v1. —    <a@b.co>` — three spaces, or a
  tab, where the name goes — passed the module's and both CI greps' `.+`, so a
  DCO line and a CLA acceptance could carry nobody's name (self-audit,
  2026-08-31, reproduced on v0.1.10). The name now starts with a character
  that is not a space; the module and the two shell regexes agree case by
  case as before. Proved by mutation: three cases red on the old shapes (#159).

- **`own_numbers` reads every place README states the split.** "The other 83
  are the rule sheets" and "The nine checks", and the Thai half's two
  counterparts, were outside its list, so a rule added left all four behind
  and the suite stayed green while CONTRIBUTING said `--write` fixes every
  other place (self-audit, 2026-08-31, reproduced on v0.1.10). The four are
  places now (23 in all), the Thai half with its own numerals, and the tree
  test names any of them that drifts (#158).

- **The posture summary counts what the machine read, and which switches are
  read by hand is held two-way.** The weekly run printed four switches "by
  hand: … cannot be read" and then "17 switches hold their declared values" —
  a person's reads counted as the machine's (self-audit, 2026-08-31, read in
  run 33352939914). The summary now counts the machine's reads and says how
  many are printed above for a person. And `readable: false` could be added to
  any switch, turning a red "blind" into a green "by hand" with nothing in a
  pull request seeing it; the set of by-hand switches is now a copy in
  `tests/test_posture.py`, held to the register both ways like every other
  register here. Proved by mutation: the summary test is red on the old module;
  a `readable: false` planted on `enforce_admins` is red against the held set
  (#157).

- **The doctor's pass-through stderr lands beside its own gate line under a
  pipe.** In a CI log — one pipe for both streams — stdout is block-buffered
  and stderr is not, so every scan's stderr surfaced above the first gate line
  and a traceback could not be matched to the gate it belonged to (self-audit,
  2026-08-31, reproduced on v0.1.10). The doctor flushes what it has said
  before passing a scan's stderr through. Proved by mutation: the ordering
  test is red on the old doctor (#156).

- **An input the instruments cannot read is exit 2 everywhere — not a traceback,
  and never "never".** A run history whose records carried every key with the
  wrong kinds behind them (`failures` a string, `attempt` a string, `created_at`
  a number or a word) raised `TypeError`, `AttributeError` or `ValueError` from
  inside the count, exit 1 — the code for a broken promise — in all three
  censuses; `schedule_census` read `{}` and `{"foo": 1}` as "declared but never
  fired", exit 0; and a registry PyYAML rejects, or one that is not there,
  killed the harness with a traceback and exit 1 (self-audit, 2026-08-31, every
  case reproduced on v0.1.10). `history.read` now holds the kind of every field
  it is told about and parses every stamp, a mapping history is held to its
  fields like a list, the schedule census requires `last_scheduled_run` with
  stamps or `null` behind it, and the harness catches what the YAML reader
  raises. Proved by mutation: twenty-four cases red on the modules as they were
  (#155).

- **The installer judges the destination before the first copy, and refuses
  plainly.** A `tools/` or `.github/workflows/` that was a symlink leading
  outside the destination took all fourteen files with it, exit 0;
  `--manifest bundle.json` landed sixteen files and then died looking for
  `overlay.json`; a manifest that was not JSON, not an object, missing
  `gates`, or a missing file, and a destination that was a file or could not
  be written, were each a raw traceback with exit 1 — the code that means
  "refused"; and `job: scans` inside a comment of a kept `gates.yaml` silenced
  the warning that the job has no gate (self-audit, 2026-08-31, every case
  reproduced on v0.1.10). Now a directory on the way to a target that resolves
  outside the destination, a destination that is a file or unwritable, and an
  incomplete bundle are all refused before anything is written; the manifest
  is copied from wherever it was named, under `tools/overlay.json`; a
  manifest that cannot be read is "cannot read the manifest: …" and exit 2;
  and comments in the kept registry are not rows. Proved by mutation: twelve
  cases red on the old installer (#154).

- **A file Python cannot parse is refused, not a traceback.** `no-debug-entrypoint`
  and `logic-knows-no-http` read the AST; a file with a syntax error made each
  die with a traceback and exit 1 — the code that means "findings" — instead of
  the "cannot read …" and exit 2 every other unreadable input gets (self-audit,
  2026-08-31, both reproduced on v0.1.10). Both now say which file they could
  not read, on stderr, and exit 2, which the doctor reports as `[error]`.
  Proved by mutation: two cases red on the old scanners (#153).

- **`logic-knows-no-http` sees every road a request symbol takes into the
  service layer.** `import flask` followed by `flask.request.args`, `from
  flask import *`, `from flask.globals import request` and werkzeug's own
  request side (`werkzeug.wrappers`, `.local`, `.exceptions`, `.routing`) all
  bring HTTP into the logic and all passed a scanner that read only `from
  flask import <symbol>` (self-audit, 2026-08-31, every case reproduced on
  v0.1.10). `flask.current_app`, `werkzeug.security` and a `request` name of
  the file's own stay clean. Proved by mutation: six cases red on the old
  scanner (#152).

- **`delete-means-soft-delete` reads code, not prose.** A docstring saying
  "never call `session.delete(` here" was a finding, and `db_session.delete(user)`
  — SQLAlchemy's own `scoped_session` name — was not, because a word boundary
  stood between `db_` and `session` (self-audit, 2026-08-31, both reproduced
  on v0.1.10). Comments and string literals are blanked with `tokenize` before
  the match, a file Python cannot tokenize is read as written, and the session
  may carry a prefix. The match stays textual, as DECISIONS
  `write-scanner-reads-session-delete` scopes it. Proved by mutation: five
  cases red on the old scanner (#151).

- **`gates-registry-total` reads a document that opens with `---`, and every
  test file pytest collects.** A workflow whose first line was `---` — the
  most common first line there is — made the shipped reader say "more than
  one document", and a project's whole index went red for it; a test file
  under `tests/unit/` or named `*_test.py`, both of which pytest runs on every
  push, was outside the partition the title promises ("every test file is
  accounted for") and never asked for a gate (self-audit, 2026-08-31, both
  reproduced on v0.1.10). One opening marker is the document's own; a second
  is still refused. The partition now reads what pytest collects, in every
  directory under the tests root. Proved by mutation: six cases red on the old
  reader (#150).

- **`csp-no-inline` reads markup the way a browser does — the `=` on the next
  line, entities inside a value, a comment that never closes, and every
  template suffix.** `<button onclick` ⏎ `="go()">` is a handler to the
  browser and was clean here (the pattern ran one line at a time);
  `href="&#106;avascript:…"` is `javascript:` once the browser decodes the
  value and was clean; a handler in a `.htm`, `.jinja2` or `.j2` template was
  never read (`*.html` only); and a `<!--` that never closes comments out the
  rest of the file to the browser but was a finding here (self-audit,
  2026-08-31, every case reproduced on v0.1.10). The patterns now run over the
  whole file with a finding on the line its attribute name starts, entities
  are decoded inside quoted attribute values only — `&lt;script&gt;` in text
  stays text — an unclosed comment is blanked to the end, and `.htm`,
  `.jinja`, `.jinja2` and `.j2` are read like `.html`. Proved by mutation: nine
  cases red on the old scanner (#149).
- **Text a shell will run is read as the command it becomes, and a script is
  followed from where the shell stands.** `bash -lc "pip install ruff"` (the
  `-c` folded into other flags), `echo "pip install ruff" | bash`, a here-string,
  `eval "…"`, `echo preparing & pip install ruff` (a lone `&`), `echo \#1 && pip
  install ruff` (an escaped `#` read as a comment), `${PIP:-pip} install ruff`, a
  string inside `python -c "… os.system('pip install ruff')"`, and `if [ $# -gt 0
  ]; then pip install …` in a script (cut at the `#`) all execute the install
  and all exited 0; `bash "scripts/setup.sh"`, `cd scripts && ./setup.sh` and
  `./setup.sh` under `working-directory: scripts` were not followed into the
  script (self-audit, 2026-08-31, every case reproduced on v0.1.10). A `#` is a
  comment only at the start of a word; `-c` counts after a shell or `python`
  only, so `grep -c "pip install ruff"` — a finding before — is prose; a script
  path resolves from the `cd` before it or the step's `working-directory:`, and
  another step's directory does not move this one. Proved by mutation: eighteen
  cases red on the old scanner — sixteen installs unread and two look-alikes
  that were findings (#148).

- **A YAML shape the platform reads is read by both pinning scanners — alias,
  quoted key, tag, and a scalar continued over lines.** `run: *cmd` with the
  anchor set anywhere else in the file, `"run":`, `!!str pip install ruff`, and
  `pip` on one line with `install ruff` on the next under `>`, in quotes or as
  a plain scalar — which YAML joins with a space before the shell sees it — all
  carry an unpinned install and all exited 0; `uses: *loc` was not followed
  into the local action it names; `uses: *co` pointing at a pinned action was
  the finding `*co`, and an input named `uses` under `with:` was a finding too
  (self-audit, 2026-08-31, every case reproduced on v0.1.10). Both readers now
  resolve an alias from its anchor (the version comment travelling with it),
  accept a quoted key, drop a tag or an anchor of the value's own, fold a
  continued scalar the way YAML does — only a literal block (`|`) keeps its
  lines apart — and read nothing under `with:` as a step. Proved by mutation:
  eighteen cases red on the old scanners; the literal-block case holds the
  clean direction either way (#147).

- **Every spelling that opens the debugger is a finding, not only `debug=True`.**
  Flask's `run()` does `self.debug = bool(debug)` and hands werkzeug
  `use_debugger=self.debug`, so `app.run(debug=1)`, `app.debug = True` before
  the run, `app.config["DEBUG"] = True`, `run(use_debugger=True)` and
  `run(**{"debug": True})` all open the console that executes code from a web
  page — and all five passed `scan_entrypoint_debug`, which read one literal
  keyword (self-audit, 2026-08-31, each proved live on Flask 3.1.3). Every
  spelling with a real constant behind it is judged and named in the finding;
  a value computed at runtime is left alone, because a scanner that guesses at
  `os.environ` is a scanner that lies. Proved by mutation: five cases red on
  the old scanner, seven look-alikes clean either way (#146).

### Added

- **The three decisions round 4 left open are recorded where a reader looks.**
  Five DECISIONS rows: the SAST here is CodeQL, not the semgrep step the
  published rule names (`codeql-not-semgrep`); there is no risk register and
  no cadence register here — the rules are published, not practised, and the
  rows say why and what ends that (`no-risk-register-here`,
  `no-cadence-register-here`); `scan_write_discipline` reads `session.delete(`
  textually and the row scopes the scan, not the rule
  (`write-scanner-reads-session-delete`); the dependency half of
  `licensing-no-copyleft` is read by a person at the pin
  (`dependency-licences-read-at-the-pin`). Each row carries its expiry
  condition; all five are held by the copy in `tests/test_decisions.py` (#145).

## [0.1.10] - 2026-08-31

The fourth outside round, six models on v0.1.9, re-verified finding by finding
— one auditor wrote no report and its evidence still held three real gaps; the
findings grouped into nine causes, three re-filed items were already decided —
and then closed one pull request at a time, each with the mutation that proves
it: a command boundary hides no install and every YAML shape the platform
reads is read, `csp-no-inline` reads markup the way a browser does, a hang and
a half-finished scan are answers rather than tracebacks, `zenodo` refuses a
wrong-shaped file the way it refuses every other unreadable input, the overlay
titles and the workflow job names are held rather than trusted, a refused
install leaves no trace, and the documents say all of it before this cut
(#137–#143).

### Fixed

- **Two small seams.** A refused install had already made `tools/checks/`
  at the destination — the directories are now made only after the manifest
  passes, so a refusal leaves no trace; and a folded `uses: > # v4` was
  "pinned with no version comment" because only the value line's remainder
  was read — the marker line's comment now counts too (outside audit,
  2026-08-31, both reproduced). Proved by mutation both ways (#142).
- **Two more registers are held, not trusted.** The shipped `overlay.json`
  described its nine scan gates in words of its own — all nine titles had
  drifted from `rules.yaml`, and the only test held that a title was
  non-empty; the titles are now the catalogue's, held two-way by a test, so
  either file edited alone is red. And a job name defined in two workflow
  files was counted once by `scan_gates_registry` — the platform runs both,
  while the second was covered by the first's gate in silence; it is now a
  finding naming both files (outside audit, 2026-08-31, both reproduced).
  Proved by mutation both ways (#141).
- **`zenodo` refuses a wrong-shaped file the way it refuses every other
  unreadable input.** `--records` holding a dict or a list of strings died
  of `AttributeError`, and a wrong-shaped releases file was coerced through
  `str()` silently (outside audit, 2026-08-31, reproduced). Both are now
  "cannot read the archive or the releases: …" and exit 2, the same answer a
  missing or unparsable file gets. Proved by mutation four ways (#140).
- **A hang and a half-finished scan are answers, not tracebacks.** A scan
  that slept past the doctor's timeout killed the doctor with a raw
  `TimeoutExpired`; the harness died the same way on a hung gate; and a scan
  that printed part of a verdict and then crashed was labelled `[found]`
  (outside audit, 2026-08-31, all reproduced). The doctor now reports
  `[error] <gate> — the scan did not answer (timed out after 300s)`, treats
  exit 1 with a traceback on stderr as `[error]` however much stdout came
  first — a warning on stderr beside a real finding is still `[found]` — and
  the harness returns a red result whose cause says the gate timed out.
  Proved by mutation three ways; the warning case holds its direction either
  way (#139).
- **`csp-no-inline` reads markup the way a browser does.** An `onclick=` at
  a wrapped line's start or after a `/` was unread (the pattern wanted
  whitespace before it), a `<script` whose tag closes on a later line was
  unread (the pattern wanted the `>` on the same line), a `<style` at a
  line's end was unread — and a `<!-- comment -->` that merely mentions the
  words was a finding (outside audit, 2026-08-31, all reproduced). Attributes
  now match at a line's start and after `/`, a `<script` tag is read to its
  `>` wherever that is with `src=` still the allowed shape, `<style\b` needs
  no character after it, and comments are blanked first, newlines kept, so
  line numbers stay true. Proved by mutation: seven of the nine new cases
  red on the old scanner; the sourced-script pair holds the clean direction
  either way (#138).
- **A command boundary is not a hiding place, and every YAML shape the
  platform reads is read.** `$(pip install ruff)`, a backtick form, a `( )`
  subshell and `sh -c "pip install ruff"` all execute the install and all
  exited 0 — the scanner wanted whitespace before `pip`; meanwhile
  `echo pip install ruff`, which installs nothing, was a finding. Each
  boundary now starts a new command to judge, and a command whose first word
  is `echo`/`printf` is prose. `uses :`/`run :` (space before the colon) and
  flow-style `- {uses: …}`/`- {run: …}` — valid YAML the platform parses —
  were unread by both pinning scanners and are now read (outside audit,
  2026-08-31, all reproduced). Proved by mutation: ten of the twelve new
  cases red on the old scanners; the other two hold the clean direction
  either way (#137).

## [0.1.9] - 2026-08-30

The third outside round of the day, four models this time, re-verified
finding by finding before anything was touched — of one auditor's twelve, five
reproduced as gaps and one as a proof pointing at the wrong pull request; the
rest were already decided, refuted by the tool itself, or wording — and then
closed one pull request at a time, each with the mutation that proves it: the
step gates are held by a copy, both pinning scanners follow a folded local
action and a script known by its shebang, the doctor tells a crashed scan from
a finding, `--require-hashes` counts only where pip reads it and only `run:` is
read, three scanners hold the whole of the title they decide, and the two
security proofs name the run that went red (#129–#135).

### Fixed

- **The two security proofs name the run that went red.** Both `ci-red` rows
  cited `pr/45` — the pull request that *added* the jobs, whose every check is
  green — while the red was seen on the throwaway pull request #46, closed
  unmerged, in run 33244862480 (`codeql` and `secret-scan` both `failure`); an
  outside audit on 2026-08-30 followed the ref, found only green, and called
  the proof unverifiable. The rows now cite `run/33244862480` and say which
  pull request it belongs to (#134).
- **Three scanners now hold the whole of the title they decide.** An outside
  audit on 2026-08-30 read each rule's title against its scanner and planted
  the clause the scanner did not read (all reproduced): `actions-sha-pinned`
  says *with the version in a comment* and a bare `@<sha>` was green — now it
  is "pinned with no version comment" (a `docker://` digest needs none; the
  folded reader also now splits the comment off the value line, where it used
  to swallow it into the ref); `adr-index-complete` says *without repeats* and
  `0001-a.md` beside `0001-b.md` was green because a dict keyed by number kept
  one — now "number used twice"; `csp-no-inline` read `onclick=` and `style=`
  in lowercase only while HTML is case-insensitive — now any case, and a
  `<style>` element is a finding beside the attribute. Proved by mutation:
  nine cases red on the old scanners (#133).
- **`--require-hashes` is an argument of the install, and only `run:` is
  judged.** The install scanner looked for the flag anywhere on the line, so
  `MARKER=--require-hashes pip install ruff` — the flag in a place pip never
  reads — was green, and it read every line of a workflow, so a step *named*
  "explain why pip install ruff is forbidden" was red (outside audit,
  2026-08-30, both reproduced). The flag now counts only among the install's
  own arguments, and in a workflow or an action only what `run:` executes is
  read — the value on the line, its continuation, or the `|`/`>` block
  beneath it; `name:`, `env:` and `with:` are prose to the runner. Scripts and
  Dockerfiles are still read whole. Proved by mutation: nine new cases red on
  the old scanner (#132).
- **The doctor tells a crashed scan from a finding.** A scan that exited
  without a verdict — seven tracebacks on a malformed `scaffold.json`, or exit
  2 with a usage line — was printed as `[found]` with its stderr swallowed
  (outside audit, 2026-08-30, reproduced), so a broken tool read as a broken
  project with nothing to say why. It is now `[error] <gate> — the scan did
  not answer (exit N)`, its stderr passed through, counted apart from the
  findings as "no verdict", and still red. Proved by mutation two ways (#131).
- **A folded local action and an extensionless script are followed too.**
  Both pinning scanners followed `uses: ./ci/action` but wanted the `./` on
  the `uses:` line, so `uses: >` with the path on the next line was unread —
  an unpinned `actions/checkout@v4` and a `pip install ruff` behind it both
  exited 0 (outside audit, 2026-08-30, reproduced); and a hand-off was a
  script only by its `.sh` name, so `./scripts/setup` with a bash shebang was
  unread. The local path is now read the way every `uses:` value is, and a
  file with no extension is a shell script when its first line is a shell
  shebang — a Python tool that prints the words is still not read as shell.
  Proved by mutation: nine new cases red on the old scanners (#130).
- **The step gates are held by a copy, two-way.** A test gate is held by its
  test file and a job gate by its job (`scan_gates_registry`), but a gate one
  named step enforces (`kind: step`) was held by nothing: an outside audit on
  2026-08-30 deleted each of the two alone and 1275 tests stayed green. The
  two are now copied into `HELD_STEP_GATES` in
  `tests/test_instruments_dogfood.py` with the job and step each names — a
  step gate removed, added or renamed, or its step gone from the workflow, is
  red until the same pull request changes the copy. Proved by mutation three
  ways (#129).

## [0.1.8] - 2026-08-30

The second five-model re-audit of the day, re-verified claim by claim before
anything was touched — nineteen of one auditor's twenty findings reproduced,
two other auditors' census findings reproduced, one finding shown to be a
no-op edit and one already covered by a DECISIONS row — and then closed one
pull request at a time, each with the mutation that proves it: the two pinning
scanners read everything a job really runs, the installer refuses what leaves
the destination and names the seam it leaves behind, three registers and two
ratchets are held by a copy a reviewer sees, the censuses tell their states
apart and refuse a history of the wrong records, and the documents say all of
it before this cut (#109–#127).

### Fixed

- **A trailing comment cannot pin an install.** `scan_install_pinning` checked
  for `--require-hashes` on the whole line, so `pip install ruff  # TODO: use
  --require-hashes one day` was green while the same line without its comment
  was red (outside audit, 2026-08-30, reproduced). Everything after a `#`
  outside quotes is dropped before the line is judged; a `#` inside quotes
  stays text. Proved by mutation both ways (#109).
- **The installer names the job its kept registry lacks.** Installing into
  a project that already has a `gates.yaml` kept it and wrote the workflow,
  whose `scans` job the kept registry did not name — the doctor was red from
  the first run and the installer had said only "check with the doctor"
  (outside audit, installed into the reference implementation, 2026-08-30).
  It now says which job has no gate and the row to add; it still exits 0,
  because the files arrived and a consumer's CI reinstalls on every run.
  Proved by mutation three ways (#110).
- **The installer refuses a manifest that leaves the destination.** Every
  `ship` name was joined under `dest/tools/` and `manifest.problems()` had no
  caller in `install.py`, so a manifest reaching it through `--manifest` with
  `../../outside/PLANTED.txt` wrote the file beside the destination and
  exited 0 (outside audit, 2026-08-30, reproduced). `problems()` names a
  `ship` entry that is absolute or climbs with `..`, and `install()` runs it
  before the first copy, refusing on any problem it names. The DECISIONS row
  `manifest-problems-is-a-test-time-check` is recorded as expired — its own
  condition was met by `--manifest`. Proved by mutation both ways (#111).
- **A local action is read wherever it lives.** Both pinning scanners read
  composite actions only under `.github/actions/`, while GitHub runs
  `uses: ./<path>` from anywhere — an outside audit planted a floating action
  and an unpinned install under `ci/actions/setup/` and both scanners exited
  0, against the 0.1.4 line that said composite actions were read (2026-08-30,
  reproduced). Every file read is followed through its `uses: ./<path>` lines
  to `<path>/action.yml` or `action.yaml`, an action calling an action
  included. Proved by mutation in each scanner (#112).
- **An unnamed Dockerfile away from the root is not nothing.** The Dockerfile
  scanner read the default root `Dockerfile`, so a project that had not named
  its Dockerfiles got "NA: no Dockerfile" for an unpinned `Dockerfile.prod`
  or `docker/Dockerfile` (outside audit, 2026-08-30, reproduced). When nothing
  is named and the default is absent, every `Dockerfile*` in the tree is a
  finding that says to name it under `dockerfiles` — NA means nothing to
  check, not nothing looked at. A project that named its files has decided.
  Proved by mutation both ways (#113).
- **Installers with no `pip` in the line are read.** The install scanner
  keyed on the word `pip`, so `uv tool install`, `uv add`, `uvx`,
  `poetry add`, `pdm add` and `pipenv install` resolved from the index unread
  (outside audit, 2026-08-30, reproduced with the first and `poetry add`).
  Each is a finding now; `uv run --locked`, `uv sync --locked`, `uv build`
  and `poetry install` install from a lock that carries hashes and are left
  alone, held by a test. Proved by mutation both ways (#114).
- **A shell script CI hands off to is read.** The install scanner read the
  workflow's own `run:` lines, so `- run: ./scripts/setup.sh` with
  `pip install ruff` inside the script was green — the install runs with the
  job's permissions all the same (outside audit, 2026-08-30, reproduced).
  Every read file is followed into the scripts it hands off to, scripts
  calling scripts included; a path that is absolute, missing or climbs out of
  the checkout is not ours. Proved by mutation three ways (#115).
- **A proof dated in the future is not evidence.** The registry schema
  checked that a `proved_by` date was a real calendar date and nothing more,
  so `date: 2099-01-01` passed the schema and the suite (outside audit,
  2026-08-30, reproduced). A date later than today anywhere on Earth is a
  problem now — UTC+14, so a proof written in Bangkok at 02:00 and dated
  tomorrow-in-UTC is not from the future. Proved by mutation three ways
  (#117).
- **Both schemas refuse a key they do not know.** `rules.problems()` and
  `registry.problems()` passed over any key they did not read, so
  `portable: true` on a rule and a misspelt key on a gate drew nothing — and
  README placed the internal-cannot-be-portable hold in the rule schema when
  it lives in the gate schema, the rule schema refusing `internal` whole
  (outside audit, 2026-08-30, reproduced). Each schema carries the keys it
  reads and refuses the rest; README says which schema holds which rule.
  Proved by mutation five ways (#119).
- **The censuses tell their three states apart.** `red_streak_census`
  printed "no gate declares a watcher (it blocks)" for any workflow without
  a promise — for the platform's own Dependabot runs and for release.yml,
  none of which a merge blocks on; `schedule_census` summed up "every
  declared schedule is still firing" above a cron that had never fired and
  was merely not due yet (outside audit, 2026-08-30, reproduced). A promise,
  a pull_request trigger, or neither — the worst, red with the fix named —
  are told apart, a platform path is named as such, and the summary counts
  what fired apart from what is excused. Proved by mutation four ways (#122).
- **The bundle's own workflow is nothing of yours to check.** Installed into
  an empty directory, the bundle wrote `gates.yml` and the two pinning scans
  said `pass` on the file it had just written — nothing of the project's
  measured (outside audit, 2026-08-30, reproduced). The untouched starting
  workflow — a pinned checkout, then the doctor — is NA in both; a line added
  or the pin loosened makes it the project's. The registry scan stays `pass`
  on purpose: `test_box_opens_true` holds the shipped index to pass, never
  NA, so an absent index cannot look like a satisfied one. Proved by mutation
  four ways (#123).
- **A history of the wrong records is unreadable, not zero.** The one reader
  the censuses share held the shape of the whole — a list, non-empty — and
  nothing about the records: `gh run list --json` fed to `--input` made
  `rerun_census` count zero failures over a hundred runs holding thirteen and
  `red_streak_census` raise `KeyError` (outside audit, 2026-08-30, reproduced
  live). A caller names the fields its records carry; records lacking them
  are the third answer, exit 2, and the message names `gh run list` when
  that is what it was given. Proved by mutation four ways (#124).
- **A folded `uses:` names its action, not the fold marker.** `uses: >`
  with the action on the next line was reported as `actions-sha-pinned:
  ci.yml: >` — red for the right reason, naming nothing (outside audit,
  2026-08-30, reproduced). The marker is followed to the line that carries
  the value. Proved by mutation both ways (#125).

### Changed

- README says what the two pinning checkers read and what a fresh install's
  one `pass` is; CONTRIBUTING lists the registers a test holds by copy, the
  ratchets a test holds to reality, the proof-date rule, the unknown-key rule,
  and the habit of reading the gates before changing a decider's answer.

### Added

- **The posture register is held, switch by switch.** `posture-declared.json`
  is read by a job that is not a required check (it needs the administrator's
  token, which a pull request does not get), so a switch turned off or
  removed in a pull request was seen by nothing (outside audit, 2026-08-30,
  reproduced both ways). `tests/test_posture.py` carries a copy of the switch
  names and what each wants, two-way, the way `test_gate_evidence.py` holds
  proof rows: turned, removed or added is red until the same pull request
  changes both. Proved by mutation four ways (#116).
- **The DECISIONS rows are held by id.** Every row's shape was held; which
  rows existed was not — a row deleted or added left the suite green (outside
  audit, 2026-08-30, reproduced both ways). The ids are copied into
  `tests/test_decisions.py` in order, so a row removed, added or reordered is
  red until the same pull request changes the list too. Proved by mutation
  three ways (#118).
- **The xenon ceilings are held to the row and to reality.** The three
  ranks on ci.yml's xenon line were read by nothing — lowered, the suite
  stayed green, while DECISIONS.md called the line a ratchet (outside audit,
  2026-08-30, reproduced). `tests/test_own_ratchets.py` holds the line to the
  row `xenon-floor-at-reality` and each rank to where reality sits, measured
  with radon: a ceiling reality has dropped below is red until the line and
  the row move up together. Proved by mutation three ways (#120).
- **Two published rules are read against this repository.** `rules.yaml`
  publishes `jobs-declare-a-time-budget` and `exception-registers-are-reasoned`,
  and nothing here read this repository's own `timeout-minutes` or its own
  suppression lines — one of each removed, the suite stayed green (outside
  audit, 2026-08-30, reproduced). `tests/test_instruments_dogfood.py` reads
  every job for an integer budget, every suppression under `src/` and
  `tests/` for a reason, and holds their number. Proved by mutation four
  ways (#121).

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

[Unreleased]: https://github.com/sayam/verifiable-gates/compare/v0.1.10...HEAD
[0.1.10]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.10
[0.1.9]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.9
[0.1.8]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.8
[0.1.7]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.7
[0.1.6]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.6
[0.1.5]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.5
[0.1.4]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.4
[0.1.3]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.3
[0.1.2]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.2
[0.1.1]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.1
[0.1.0]: https://github.com/sayam/verifiable-gates/releases/tag/v0.1.0
