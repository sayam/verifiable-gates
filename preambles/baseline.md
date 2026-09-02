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
