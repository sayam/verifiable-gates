"""Render a rule sheet from a registry — the rules are data, the prose is an input.

A hand-written rule sheet is a third register, and it drifts from `gates.yaml` the
moment somebody edits one side. So the whole body is **generated**: the rule is a
gate's `title`, the lesson is its `born_from`, and what enforces it is its
`enforced_by` — every field already held to reality by the registry's own checks.

**Two things are inputs rather than constants**, and both were constants in the
reference implementation:

- **the registry**, so one renderer serves any project's rules;
- **the preamble**, because the opening of a rule sheet is prose a project writes
  about itself — which framework its enforcers live in, which decisions it made,
  what the layers mean there. Baking one project's paragraphs into the tool would
  make every other project ship that project's story.

Rendering is a pure function of those two, so the same inputs produce the same
bytes and a project can hold its committed file against a fresh render.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from typing import Any

from verifiable_gates import registry

__all__ = ["main", "portable_gates", "render"]

EXPECTED_LABELS = 3


def portable_gates(gates: list[dict[str, Any]], layer: str | None = None) -> list[dict[str, Any]]:
    """The exportable gates, optionally of one layer, in the order the file lists them.

    Order comes from the file rather than from sorting, because a registry is
    written to be read: the neighbours of a rule are part of what it means.
    """
    return [
        gate
        for gate in gates
        if gate.get("portable") and (layer is None or gate.get("layer") == layer)
    ]


def _enforcement(gate: dict[str, Any]) -> str:
    """Point at what actually enforces the rule, rather than restating the command."""
    enforced = gate["enforced_by"]
    if gate["kind"] == "test":
        return " · ".join(f"`{name}`" for name in enforced["tests"])
    if gate["kind"] == "step":
        return f'job `{enforced["job"]}` step "{enforced["step"]}"'
    return f"job `{enforced['job']}`"


def render(
    gates: list[dict[str, Any]],
    preamble: str,
    layer: str | None = None,
    labels: tuple[str, str, str] = ("Rule", "Born from", "Enforced in the reference"),
) -> str:
    """Assemble one sheet. Byte-identical for the same inputs, every time.

    `labels` exists because the reference implementation writes its sheets in
    Thai. A renderer that hard-coded English headings would force every project
    into one language, which is the same mistake as hard-coding the preamble.
    """
    rule, born_from, enforced = labels
    lines = [preamble]
    for gate in portable_gates(gates, layer):
        born = re.sub(r"\s+", " ", str(gate.get("born_from", ""))).strip()
        lines.append(f"### `{gate['id']}`\n")
        lines.append(f"**{rule}:** {gate['title']}\n")
        lines.append(f"**{born_from}:** {born}\n")
        lines.append(f"**{enforced}:** {_enforcement(gate)}\n")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a rule sheet from a gate registry.")
    parser.add_argument("--registry", default="gates.yaml", help="the registry to read")
    parser.add_argument(
        "--preamble", required=True, help="the file holding this sheet's opening prose"
    )
    parser.add_argument("--out", required=True, help="where to write the sheet")
    parser.add_argument("--layer", default=None, help="only gates of this layer")
    parser.add_argument(
        "--labels",
        default=None,
        help="three field headings separated by | (default: English)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if the file on disk differs from a fresh render",
    )
    args = parser.parse_args(argv)

    gates = registry.load(args.registry)
    problems = registry.problems(gates)
    if problems:
        for problem in problems:
            print(f"registry: {problem}", file=sys.stderr)
        return 2

    preamble = pathlib.Path(args.preamble).read_text(encoding="utf-8")
    if args.labels:
        parts = args.labels.split("|")
        if len(parts) != EXPECTED_LABELS:
            print(f"--labels needs {EXPECTED_LABELS} headings separated by |", file=sys.stderr)
            return 2
        fresh = render(gates, preamble, args.layer, (parts[0], parts[1], parts[2]))
    else:
        fresh = render(gates, preamble, args.layer)

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
