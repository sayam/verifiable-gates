---
name: verifiable-gates
description: Production-discipline rules for a software project — each one carrying the real incident that produced it, nine of them decided mechanically by the bundle's own scanners. Use when writing or reviewing code in a project that has installed the verifiable-gates bundle (a tools/gates_doctor.py exists), when asked which rules bind a repository, or when a change touches a service layer, templates, a Dockerfile, a CI workflow, an ADR index, or a gate registry.
license: CC-BY-4.0
compatibility: The sheets need nothing. The scanners they cite run under a bare python3 (3.11 or later) with no packages, from the bundle that `python -m verifiable_gates.install` writes into a project's tools/ directory.
metadata:
  author: sayam
  source: https://github.com/sayam/verifiable-gates
---

# verifiable-gates — the rules, and how to read them

**This file is generated. Do not edit it by hand.** Rebuild it with
`python -m verifiable_gates.skill --index --preamble preambles/skill.md
--out skills/verifiable-gates/SKILL.md`. The source is `rules.yaml`, and a gate
compares the two on every test run.

## How to use this skill

1. **If the project has installed the bundle** (`tools/gates_doctor.py` exists), run
   `python3 tools/gates_doctor.py --rules` first. It prints the rules a scanner in *that*
   installation decides, read off the installed manifest — those are the ones a red
   build will hold you to, and an upgrade cannot leave you on yesterday's copy.
2. **Read the full entry for the rule you are about to touch**, not the whole sheet:
   [`references/baseline.md`](references/baseline.md) holds the baseline layer, where
   deviating is a defect; [`references/business.md`](references/business.md) holds the
   agreements an application of a given kind may legitimately decide differently. Each
   entry is the rule, the incident that produced it, and how one real project enforces it.
3. **The index below names every rule.** Skim it once to know what exists.
4. **[`references/working.md`](references/working.md) is a different kind of sheet** and
   optional. It is not rules — it is how the work is done: ten practices, each with the
   ledger entry that paid for it and the pull requests it held on. Nothing there is
   decided by a scanner, and `--rules` never prints one. Read it once, then keep your own
   ledger; in a few months your entries will be better for your project than ours are.

Every rule is **framework-agnostic**. What enforces a rule is not: enforcement is
written in some project's own framework, and each entry's *Enforced in the reference*
line points at how one real project does it. That separation is the whole design — the
rule and its enforcement live in different files because they have different lifetimes.

Every rule carries the incident that produced it. That is not decoration. A rule whose
origin nobody recorded is a rule nobody can ever retire, because no one can tell whether
the conditions that created it still hold.

## The practices underneath — how every rule was made and is kept

1. **A new test is not finished until a mutation test has proved it.** Break the
   code it claims to cover, one point at a time; the test must go red; then restore
   the code. Broken code with a green test means the test checks nothing — fix the
   test, do not wave it through.
2. **A gate must be proved in both directions** — red when it should be red, and
   green when it should be green. A gate that passes looks exactly like a gate that
   checks nothing, until somebody measures which one it is.
3. **Thresholds are ratchets that move one way.** Coverage, type-checker strictness,
   the count of unassessed items — none of them may slip back unseen. And when scope
   is genuinely removed, the floor comes down with it in the same change, so the
   space just freed cannot be quietly refilled.
4. **Every significant decision has a record** — including what was deliberately
   *cut*, and the condition that would make the decision expire.
5. **A register is held to reality, not written alongside it.** Anything derivable is
   generated; anything that is a human judgement is cross-checked in both directions,
   so that neither a missing row nor a phantom row can pass.

## The index

One line per rule, grouped by layer, then the practices under their own heading. The link
on each is its full entry.

### baseline — 79 rules · full entries in `references/baseline.md`

- [`gates-registry-total`](references/baseline.md#gates-registry-total) — The gate index matches reality in both directions, and every test file is accounted for
- [`gates-carry-red-evidence`](references/baseline.md#gates-carry-red-evidence) — A new gate arrives with evidence that it went red on a real defect — the list of ones that have not can only shrink
- [`logic-knows-no-http`](references/baseline.md#logic-knows-no-http) — All logic lives in the service layer and knows nothing about HTTP
- [`every-column-classified`](references/baseline.md#every-column-classified) — Every column is assigned a data class in DATA-CLASSIFICATION.md
- [`every-column-export-decided`](references/baseline.md#every-column-export-decided) — Every column of an owned table is decided: exported, or listed as not exported with a reason
- [`models-match-migrations`](references/baseline.md#models-match-migrations) — Schema comes only from migrations, and it matches the models exactly
- [`dialect-discipline`](references/baseline.md#dialect-discipline) — Time columns are stored in UTC at full precision (migrations included) · string columns declare a length · written once, runs on every database brand the project targets
- [`fail-fix-harness-honest`](references/baseline.md#fail-fix-harness-honest) — The developer harness reports the truth, never passes silently, and does not keep a second copy of CI's commands
- [`csrf-guards-every-form`](references/baseline.md#csrf-guards-every-form) — CSRF protects the whole app and is decided before login, always
- [`session-hardening`](references/baseline.md#session-hardening) — Idle and absolute timeouts are checked server-side · the cookie is bound to the current credential
- [`login-rate-limited-two-ways`](references/baseline.md#login-rate-limited-two-ways) — Login quotas apply per IP and per username · once throttled the answer is 429 even for the right password
- [`route-authz-enumerated`](references/baseline.md#route-authz-enumerated) — Every route is enumerated against the exception list in both directions — a forgotten decorator goes red
- [`authz-in-service-layer`](references/baseline.md#authz-in-service-layer) — Authorisation is decided in the service layer, not at the route · someone else's row answers 404, an insufficient role answers 403
- [`password-policy-nist`](references/baseline.md#password-policy-nist) — The NIST-aligned password policy lives in one place, called by both the CLI and the web
- [`logs-carry-no-pii`](references/baseline.md#logs-carry-no-pii) — Logs are JSON, carry a request id, and record the actor as a username rather than a real name
- [`csp-no-inline`](references/baseline.md#csp-no-inline) — CSP is pure self — no inline script, style, or handler anywhere
- [`config-fails-loud`](references/baseline.md#config-fails-loud) — A missing SECRET_KEY or an unknown scheme means the app does not start — never a silent fallback
- [`no-debug-entrypoint`](references/baseline.md#no-debug-entrypoint) — No entrypoint file can open a debug console, even when the wrong one is run
- [`api-contract-snapshot`](references/baseline.md#api-contract-snapshot) — openapi.json is a photograph of the code — change the API and it must be regenerated
- [`api-fuzzed-from-spec`](references/baseline.md#api-fuzzed-from-spec) — The fuzzer builds requests from the spec itself — new endpoints are covered automatically
- [`fk-enforced-measured`](references/baseline.md#fk-enforced-measured) — Foreign keys are genuinely enforced — measured by the outcome (IntegrityError), not by reading a pragma
- [`a11y-structural`](references/baseline.md#a11y-structural) — WCAG structure is checked on every test run (labels present, fallback buttons, target size)
- [`i18n-catalog-integrity`](references/baseline.md#i18n-catalog-integrity) — The catalogue has no empty or fuzzy entries and covers every msgid present in the code
- [`asvs-evidence-real`](references/baseline.md#asvs-evidence-real) — Every piece of evidence in ASVS.md points at something that exists · the standard is pinned by checksum
- [`declared-prohibitions-enforced`](references/baseline.md#declared-prohibitions-enforced) — A prohibition a machine can check has a machine checking it — and the gate must quote a rule that still exists
- [`stack-images-pinned-and-moved`](references/baseline.md#stack-images-pinned-and-moved) — Stack images are pinned by digest · something moves them · and the mover asks only for digests, not new versions
- [`test-databases-must-be-throwaway`](references/baseline.md#test-databases-must-be-throwaway) — A test suite's target must declare itself disposable — a suite that drops the schema in every fixture must have no way to point at a real database
- [`data-health-is-checkable`](references/baseline.md#data-health-is-checkable) — One command answers which rules the data in the database is breaking *right now* — read-only
- [`scripts-declare-their-role`](references/baseline.md#scripts-declare-their-role) — Every script declares its own kind · someone touches it · and what it generates still works
- [`adr-index-complete`](references/baseline.md#adr-index-complete) — The ADR index covers every record, numbered without repeats or gaps · and supersessions are recorded in both directions
- [`cadence-not-overdue`](references/baseline.md#cadence-not-overdue) — The periodic-review schedule is genuinely read; more than 7 days overdue is red · and the register of deliberate deferrals keeps up with the ADRs
- [`risk-method-and-register-current`](references/baseline.md#risk-method-and-register-current) — The risk method exists, levels match the formula, the mechanisms behind high rows point at real things, and the full cycle is chased
- [`backup-restore-drilled-every-push`](references/baseline.md#backup-restore-drilled-every-push) — The backup → damage → restore drill runs for real on every push, and the drill genuinely detects damage
- [`licensing-no-copyleft`](references/baseline.md#licensing-no-copyleft) — The LICENSE is the real text the ADR declares · the core carries no dependency with a copyleft obligation
- [`security-policy-consistent`](references/baseline.md#security-policy-consistent) — The timeframes quoted in SECURITY.md agree across every copy, and no email address appears in the file
- [`contributor-docs-truthful`](references/baseline.md#contributor-docs-truthful) — The numbers advertised in the docs are read from the real source (job count, ADR count, coverage floor, version on the badge answer)
- [`changelog-tracks-version`](references/baseline.md#changelog-tracks-version) — The CHANGELOG is tied to the application's __version__
- [`actions-sha-pinned`](references/baseline.md#actions-sha-pinned) — Every action is pinned to a commit SHA with the version in a comment
- [`image-digest-pinned`](references/baseline.md#image-digest-pinned) — The base image is pinned to a manifest-index digest and Dependabot moves it
- [`ci-tools-hash-pinned`](references/baseline.md#ci-tools-hash-pinned) — Tools CI installs for itself are pinned by hash, on both the Python and the Node side
- [`checkers-proven-two-way`](references/baseline.md#checkers-proven-two-way) — A script that decides pass or fail has tests with a planted violation and with clean input · and its report may not contradict itself
- [`pins-exceptions-honest`](references/baseline.md#pins-exceptions-honest) — The advisory exception list is checked in both directions, and every ID has a documented reason
- [`semgrep-scope-proven`](references/baseline.md#semgrep-scope-proven) — semgrep must prove what it scanned — the real file set is compared against git ls-files
- [`dependabot-fits-the-gates`](references/baseline.md#dependabot-fits-the-gates) — Dependabot's prefix is a type commit-lint accepts, and pip is constrained by path
- [`bare-clone-still-green`](references/baseline.md#bare-clone-still-green) — A bare clone (with none of the optional extras installed) must be green — "remove it and the system still works" is measurable
- [`changed-lines-fully-tested`](references/baseline.md#changed-lines-fully-tested) — Lines a pull request changes must be 100% covered — a whole-file coverage floor cannot answer that question
- [`static-quality-battery`](references/baseline.md#static-quality-battery) — ruff + format + xenon + interrogate + mypy + the ASVS worksheet — ratchets that only move up
- [`n-minus-one-served`](references/baseline.md#n-minus-one-served) — The code at the latest tag must genuinely serve traffic on HEAD's schema (expand–contract)
- [`schema-drift-zero`](references/baseline.md#schema-drift-zero) — Run the migrations on an empty database and compare with the models — drift must be zero
- [`openapi-regen-clean`](references/baseline.md#openapi-regen-clean) — Regenerate the spec and git diff must be empty
- [`conventional-commits`](references/baseline.md#conventional-commits) — Commits are Conventional Commits of at most 72 characters and carry Signed-off-by (DCO), checked only on what the branch actually adds
- [`core-deps-cve-audit`](references/baseline.md#core-deps-cve-audit) — pip-audit over the core — a CVE in something that cannot be removed must be able to stop the pipeline
- [`deploy-deps-cve-audit`](references/baseline.md#deploy-deps-cve-audit) — The deploy category is audited — nobody else watches the server that takes real requests
- [`ci-tools-cve-audit`](references/baseline.md#ci-tools-cve-audit) — pins/ is audited on both the Python side (pip-audit) and the Node side (npm audit), in both directions
- [`semgrep-sast`](references/baseline.md#semgrep-sast) — SAST with the framework and language rulesets — decided by the report, not by the exit code
- [`good-first-issue-not-taken-silently`](references/baseline.md#good-first-issue-not-taken-silently) — A pull request closing an issue still labelled good first issue must state why
- [`a11y-real-browser`](references/baseline.md#a11y-real-browser) — Accessibility is checked in a real browser after the CSS has run, in every theme and every language the application ships
- [`image-built-and-probed`](references/baseline.md#image-built-and-probed) — The image is really built and then probed — not running as root, code not writable, answers 200
- [`dockerfile-linted`](references/baseline.md#dockerfile-linted) — The Dockerfile passes hadolint at every level including info — exceptions carry reasons in one config
- [`image-os-cve-audit`](references/baseline.md#image-os-cve-audit) — The image's OS layer is scanned for CVEs and decided against an exception list, in both directions
- [`image-exceptions-honest`](references/baseline.md#image-exceptions-honest) — The image's CVE exception list is checked in both directions, and every ID has a documented reason
- [`perf-regression-tripwire`](references/baseline.md#perf-regression-tripwire) — A real journey against a real image on every push — a loose threshold (2× the target) catches step-change regressions
- [`tls-modern-protocols-only`](references/baseline.md#tls-modern-protocols-only) — Only TLS 1.2 and 1.3 are accepted — proving the server refuses, not that the client refused on its own
- [`tls-forward-secrecy`](references/baseline.md#tls-forward-secrecy) — TLS offers forward secrecy on every reachable path — forcing a weak suite must be refused
- [`alerts-fire-for-real`](references/baseline.md#alerts-fire-for-real) — Alert rules must actually fire when the events they watch for are fired at the stack, not merely exist while the stack comes up
- [`zap-authenticated-scan`](references/baseline.md#zap-authenticated-scan) — ZAP baseline fires at the real stack while logged in — and the app's own logs measure that it really scanned
- [`purge-timer-real-systemd`](references/baseline.md#purge-timer-real-systemd) — The expiry-purge job is installed on a real scheduler and its failures are visible to a person, not only to the exit code
- [`push-secret-scan`](references/baseline.md#push-secret-scan) — gitleaks checks the commits in that push (a separate periodic script covers the whole history)
- [`release-signed-and-attested`](references/baseline.md#release-signed-and-attested) — A release's SBOM is generated in CI, signed keyless with provenance, and verified in both directions before it is attached
- [`codeql-sast`](references/baseline.md#codeql-sast) — CodeQL security-extended for both Python and JavaScript — as a job, not the default setup
- [`platform-posture-verified`](references/baseline.md#platform-posture-verified) — The platform-side posture (branch protection · required checks · auto-merge · alerts left standing on the Security tab) is machine-checked, not merely written down
- [`watched-promises-are-measured`](references/baseline.md#watched-promises-are-measured) — A declared `within_days` must be measured against reality, not merely checked for shape
- [`schedules-still-fire`](references/baseline.md#schedules-still-fire) — A declared schedule must be provably still firing — "no runs at all" must not look as quiet as "no run went red"
- [`watcher-windows-fit-platform-silence`](references/baseline.md#watcher-windows-fit-platform-silence) — A watcher's promise must be shorter than the platform's silence window — a watcher that arrives after the machine is switched off is not a watcher
- [`instruction-file-under-a-declared-ceiling`](references/baseline.md#instruction-file-under-a-declared-ceiling) — A file people read constantly has a declared ceiling, and the ceiling may not float above reality
- [`exception-registers-are-reasoned`](references/baseline.md#exception-registers-are-reasoned) — A file that silences a gate needs a reason on every line, must actually be used, and may not relax a whole class at once
- [`ratchets-do-not-drift-below-reality`](references/baseline.md#ratchets-do-not-drift-below-reality) — A ratchet's floor stays against reality in both directions · and what is removed has to be signed for
- [`jobs-declare-a-time-budget`](references/baseline.md#jobs-declare-a-time-budget) — Every job, and every command our own tools fire outward, declares a time budget — "hung" and "slow" must be distinguishable
- [`workflows-are-startable`](references/baseline.md#workflows-are-startable) — Every workflow must genuinely start — scope, triggers and jobs are what GitHub accepts

### business — 13 rules · full entries in `references/business.md`

- [`delete-means-soft-delete`](references/business.md#delete-means-soft-delete) — Delete means hide (soft delete) — only purge removes rows for real
- [`every-write-audited`](references/business.md#every-write-audited) — Every write lands in an append-only audit trail with a hash chain
- [`core-never-names-plugins`](references/business.md#core-never-names-plugins) — The core knows only how to find plugins — no plugin name appears in core code
- [`migration-class-declared`](references/business.md#migration-class-declared) — Every plugin declares its migration class (live/warm/cold) as its port's rules require
- [`ropa-current`](references/business.md#ropa-current) — The ROPA, the log inventory and the runbook match the real system
- [`design-doc-matches-the-ui`](references/business.md#design-doc-matches-the-ui) — docs/DESIGN.md matches the real UI — every full page has a declared mode, and the colour variables match base.css in both directions
- [`admin-masking-by-classification`](references/business.md#admin-masking-by-classification) — Admin pages show user data masked according to its data class, and unmasking is audited
- [`admin-panels-read-real-state`](references/business.md#admin-panels-read-real-state) — Admin system panels read live runtime and disk state, answer truthfully, and are for administrators only
- [`secrets-encrypted-at-rest`](references/business.md#secrets-encrypted-at-rest) — Secrets that must be readable again are encrypted on disk, and a missing or wrong key fails loudly with the reason
- [`legal-pdpa-worksheet-honest`](references/business.md#legal-pdpa-worksheet-honest) — The PDPA worksheet cites evidence that exists, and every gap is in the backlog
- [`suite-on-three-brands`](references/business.md#suite-on-three-brands) — The whole test suite passes on MySQL 8 and MariaDB 11 for real, not only on SQLite
- [`plugin-deps-cve-decided`](references/business.md#plugin-deps-cve-decided) — Every CVE in a plugin's libraries must have been decided (upgraded · removed · or accepted with a reason)
- [`sbom-per-category`](references/business.md#sbom-per-category) — SBOMs are split per category — able to answer which components disappear when a plugin is removed

### working — 10 practices · full entries in `references/working.md`

How the work is done, not what the code must be. Each carries the lesson that paid for it and the pull requests it held on; none is decided by a scanner, and `gates_doctor --rules` never prints one.

- [`keep-a-ledger-of-the-working`](references/working.md#keep-a-ledger-of-the-working) — A lesson learnt about the working is written down where the next session will read it
- [`a-lesson-is-written-in-the-turn-it-appears`](references/working.md#a-lesson-is-written-in-the-turn-it-appears) — The entry is written in the turn the lesson appears, not at the end of the session
- [`work-products-live-where-they-survive`](references/working.md#work-products-live-where-they-survive) — Anything a later session could want is written where a cleared context cannot take it
- [`a-fix-lands-in-three-phases`](references/working.md#a-fix-lands-in-three-phases) — A fix lands in three phases, and the proof row is on the critical path of the second
- [`a-mutation-is-watched-not-assumed`](references/working.md#a-mutation-is-watched-not-assumed) — A test is believed when a planted defect is watched going red, and the tree is checked back
- [`a-green-mutation-is-a-missing-test`](references/working.md#a-green-mutation-is-a-missing-test) — A planted defect that stays green names a test that does not exist yet
- [`a-race-is-a-seam-and-a-probe`](references/working.md#a-race-is-a-seam-and-a-probe) — A race is proved by a seam and measured by a probe — after the fix, not only before
- [`the-body-is-on-disk-before-the-branch`](references/working.md#the-body-is-on-disk-before-the-branch) — The text a pull request needs is written to a file before the branch exists
- [`guards-chains-and-paths`](references/working.md#guards-chains-and-paths) — A guard guards only if nothing follows it, and a relative path lands where you are not
- [`no-ai-trailers`](references/working.md#no-ai-trailers) — The authorship a commit claims is the project's decision, not the harness's default
