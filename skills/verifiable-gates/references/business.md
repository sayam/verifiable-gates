# Application-level agreements — the business layer

**This file is generated. Do not edit it by hand.** Rebuild it with
`python -m verifiable_gates.skill --preamble preambles/business.md
--out skills/verifiable-gates/references/business.md --layer business`. The source is
`rules.yaml`, and a gate compares the two on every test run.

**This is a reference sheet of the `verifiable-gates` skill, and it builds on
[`baseline.md`](baseline.md). Take the baseline first.** The agreements below
are written assuming the underlying practices — mutation testing, gates proved in
both directions, ratchets, recorded decisions — are already in place.

How this differs from the baseline: these are **choices an application of this kind
makes**. Another application may decide differently without being defective — an
application under a legal erasure obligation, for example, has no business using soft
delete. The baseline admits no such latitude; this layer is where it lives.

Measurement in the reference implementation pointed at this layer specifically: asking
a capable model to review its own work recovered most of the *baseline* gaps on its
own, but almost none of these. They are project agreements, and an agreement cannot be
inferred from the code — somebody has to have written it down.

## The rules

Each entry: **Rule** (for this kind of application, still framework-agnostic) ·
**Born from** (the real trap) · **Enforced in the reference** (how one project
enforces it today).

### `delete-means-soft-delete`

**Rule:** Delete means hide (soft delete) — only purge removes rows for real

**Born from:** ADR 0014 — a `--dry-run` implemented as a rollback once deleted real data, because purge committed before the savepoint closed · so there must be exactly one place that can delete.

**Enforced in the reference:** `tests/test_write_discipline.py` · `tests/test_soft_delete.py`

**Reads:** Python modules under app (scaffold.json src_path) — session.delete calls outside the purge_paths

### `every-write-audited`

**Rule:** Every write lands in an append-only audit trail with a hash chain

**Born from:** ADR 0015/0035 — an after-flush event catches every insert, update and delete on its own, so feature code calls nothing, because "forgot to call it" is among the quietest bugs there is.

**Enforced in the reference:** `tests/test_audit.py`

### `core-never-names-plugins`

**Rule:** The core knows only how to find plugins — no plugin name appears in core code

**Born from:** ADR 0023/0025 — the day the core names a plugin is the day removing that directory breaks the system, and the plugin's supply chain is no longer separable from the core's.

**Enforced in the reference:** `tests/test_plugins.py`

### `migration-class-declared`

**Rule:** Every plugin declares its migration class (live/warm/cold) as its port's rules require

**Born from:** "Swappable" that never says *how* it swaps is a promise the person on shift has to guess at three in the morning — the declared class must be enforced at load time and backed by a measurement.

**Enforced in the reference:** `tests/test_migration_class.py`

### `ropa-current`

**Rule:** The ROPA, the log inventory and the runbook match the real system

**Born from:** An application processing personal data has to be able to say what it keeps, where, and for how long — a ROPA that does not match the system is a document that is quietly wrong · raised to the business layer per ADR 0057.

**Enforced in the reference:** `tests/test_ropa.py`

### `design-doc-matches-the-ui`

**Rule:** docs/DESIGN.md matches the real UI — every full page has a declared mode, and the colour variables match base.css in both directions

**Born from:** CR#4 — captions floated centred on several pages because the reading axis of the page as a whole had never been written down, so new pages inherited the browser's defaults · a design document with no gate is a document that goes stale and then misleads the next page.

**Enforced in the reference:** `tests/test_design_doc.py`

### `admin-masking-by-classification`

**Rule:** Admin pages show user data masked according to its data class, and unmasking is audited

**Born from:** ADR 0045 (phase 14-02) — a data class that has no effect on what an administrator sees on screen is a data class on paper · this can become portable once an overlay checker can actually check it in another project.

**Enforced in the reference:** `tests/test_masking.py`

### `admin-panels-read-real-state`

**Rule:** Admin system panels read live runtime and disk state, answer truthfully, and are for administrators only

**Born from:** Phases 14-04/14-06 — the lesson from the documentation reviews: a number not read from the real thing is already wrong, so an admin page showing system state must be compared against the real source, and whatever cannot be read must say so plainly rather than guess.

**Enforced in the reference:** `tests/test_admin_panels.py`

### `secrets-encrypted-at-rest`

**Rule:** Secrets that must be readable again are encrypted on disk, and a missing or wrong key fails loudly with the reason

**Born from:** ADR 0046 (phase 15) — a single database dump used to yield every TOTP secret, because it was the one class C1 value that has to be stored in the clear · decryption must fail loudly when the key is missing or wrong rather than return garbage — and those two messages must point at different remedies.

**Enforced in the reference:** `tests/test_totp_encryption.py`

### `legal-pdpa-worksheet-honest`

**Rule:** The PDPA worksheet cites evidence that exists, and every gap is in the backlog

**Born from:** The pilot for the legal layer (ADR 0042 · phase 13-04) — a document mapping the law whose evidence nobody checks will be used to make a decision on the day something real happens, which is too late to fix it.

**Enforced in the reference:** `tests/test_pdpa.py`

### `suite-on-three-brands`

**Rule:** The whole test suite passes on MySQL 8 and MariaDB 11 for real, not only on SQLite

**Born from:** "Supports several brands" that has never been fired at a real brand is advertising — the audit chain's deadlock is findable only on real InnoDB (ADR 0032/0035).

**Enforced in the reference:** job `dialects`

### `plugin-deps-cve-decided`

**Rule:** Every CVE in a plugin's libraries must have been decided (upgraded · removed · or accepted with a reason)

**Born from:** ADR 0025 — a CVE in something removable always has a faster way out than waiting for a patch, so it should not stop the core's pipeline · **but the second half of that sentence ("it must be loud enough to notice") was not true**: audit round 13 measured that the signal was an annotation on a job that was already green, which nobody reads — so the time to *know* was 90 days while the remediation window for critical is 7 days from the day you know · two of our own policies could not both hold · the fix is not "no CVEs allowed" but "someone must decide", which takes minutes down all three paths.

**Enforced in the reference:** job `plugin-audit`

### `sbom-per-category`

**Rule:** SBOMs are split per category — able to answer which components disappear when a plugin is removed

**Born from:** A single SBOM cannot answer the first question of the day a CVE lands — "if I remove this, what goes with it?"

**Enforced in the reference:** job `sbom`
