# What the doctor's output means

The doctor, `tools/gates_doctor.py`, gives one of four answers per gate and one exit
code per run. This page is the full taxonomy: every situation the scanners were built
to tell apart, what each answers, and why it does not answer the other thing. The short
form is in the README under *Reading the output*; this is where the cases live.

The exit codes are the contract every scanner shares: **0** clean or `NA`, **1**
findings or `[error]`, **2** misuse — two questions asked at once, two roots, a bundle
`--rules` cannot vouch for.

## The four answers

| Answer    | The checker…                                   | The doctor exits |
|-----------|------------------------------------------------|------------------|
| `[ pass]` | looked, and the rule holds                     | 0                |
| `[found]` | looked, and the rule is broken                 | 1                |
| `[   NA]` | had nothing of the kind it reads to look at; it names what it looked for | 0 |
| `[error]` | could not answer; its stderr is passed through | 1                |
| `[waived]` | looked, found it, and a waiver in `scaffold.json` covers it — the run prints what was excused | 0 (for that gate) |

## Situation → verdict → why not the other one

| Situation | Verdict | Why not the other verdict |
|---|---|---|
| A rule the doctor cannot decide here — nothing of the kind the checker reads exists | `NA` | A rule the tool cannot check must not look like a rule it checked. |
| Every rule is `NA` | exit 0 | That is "nothing was measured", not "the project passed". The doctor cannot know how many scans *should* apply; a floor belongs to the project (`DECISIONS.md` `doctor-all-na-exits-zero`). |
| A path `scaffold.json` *names* and the project does not have | finding | A broken configuration is a defect, not an absence. |
| A `scaffold.json` value of the wrong shape — a list where one path goes, a string where a list of names goes | finding, naming the key | Same: the configuration is broken, and the finding says where. |
| A `scaffold.json` path that leads outside the project | finding, naming the key | Same. |
| A finding a waiver covers — `waivers: [{gate, reason, until, decided_by, scope?}]` in `scaffold.json` | `[waived]`, and `waived: N findings under M waivers` on every run that declares one | Not silence: the count is printed on a green run too, a waiver that excused nothing is told so, and the SARIF keeps the result with the reason as its suppression. |
| A waiver past its `until`, or missing a field, naming a scan the bundle does not run, or a scope that leads outside | finding under the doctor's own `waivers`, and it excuses nothing | A waiver with no reason is `# noqa`; one with no `until` is permanent; one nobody signed is nobody's. The tool never learned to write any of those. |
| A `scaffold.json` key no scanner reads — `templates_pth` for `templates_path` | finding, naming the nearest key the bundle does read | Every scanner would answer from its default while the project pointed elsewhere (measured 2026-09-05, round 23). |
| A `Dockerfile*` the project has but never named in `scaffold.json` | finding | Not "no Dockerfile": the file is there and unjudged. |
| A directory that is *there* and holds no file of the kind a checker reads — an `app/` of Go, a templates directory of `.ejs` | `NA`, naming what it looked for | Not a pass: nothing was read. |
| A scan that crashes | `[error]`, stderr passed through | Never `[found]`: a tool that crashed has judged nothing. Still red — an outside audit on 2026-08-30 fed a malformed config and saw `[found]` seven times with the tracebacks swallowed. |
| A scan that hangs past its timeout | `[error]` | Same (the doctor tracebacked with `TimeoutExpired`, outside audit 2026-08-31). |
| A scan that answers half a verdict before crashing | `[error]` | A traceback on stderr beside exit 1 means the scan did not finish. |
| A file the scanner cannot decode, may not open, or that is larger than the 8 MiB a scanner reads whole | `[error]` | The file was not read, so nothing about it is known. |
| `scaffold.json` that cannot be read as a configuration at all | `[error]` | Same. |
| A directory the scanner cannot walk — closed to it | `[error]` | A directory closed to the scanner is *not* the answer a directory that is not there gets, which stays `NA`. |
| A fresh install | `pass` for `gates-registry-total` only; `NA` for the two pinning checkers | The shipped index has to be true about itself. The starting workflow the installer wrote is the bundle's own file until a line of it changes — a green on that file says nothing about the project. |
| A gate whose job cannot turn the build red — a workflow with no trigger, `if: false`, or `continue-on-error: true` | finding from `gates-registry-total` | A row nothing can fail is a row and nothing else. Each finding names the file to open and the row to add or change, so the first line a stranger reads points at the second. |

## A finding, as printed

The run from the README, in full: an empty repository that installed the bundle and
then gained one workflow, `lint.yml`, with `uses: actions/checkout@v4` and
`run: pip install ruff` (2026-09-05, v0.3.0). The third finding is the new job itself,
which has no row in `gates.yaml`:

```text
$ python3 tools/gates_doctor.py
[found] actions-sha-pinned — Every action is pinned to a commit SHA with the version in a comment
  born from: Tags move, commits do not — upload-artifact once sat on @v4 at a single call site for ten days with CI green throughout.
actions-sha-pinned: .github/workflows/lint.yml: actions/checkout@v4
[   NA] adr-index-complete — no docs/adr — this rule reads the .md records and the README.md index under docs/adr (scaffold.json adr_path)
[found] ci-tools-hash-pinned — Tools CI installs for itself are pinned by hash, on both the Python and the Node side
  born from: An unpinned install command takes whatever is newest at the second the job runs, and it runs with our workflow's privileges · pinning one package at a time pins only that package while the rest of the tree still floats.
ci-tools-hash-pinned: .github/workflows/lint.yml: pip install ruff
[   NA] csp-no-inline — no app/templates — this rule reads .html, .htm, .jinja, .jinja2 and .j2 templates under app/templates (scaffold.json templates_path)
[   NA] delete-means-soft-delete — no app — this rule reads Python modules under app (scaffold.json src_path) — session.delete calls outside the purge_paths
[found] gates-registry-total — The gate index matches reality in both directions, and every test file is accounted for
  born from: semgrep was scanning only 71 of 136 files because its scope was declared in two places — an index nothing holds to reality is an index that quietly reports things that are not true · audit round 7 added another field (`guards:` — ADR 0062): a gate that is expensive and has never caught anything has to be able to say *which path* it earns its keep on, or the question "is it still worth it" is answered by feel every time.
gates-registry-total: job with no gate in the index: lint — add a row to gates.yaml: id, title, kind: job, severity, enforced_by: {job: lint}
[   NA] image-digest-pinned — no Dockerfile — this rule reads the FROM lines of the root Dockerfile (scaffold.json dockerfiles), and .github/dependabot.yml for a docker ecosystem
[   NA] logic-knows-no-http — no app/services — this rule reads Python modules under app/services (scaffold.json services_path) — their imports, for request-side symbols
[   NA] no-debug-entrypoint — no entrypoint — this rule reads the Python entrypoints run.py, wsgi.py, app.py and main.py (scaffold.json entrypoints), as an AST

waiting on this project's own tests: 0 gates
** scans found problems in 3 gates: actions-sha-pinned, ci-tools-hash-pinned, gates-registry-total
[exit 1]
```

A finding carries two lines above the scanner's own — `[found] <gate> — <rule>` and
`born from: <incident>` — read off the installed manifest. Off a bundle the installed
record no longer vouches for (below), it carries the gate alone and one line saying
why; the scanner's findings are printed either way.

## `--installed`: the record of what was installed

The bundle keeps a record of what it installed, `tools/installed.json`.
`gates_doctor --installed` holds every file it wrote to the *contents* it wrote, not
merely to being present — and writes nothing into the tree it checks, not even
bytecode. An upgrade names what this version no longer ships and leaves it in place,
because a file in your repository is yours to remove.

An install that stopped partway is read as one: the doctor leads with *the last install
into this tree did not finish* rather than reporting the files that did land as files
somebody edited. One still under way is read as one too, because the record is written
before the first file and names what each file is about to become.

## `--rules`: the rules the bundle decides

`gates_doctor --rules` prints the rules the bundle decides — each with where it came
from and which scanner reads it — for the instruction file a project keeps for its
agents (`AGENTS.md`, `CLAUDE.md`) to point at. It is read at run time from the
installed manifest, so an upgrade cannot leave an agent on yesterday's rule, and it
prints only the rules a scanner here can decide, so no instruction stands without a
gate behind it (`DECISIONS.md` `rules-are-read-off-the-installed-bundle`).

It prints them only off a bundle the installed record still vouches for: an edited
manifest, an edited scanner, or no record at all prints no rules and **exits 2**,
because the file it reads lives inside the project it holds to account
(`DECISIONS.md` `the-rules-are-read-off-a-bundle-that-is-still-intact`).

## `--sarif FILE`: the same run for code scanning

`gates_doctor --sarif FILE` writes the same run as SARIF 2.1.0 for code scanning,
reviewdog or an IDE. The mapping, measured against GitHub's Security tab in round 23:

| In the run | In the SARIF | Why |
|---|---|---|
| a finding | a **result** | It is what a reader counts. |
| `NA` | a **notification** on the invocation, never a result | GitHub keeps a SARIF's results and drops its invocation, so a reader counting results must not see "could not look" as "looked and found nothing". |
| a scan that did not answer | **both** — an error notification, and a result of the doctor's own rule `scan-did-not-answer` | Same reason: the result is the one shape that reader keeps. |
| every result | carries a **location** the tree has — the file the finding names, else `scaffold.json` | GitHub refuses a whole file over one result without one. |
| every result | carries a **fingerprint** (`partialFingerprints.primaryLocationLineHash`): the rule, the message with its line number taken out, and its place among identical sentences in the run | GitHub matches an alert across commits on it; a line inserted above a finding moves its region and its `:N`, and must not re-open it (round 26). |
| a waived finding | a **result with `suppressions`** — `kind: external`, the waiver's reason, `until` and `decided_by` as the justification | A reader counts it, and sees why it does not fail the run; code scanning shows a suppressed result as dismissed with its justification rather than gone (what GitHub does with it was not measured in round 26; the file is). |
| the run | the invocation names the doctor's exit code and why | The one line about the run that GitHub keeps; the notifications it drops. |

A file already at that path is replaced only if it is this doctor's run over the same
root; another tree's run, or anything else, is left where it is and named — two trees
given one path lose no answer.

## The catalogue reader

`rules.problems()` checks that a rule's `script:` exists only when it is given the
package directory (`package_dir=`), as the doctor does; without it, only the shape of
the path is checked — a checker that is not there would go unnoticed.
