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

Role: decider — it answers whether a catalogue is well-formed and its claims
resolvable. Its evidence is a planted defect per rule in `tests/test_rules_catalogue.py`.
"""

from __future__ import annotations

import pathlib
import re
from typing import Any

import yaml

__all__ = [
    "FRAMEWORK_NAMES",
    "KINDS",
    "LAYERS",
    "PILLARS",
    "SCHEMA_VERSION",
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
# Every key a rule may carry. A key outside this set is data nobody reads — a
# misspelt `born_frm` is a rule with no origin that looks like one with, and
# `portable: true` on a rule is a gate's field: a rule in this catalogue is
# published whole, portability is decided per gate in a registry. An outside
# audit on 2026-08-30 wrote both and the schema said nothing.
KEYS = frozenset(
    {
        "id",
        "layer",
        "pillar",
        "title",
        "title_th",
        "born_from",
        "born_from_th",
        "reference",
        "script",
    }
)


def load(path: str | pathlib.Path) -> list[dict[str, Any]]:
    """Read a catalogue file and hand back its rules in the order it lists them.

    Order comes from the file rather than from sorting, because a catalogue is
    written to be read: the neighbours of a rule are part of what it means.
    """
    data = yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path}: a catalogue must be a mapping with 'version' and 'rules'")
    version = data.get("version")
    if version != SCHEMA_VERSION:
        raise ValueError(f"{path}: version {version!r}, this reader speaks {SCHEMA_VERSION}")
    rules = data.get("rules")
    if not isinstance(rules, list):
        raise TypeError(f"{path}: 'rules' must be a list, got {type(rules).__name__}")
    return rules


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
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            found.append(f"rule {index}: must be a mapping")
            continue
        rule_id = str(rule.get("id", f"<rule {index}>"))
        found += _field_problems(rule_id, rule)
        found += _key_problems(rule_id, rule)
        if rule_id in seen:
            found.append(f"{rule_id}: listed more than once")
        seen.add(rule_id)
        if "reference" in rule:
            found += _reference_problems(rule_id, rule["reference"])
        found += _leaks(rule)
        found += _script_problems(rule_id, rule.get("script"), package_dir)
    return found
