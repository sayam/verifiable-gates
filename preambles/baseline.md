# Production discipline — the baseline layer

**This file is generated. Do not edit it by hand.** Rebuild it with
`python -m verifiable_gates.skill --preamble preambles/baseline.md --out SKILL.md
--layer baseline`. The source is `rules.yaml`, and a gate compares the two on every
test run.

Every rule below is **framework-agnostic**. What enforces a rule is not: enforcement
is written in some project's own framework, and each rule's *Enforced in the
reference* line points at how one real project does it. That separation is the whole
design — see the note at the top of `rules.yaml` for why the rule and its enforcement
live in different files.

This is the **baseline** layer: a project that deviates from one of these is
defective, not different. Agreements at the level of *one application* — things a
project may legitimately decide differently, such as whether delete means hide — are
a separate sheet, `SKILL-BUSINESS.md`.

Every rule carries the incident that produced it. That is not decoration. A rule
whose origin nobody recorded is a rule nobody can ever retire, because no one can
tell whether the conditions that created it still hold.

## The practices underneath — how every rule below was made and is kept

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

## The rules

Each entry: **Rule** (universal) · **Born from** (the real trap that produced it, not
a theory) · **Enforced in the reference** (how one project enforces it today).
