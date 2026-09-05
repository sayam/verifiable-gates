"""The rule catalogue — what was learned, kept apart from any one project's enforcement.

A **rule** is a lesson with an incident behind it. A **gate** is one project's
enforcement of a rule: a test file, a CI job, a step. They live in different files
because they have different lifetimes. Enforcement moves whenever a project
reorganises its tests, and it is written in that project's framework. The rule
changes only when reality teaches something new.

Keeping them in one file was the reference implementation's arrangement, and it
worked there because there was one project. It stops working the moment a second
project adopts a rule: its `enforced_by` would point at files that project does not
have, and a registry whose rows point at nothing is exactly what this bundle exists
to prevent.

So `gates.yaml` in this repository holds the gates *this repository* is held to, and
`rules.yaml` holds the catalogue it publishes to everybody else.

Three invariants are enforced here rather than left to a reader:

- **Every rule names the incident that created it.** A rule with no `born_from` is
  somebody's preference, and preferences do not deserve a gate. This is the field
  that decides, years later, whether a rule can be retired.
- **No layer `internal`.** An internal rule is tied to one project's architecture;
  publishing it as universal is an overclaim (ADR 0042 in the reference
  implementation, where a governance audit measured five rules carrying the wrong
  label). The catalogue cannot express the value, so the mistake cannot be made.
- **No framework library name in the rule or the lesson.** A rule that says
  "Flask-WTF" is a rule that means nothing to a reader on another stack, while still
  claiming to be universal. The `reference` block is exempt on purpose: naming the
  reference implementation's own files is what makes it evidence.

`problems()` returns a list rather than raising, because every caller wants to see
all of them at once instead of the first one and a stop.

**A second catalogue, `working.yaml`, is read by the same loader and held to its own
shape.** A *practice* is a rule whose defect was in the working rather than in the
tree, and it carries the same two kinds of evidence a rule and a gate do, in the same
spirit: `born_from` is the ledger entry that paid for it — `L-NNNN · YYYY-MM-DD · one
sentence` — and `held_on` is the pull requests where it was applied and nothing had to
be re-learned, at least three of them, which is what keeps a good idea out of the file
(`DECISIONS.md` `a-practice-is-promoted-by-held-on`). `held_by` says honestly what stands
behind it — `tool` (a shipped file refuses the violation, and `tool:` names it), `file`
(a shipped template carries the shape, and `file:` names it) or `reading` (nothing but
the agent reading the line) — and a name given must be a file the bundle ships. A
practice is English only and has no pillar: the ledger is written in English by its own
rule, so a Thai column would be a retelling of a record rather than a record, and the
four pillars describe what a rule protects in a product, where a practice protects the
work (`DECISIONS.md` `the-working-is-english-and-has-no-pillar`).

Role: decider — it answers whether a catalogue is well-formed and its claims
resolvable. Its evidence is a planted defect per rule in `tests/test_rules_catalogue.py`.
"""

from __future__ import annotations

import datetime
import pathlib
import re
import sys
from typing import Any

import yaml

from verifiable_gates import registry

__all__ = [
    "FRAMEWORK_NAMES",
    "HELD_BY",
    "HELD_ON_FLOOR",
    "KINDS",
    "LAYERS",
    "PILLARS",
    "SCHEMA_VERSION",
    "WORKING",
    "by_layer",
    "load",
    "problems",
]

SCHEMA_VERSION = 1

KINDS = frozenset({"test", "job", "step"})
LAYERS = frozenset({"baseline", "business"})
PILLARS = frozenset({"security", "performance", "manageability", "devx"})

REQUIRED = (
    "id",
    "layer",
    "pillar",
    "title",
    "title_th",
    "born_from",
    "born_from_th",
    "reference",
)

# Library names from one web ecosystem. A universal rule that leans on one of these
# is not universal. Names of *external systems* (redis, mysql, systemd) are absent
# on purpose: those are things any stack talks to, not the stack itself.
FRAMEWORK_NAMES = (
    "flask",
    "werkzeug",
    "jinja",
    "sqlalchemy",
    "alembic",
    "talisman",
    "wtform",
    "marshmallow",
    "smorest",
    "gunicorn",
    "pipenv",
)

RULE_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# The working catalogue. Its layer is not in LAYERS on purpose: LAYERS is what a rule may
# be published as, and the sheet index walks it; a practice is never a rule.
WORKING = "working"
HELD_BY = frozenset({"tool", "file", "reading"})
# The pull requests a practice must have held on before it is written down. Three is the
# owner's number (2026-09-04), re-decided in DECISIONS.md and never here.
HELD_ON_FLOOR = 3
WORKING_REQUIRED = ("id", "layer", "title", "born_from", "held_by", "held_on", "apply")
WORKING_KEYS = frozenset({*WORKING_REQUIRED, "tool", "file", "retracted"})
# `L-0124 · 2026-09-03 · one sentence` — the ledger entry, its stamp, and what it cost.
BORN_FROM_LEDGER = re.compile(r"^L-\d{4} · \d{4}-\d{2}-\d{2} · \S")
HELD_ON_REF = re.compile(r"^(pr|run)/\d+$")
# Every key a rule may carry. A key outside this set is data nobody reads — a
# misspelt `born_frm` is a rule with no origin that looks like one with, and
# `portable: true` on a rule is a gate's field: a rule in this catalogue is
# published whole, portability is decided per gate in a registry. An outside
# audit on 2026-08-30 wrote both and the schema said nothing.
# The keys a rule may carry beyond REQUIRED. `script` names the checker that decides
# it; `reads` is what that checker reads, in the checker's own words (a test holds the
# two equal), and travels with `script` or not at all — a rule held by reading reads
# nothing. A key added later is added here, in one place.
OPTIONAL = frozenset({"script", "reads", "retracted", "maps_to"})
KEYS = frozenset({*REQUIRED, *OPTIONAL})
# What a withdrawal says. A rule that turned out to be wrong is **not deleted**: it stays
# in the catalogue carrying the date it was withdrawn, the reason, and — when there is one
# — the rule that replaced it. A deletion leaves a reader who followed the old rule with
# nothing to read; a certificate authority publishes a revocation list rather than
# pretending the certificate was never issued, and for the same reason (`DECISIONS.md`
# `a-withdrawal-is-published-not-deleted`).
# Where a rule sits in a vocabulary somebody else already speaks. An auditor who works
# from OpenSSF Scorecard, SLSA or NIST's SSDF can find a rule from the item they know,
# without learning this catalogue's words first — which is the whole of what `maps_to`
# buys, and the reason it is a closed set rather than free text: a misspelt item is a
# mapping to nothing that reads like a mapping to something.
#
# A mapping says **this rule would satisfy or contribute to that item**, not that the two
# are equal: a rule is often stricter, and an item usually needs more than one rule. The
# three lists below were read from the publications themselves on 2026-09-05 — never from
# memory (`DECISIONS.md` `a-mapping-is-read-from-the-framework-not-from-memory`).
#
# OpenSSF Scorecard's checks, from `ossf/scorecard` `docs/checks.md`.
SCORECARD = frozenset(
    {
        "Binary-Artifacts",
        "Branch-Protection",
        "CI-Tests",
        "CII-Best-Practices",
        "Code-Review",
        "Contributors",
        "Dangerous-Workflow",
        "Dependency-Update-Tool",
        "Fuzzing",
        "License",
        "Maintained",
        "Packaging",
        "Pinned-Dependencies",
        "SAST",
        "SBOM",
        "Security-Policy",
        "Signed-Releases",
        "Token-Permissions",
        "Vulnerabilities",
        "Webhooks",
    }
)
# SLSA v1.0's build track, from `slsa.dev/spec/v1.0/levels`. The levels are cumulative, so
# a rule names the highest one its own words reach.
SLSA = frozenset({"build-L1", "build-L2", "build-L3"})
# NIST SP 800-218 v1.1 (February 2022), the twenty practices. Tasks (`PW.7.1`) are not
# here: a rule maps to a practice, and a task is one project's way of meeting it.
SSDF = frozenset(
    {f"PO.{n}" for n in range(1, 6)}
    | {f"PS.{n}" for n in range(1, 4)}
    | {f"PW.{n}" for n in range(1, 10)}
    | {f"RV.{n}" for n in range(1, 4)}
)
FRAMEWORKS = {"scorecard": SCORECARD, "slsa": SLSA, "ssdf": SSDF}

RETRACTED_REQUIRED = ("date", "reason")
RETRACTED_KEYS = frozenset({*RETRACTED_REQUIRED, "replaced_by"})


def load(path: str | pathlib.Path, key: str = "rules") -> list[dict[str, Any]]:
    """Read a catalogue file and hand back its entries in the order it lists them.

    Order comes from the file rather than from sorting, because a catalogue is
    written to be read: the neighbours of a rule are part of what it means. `key` is
    the list's name in the file — `rules` for the published catalogue, `practices`
    for `working.yaml` — because a file of practices that called them rules would be
    the one place this repository lets a name lie.
    """
    data = yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path}: a catalogue must be a mapping with 'version' and {key!r}")
    version = data.get("version")
    if version != SCHEMA_VERSION:
        raise ValueError(f"{path}: version {version!r}, this reader speaks {SCHEMA_VERSION}")
    rules = data.get(key)
    if not isinstance(rules, list):
        raise TypeError(f"{path}: {key!r} must be a list, got {type(rules).__name__}")
    return rules


def live(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The entries still in force — everything a reader is being asked to follow.

    Every count this repository advertises is of these: "92 rules" has to mean 92 rules
    somebody is held to, or the number grows every time one is withdrawn, which is the
    direction that makes a catalogue look busier the more of it turns out to be wrong.
    """
    return [entry for entry in entries if not entry.get("retracted")]


def retracted(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The entries that were withdrawn, in catalogue order — the list a reader who
    followed one of them needs, and the one a deletion would have taken away."""
    return [entry for entry in entries if entry.get("retracted")]


def by_layer(rules: list[dict[str, Any]], layer: str | None = None) -> list[dict[str, Any]]:
    """The rules of one layer, or all of them, in catalogue order."""
    return [rule for rule in rules if layer is None or rule.get("layer") == layer]


def _reference_problems(rule_id: str, reference: object) -> list[str]:
    """Check the block that says how the reference implementation enforces the rule."""
    if not isinstance(reference, dict):
        return [f"{rule_id}: 'reference' must be a mapping"]
    found = []
    kind = reference.get("kind")
    if kind not in KINDS:
        found.append(f"{rule_id}: reference kind {kind!r} is outside {sorted(KINDS)}")
    if not reference.get("job"):
        found.append(f"{rule_id}: reference names no job")
    if kind == "test" and not reference.get("tests"):
        found.append(f"{rule_id}: a test reference names no test file")
    if kind == "step" and not reference.get("step"):
        found.append(f"{rule_id}: a step reference names no step")
    return found


def _leaks(rule: dict[str, Any]) -> list[str]:
    """Framework library names in the rule or the lesson — never in `reference`."""
    text = " ".join(
        str(rule.get(field, "")) for field in ("title", "title_th", "born_from", "born_from_th")
    ).lower()
    found = [name for name in FRAMEWORK_NAMES if name in text]
    return [
        f"{rule.get('id')}: {name!r} is a framework library name, so the rule is not universal"
        for name in found
    ]


def _field_problems(rule_id: str, rule: dict[str, Any]) -> list[str]:
    """Required fields, the id's shape, and the two closed vocabularies."""
    found = [f"{rule_id}: missing {field}" for field in REQUIRED if not rule.get(field)]
    if not RULE_ID.match(rule_id):
        found.append(f"{rule_id}: id must be lowercase words joined by hyphens")
    layer = rule.get("layer")
    if layer is not None and layer not in LAYERS:
        found.append(
            f"{rule_id}: layer {layer!r} is outside {sorted(LAYERS)}"
            " — an internal rule is tied to one architecture and is never published"
        )
    pillar = rule.get("pillar")
    if pillar is not None and pillar not in PILLARS:
        found.append(f"{rule_id}: pillar {pillar!r} is outside {sorted(PILLARS)}")
    return found


def _key_problems(rule_id: str, rule: dict[str, Any]) -> list[str]:
    """A key the schema does not know is refused, not skipped."""
    found: list[str] = []
    for key in sorted(set(rule) - KEYS):
        if key == "portable":
            found.append(
                f"{rule_id}: portable is a gate's field, not a rule's — a rule here is "
                "published whole; a registry says which of its gates are portable"
            )
        else:
            found.append(f"{rule_id}: {key!r} is not a field of a rule — nothing reads it")
    return found


def _maps_to_problems(rule_id: str, maps_to: object) -> list[str]:
    """Where the rule sits in somebody else's vocabulary — held to that vocabulary.

    Free text here would be worse than nothing: an auditor searching for
    `Pinned-Dependencies` and finding `pinned-deps` learns that this catalogue does not
    map to Scorecard, which is false. So the framework and the item are both closed, and
    the list is sorted and without repeats — a register a reviewer reads in one glance.
    """
    if maps_to is None:
        return []
    if not isinstance(maps_to, list) or not all(isinstance(item, str) for item in maps_to):
        return [f"{rule_id}: maps_to must be a list of `framework:item` strings"]
    found: list[str] = []
    for item in maps_to:
        framework, _, name = item.partition(":")
        if framework not in FRAMEWORKS:
            found.append(
                f"{rule_id}: maps_to {item!r} names no framework this catalogue knows"
                f" — one of {sorted(FRAMEWORKS)}"
            )
        elif name not in FRAMEWORKS[framework]:
            found.append(
                f"{rule_id}: maps_to {item!r} is not an item of {framework} —"
                " read it off the publication, not off memory"
            )
    if len(set(maps_to)) != len(maps_to):
        found.append(f"{rule_id}: maps_to repeats an item")
    if maps_to != sorted(maps_to):
        found.append(f"{rule_id}: maps_to is not in order — sorted, so a reader sees a set")
    return found


def _retracted_problems(
    rule_id: str, entry: dict[str, Any], known: frozenset[str] | None = None
) -> list[str]:
    """A withdrawal is dated evidence like any other, and it has to *stop* something.

    Three refusals, each a way a withdrawal could be decoration. A date that is not a
    date, or is in the future, is the same hole `proved_by` closed on the gate side. A
    `replaced_by` naming a rule that is not in the catalogue — or naming one that was
    itself withdrawn — sends the reader who followed the old rule nowhere, which is the
    one thing publishing the withdrawal instead of deleting it was for. And a withdrawn
    rule may not keep a `script`: a checker that goes on deciding a rule nobody is held
    to is enforcement without a rule, so the pull request that withdraws it takes the
    checker out too.
    """
    record = entry.get("retracted")
    if record is None:
        return []
    if not isinstance(record, dict):
        return [f"{rule_id}: 'retracted' must be a mapping — date, reason, replaced_by"]
    found = [
        f"{rule_id}: retracted is missing {field}"
        for field in RETRACTED_REQUIRED
        if not record.get(field)
    ]
    found += [
        f"{rule_id}: retracted has no field {key!r} — nothing reads it"
        for key in sorted(set(record) - RETRACTED_KEYS)
    ]
    found += _retracted_date_problems(rule_id, record.get("date"))
    replaced_by = record.get("replaced_by")
    if replaced_by is not None and known is not None and replaced_by not in known:
        found.append(
            f"{rule_id}: retracted replaced_by {replaced_by!r} is not a rule in force here"
            " — a withdrawal that points nowhere is a deletion with extra words"
        )
    if replaced_by == rule_id:
        found.append(f"{rule_id}: retracted replaced_by names itself")
    if entry.get("script"):
        found.append(
            f"{rule_id}: a withdrawn rule keeps `script:` — a checker that goes on deciding"
            " a rule nobody is held to is enforcement with no rule behind it"
        )
    return found


def _retracted_date_problems(rule_id: str, value: object) -> list[str]:
    """The date it was withdrawn: a real one, and not one that has not happened yet."""
    if value is None:
        return []
    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        date = value
    else:
        try:
            date = datetime.date.fromisoformat(str(value))
        except ValueError:
            return [f"{rule_id}: retracted date must be a real YYYY-MM-DD date, got {value!r}"]
    if date > registry.latest_today():
        return [f"{rule_id}: retracted date {date} has not happened yet, anywhere on Earth"]
    return []


def _script_problems(
    rule_id: str, script: object, package_dir: str | pathlib.Path | None
) -> list[str]:
    """A rule may claim a checker only if the bundle actually carries it."""
    if script is None:
        return []
    if not isinstance(script, str) or script.startswith("/") or ".." in script:
        return [f"{rule_id}: script {script!r} must be a path inside the bundle"]
    if package_dir is not None and not (pathlib.Path(package_dir) / script).is_file():
        return [f"{rule_id}: script {script!r} is not shipped by this bundle"]
    return []


def _reads_problems(rule_id: str, rule: dict[str, Any]) -> list[str]:
    """`reads` says what the scanner reads and goes with `script`: a scripted rule without
    it leaves a reader guessing which stacks it can ever apply to (self-audit round 22,
    2026-09-04), and a reading-held rule with it claims a tool that is not there."""
    reads, script = rule.get("reads"), rule.get("script")
    if script and not (isinstance(reads, str) and reads.strip()):
        return [f"{rule_id}: a rule with a script says what it reads — `reads` is missing"]
    if reads and not script:
        return [f"{rule_id}: `reads` without a script — nothing here reads anything"]
    return []


def _working_problems(
    rule_id: str, entry: dict[str, Any], package_dir: str | pathlib.Path | None
) -> list[str]:
    """A practice: the ledger entry behind it, what holds it, and where it held.

    Each refusal here is a way the file could grow by a good idea instead of a habit that
    held, which is the failure the working catalogue exists to refuse.
    """
    found = [f"{rule_id}: missing {field}" for field in WORKING_REQUIRED if not entry.get(field)]
    found += [
        f"{rule_id}: {key!r} is not a field of a practice — nothing reads it"
        for key in sorted(set(entry) - WORKING_KEYS)
    ]
    if not RULE_ID.match(rule_id):
        found.append(f"{rule_id}: id must be lowercase words joined by hyphens")
    born = " ".join(str(entry.get("born_from", "")).split())
    if born and not BORN_FROM_LEDGER.match(born):
        found.append(
            f"{rule_id}: born_from must be a ledger entry — `L-NNNN · YYYY-MM-DD · sentence` —"
            " a practice with no lesson behind it is a preference"
        )
    held_by = entry.get("held_by")
    if held_by is not None and held_by not in HELD_BY:
        found.append(f"{rule_id}: held_by {held_by!r} is outside {sorted(HELD_BY)}")
    found += _named_holder_problems(rule_id, entry, held_by, package_dir)
    found += _held_on_problems(rule_id, entry.get("held_on"))
    return found


def _named_holder_problems(
    rule_id: str, entry: dict[str, Any], held_by: object, package_dir: str | pathlib.Path | None
) -> list[str]:
    """`tool` and `file` name what holds them, and the name is a file the bundle ships."""
    found: list[str] = []
    for kind in ("tool", "file"):
        named = entry.get(kind)
        if held_by == kind and not named:
            found.append(f"{rule_id}: held_by {kind!r} must say which — add `{kind}:`")
        if named is not None and held_by != kind:
            found.append(f"{rule_id}: `{kind}:` is given but held_by is {held_by!r}")
        if isinstance(named, str) and (named.startswith("/") or ".." in named):
            found.append(f"{rule_id}: {kind} {named!r} must be a path inside the bundle")
        elif (
            isinstance(named, str)
            and package_dir is not None
            and not (pathlib.Path(package_dir) / named).is_file()
        ):
            found.append(f"{rule_id}: {kind} {named!r} is not shipped by this bundle")
    return found


def _held_on_problems(rule_id: str, held_on: object) -> list[str]:
    """At least HELD_ON_FLOOR pull requests, each a ref somebody can look up."""
    if held_on is None:
        return []
    if not isinstance(held_on, list):
        return [f"{rule_id}: held_on must be a list of refs, got {type(held_on).__name__}"]
    found = [
        f"{rule_id}: held_on ref {ref!r} is not `pr/N` or `run/N` — a ref nobody can look up"
        " is not evidence"
        for ref in held_on
        if not (isinstance(ref, str) and HELD_ON_REF.match(ref))
    ]
    if len(held_on) < HELD_ON_FLOOR:
        found.append(
            f"{rule_id}: held_on lists {len(held_on)} — a practice needs at least"
            f" {HELD_ON_FLOOR} pull requests it held on before it is written down"
        )
    return found


def problems(
    rules: list[dict[str, Any]], package_dir: str | pathlib.Path | None = None
) -> list[str]:
    """Everything wrong with a catalogue, as a list of sentences.

    `package_dir` is where a rule's `script` is resolved from. Pass it and a rule
    claiming a checker that is not shipped becomes an error; leave it out and the
    path is only checked for shape. A rule that promises a script this bundle does
    not carry is a rule that reports "pending" forever while looking answered.
    """
    found: list[str] = []
    seen: set[str] = set()
    # A withdrawal may only point at a rule still in force, so the ids in force are read
    # first: a `replaced_by` naming a rule further down the file is as good as one above it.
    in_force = frozenset(
        str(rule["id"])
        for rule in rules
        if isinstance(rule, dict) and rule.get("id") and not rule.get("retracted")
    )
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            found.append(f"rule {index}: must be a mapping")
            continue
        rule_id = str(rule.get("id", f"<rule {index}>"))
        found += _retracted_problems(rule_id, rule, in_force)
        if rule.get("layer") == WORKING:
            found += _working_problems(rule_id, rule, package_dir)
            if rule_id in seen:
                found.append(f"{rule_id}: listed more than once")
            seen.add(rule_id)
            continue
        found += _field_problems(rule_id, rule)
        found += _key_problems(rule_id, rule)
        if rule_id in seen:
            found.append(f"{rule_id}: listed more than once")
        seen.add(rule_id)
        if "reference" in rule:
            found += _reference_problems(rule_id, rule["reference"])
        found += _leaks(rule)
        found += _script_problems(rule_id, rule.get("script"), package_dir)
        found += _reads_problems(rule_id, rule)
        found += _maps_to_problems(rule_id, rule.get("maps_to"))
    return found


if __name__ == "__main__":
    # A helper is not a command. Run as one, these modules imported cleanly and exited 0
    # with nothing done — a wrong call that looked like a pass, which `gates.yaml` forbids
    # in as many words ("A misuse must exit 2, never 0") and which `gates_doctor` had
    # already decided once, by accepting `--root` as the spelling an operator reaches for
    # (self-audit round 2, owner decision B6, 2026-09-01). `sys.stderr.write` rather than
    # `print`, because a helper may not print and the suppression ceiling only falls.
    sys.stderr.write(
        "verifiable_gates.rules is a helper, not a command — it has no entry point of\\n"
        "its own; the readers that answer for themselves are listed in CONTRIBUTING.\\n"
    )
    sys.exit(2)
