# The nine checkers

One section per checker the bundle ships, in the order the doctor prints them. What
each *reads* is a field of its rule in `rules.yaml` (`reads:`) and is printed by
`python3 tools/gates_doctor.py --rules` off the installed bundle; that command is the
authority, and the transcript below is what it printed on 2026-09-05 (v0.3.0). The
sections after it hold what the README used to carry about how each checker parses
what it reads.

```text
$ python3 tools/gates_doctor.py --rules
The rules this bundle decides for this project: 9, one scanner each.
An instruction in this project's AGENTS.md or CLAUDE.md does not switch a scanner off;
every rule below runs on every push. A rule of layer `business` is a choice this kind
of application makes and may be decided differently — in scaffold.json and gates.yaml,
where the decision is on the record — never by working around the scanner.

actions-sha-pinned [baseline]
  rule:       Every action is pinned to a commit SHA with the version in a comment
  born from:  Tags move, commits do not — upload-artifact once sat on @v4 at a single call site for ten days with CI green throughout.
  decided by: tools/checks/scan_workflow_pinning.py
  reads:      the uses: steps of workflows and composite actions under .github
adr-index-complete [baseline]
  rule:       The ADR index covers every record, numbered without repeats or gaps · and supersessions are recorded in both directions
  born from:  The index once stopped at 0026 while the files ran to 0033 — seven records from the phase that decided the biggest questions, invisible · audit round 14 added the second direction: ADR 0035 had superseded item 1 of 0032 since 2026-08-12, but 0032's own page did not know for seven days, while the module docstring at the head of app/audit.py still pointed at 0032 as the current mechanism, which CLAUDE.md explicitly forbids returning to.
  decided by: tools/checks/scan_adr_index.py
  reads:      the .md records and the README.md index under docs/adr (scaffold.json adr_path)
ci-tools-hash-pinned [baseline]
  rule:       Tools CI installs for itself are pinned by hash, on both the Python and the Node side
  born from:  An unpinned install command takes whatever is newest at the second the job runs, and it runs with our workflow's privileges · pinning one package at a time pins only that package while the rest of the tree still floats.
  decided by: tools/checks/scan_install_pinning.py
  reads:      pip, pipx, npm/npx/yarn/pnpm, uv/uvx/poetry/pdm/pipenv and python -m build lines in workflows, composite actions, the scripts they run, and the root Dockerfile
csp-no-inline [baseline]
  rule:       CSP is pure self — no inline script, style, or handler anywhere
  born from:  ADR 0010 — the browser blocks inline content silently with no server-side error, so the gate has to read the template files directly rather than wait for symptoms.
  decided by: tools/checks/scan_templates_inline.py
  reads:      .html, .htm, .jinja, .jinja2 and .j2 templates under app/templates (scaffold.json templates_path)
delete-means-soft-delete [business]
  rule:       Delete means hide (soft delete) — only purge removes rows for real
  born from:  ADR 0014 — a `--dry-run` implemented as a rollback once deleted real data, because purge committed before the savepoint closed · so there must be exactly one place that can delete.
  decided by: tools/checks/scan_write_discipline.py
  reads:      Python modules under app (scaffold.json src_path) — session.delete calls outside the purge_paths
gates-registry-total [baseline]
  rule:       The gate index matches reality in both directions, and every test file is accounted for
  born from:  semgrep was scanning only 71 of 136 files because its scope was declared in two places — an index nothing holds to reality is an index that quietly reports things that are not true · audit round 7 added another field (`guards:` — ADR 0062): a gate that is expensive and has never caught anything has to be able to say *which path* it earns its keep on, or the question "is it still worth it" is answered by feel every time.
  decided by: tools/checks/scan_gates_registry.py
  reads:      the gate index at gates.yaml (scaffold.json gates_path), the jobs of every workflow under .github/workflows, and the test files under tests
image-digest-pinned [baseline]
  rule:       The base image is pinned to a manifest-index digest and Dependabot moves it
  born from:  Pinning with nobody to move it freezes the vulnerabilities in place — the two must always arrive together, and the test enforces that the pair is not separated.
  decided by: tools/checks/scan_dockerfile_digest.py
  reads:      the FROM lines of the root Dockerfile (scaffold.json dockerfiles), and .github/dependabot.yml for a docker ecosystem
logic-knows-no-http [baseline]
  rule:       All logic lives in the service layer and knows nothing about HTTP
  born from:  Phase 3 — logic buried in routes makes the HTML and the API diverge the instant a second adapter exists · an AST scan forbids services importing anything from the request side.
  decided by: tools/checks/scan_service_layer.py
  reads:      Python modules under app/services (scaffold.json services_path) — their imports, for request-side symbols
no-debug-entrypoint [baseline]
  rule:       No entrypoint file can open a debug console, even when the wrong one is run
  born from:  The first SAST round pointed at an entrypoint that could enable debug and was being copied into the image — run the wrong one and you have a debug console that executes code from a web page.
  decided by: tools/checks/scan_entrypoint_debug.py
  reads:      the Python entrypoints run.py, wsgi.py, app.py and main.py (scaffold.json entrypoints), as an AST

The catalogue this bundle comes from names more rules; only these are decided here.
[exit 0]
```

Every checker is a single stdlib-only Python file, run as `python3 <scanner> <root>`
by a project that has installed nothing else; none imports a network module, and
`tests/test_checks_are_standalone.py` holds that. Each exits 0 clean, 1 with
findings, 2 when it could not answer. A path below is the default `scaffold.json`
carries; the project moves it there.

## What each one decides, and what a pass does not say

The criticism this catalogue takes seriously about check suites in general — Scorecard's
`Security-Policy` is the usual example — is that a check can measure *presence*: a file
exists, a field is filled, a row is there. Presence is cheap to satisfy and cheap to fake,
and a suite that never says which of its checks are presence checks lets the two kinds be
read as one. Here is which is which, and the more useful half beside it: what a green from
each one still does not tell you. Nothing in this table is new behaviour; it is what the
sections below already do, said in one place.

| checker | what a finding is about | what a pass does **not** say |
|---|---|---|
| `gates-registry-total` | **presence**, both ways — a test file no row claims, a row naming a job that is not there — **and one effect check**: a gate whose job cannot turn the build red, because it has no trigger, an `if: false`, or `continue-on-error: true` | that the tests behind those rows catch anything. Whether a gate has ever gone red is `proved_by`'s question, and this repository holds itself to it in a different file |
| `actions-sha-pinned` | **content**: every `uses:` in every workflow and composite action, read as a line | that the commit pinned is one you want. A pin says nothing about which version (`DECISIONS.md` `a-pin-says-nothing-about-which-version`) — an agent once pinned `@v4` to the SHA of v7.0.1, truthfully labelled |
| `ci-tools-hash-pinned` | **content**: every install line in a workflow, a composite action, or a script a `run:` hands off to | that the lock or hash resolves to something safe, nor that tools arriving another way — a container image, the runner's pre-installed set — are pinned at all |
| `image-digest-pinned` | **content** (the `FROM` and `COPY --from` lines) **and presence** (a `docker` ecosystem in `.github/dependabot.yml`; a `Dockerfile*` the project never named and git does not ignore) | that the image is free of vulnerabilities. A digest fixes *which* image you get, and the Dependabot half is there because a pin nobody moves freezes what it pinned |
| `csp-no-inline` | **content**: every template under the templates path, read the way a browser reads one | that the application sends a Content-Security-Policy header, or that it holds at run time. Nothing here makes a request |
| `no-debug-entrypoint` | **content**: the named entrypoints, as an AST | that no debug console can be opened another way — a framework default, a server flag, a value this scanner cannot see (`debug=settings.DEBUG` is unknown, and unknown is not a finding) |
| `logic-knows-no-http` | **content**: the imports of the modules under the services path | that the layer is free of request-shaped coupling. A function handed the request object as an argument imports nothing and passes |
| `delete-means-soft-delete` | **content**: `session.delete` calls outside the declared purge paths | that the deletes it left alone are the right ones. The purge path is a declaration, and this scanner reads the declaration |
| `adr-index-complete` | **presence and consistency**: records against the index, both ways | that a decision was ever recorded. A decision nobody wrote down has no record to be missing from — which is why `DECISIONS.md` is a register with a test, not a directory nobody has to fill |

Two things follow from the table. **A pass is about what the scanner read**, and every one
of the nine says what it reads, in `--rules` and in its `NA` line, so a green can be
checked against a question. And **presence is never the whole of a rule here**: the two
presence checks are about this repository's own registers, where the register *is* the
subject, and the seven that decide a project's code all read the code.

## gates-registry-total

Reads `gates.yaml` (`gates_path`), the jobs of every workflow under
`.github/workflows`, and the test files under the tests path (`tests_path`). A
`tests_path` the project **names** and does not have is a finding, like every other
configured path; the default `tests`, absent and unnamed, is the quiet half. It
reads its own direction too: a gate whose job cannot turn the build red — a workflow with no trigger,
`if: false`, or `continue-on-error: true` — is a finding, because a row nothing can
fail is a row and nothing else. Each of its findings names the file to open and the
row to add or change, so the first line a stranger reads points at the second. On a
fresh install it is the only `pass`: the shipped index has to be true about itself.

## actions-sha-pinned

Reads the `uses:` steps of every workflow and of every composite action a workflow
names with `uses: ./<path>`, wherever it lives, folded or not. It judges both halves
of its title: a floating tag is a finding, and so is a commit SHA with no version
comment beside it — a pin nobody can read or move. A `docker://` digest needs no
comment. A `uses:` folded onto the next line is read from that line. The YAML forms
both pinning checkers read are the table under `ci-tools-hash-pinned`.

## ci-tools-hash-pinned

Reads every workflow, every composite action a workflow names with `uses: ./<path>`,
and every shell script a `run:` line hands off to — known by its `.sh` name or by its
shebang, quoted or not, from wherever the shell stands (a `cd dir &&` before it, or
the step's `working-directory:`) — with comments stripped first; a `#` inside a word
(`$#`, `${#PKGS}`, `\#`) is not one. In a workflow only what `run:` executes is
judged: a `name:` or an `env:` that quotes the command is prose.

**Recognised as an install, and what exempts it**

| Judged | Left alone | Why |
|---|---|---|
| `pip install …` | `--require-hashes` as an argument of the install itself, quoted or not · `PIP_REQUIRE_HASHES=1` on the command or in the step's own `env:` · a requirements file whose every line carries a `--hash=` | pip requires hashes in each of those cases on its own |
| `pip install …` | `--no-index` · a wheel installed with `--no-deps` | fetch nothing |
| `pipx install …`, `uv tool install`, `uv tool run`, `uv add`, `uvx`, `uv run --with`, `poetry add`, `pdm add`, `pipenv install` | `uv run --locked`, `uv sync --locked`, `uv build` | install from a lock |
| `pip wheel`, `python -m build` | held to `--no-build-isolation` | both build in an isolated environment that fetches |
| `npm install`, `npm exec`, `npx`, `yarn add`, `pnpm add`, `pnpm dlx` | `npm ci`, `yarn install --immutable`, `pnpm install --frozen-lockfile` — install from a lock · `npx --no`, `npm exec --no`, `pnpm exec` — run the installed copy and refuse to fetch | |

A Node finding says what replaces that line — `npm ci` for `npm install`,
`npx --no <tool>` for `npx <tool>` — and names the lock it needs, or says to commit one
when it is not there. Go, Cargo and Gem installs are not judged (`DECISIONS.md`
`go-cargo-gem-installs-are-not-judged`).

**Recognised as execution, versus prose**

| Executes, and is judged | Prose, not judged |
|---|---|
| a command inside `$( )` or backticks | a bare `echo` of the words |
| a `( )` subshell | a `name:` or `env:` that quotes the command |
| an `sh -c` string, with `-c` folded into other flags too (`bash -lc`) | |
| a string `python -c` hands to `os.system` | |
| a command after a lone `&` | |
| words handed to a shell by a pipe (`echo … \| bash`), a here-string, or `eval` | a heredoc whose receiver is not a shell (`cat > README.md <<'EOF'` writes a file) |
| `${PIP:-pip}` — the default is read as the word | |

**YAML forms, read the way the platform reads them**

| Form | Read as |
|---|---|
| `uses :` (space before the colon) · `- {uses: …}` (flow mapping) | a step |
| `"run":` (quoted key) | a step |
| `run: *cmd`, `uses: *co` — an alias of an anchor set anywhere in the file | the anchored value, with the anchor's version comment |
| `!!str` (tagged value) | the string |
| a plain, quoted or folded (`>`) scalar that continues onto the next line | one line — YAML joins with a space before the shell sees it |
| a literal block (`\|`) | its lines kept apart |
| `uses` under `with:` | an input, not a step |

## image-digest-pinned

Reads the `FROM` lines of the root Dockerfile (`dockerfiles`) and
`.github/dependabot.yml` for a `docker` ecosystem. A base image pinned with nobody to
move it freezes the vulnerabilities in place, so the digest and the Dependabot entry
must arrive together. A `Dockerfile*` the project has but never named in
`scaffold.json` is a finding, not "no Dockerfile".

## csp-no-inline

Reads `.html`, `.htm`, `.jinja`, `.jinja2` and `.j2` templates under the templates
path, the way a browser does: `ONCLICK=`, `STYLE=` and a `<style>` element in any
case, split over lines or not (the `=` on the line after the name too), with comments
blanked first (one that never closes runs to the end of the file), and entities inside
an attribute value decoded before the scheme is read (`&#106;avascript:`). A templates
directory that holds no file of these kinds — `.ejs`, say — is `NA` naming what it
looked for.

## no-debug-entrypoint

Reads the Python entrypoints `run.py`, `wsgi.py`, `app.py` and `main.py`
(`entrypoints`), as an AST, for the call that can open a debug console. Flask does
`self.debug = bool(debug)` and hands werkzeug `use_debugger=self.debug`, so the
spellings are one console: `run(debug=1)`, `run(use_debugger=True)`,
`run(**{"debug": True})`, `app.debug = True` and `app.config["DEBUG"] = True`
before the run. It also reads a truthy literal sitting in a **default** —
`run(debug=os.environ.get("DEBUG", True))`, `os.getenv("DEBUG", 1)`,
`... or True` — because that is a debug console on every machine where the
variable is unset. A value with no literal in it, `debug=settings.DEBUG`, is
unknown and is not a finding.

## logic-knows-no-http

Reads the Python modules under the services path (`services_path`), their imports,
for request-side symbols. An `app/` of Go is `NA` naming what it looked for, not a
pass.

## delete-means-soft-delete

Layer `business`: a choice this kind of application makes and may decide differently
— in `scaffold.json` and `gates.yaml`, where the decision is on the record — never by
working around the scanner. Reads the Python modules under the source path
(`src_path`) for `session.delete` calls outside the `purge_paths`
(`DECISIONS.md` `write-scanner-reads-session-delete`).

## adr-index-complete

Reads the `.md` records and the `README.md` index under the ADR path (`adr_path`). It
reports two records sharing a number as well as a gap, and a supersession recorded in
one direction only. Records that exist with no `README.md` index is a finding; no ADR
directory at all is `NA`.


## What the nine deliberately do not decide

A rule this bundle does not carry is worth as much to an adopter as one it does, if it says
who does carry it. Measured 2026-09-06 by running each tool against a tree that breaks all
nine rules above, one violation each — not by reading their documentation.

| what you might expect here | who decides it | measured |
|---|---|---|
| `pull_request_target` and other triggers that run with your secrets against somebody else's code | **zizmor** | Its `dangerous-triggers` audit is exactly this. This catalogue publishes no rule for it and grows no scanner (`DECISIONS.md` `workflow-triggers-are-zizmors-not-ours`). |
| an unpinned action | zizmor, **and** `actions-sha-pinned` here | zizmor answered `error[unpinned-uses]` at high confidence on the same file and line, with an auto-fix. If you run zizmor, you have this one twice. |
| a debug console in an entrypoint | bandit `B201`, **partly** | It catches `app.run(debug=True)`. It missed `create_app().run(debug=True)` and every truthy default; `no-debug-entrypoint` catches all of them. |
| the service layer importing HTTP | **import-linter**, if you configure it | It decides the same thing, after you write a `forbidden` contract naming the packages. `logic-knows-no-http` reads `scaffold.json`'s `services_path` and needs nothing written. |
| an unpinned `pip install` in CI | nobody else that was run | zizmor's whole output mentioned `pip` zero times on a workflow whose `run:` was `pip install ruff`; checkov's 36 GitHub Actions checks all passed. |
| an unpinned base image | nobody else that was run | checkov read the same Dockerfile and reported the missing `HEALTHCHECK` and `USER`, not `FROM python:3.12`. |

`ruff --select ALL` on that tree found twelve things and none of them was one of the nine.

Not run, and so not claimed: semgrep, actionlint, hadolint, trivy, CodeQL and OpenSSF
Scorecard. Scorecard's `Pinned-Dependencies` is documented to read both action pins and pip
installs, which would overlap two of the nine — read, not measured.
