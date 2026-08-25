# Application-level agreements — the business layer

**This file is generated. Do not edit it by hand.** Rebuild it with
`python -m verifiable_gates.skill --preamble preambles/business.md
--out SKILL-BUSINESS.md --layer business`. The source is `rules.yaml`.

**This sheet builds on `SKILL.md`. Take the baseline first.** The agreements below
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
