# Production discipline — the baseline layer

**This file is generated. Do not edit it by hand.** Rebuild it with
`python -m verifiable_gates.skill --preamble preambles/baseline.md
--out skills/verifiable-gates/references/baseline.md --layer baseline`. The source
is `rules.yaml`, and a gate compares the two on every test run.

**This is a reference sheet of the `verifiable-gates` skill.** How to read it, and the
five practices every rule below rests on, are in [`../SKILL.md`](../SKILL.md); read the
entry for the rule you are about to touch rather than the whole file.

Every rule below is **framework-agnostic**. What enforces a rule is not: enforcement
is written in some project's own framework, and each rule's *Enforced in the
reference* line points at how one real project does it. That separation is the whole
design — see the note at the top of `rules.yaml` for why the rule and its enforcement
live in different files.

This is the **baseline** layer: a project that deviates from one of these is
defective, not different. Agreements at the level of *one application* — things a
project may legitimately decide differently, such as whether delete means hide — are
a separate sheet, [`business.md`](business.md).

Every rule carries the incident that produced it. That is not decoration. A rule
whose origin nobody recorded is a rule nobody can ever retire, because no one can
tell whether the conditions that created it still hold.

## The rules

Each entry: **Rule** (universal) · **Born from** (the real trap that produced it, not
a theory) · **Enforced in the reference** (how one project enforces it today).

### `gates-registry-total`

**Rule:** The gate index matches reality in both directions, and every test file is accounted for

**Born from:** semgrep was scanning only 71 of 136 files because its scope was declared in two places — an index nothing holds to reality is an index that quietly reports things that are not true · audit round 7 added another field (`guards:` — ADR 0062): a gate that is expensive and has never caught anything has to be able to say *which path* it earns its keep on, or the question "is it still worth it" is answered by feel every time.

**Enforced in the reference:** `tests/test_gates.py`

**Reads:** the gate index at gates.yaml (scaffold.json gates_path), the jobs of every workflow under .github/workflows, and the test files under tests

### `gates-carry-red-evidence`

**Rule:** A new gate arrives with evidence that it went red on a real defect — the list of ones that have not can only shrink

**Born from:** Governance audit round 6 (2026-08-17) — measured across the last 200 runs and found **21 jobs that had never once gone red**, which from the outside is indistinguishable between "the code really is fine" and "the gate checks nothing" · a gate nobody has seen fail is a gate nobody has proved checks anything — collect the evidence when it happens, not when you need it.

**Enforced in the reference:** `tests/test_gate_evidence.py`

### `logic-knows-no-http`

**Rule:** All logic lives in the service layer and knows nothing about HTTP

**Born from:** Phase 3 — logic buried in routes makes the HTML and the API diverge the instant a second adapter exists · an AST scan forbids services importing anything from the request side.

**Enforced in the reference:** `tests/test_service_layer.py` · `tests/test_services.py`

**Reads:** Python modules under app/services (scaffold.json services_path) — their imports, for request-side symbols

### `every-column-classified`

**Rule:** Every column is assigned a data class in DATA-CLASSIFICATION.md

**Born from:** A data class not decided when the column is added gets decided when the data leaks — and what the audit trail is allowed to record follows from that class.

**Enforced in the reference:** `tests/test_data_classification.py`

### `every-column-export-decided`

**Rule:** Every column of an owned table is decided: exported, or listed as not exported with a reason

**Born from:** ADR 0034 — when each caller deleted on its own, the CLI forgot to clear the second-factor secrets entirely · one path plus every column decided means nothing is left behind.

**Enforced in the reference:** `tests/test_personal_data.py` · `tests/test_close_account.py`

### `models-match-migrations`

**Rule:** Schema comes only from migrations, and it matches the models exactly

**Born from:** An index that lived in a migration but not in the model was nearly dropped, silently, by the next generated migration — while every SELECT in the system depended on it.

**Enforced in the reference:** `tests/test_migrations.py`

### `dialect-discipline`

**Rule:** Time columns are stored in UTC at full precision (migrations included) · string columns declare a length · written once, runs on every database brand the project targets

**Born from:** MySQL's DATETIME truncates sub-second precision silently — records created milliseconds apart get the same timestamp and then sort in the wrong order · findable only by firing the suite at a real brand.

**Enforced in the reference:** `tests/test_dialect_parity.py` · `tests/test_db_backend.py` · `tests/test_migration_lint.py`

### `fail-fix-harness-honest`

**Rule:** The developer harness reports the truth, never passes silently, and does not keep a second copy of CI's commands

**Born from:** A harness that reports success while tests are red feeds false confidence to the loop that trusts it completely — and the first attempt to prove 11-03 repeated the lesson: a planted defect that landed inside a docstring produced "passes when it should be red" without the gate being blind at all · audit round 6 added a layer (ADR 0060): a preflight that *copies* CI's commands into itself will drift, and then say "pass" at the exact moment CI is about to say otherwise.

**Enforced in the reference:** `tests/test_vendored_tooling.py`

### `csrf-guards-every-form`

**Rule:** CSRF protects the whole app and is decided before login, always

**Born from:** Ordinary tests switch CSRF off for convenience — without a separate suite that turns it on for real, the day `csrf.init_app()` goes missing nothing would catch it.

**Enforced in the reference:** `tests/test_csrf.py`

### `session-hardening`

**Rule:** Idle and absolute timeouts are checked server-side · the cookie is bound to the current credential

**Born from:** ADR 0020 — an expiry stamped on a cookie is something the client can edit · change the password and every cookie issued earlier must die at once, not wait to expire.

**Enforced in the reference:** `tests/test_session_security.py`

### `login-rate-limited-two-ways`

**Rule:** Login quotas apply per IP and per username · once throttled the answer is 429 even for the right password

**Born from:** ADR 0021 — the per-IP dimension alone loses to anyone rotating addresses · and if a correct password sails through the gate, whoever is guessing learns immediately that they found it.

**Enforced in the reference:** `tests/test_ratelimit.py` · `tests/test_api_ratelimit.py`

### `route-authz-enumerated`

**Rule:** Every route is enumerated against the exception list in both directions — a forgotten decorator goes red

**Born from:** Governance audit round 5 (2026-08-17) — the project's first rule was "every route carries login_required" with an exception list annotated "these are all of them", but nothing checked that list and it was not in fact complete (the route serving enhancement files had been public since Phase 4 without being counted) · the old authz test covered the routes its author thought of, not every route that exists — OWASP A01 by omission.

**Enforced in the reference:** `tests/test_route_authz.py`

### `authz-in-service-layer`

**Rule:** Authorisation is decided in the service layer, not at the route · someone else's row answers 404, an insufficient role answers 403

**Born from:** ADR 0004/0022 — there are three adapters (HTML, API, CLI), and a gate that lives at the route is a gate the next adapter can forget · hiding a menu item is not access control.

**Enforced in the reference:** `tests/test_rbac.py`

### `password-policy-nist`

**Rule:** The NIST-aligned password policy lives in one place, called by both the CLI and the web

**Born from:** ADR 0019 — NFKC normalisation has to sit in set and check together; the day it happens on only one side, anyone whose password is in Thai (the sara am vowel) can no longer log in although they typed exactly what they always typed.

**Enforced in the reference:** `tests/test_passwords.py`

### `logs-carry-no-pii`

**Rule:** Logs are JSON, carry a request id, and record the actor as a username rather than a real name

**Born from:** ADR 0011 — the path appears on every log line, a class C6 record kept 90 days — so what must never appear in a log needs a test that catches it, not care.

**Enforced in the reference:** `tests/test_logging.py`

### `csp-no-inline`

**Rule:** CSP is pure self — no inline script, style, or handler anywhere

**Born from:** ADR 0010 — the browser blocks inline content silently with no server-side error, so the gate has to read the template files directly rather than wait for symptoms.

**Enforced in the reference:** `tests/test_security_headers.py`

**Reads:** .html, .htm, .jinja, .jinja2 and .j2 templates under app/templates (scaffold.json templates_path)

### `config-fails-loud`

**Rule:** A missing SECRET_KEY or an unknown scheme means the app does not start — never a silent fallback

**Born from:** ADR 0026/0030 — production that is misconfigured yet "works" on SQLite fails on the day somebody asks for the data that was never there · failing loudly at start-up is always cheaper.

**Enforced in the reference:** `tests/test_config.py` · `tests/test_secrets.py`

### `no-debug-entrypoint`

**Rule:** No entrypoint file can open a debug console, even when the wrong one is run

**Born from:** The first SAST round pointed at an entrypoint that could enable debug and was being copied into the image — run the wrong one and you have a debug console that executes code from a web page.

**Enforced in the reference:** `tests/test_entrypoint.py`

**Reads:** the Python entrypoints run.py, wsgi.py, app.py and main.py (scaffold.json entrypoints), as an AST

### `api-contract-snapshot`

**Rule:** openapi.json is a photograph of the code — change the API and it must be regenerated

**Born from:** ADR 0018 — a contract nobody compares against the code is a contract that can change silently · v1 is frozen, so something has to complain when anyone alters it.

**Enforced in the reference:** `tests/test_openapi.py`

### `api-fuzzed-from-spec`

**Rule:** The fuzzer builds requests from the spec itself — new endpoints are covered automatically

**Born from:** The first round caught three things the hand-written tests had missed (an id past 64 bits returning 500, an unparseable date returning 500, and requests rejected at the routing layer returning HTML).

**Enforced in the reference:** `tests/test_api_fuzz.py`

### `fk-enforced-measured`

**Rule:** Foreign keys are genuinely enforced — measured by the outcome (IntegrityError), not by reading a pragma

**Born from:** SQLite disables foreign keys by default, per connection — remove the line that loads the backend and there is no error at all, just data going quietly wrong · a gate that reads the pragma stays green in exactly that state.

**Enforced in the reference:** `tests/test_db_integrity.py`

### `a11y-structural`

**Rule:** WCAG structure is checked on every test run (labels present, fallback buttons, target size)

**Born from:** ADR 0012 — a form that relies on data-auto-submit alone is unusable when JS does not run, and nobody notices until they are the person with JS switched off.

**Enforced in the reference:** `tests/test_a11y.py`

### `i18n-catalog-integrity`

**Rule:** The catalogue has no empty or fuzzy entries and covers every msgid present in the code

**Born from:** The whole SSO/LDAP message set had never been extracted into the catalogue — Thai-speaking users saw English throughout and nothing said so (P7-03b) · and pybabel once guessed "First name" as the Thai for "task name".

**Enforced in the reference:** `tests/test_i18n.py`

### `asvs-evidence-real`

**Rule:** Every piece of evidence in ASVS.md points at something that exists · the standard is pinned by checksum

**Born from:** A standard that shifts underfoot makes yesterday's "pass" not today's, without any commit saying so · evidence nobody checks the existence of is the first thing to go stale.

**Enforced in the reference:** `tests/test_asvs.py`

### `declared-prohibitions-enforced`

**Rule:** A prohibition a machine can check has a machine checking it — and the gate must quote a rule that still exists

**Born from:** Audit round 14 counted 61 prohibitions in CLAUDE.md · 51 were machine-checkable · 19 were sentences only — and none of those 19 had been violated, which means the rules were being followed by discipline rather than by mechanism: enough for the person who wrote them, not for the next one · the first batch caught something real on its first run: tests/test_metrics_multiproc.py created its own tables with no teardown, which on the dialects job means leaving rows behind for the next test · audit round 15 added three more and put a ratchet on the register (`enforced_prohibitions` in pyproject), because nothing was shrinking the remaining pile and nothing prevented backsliding.

**Enforced in the reference:** `tests/test_declared_prohibitions.py`

### `stack-images-pinned-and-moved`

**Rule:** Stack images are pinned by digest · something moves them · and the mover asks only for digests, not new versions

**Born from:** Audit round 15 — the project had three gates enforcing pinning (action to SHA, base image to digest, CI tools by hash) and none of them opened a compose file · measured: 11 images pulled by tag, running in 11 of 25 jobs on every push · among them ghcr.io/zaproxy/zaproxy:stable, a floating tag that decides a security outcome — so last week's green dast run cannot be reproduced · Dependabot separates docker-compose from docker (which reads only the Dockerfile) and we had declared only the latter, so pinning without a mover would have frozen the vulnerabilities in place; this gate enforces both halves together · audit round 16 added a third: the mover must ignore major and minor bumps — the first batch this ecosystem opened proposed mysql 8 → 26, redis 7 → 8 and vault 1.18 → 2.0 among nine at once · the reasoning for the ignore rules had lived only in a comment, and it was measured that they could be removed with nothing complaining.

**Enforced in the reference:** `tests/test_stack_image_pinning.py`

### `test-databases-must-be-throwaway`

**Rule:** A test suite's target must declare itself disposable — a suite that drops the schema in every fixture must have no way to point at a real database

**Born from:** A review question after audit round 26 — ISO/IEC 27001 `A.8.31`/`A.8.33` had long been declared **passing** on the claim that "the fixture refuses real databases" · checking found that the thing actually refusing was `scripts/a11y_fixture.py`, which **(a)** is a different path from the test suite, **(b)** tests `"instance" in uri` and so catches only the dev SQLite shape, and **(c)** declares its own role as `helper`, defined as "decides nothing and is never cited as evidence" · meanwhile the most dangerous path — `TEST_DATABASE_URL`, which `CLAUDE.md` tells people to set themselves, with every fixture calling `create_all()`/`drop_all()` through it — **had nothing guarding it at all**: one typo in the database name permanently drops every table in it · the criterion is an allowlist ("the database name must say it is for testing") rather than a blocklist, because guessing what a real database looks like is never complete, whereas an allowlist errs toward safety.

**Enforced in the reference:** `tests/test_throwaway_database.py`

### `data-health-is-checkable`

**Rule:** One command answers which rules the data in the database is breaking *right now* — read-only

**Born from:** Audit round 19 — the eighteen preceding rounds examined code, config, documentation, CI, registers, and even the tools that check the tools; all of it lives in git · **the data is the one thing that is not in git and the one thing users see** · a defect was planted at the data layer in a freshly migrated database and measured: an orphaned row passed every command, every healthcheck and every job · the string `foreign_key_check` appeared nowhere in the repo, not once · of 26 CLI commands, exactly one asked the data whether it was still sound, and it checked only the audit chain.

**Enforced in the reference:** `tests/test_data_doctor.py`

### `scripts-declare-their-role`

**Rule:** Every script declares its own kind · someone touches it · and what it generates still works

**Born from:** Audit round 17 — 83 of 105 gates were decided by code in scripts/, yet its coverage was 43.8% and 14 files sat at 0% · among them run_gates.py, deliberately tested through a subprocess, and generators checked by their output — **so coverage was the wrong instrument for half the files** · classifying by kind made it possible to demand the right sort of evidence, and revealed three files touched by no test, no workflow and no hook at all (build_eol_table · build_password_blocklist · measure_generated).

**Enforced in the reference:** `tests/test_script_roles.py` · `tests/test_generated_tables.py`

### `adr-index-complete`

**Rule:** The ADR index covers every record, numbered without repeats or gaps · and supersessions are recorded in both directions

**Born from:** The index once stopped at 0026 while the files ran to 0033 — seven records from the phase that decided the biggest questions, invisible · audit round 14 added the second direction: ADR 0035 had superseded item 1 of 0032 since 2026-08-12, but 0032's own page did not know for seven days, while the module docstring at the head of app/audit.py still pointed at 0032 as the current mechanism, which CLAUDE.md explicitly forbids returning to.

**Enforced in the reference:** `tests/test_adr_index.py`

**Reads:** the .md records and the README.md index under docs/adr (scaffold.json adr_path)

### `cadence-not-overdue`

**Rule:** The periodic-review schedule is genuinely read; more than 7 days overdue is red · and the register of deliberate deferrals keeps up with the ADRs

**Born from:** Periodic work with nothing to chase it is work that quietly stops happening — a due date must be a date or a decidable condition, never "when we're ready".

**Enforced in the reference:** `tests/test_cadence.py`

### `risk-method-and-register-current`

**Rule:** The risk method exists, levels match the formula, the mechanisms behind high rows point at real things, and the full cycle is chased

**Born from:** Closing ISO 27001 backlog items 6.1/8.2 (owner's instruction, 2026-08-16) — risk decisions had been scattered across individual ADRs with no shared method · a level computed by a fixed formula moves the argument to the input scores rather than to the conclusion.

**Enforced in the reference:** `tests/test_risk_assessment.py`

### `backup-restore-drilled-every-push`

**Rule:** The backup → damage → restore drill runs for real on every push, and the drill genuinely detects damage

**Born from:** Closing ISO 27001 backlog items A.5.30/A.8.13 — a restore never rehearsed is a hope, not a plan · so the drill is a test rather than an annual ceremony, and the drill itself is proved in both directions (a restore that lost data must be reported).

**Enforced in the reference:** `tests/test_backup_drill.py`

### `licensing-no-copyleft`

**Rule:** The LICENSE is the real text the ADR declares · the core carries no dependency with a copyleft obligation

**Born from:** That library was LGPLv3 and happened to sit in the group of optional dependencies — separating the supply chain separated the legal obligation too, without anyone designing it that way · "not found" is not the same as "unreadable, therefore not found" · ADR 0070 (2026-08-19) changed the licences to AGPL-3.0 and CC BY-SA 4.0 — so this gate checks the body of the AGPL (including clause 13 on network use, which is the entire reason that licence was chosen) and that LICENSE-docs exists · **the dependency-copyleft half is unchanged**, because that obligation belongs to the downstream user, not to us.

**Enforced in the reference:** `tests/test_licensing.py`

### `security-policy-consistent`

**Rule:** The timeframes quoted in SECURITY.md agree across every copy, and no email address appears in the file

**Born from:** A policy whose numbers disagree in three places is a policy where the reporter can always choose whichever copy suits them.

**Enforced in the reference:** `tests/test_security_policy.py`

### `contributor-docs-truthful`

**Rule:** The numbers advertised in the docs are read from the real source (job count, ADR count, coverage floor, version on the badge answer)

**Born from:** Three documents said "CI: 21 jobs" while the workflow defined 20 — nobody was being untruthful, but nobody was checking · 2026-08-17 repeated it a layer up: the badge answer still said v1.5.0 three days after v1.6.0 shipped, although the runbook had a step for updating it — **a step with no test reading alongside it goes stale exactly like a number with no test reading alongside it**.

**Enforced in the reference:** `tests/test_contributor_docs.py`

### `changelog-tracks-version`

**Rule:** The CHANGELOG is tied to the application's __version__

**Born from:** The declared version and the version the code reports have been free to drift apart, silently, since the first release.

**Enforced in the reference:** `tests/test_changelog.py`

### `actions-sha-pinned`

**Rule:** Every action is pinned to a commit SHA with the version in a comment

**Born from:** Tags move, commits do not — upload-artifact once sat on @v4 at a single call site for ten days with CI green throughout.

**Enforced in the reference:** `tests/test_workflow_pinning.py`

**Reads:** the uses: steps of workflows and composite actions under .github

### `image-digest-pinned`

**Rule:** The base image is pinned to a manifest-index digest and Dependabot moves it

**Born from:** Pinning with nobody to move it freezes the vulnerabilities in place — the two must always arrive together, and the test enforces that the pair is not separated.

**Enforced in the reference:** `tests/test_dockerfile_pinning.py`

**Reads:** the FROM lines of the root Dockerfile (scaffold.json dockerfiles), and .github/dependabot.yml for a docker ecosystem

### `ci-tools-hash-pinned`

**Rule:** Tools CI installs for itself are pinned by hash, on both the Python and the Node side

**Born from:** An unpinned install command takes whatever is newest at the second the job runs, and it runs with our workflow's privileges · pinning one package at a time pins only that package while the rest of the tree still floats.

**Enforced in the reference:** `tests/test_ci_pinning.py`

**Reads:** pip, pipx, npm/npx/yarn/pnpm, uv/uvx/poetry/pdm/pipenv and python -m build lines in workflows, composite actions, the scripts they run, and the root Dockerfile

### `checkers-proven-two-way`

**Rule:** A script that decides pass or fail has tests with a planted violation and with clean input · and its report may not contradict itself

**Born from:** Governance audit round 4 (2026-08-17) — the three deciders of the supply-chain axis (`audit_pins` · `audit_image` · `check_semgrep`) had matching test files, but those tests checked only the index and the wiring · invert a line of set arithmetic and everything stayed green while CI reported "nothing new" forever without deciding anything — the rules we export to others (the overlay's eight checkers) had always been tested in both directions; the deciders we use ourselves must not be held to less · **audit round 27, item 3**: `bestpractices.dev` is the one row in the provider register that answers "no machine check", and the clock is entirely theirs — they can change the criteria while we do nothing and the badge quietly drops a level, with only a 12-month review row to chase it · `audit_posture.py` reads the live JSON answer and compares it with the percentage table in the documentation (setting the gate up immediately found a real staleness: the document said gold 26% while the site answered 57%).

**Enforced in the reference:** `tests/test_checker_logic.py`

### `pins-exceptions-honest`

**Rule:** The advisory exception list is checked in both directions, and every ID has a documented reason

**Born from:** `--ignore-vuln` is silent whenever the ID disappears — an exception list nobody removes entries from becomes a real muzzle on the day that package gets a new advisory.

**Enforced in the reference:** `tests/test_pins_audit.py`

### `semgrep-scope-proven`

**Rule:** semgrep must prove what it scanned — the real file set is compared against git ls-files

**Born from:** semgrep's defaults exclude tests/ — 61 of 136 files had never been scanned, with no line anywhere in the repo saying so · "found nothing" looks exactly like "checked nothing".

**Enforced in the reference:** `tests/test_semgrep_gate.py`

### `dependabot-fits-the-gates`

**Rule:** Dependabot's prefix is a type commit-lint accepts, and pip is constrained by path

**Born from:** A machine's pull requests that are red from the first one teach the maintainer to ignore all of the machine's pull requests — which is worse than not enabling it.

**Enforced in the reference:** `tests/test_dependabot.py`

### `bare-clone-still-green`

**Rule:** A bare clone (with none of the optional extras installed) must be green — "remove it and the system still works" is measurable

**Born from:** ADR 0025 — importorskip is forbidden because it makes the main job skip that test silently when the library is missing, which is precisely the case we most want to be red.

**Enforced in the reference:** job `bare`

### `changed-lines-fully-tested`

**Rule:** Lines a pull request changes must be 100% covered — a whole-file coverage floor cannot answer that question

**Born from:** Governance audit round 6 (2026-08-17) — the gate that went red most often in this repo (5 of the 13 failing runs in the last 200) had no row in the index at all, because the rule "every job has a gate" treated job `test` as covered by the gates of the test files · an already-high repo-wide coverage figure will always hide new lines that nobody tested.

**Enforced in the reference:** job `test` step "diff-cover (บรรทัดที่แก้ต้องมีเทสต์ 100%)"

### `static-quality-battery`

**Rule:** ruff + format + xenon + interrogate + mypy + the ASVS worksheet — ratchets that only move up

**Born from:** Every step carries if !cancelled() because xenon once went red first and hid a mypy failure behind it — the first gate to go red must not mask the ones after it.

**Enforced in the reference:** job `lint`

### `n-minus-one-served`

**Rule:** The code at the latest tag must genuinely serve traffic on HEAD's schema (expand–contract)

**Born from:** A rolling deploy always has a window where two versions run against one schema — a migration that is correct for the new code but kills the old one is downtime nobody announced · a promise with no gate running behind it is a promise waiting to go stale (ADR 0048).

**Enforced in the reference:** job `n-1`

### `schema-drift-zero`

**Rule:** Run the migrations on an empty database and compare with the models — drift must be zero

**Born from:** Tests use create_all from the models and therefore cannot see a migration that has gone wrong — there has to be a gate that runs the real migrations on an empty database.

**Enforced in the reference:** job `schema`

### `openapi-regen-clean`

**Rule:** Regenerate the spec and git diff must be empty

**Born from:** A photograph not compared against the code on every push is a photograph of the past.

**Enforced in the reference:** job `openapi`

### `conventional-commits`

**Rule:** Commits are Conventional Commits of at most 72 characters and carry Signed-off-by (DCO), checked only on what the branch actually adds

**Born from:** A required check that gets skipped on a pull request leaves it BLOCKED forever with nothing red to see — and the merge commit from the Update branch button once failed the gate itself · **ADR 0073 brought the DCO signature into the same gate**: the project had never asked contributors to certify their legal right to what they send, which was the one unmet item of the 19 in OSPS Baseline level 2, and the same reason the badge's silver-level `dco` criterion had been Unmet from the start.

**Enforced in the reference:** job `commit-lint`

### `core-deps-cve-audit`

**Rule:** pip-audit over the core — a CVE in something that cannot be removed must be able to stop the pipeline

**Born from:** The core's supply chain cannot be removed — a CVE here has no way out but a fix, so it can go red without apology, unlike an optional dependency where the answer is to remove it.

**Enforced in the reference:** job `security` step "pip-audit ของ core (ตรึงรุ่น pip ใน venv ก่อน — ตัว pip เองก็ถูก audit)"

### `deploy-deps-cve-audit`

**Rule:** The deploy category is audited — nobody else watches the server that takes real requests

**Born from:** The deploy category is invisible to every tool installed with the dev set — found twice in one day from two different directions · the component handling every real request had nobody watching it.

**Enforced in the reference:** job `security` step "pip-audit ของ deploy (gunicorn ฯลฯ — ไม่มีใครเฝ้าให้ที่อื่น)"

### `ci-tools-cve-audit`

**Rule:** pins/ is audited on both the Python side (pip-audit) and the Node side (npm audit), in both directions

**Born from:** A gate covering one language in a directory that holds two is a gate whose name makes people believe it is covered — more dangerous than no gate at all.

**Enforced in the reference:** job `security` step "audit ของ pins/ (เครื่องมือของ CI เอง — ทั้ง python และ node)"

### `semgrep-sast`

**Rule:** SAST with the framework and language rulesets — decided by the report, not by the exit code

**Born from:** A scan that passes silently looks exactly like a scan that checked nothing — the decider is check_semgrep.py, which compares the set of files actually scanned.

**Enforced in the reference:** job `security` step "semgrep (flask + python rulesets)"

### `good-first-issue-not-taken-silently`

**Rule:** A pull request closing an issue still labelled good first issue must state why

**Born from:** 2026-08-20 — the issue was labelled good first issue at 12:14Z · the maintainer opened their own pull request for the same issue at 16:40Z and merged it at 16:51Z · an outside contributor opened theirs at 17:39Z, having started hours earlier · the label stayed on throughout, with no assignee and no comment — they lost an afternoon to work that was already closed.

**Enforced in the reference:** job `lint` step "issue ที่เปิดให้คนใหม่ ต้องไม่ถูกปิดเงียบ ๆ"

### `a11y-real-browser`

**Rule:** Accessibility is checked in a real browser after the CSS has run, in every theme and every language the application ships

**Born from:** Contrast after the CSS has run, against the names assistive technology actually computes, cannot be checked from template files — it needs a real browser, and dark mode and other languages have different contrast.

**Enforced in the reference:** job `a11y`

### `image-built-and-probed`

**Rule:** The image is really built and then probed — not running as root, code not writable, answers 200

**Born from:** A Dockerfile nobody ever builds is an ordinary text file — and the venv's shebang once failed in a way whose error message untruthfully claimed the file did not exist.

**Enforced in the reference:** job `image`

### `dockerfile-linted`

**Rule:** The Dockerfile passes hadolint at every level including info — exceptions carry reasons in one config

**Born from:** Governance audit 2026-08-16 (ADR 0055) — the code passed SAST on two engines, while the file defining the environment that code runs in was checked by nothing except the fact that it worked · CIS Docker-class misconfiguration is something a machine checks for free.

**Enforced in the reference:** job `lint` step "lint Dockerfile (hadolint — ADR 0055)"

### `image-os-cve-audit`

**Rule:** The image's OS layer is scanned for CVEs and decided against an exception list, in both directions

**Born from:** Governance audit 2026-08-16 (ADR 0054) — the image's SBOM had eight files and nobody scanned the OS layer at all: having an SBOM is not the same as having a reader · a CVE in the glibc or openssl inside the image is something we would learn about only when somebody else told us.

**Enforced in the reference:** job `image` step "ตัดสินผลสแกนเทียบรายการยกเว้น — สองทิศ"

### `image-exceptions-honest`

**Rule:** The image's CVE exception list is checked in both directions, and every ID has a documented reason

**Born from:** The same principle as pins-exceptions-honest — an exception list nobody removes entries from becomes a real muzzle one day, and a scan scope (severity, unfixed) that quietly goes missing is a gate that changed meaning with no commit saying so.

**Enforced in the reference:** `tests/test_image_audit.py`

### `perf-regression-tripwire`

**Rule:** A real journey against a real image on every push — a loose threshold (2× the target) catches step-change regressions

**Born from:** Governance audit 2026-08-16 (ADR 0056) — the charter's second pillar had no per-push latency gate at all; a step-change regression (a new N+1, a lost index) could reach main silently until the next time somebody ran a load test by hand.

**Enforced in the reference:** job `perf-smoke`

### `tls-modern-protocols-only`

**Rule:** Only TLS 1.2 and 1.3 are accepted — proving the server refuses, not that the client refused on its own

**Born from:** openssl 3 already disables TLS 1.0/1.1 on the client side — a gate that does not set SECLEVEL=0 proves only that openssl refuses itself, and passes every time even with ssl_protocols deleted.

**Enforced in the reference:** job `stack` step "รับเฉพาะ TLS 1.2 กับ 1.3"

### `tls-forward-secrecy`

**Rule:** TLS offers forward secrecy on every reachable path — forcing a weak suite must be refused

**Born from:** Ordinary negotiation yields ECDHE and looks perfectly safe, but a client asking for RSA key exchange directly was served too — a gate that looks only at "what gets negotiated" reports a pass while the path without forward secrecy is still open (measured 2026-08-13).

**Enforced in the reference:** job `stack` step "TLS ต้องให้ perfect forward secrecy ทุกทางที่เข้าถึงได้"

### `alerts-fire-for-real`

**Rule:** Alert rules must actually fire when the events they watch for are fired at the stack, not merely exist while the stack comes up

**Born from:** ADR 0037 — a rule counting only 401s falls silent exactly when the attack is heaviest, because the quota cuts in at 5 and the rest become 429 · what must be proved is that the alert fires, not that a rule exists.

**Enforced in the reference:** job `siem`

### `zap-authenticated-scan`

**Rule:** ZAP baseline fires at the real stack while logged in — and the app's own logs measure that it really scanned

**Born from:** Scanning without logging in sees only the login page — such a gate is green forever without checking anything · and on the day the alerts are all fixed, checking the report would turn "found nothing" into "did not scan".

**Enforced in the reference:** job `dast`

### `purge-timer-real-systemd`

**Rule:** The expiry-purge job is installed on a real scheduler and its failures are visible to a person, not only to the exit code

**Born from:** Retention periods become real only when something runs purge on a schedule — and periodic work that goes quiet when it fails is worse than none · `$?` inside an if! branch is always 0 · audit round 10 item 4 added a layer: this gate's idea of "visible" covered only **the exit code the script hands systemd**, while what happens after that is a state somebody has to walk over and ask about — so the unit needs an OnFailure that leaves a machine-searchable line, and the job has to check that it still points somewhere and that the target unit was installed too.

**Enforced in the reference:** job `purge-timer`

### `push-secret-scan`

**Rule:** gitleaks checks the commits in that push (a separate periodic script covers the whole history)

**Born from:** A secret that reaches history cannot truly be deleted on GitHub — old objects are still served by SHA · stopping it on the way in is always cheaper.

**Enforced in the reference:** job `secret-scan`

### `release-signed-and-attested`

**Rule:** A release's SBOM is generated in CI, signed keyless with provenance, and verified in both directions before it is attached

**Born from:** Governance audit 2026-08-16 (ADR 0058) — releases had attached an SBOM since v1.0.0 with no file signed: a downloader could not verify it came from CI at all, and something built outside CI cannot say what it was built from even if signed.

**Enforced in the reference:** job `release-sign`

### `codeql-sast`

**Rule:** CodeQL security-extended for both Python and JavaScript — as a job, not the default setup

**Born from:** Something clicked into place in a UI cannot be reviewed and can disappear silently (the ADR 0037 principle) · the first round found two real things, including a debugger that was shipping inside the image.

**Enforced in the reference:** job `codeql`

### `platform-posture-verified`

**Rule:** The platform-side posture (branch protection · required checks · auto-merge · alerts left standing on the Security tab) is machine-checked, not merely written down

**Born from:** Governance audit round 7 (2026-08-17) — the rules everything else leans on ("main takes changes only through pull requests · enforce_admins on · required checks for every job that runs on a pull request" — ADR 0053) are provider-side settings that **nothing in the repository reads** · switch them off in the settings page and the documentation still claims otherwise · checking the API that day also found `sha_pinning_required` switched off, although we enforce SHA pinning with our own test.

**Enforced in the reference:** job `posture`

### `watched-promises-are-measured`

**Rule:** A declared `within_days` must be measured against reality, not merely checked for shape

**Born from:** Audit round 11 item 2 — ADR 0066 made every non-blocking gate declare within how many days somebody sees it, but the only thing checked was the *shape* (a number, at most 90) · measured over the same 4-day window: redness that blocked somebody stood for 0.4 hours, redness that blocked nobody stood for 14.6 — 36 times longer, with nothing comparing that figure against what was promised.

**Enforced in the reference:** job `posture` step "คำสัญญาของผู้เฝ้าต้องทำได้จริง"

### `schedules-still-fire`

**Rule:** A declared schedule must be provably still firing — "no runs at all" must not look as quiet as "no run went red"

**Born from:** Audit round 10 item 2 — ADR 0064 closed the layer "a workflow that never started = 0 jobs", but the layer above it was still open: **a workflow never triggered = 0 runs**, which looks exactly like "no run went red" in every tool there is · the cron in `scorecard.yml` had fired exactly once in the repository's lifetime, and if it stopped today no test, job or cadence row would know · GitHub also disables schedules for repositories quiet for 60 days, which is silence arriving from outside.

**Enforced in the reference:** job `posture` step "ตารางเวลาที่ประกาศไว้ต้องยังยิงอยู่จริง"

### `watcher-windows-fit-platform-silence`

**Rule:** A watcher's promise must be shorter than the platform's silence window — a watcher that arrives after the machine is switched off is not a watcher

**Born from:** Audit round 26 item 1 — `schedules-still-fire` was built specifically to catch the rule "GitHub disables schedules for public repositories after 60 days of silence", but it was enforced by a job running inside that very cron — **the watcher sat underneath the thing it watched** and died in the same second it had something to report · worse, its promise at the time was 90 days, **longer than the window that creates the failure**: the watcher could arrive at least a month after the thing it watches without breaking a single promise · this rule enforces one thing — among the workflows that only a cron can save, at least one promise must be shorter than that window, because acting once resets the platform's clock for the whole repository at once.

**Enforced in the reference:** `tests/test_watcher_windows.py`

### `instruction-file-under-a-declared-ceiling`

**Rule:** A file people read constantly has a declared ceiling, and the ceiling may not float above reality

**Born from:** A file an agent reads in full every session is unlike every other document — its cost is paid over and over, not when somebody opens it · measured when the rule was set (audit r8): 22 lines on the project's first day, grown to **1,240 lines and 8,488 words in 16 days**, with 66 commits in the last 7 touching it — it grew every time there was governance work, and nobody had ever decided how much it was allowed to grow · the right answer is a two-way ratchet rather than a ban on growth: when it is full, move content out and link back, and **on the day content moves out the ceiling must come down with it**, or the space just freed gets quietly filled again next round.

**Enforced in the reference:** `tests/test_instruction_budget.py`

### `exception-registers-are-reasoned`

**Rule:** A file that silences a gate needs a reason on every line, must actually be used, and may not relax a whole class at once

**Born from:** Audit r9 — `pins/accepted-advisories.txt` had two-way tests from the beginning, but the other two files doing the same job (silencing what a security tool reports) **were read by no test at all**, although the documentation declared for both that every line needs a reason · the risk is not the lines that exist today, all of which have reasons, but the next line somebody adds in a hurry with nothing to complain — and relaxing a whole class by editing one word (FAIL → WARN), which appears in no report anywhere.

**Enforced in the reference:** `tests/test_exception_registers.py`

### `ratchets-do-not-drift-below-reality`

**Rule:** A ratchet's floor stays against reality in both directions · and what is removed has to be signed for

**Born from:** Audit round 12 — `pyproject.toml` was annotated "moves up only" in both places, but nothing was moving it · six days after the number was set, real coverage had climbed to 97.11% while the floor was still 96 (set when it measured 96.31%) — that 1.11 points of slack was roughly 54 covered lines that could vanish with nothing going red · the right mechanism already existed in this project (`LINE_SLACK` from ADR 0065), it had simply never been applied to any other ratchet · audit round 14 added mypy's strict list — a ratchet written as a sentence survived the first chaser, because that chaser read only numeric floors in tool config · reality covered 34 of 72 modules while the annotated target had expired sixteen phases earlier · audit round 16 added the pile guarding against *removal* (ADR 0069): measured by really deleting things 11 times, and found that a gate could be removed with CI fully green if you tidied 6 places, and that 37 rows across three paper registers could be deleted in complete silence, because deleting both sides at once still counts as "matching".

**Enforced in the reference:** job `test` step "พื้นของ ratchet ต้องไม่ลอยต่ำกว่าของจริง"

### `jobs-declare-a-time-budget`

**Rule:** Every job, and every command our own tools fire outward, declares a time budget — "hung" and "slow" must be distinguishable

**Born from:** Audit round 11 — not one job set `timeout-minutes` (0 of 28), so the ceiling was GitHub's default of 6 hours, which is not a ceiling anybody chose · the price is paid in decisions, not machine time: a job that has genuinely hung and a job merely slower than usual give identical signals · it happened for real the same day — `dialect (mysql-8)` was cancelled while running at 92% because the reviewer could not tell the two apart · later in the same round it was extended to all 11 `subprocess.run` call sites in the checkers, none of which had `timeout=` — one unanswering command eats the job's whole budget and then reports "job timed out", which points at the wrong place.

**Enforced in the reference:** `tests/test_job_timeouts.py`

### `workflows-are-startable`

**Rule:** Every workflow must genuinely start — scope, triggers and jobs are what GitHub accepts

**Born from:** Audit r9 — the pinning checkers were all present, but none checked whether the platform would agree to start the file · a YAML parser accepts any key that is syntactically well spelled, while GitHub rejects keys outside its schema and **fails the whole run before creating a single job** · it happened and lasted more than a day: a `permissions:` block asking for a scope that does not exist made the entire workflow fail on every run, and the jobs inside it **never ran once** · it stayed quiet because that job was not a required check, so no pull request ever showed red — **a gate that does not run behaves exactly like a gate that does not exist, except that documentation says it is there**.

**Enforced in the reference:** `tests/test_workflow_validity.py`
