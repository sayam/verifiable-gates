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
