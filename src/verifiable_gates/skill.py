"""Render a rule sheet from the catalogue — the rules are data, the prose is an input.

A hand-written rule sheet is a third register, and it drifts from the catalogue the
moment somebody edits one side. So the whole body is **generated**: the rule is a
rule's `title`, the lesson is its `born_from`, and what enforces it in the reference
implementation is its `reference` — every field already held to shape by the
catalogue's own checks.

**Three things are inputs rather than constants**, and all three were constants in
the reference implementation:

- **the catalogue**, so one renderer serves any set of rules;
- **the preamble**, because the opening of a rule sheet is prose a project writes
  about itself — what the layers mean there, which decisions it made. Baking one
  project's paragraphs into the tool would make every other project ship that
  project's story;
- **the language**, because the catalogue carries the published English and the
  original wording side by side. A renderer that could only reach one of them would
  make the other dead weight in the file, and dead weight is what stops being
  maintained.

Rendering is a pure function of those, so the same inputs produce the same bytes and
a project can hold its committed file against a fresh render.

Role: generator — the evidence is that the committed sheet equals the render,
held on every run by `tests/test_sheets.py`.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from typing import Any

from verifiable_gates import rules as catalogue

__all__ = ["LANGUAGES", "main", "render"]

EXPECTED_LABELS = 3

# Suffix appended to a field name to reach that language. English is the published
# text and carries no suffix; every other language is an addition to it.
LANGUAGES = {"en": "", "th": "_th"}

DEFAULT_LABELS = {
    "en": ("Rule", "Born from", "Enforced in the reference"),
    "th": ("กฎ", "เกิดจาก", "ตัวบังคับใน reference"),
}


def _field(rule: dict[str, Any], name: str, language: str) -> str:
    """One field in one language, whitespace flattened to single spaces."""
    value = rule.get(f"{name}{LANGUAGES[language]}") or rule.get(name, "")
    return re.sub(r"\s+", " ", str(value)).strip()


def _enforcement(rule: dict[str, Any]) -> str:
    """Point at what enforces the rule in the reference, rather than restating a command."""
    reference = rule["reference"]
    if reference["kind"] == "test":
        return " · ".join(f"`{name}`" for name in reference["tests"])
    if reference["kind"] == "step":
        return f'job `{reference["job"]}` step "{reference["step"]}"'
    return f"job `{reference['job']}`"


def render(
    rules: list[dict[str, Any]],
    preamble: str,
    layer: str | None = None,
    language: str = "en",
    labels: tuple[str, str, str] | None = None,
) -> str:
    """Assemble one sheet. Byte-identical for the same inputs, every time."""
    rule_label, born_label, enforced_label = labels or DEFAULT_LABELS[language]
    lines = [preamble]
    for rule in catalogue.by_layer(rules, layer):
        lines.append(f"### `{rule['id']}`\n")
        lines.append(f"**{rule_label}:** {_field(rule, 'title', language)}\n")
        lines.append(f"**{born_label}:** {_field(rule, 'born_from', language)}\n")
        lines.append(f"**{enforced_label}:** {_enforcement(rule)}\n")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a rule sheet from a rule catalogue.")
    parser.add_argument("--catalogue", default="rules.yaml", help="the catalogue to read")
    parser.add_argument(
        "--preamble", required=True, help="the file holding this sheet's opening prose"
    )
    parser.add_argument("--out", required=True, help="where to write the sheet")
    parser.add_argument("--layer", default=None, help="only rules of this layer")
    parser.add_argument(
        "--language",
        default="en",
        choices=sorted(LANGUAGES),
        help="which of the catalogue's languages to render (default: en)",
    )
    parser.add_argument(
        "--labels",
        default=None,
        help="three field headings separated by | (default: this language's headings)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if the file on disk differs from a fresh render",
    )
    args = parser.parse_args(argv)

    rules = catalogue.load(args.catalogue)
    problems = catalogue.problems(rules)
    if problems:
        for problem in problems:
            print(f"catalogue: {problem}", file=sys.stderr)
        return 2

    labels = None
    if args.labels:
        parts = args.labels.split("|")
        if len(parts) != EXPECTED_LABELS:
            print(f"--labels needs {EXPECTED_LABELS} headings separated by |", file=sys.stderr)
            return 2
        labels = (parts[0], parts[1], parts[2])

    preamble = pathlib.Path(args.preamble).read_text(encoding="utf-8")
    fresh = render(rules, preamble, args.layer, args.language, labels)

    out = pathlib.Path(args.out)
    if args.check:
        current = out.read_text(encoding="utf-8") if out.is_file() else None
        if current == fresh:
            print(f"up to date: {out}")
            return 0
        print(f"** {out} differs from a fresh render — regenerate it", file=sys.stderr)
        return 1

    changed = not out.is_file() or out.read_text(encoding="utf-8") != fresh
    out.write_text(fresh, encoding="utf-8")
    print(f"{'rewrote' if changed else 'unchanged'}: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
