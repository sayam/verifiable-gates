# Does exported scaffolding change the code that actually gets written?

The question is not "is the rule sheet well written". It is **"is the resulting
code different when one battery reads all of it"** — a document whose effect
nobody measured is advice, not scaffolding.

> **These reports were thought and written in Thai.** The English here is the
> published text; the originals are kept beside it under
> [`reference/`](reference/), unchanged. **A translation of a record is a
> retelling, and the retelling is not the record** — the same reason the rule
> catalogue keeps each rule's original wording next to its published English.

| file | what it is |
|---|---|
| `spec-notes-app.md` | the brief every agent received **word for word**, and what each arm got in addition |
| `results-2026-08-14.md` | that day's measurement — the numbers, and what the numbers do not say |
| `results-2026-08-14.json` | the raw rows, one per app — a test holds the report's table to this file |
| `reference/*.th.md` | the originals, in the language they were thought in |

## Method

- **Three arms, one thing different at a time**: (1) the bare brief · (2) the
  brief plus "review your own work once" · (3) the brief plus the rule sheet, the
  installed checkers, and a loop of the doctor until nothing is found.
  **The second arm exists to separate the effect of *having a second pass* from
  the effect of the rules' content** — a two-arm experiment cannot, and this one
  answers that roughly three quarters of the gap belongs to the second pass.
- **What is held constant**: the model · the wording of the brief · the battery ·
  and that every agent is a fresh session that has never seen this repository
  (reading anything but the rule sheet would measure copying rather than
  following).
- **N = 5 per arm, 15 apps** — a language model does not answer the same way
  twice, so a single number is not evidence. **There is no statistical treatment
  at all**: what can be read from this is consistency inside an arm, never the
  distance between two means.

## The battery — the same one on every arm

1. **the bundle's own scanners** — the portable rules, as code
2. **an ASVS probe of ten items** — the ones provable from the files themselves
3. **an outside scanner** — an axis **this project did not define**

The runner is `verifiable_gates.measure_apps` (runnable at any time — see its
docstring). The outside scanner's path is passed as an argument, **never through
the environment**: a runner named by an environment variable is one that can
change without appearing in the command. That rule came from the project's own
scanner flagging the earlier shape when the script arrived — a check catching the
person who writes checks is a check that works.

## What makes these numbers believable — and what would stop them being so

- **The instrument is measured first.** A pair of apps is planted, one violating
  every item and one satisfying every item, and **every item has to tell them
  apart**. An item answering the same for both measures nothing.
- **The probe must not be tied to one idiom**, or it measures "written like our
  example?" and leans by construction toward whichever arm read our own rules.
  Fixtures in a second and third idiom hold that open — two real cases were
  caught this way on the first control-arm run.
- **Whatever the installer added comes out before measuring** — the tooling, the
  config, the starting workflow. Counting our own work for one arm is adding to
  the score, not measuring.
- **`na` is not `ok`.** A small app has no container file, no workflow and no
  decision records, so those scanners judged nothing. The report keeps that in
  its own column.
- **The tree measured holds only the project's own code.** The probe's exclusion
  list takes out environments, installed packages and build output, from both the
  instrument and the line counter. This used to be true only by luck — generated
  apps never carry an environment — until the probe was pointed at a real
  repository and **4,171 of the 4,299 files it read turned out to be library
  sources**, flipping three answers on somebody else's evidence. The published
  numbers here are unaffected (the largest app measured has 35 Python files), but
  a test now stands where the luck was.
- **The model and the date are recorded beside the numbers.** Results depend on a
  model and a prompt, both of which change underfoot. The claim is only ever "in
  those conditions".

## What this experiment does **not** answer

- Not whether the resulting apps are *safe* — the probe answers "is there a trace
  of the defence", not "does the defence work". Nothing was run or attacked.
- Not which individual rule had an effect — the sheet was given as a whole.
- Not whether any of it holds for a different model or a different brief.
