"""gate: gates-registry-total — a project's gate index has to match reality, both ways.

Most of the rules in this bundle end the same way: "register it in your project's
gates.yaml". That instruction means nothing unless something holds the register to
reality. This is that something — an index nobody holds to reality is an index
that lies quietly.

Four directions:

- **forward (job)**: every gate points at a job that exists in the workflows
- **forward (step/test)**: `kind: step` names a step that exists; `kind: test`
  names files that exist
- **back (job)**: every job in every workflow has a gate — a new job with none is
  a finding
- **back (tests)**: every test file is claimed by exactly one gate, a partition,
  so anything new and unclaimed has to speak rather than slip past

**The YAML reader is a deliberately narrow subset**: stdlib only, because this
file is shipped into projects that have installed nothing. Anything outside the
subset makes it **raise**, never skip — a reader more forgiving than the real one
reports green on files it did not understand.

exit 0 = clean or N/A · 1 = findings · 2 = called wrongly
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Any

KINDS = {"test", "step", "job"}
GATE_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# A block scalar opener sits at end of line and only after `: ` or `- `.
# (`title: a|` is not one — a looser pattern swallows the following lines.)
BLOCK_SCALAR = re.compile(r"(?:^|(?<=: )|(?<=- ))[|>][-+]?$")


class SubsetError(Exception):
    """The file uses YAML outside the subset this reader accepts — say so, do not guess."""


def _uncomment(line: str) -> str:
    """Strip a trailing comment without touching a `#` inside quotes."""
    quote = None
    for index, char in enumerate(line):
        if quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "#" and (index == 0 or line[index - 1] in " \t"):
            return line[:index]
    return line


def _significant(text: str) -> list[tuple[int, str]]:
    """(column, content) for lines that carry meaning; `- x` becomes two entries.

    The body of a block scalar is discarded — we never use those values — but it
    has to be **skipped correctly**, or the prose inside gets read as structure.
    """
    raw = text.splitlines()
    out: list[tuple[int, str]] = []
    index = 0
    while index < len(raw):
        line = raw[index]
        index += 1
        if "\t" in line:
            message = f"line {index}: contains a tab — YAML indents with spaces only"
            raise SubsetError(message)
        content = _uncomment(line).rstrip()
        if not content.strip():
            continue
        column = len(content) - len(content.lstrip(" "))
        content = content.strip()
        if content.startswith(("---", "...")):
            message = f"line {index}: more than one document in the file — outside the subset"
            raise SubsetError(message)
        if content[0] in "&*!":
            message = f"line {index}: anchor, alias or tag — outside the subset"
            raise SubsetError(message)
        if BLOCK_SCALAR.search(content):
            while index < len(raw) and (
                not raw[index].strip() or len(raw[index]) - len(raw[index].lstrip(" ")) > column
            ):
                index += 1
            content = BLOCK_SCALAR.sub('""', content)
        while content.startswith("- ") or content == "-":
            out.append((column, "-"))
            rest = content[1:].lstrip(" ")
            if not rest:
                break
            column += len(content) - len(rest)
            content = rest
        else:
            out.append((column, content))
    return out


def _flow_value(text: str) -> tuple[object, str]:
    """One value in flow style — returns (value, what is left)."""
    text = text.lstrip()
    if text[:1] in ("[", "{"):
        return _flow(text)
    if text[:1] in ('"', "'"):
        quote = text[0]
        end = text.find(quote, 1)
        if end < 0:
            message = f"unclosed quote: {text!r}"
            raise SubsetError(message)
        return text[1:end], text[end + 1 :]
    end = 0
    while end < len(text):
        char = text[end]
        if char in ",]}" or (char == ":" and text[end + 1 : end + 2] in ("", " ")):
            break
        end += 1
    return text[:end].strip(), text[end:]


def _flow(text: str) -> tuple[object, str]:
    """`[a, b]` or `{k: v}` — the one shorthand the index uses on a single line."""
    closing = "]" if text[0] == "[" else "}"
    rest = text[1:].lstrip()
    items: list[object] = []
    mapping: dict[str, object] = {}
    if rest.startswith(closing):
        return (items if closing == "]" else mapping), rest[1:]
    while True:
        key, rest = _flow_value(rest)
        if closing == "]":
            items.append(key)
        else:
            rest = rest.lstrip()
            if not rest.startswith(":"):
                message = f"flow mapping missing ':' at {rest!r}"
                raise SubsetError(message)
            value, rest = _flow_value(rest[1:])
            mapping[str(key)] = value
        rest = rest.lstrip()
        if rest.startswith(","):
            rest = rest[1:].lstrip()
            continue
        if rest.startswith(closing):
            return (items if closing == "]" else mapping), rest[1:]
        message = f"flow closed wrongly at {rest!r}"
        raise SubsetError(message)


def _scalar(raw: str) -> object:
    raw = raw.strip()
    if raw[:1] in ("[", "{"):
        value, rest = _flow(raw)
        if rest.strip():
            message = f"trailing content after a flow value: {rest!r}"
            raise SubsetError(message)
        return value
    # An anchor, alias or tag in *value* position. The check at the start of the
    # line misses these, and without this they are read as ordinary text: the
    # reader would then be more permissive than YAML, which is the failure this
    # subset exists to avoid.
    if raw[:1] in ("&", "*", "!"):
        message = f"anchor, alias or tag in a value — outside the subset: {raw!r}"
        raise SubsetError(message)
    if raw[:1] in ('"', "'"):
        if len(raw) < 2 or raw[-1] != raw[0]:
            message = f"unclosed quote: {raw!r}"
            raise SubsetError(message)
        return raw[1:-1]
    # An unquoted true/false/null means what YAML says it means. Returning the
    # *string* "false" for `portable: false` would be truthy, so a rule that ever
    # reads a boolean would read it backwards — and read it that way silently.
    # Numbers stay as text on purpose: nothing here compares them numerically,
    # and guessing int from float is a second way to be subtly wrong.
    if raw in ("true", "True"):
        return True
    if raw in ("false", "False"):
        return False
    if raw in ("null", "Null", "~"):
        return None
    return raw


def _split_key(text: str) -> tuple[str, str]:
    quote = None
    depth = 0
    for index, char in enumerate(text):
        if quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        elif char == ":" and depth == 0 and text[index + 1 : index + 2] in ("", " "):
            return str(_scalar(text[:index])), text[index + 1 :].strip()
    message = f"not a key/value pair: {text!r}"
    raise SubsetError(message)


def _is_key(text: str) -> bool:
    try:
        _split_key(text)
    except SubsetError:
        return False
    return True


def _parse(lines: list[tuple[int, str]], index: int, column: int) -> tuple[object, int]:
    if lines[index][1] == "-":
        return _parse_sequence(lines, index, column)
    if not _is_key(lines[index][1]):
        # A bare scalar — an item of a list, such as `- tests/test_x.py`
        return _scalar(lines[index][1]), index + 1
    return _parse_mapping(lines, index, column)


def _parse_sequence(
    lines: list[tuple[int, str]], index: int, column: int
) -> tuple[list[object], int]:
    items: list[object] = []
    while index < len(lines) and lines[index][0] == column and lines[index][1] == "-":
        index += 1
        if index < len(lines) and lines[index][0] > column:
            value, index = _parse(lines, index, lines[index][0])
        else:
            value = None
        items.append(value)
    return items, index


def _parse_mapping(
    lines: list[tuple[int, str]], index: int, column: int
) -> tuple[dict[str, object], int]:
    mapping: dict[str, object] = {}
    while index < len(lines) and lines[index][0] == column and lines[index][1] != "-":
        key, raw = _split_key(lines[index][1])
        index += 1
        if raw:
            value: object = _scalar(raw)
        elif index < len(lines) and lines[index][0] > column:
            value, index = _parse(lines, index, lines[index][0])
        elif index < len(lines) and lines[index][0] == column and lines[index][1] == "-":
            value, index = _parse_sequence(lines, index, column)
        else:
            value = None
        mapping[key] = value
    return mapping, index


def load(text: str) -> object:
    """Read the YAML subset the index and the workflows use. Anything else raises."""
    lines = _significant(text)
    if not lines:
        return None
    value, index = _parse(lines, 0, lines[0][0])
    if index != len(lines):
        message = f"stopped early — inconsistent indentation at {lines[index][1]!r}"
        raise SubsetError(message)
    return value


def workflow_jobs(root: pathlib.Path) -> tuple[dict[str, list[str]], list[str]]:
    """job → the names of its named steps, plus a list of files that could not be read."""
    jobs: dict[str, list[str]] = {}
    unreadable: list[str] = []
    for path in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        try:
            workflow = load(path.read_text(encoding="utf-8"))
        except SubsetError as error:
            unreadable.append(f"{path.relative_to(root)}: {error}")
            continue
        if not isinstance(workflow, dict):
            unreadable.append(f"{path.relative_to(root)}: not a mapping")
            continue
        for name, job in (workflow.get("jobs") or {}).items():
            steps = (job or {}).get("steps") or [] if isinstance(job, dict) else []
            jobs[str(name)] = [
                str(s["name"]) for s in steps if isinstance(s, dict) and s.get("name")
            ]
    return jobs, unreadable


def _gate_findings(gates: list[object]) -> tuple[list[str], list[dict[str, Any]]]:
    """Keep the well-formed gates for the checks below; report the rest as findings."""
    findings: list[str] = []
    usable: list[dict[str, Any]] = []
    seen: set[str] = set()
    for gate in gates:
        if not isinstance(gate, dict):
            findings.append(f"a row in the index is not a mapping: {gate!r}")
            continue
        gid = str(gate.get("id") or "")
        if not GATE_ID.match(gid):
            findings.append(f"id is not kebab-case: {gid!r}")
            continue
        if gid in seen:
            findings.append(f"duplicate id: {gid}")
            continue
        seen.add(gid)
        if not gate.get("title"):
            findings.append(f"{gid}: no title")
        if gate.get("kind") not in KINDS:
            findings.append(f"{gid}: kind {gate.get('kind')!r} is not one of {sorted(KINDS)}")
        if not isinstance(gate.get("enforced_by"), dict) or not gate["enforced_by"].get("job"):
            findings.append(f"{gid}: enforced_by must name the job that enforces this rule")
            continue
        usable.append(gate)
    return findings, usable


def _forward(
    gates: list[dict[str, Any]], jobs: dict[str, list[str]], root: pathlib.Path
) -> list[str]:
    """Forward: does each gate point at a job, step, or file that exists?"""
    findings: list[str] = []
    for gate in gates:
        gid, enforced = gate["id"], gate["enforced_by"]
        job = str(enforced["job"])
        if job not in jobs:
            findings.append(f"{gid}: points at job {job!r}, which no workflow defines")
        elif gate["kind"] == "step":
            step = enforced.get("step")
            if not step or str(step) not in jobs[job]:
                findings.append(f"{gid}: job {job!r} has no step {step!r}")
        elif gate["kind"] == "test":
            files = enforced.get("tests") or []
            if not isinstance(files, list) or not files:
                findings.append(f"{gid}: kind 'test' must list test files")
            else:
                findings += [
                    f"{gid}: no such file {name}"
                    for name in files
                    if not (root / str(name)).is_file()
                ]
    return findings


def _partition(
    gates: list[dict[str, Any]], root: pathlib.Path, tests_dir: pathlib.Path
) -> list[str]:
    """Back (tests): every test file is claimed, and claimed by exactly one gate."""
    if not tests_dir.is_dir():
        return []
    claims: dict[str, list[str]] = {}
    for gate in gates:
        for name in gate["enforced_by"].get("tests") or []:
            claims.setdefault(str(name), []).append(gate["id"])

    prefix = tests_dir.relative_to(root).as_posix()
    on_disk = {f"{prefix}/{path.name}" for path in tests_dir.glob("test_*.py")}
    findings = [
        f"no gate claims this test file: {name}" for name in sorted(on_disk - claims.keys())
    ]
    findings += [
        f"the index claims a file that is gone: {name}" for name in sorted(claims.keys() - on_disk)
    ]
    findings += [
        f"the partition is broken — {name} is claimed by {sorted(owners)}"
        for name, owners in sorted(claims.items())
        if len(owners) > 1
    ]
    return findings


def _read_registry(registry: pathlib.Path) -> tuple[list[str], list[object]]:
    """Read the index. Unreadable or malformed is a finding, not an excuse to skip."""
    try:
        document = load(registry.read_text(encoding="utf-8"))
    except SubsetError as error:
        return [f"{registry.name} could not be read — {error}"], []
    if not isinstance(document, dict) or not isinstance(document.get("gates"), list):
        return [f"{registry.name} must have a 'gates' key holding a list"], []
    return [], document["gates"]


def main(root: pathlib.Path) -> int:
    config_path = root / "scaffold.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    declared = config.get("gates_path", "gates.yaml")
    registry = root / declared
    if not registry.is_file():
        print(f"NA: no {declared} — there is no index to check yet")
        return 0

    findings, rows = _read_registry(registry)
    if not findings:
        shape, gates = _gate_findings(rows)
        findings += shape
        if not gates and not shape:
            findings.append(f"{registry.name} lists no gates — an empty index enforces nothing")

        jobs, unreadable = workflow_jobs(root)
        findings += [f"a workflow could not be read — {problem}" for problem in unreadable]
        findings += _forward(gates, jobs, root)

        covered = {str(gate["enforced_by"]["job"]) for gate in gates}
        findings += [
            f"job with no gate in the index: {job} — give it one"
            for job in sorted(set(jobs) - covered)
        ]
        findings += _partition(gates, root, root / config.get("tests_path", "tests"))

    for finding in findings:
        print(f"gates-registry-total: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_gates_registry.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
