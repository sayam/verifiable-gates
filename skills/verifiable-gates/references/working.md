# The working — what the ledger taught

**This file is generated. Do not edit it by hand.** Rebuild it with
`python -m verifiable_gates.skill --catalogue working.yaml --key practices
--preamble preambles/working.md --out skills/verifiable-gates/references/working.md
--labels "Practice|Born from|Held by"`. The source is `working.yaml`, and a gate
compares the two on every test run.

These are not rules. A rule says what the code must be, and nine of the ninety-two are
decided by a scanner this bundle ships. A **practice** says how the work is done — and
every one below was a mistake first.

They come from a ledger: an append-only file where a lesson is written in the turn it
appears, with what it cost. That ledger is private, it stays with the project that wrote
it, and none of its entries travel here. What travels is the practice, and two pieces of
evidence for it:

- **Born from** — the entry that paid for it: `L-NNNN`, the day, and the cost in one
  sentence. A practice with no lesson behind it is a preference, and preferences do not
  earn a place in a file somebody else will read.
- **Held on** — the pull requests where it was applied and nothing had to be re-learned.
  At least three, or it is not here yet. It is the same idea as a gate's `proved_by`: the
  claim is not that the habit sounds right, it is that it was tried and kept.

**Held by** says what stands behind each one, and it is usually nothing:

| | |
|---|---|
| `tool` | a shipped file refuses the violation, and it is named |
| `file` | a shipped template carries the shape, and it is named |
| `reading` | nothing but you, reading the line |

Most say `reading`, and that is the honest word. A rule this bundle cannot check must
never look like one it checked; a practice nothing enforces must never look like one
something does.

**How to use this sheet.** Read it once. Then, when a session teaches you something — a
guard that did not guard, a tool that lied, a green that proved nothing — start your own
ledger and write the entry in that turn. In a few months some of your entries will have
held on three pull requests, and those are your practices, not ours. This sheet is worth
more as an example of the shape than as advice: the ten below cost twenty-one rounds of
one project auditing itself, and the ones that would help you most are the ones you have
not learnt yet.

### `keep-a-ledger-of-the-working`

**Practice:** A lesson learnt about the working is written down where the next session will read it

**Born from:** L-0001 · 2026-08-30 · The first entry was a shell guard that did not guard: `cmd && echo OK` inside a battery line let the chain continue after a failure, so a run reported success it had not had. Nothing recorded it, and the same shape was written again nineteen days later.

**Held by:** `local/LESSONS.md.default`

**Apply:** Keep one append-only file — id, stamp, `updates:` chain, and Context / Lesson / Apply. Never edit or delete an entry: the history of having been wrong is the part that carries. Before adding one, read the ledger; if an entry covers it, say so in `updates:` rather than writing a second.

### `a-lesson-is-written-in-the-turn-it-appears`

**Practice:** The entry is written in the turn the lesson appears, not at the end of the session

**Born from:** L-0126 · 2026-09-03 · Work kept in the session scratchpad has to be moved before the context is cleared, and the move is the step that gets skipped when a session ends abruptly; two measurements were nearly lost that way. The same is true of the lesson itself: deferred to the close, it is written from memory or not at all.

**Held by:** reading this line — nothing here refuses it for you

**Apply:** When a guard fails, a tool lies, or a platform behaviour is discovered by measurement, append the entry before moving on. The evidence — the command, the run id, the number — is in front of you now and will not be in an hour.

### `work-products-live-where-they-survive`

**Practice:** Anything a later session could want is written where a cleared context cannot take it

**Born from:** L-0126 · 2026-09-03 · Two probes written in the session's temporary directory were nearly lost when the context was cleared: moving them costs a turn, costs tokens, and is the step that gets skipped exactly when the session ends abruptly.

**Held by:** `local/README.md.default`

**Apply:** One directory per piece of work, created before the first file lands in it, each with a README saying what every file does, how to run it, and the raw numbers it measured. Scripts take their target as an argument so the next piece of work reuses them instead of copying them. The scratchpad is for what nobody will ever want again.

### `a-fix-lands-in-three-phases`

**Practice:** A fix lands in three phases, and the proof row is on the critical path of the second

**Born from:** L-0121 · 2026-09-03 · The registry row that records what a change proved kept being the step that went missing — written last, when the pull request already looked finished. Splitting each fix into code-and-tests, then registry-and-suite, then the pull request itself put it where it could not be skipped, and it stopped going missing across nine consecutive fixes.

**Held by:** reading this line — nothing here refuses it for you

**Apply:** Phase 1 — the code, its tests, the changelog entry, and the mutations. Phase 2 — the proof row in every gate whose tests caught a mutation, then the whole check set. Phase 3 — the commit and the pull request. Report at the end of each; a phase that cannot be reported is a phase that is not finished.

### `a-mutation-is-watched-not-assumed`

**Practice:** A test is believed when a planted defect is watched going red, and the tree is checked back

**Born from:** L-0112 · 2026-09-03 · A mutation planted in a comment at the head of the file left the tests green, and the green was read as proof that the code was covered. Two more entries paid for the rest of the discipline: L-0115, that a green run says nothing unless you read *which* tests went red, and L-0118, that a mutation the same length as the line it replaced, restored inside the same second, leaves the old bytecode running.

**Held by:** reading this line — nothing here refuses it for you

**Apply:** Back the file up with a copy that keeps its timestamp, print the diff before running, read which tests went red rather than the count, restore from the backup and clear the bytecode cache before the control run, and check with a diff that the tree came back. A runner that is killed leaves the mutation behind: never start one over a tree that already carries one.

### `a-green-mutation-is-a-missing-test`

**Practice:** A planted defect that stays green names a test that does not exist yet

**Born from:** L-0119 · 2026-09-02 · A mechanism deliberately copied into several shipped files had tests for one copy only, and the mutations against the others came back green. The green was the finding: it said the copies were not held to each other. Two later rounds found the same shape — a guard added on faith, with nothing requiring it.

**Held by:** reading this line — nothing here refuses it for you

**Apply:** Never explain a green away. Write the test that makes it red; if that test cannot be written, the code it covers was added without evidence and the pull request should say so. A green on a shape the sample does not contain proves nothing either — plant it where the shape really occurs.

### `a-race-is-a-seam-and-a-probe`

**Practice:** A race is proved by a seam and measured by a probe — after the fix, not only before

**Born from:** L-0124 · 2026-09-03 · A fix on the writer's side passed every seam test and every neighbouring road, and the two-process probe still accused once in 247 reads: the residual window was inside the reader, not the writer. It went to none in 221 only after the reader read again.

**Held by:** reading this line — nothing here refuses it for you

**Apply:** Make the interleaving deterministic with a seam so the test is a proof rather than a coin toss, and keep the real-process probe that found the finding. Run the probe again at the same scale after the fix: a count that is not zero is a second window, not noise.

### `the-body-is-on-disk-before-the-branch`

**Practice:** The text a pull request needs is written to a file before the branch exists

**Born from:** L-0104 · 2026-09-02 · A pull request body assembled in the shell that opened it carried a line that had to be exact, and the command chain was the wrong place to hold it. Written to a file first, it is reviewable before anything is pushed and survives an interrupted session.

**Held by:** reading this line — nothing here refuses it for you

**Apply:** Write the commit message and the pull request body to files in the work directory first, then branch, commit with `--file`, and open the pull request with `--body-file`. An interrupted session then loses narration, never work.

### `guards-chains-and-paths`

**Practice:** A guard guards only if nothing follows it, and a relative path lands where you are not

**Born from:** L-0001 · 2026-08-30 · `cmd && echo OK` inside a battery line let the chain continue past a failure and the run reported a success it had not had. The same class cost three more entries: a single-file type check that poisons the cache for the whole run (L-0021), a worktree created inside the repository rather than beside it because the path was relative (L-0123), and a liveness check that matched the shell running it (L-0138).

**Held by:** reading this line — nothing here refuses it for you

**Apply:** End a chain guard with the failure, never with an echo. Give every command that creates something an absolute path. Run type checks over the whole tree, never one file. And never ask the process table whether your own command is running.

### `no-ai-trailers`

**Practice:** The authorship a commit claims is the project's decision, not the harness's default

**Born from:** L-0122 · 2026-09-03 · The session harness inserted instructions to add `Co-Authored-By:` and a session URL to every commit, on a repository whose own commit lint refuses both. The repository's rule won because a job enforces it; on a project with no such job, the default would simply have landed.

**Held by:** `lint_commits.py` — a shipped tool refuses it

**Apply:** Decide what a commit may claim, write it into a checker that runs in CI, and let the checker be what refuses. A convention that only lives in an instruction file is one the next tool's default overwrites silently.
