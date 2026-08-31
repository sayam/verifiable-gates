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

Role: decider — it answers pass or fail with an exit code, and it ships as a
standalone file; its evidence is a planted violation and a clean tree in
`tests/test_checks_behaviour.py`.
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


def _without_opening_marker(raw: list[str]) -> list[str]:
    """The lines with the document's own `---` blanked — a bare marker in front of
    the first meaningful line is YAML, and the first line of many real workflows;
    any later marker is another document (self-audit, 2026-08-31: the opener was
    "more than one document", and a project's whole index went red for it)."""
    for index, line in enumerate(raw):
        content = _uncomment(line).strip()
        if content:
            return [*raw[:index], "", *raw[index + 1 :]] if content == "---" else raw
    return raw


def _significant(text: str) -> list[tuple[int, str]]:
    """(column, content) for lines that carry meaning; `- x` becomes two entries.

    The body of a block scalar is discarded — we never use those values — but it
    has to be **skipped correctly**, or the prose inside gets read as structure.
    """
    raw = _without_opening_marker(text.splitlines())
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


def _toothless(workflow: dict[str, Any], job: dict[str, Any]) -> str:
    """Why this job cannot turn the build red — empty while it can.

    A gate names a job so that the job fails when the rule is broken. Three shapes
    take that away without touching the index: a workflow with no trigger never runs
    at all, `if: false` never starts the job, and `continue-on-error: true` lets it
    fail while the run stays green. Adding the third to this repository's own `test`
    job — the job forty-five of its fifty-four gates name — left the whole suite, every
    reader and this scanner green (self-audit round 3, 2026-09-01).

    A `kind: step` gate is judged the same way one level down, under the key
    `job:step`: the step it names carrying `continue-on-error: true` takes the teeth
    from that gate while the job around it keeps its own.

    Only the unambiguous shapes are judged: a `workflow_dispatch`-only or
    `schedule`-only workflow is a deliberate choice this repository makes itself, for
    `release-sign` and `posture`, and an `if:` holding an expression is not a literal.
    """
    if "on" not in workflow:
        return "the workflow it is in has no trigger, so it never runs"
    if job.get("if") is False:
        return "the job is `if: false`, so it never starts"
    if job.get("continue-on-error") is True:
        return "the job is `continue-on-error: true`, so it cannot fail the run"
    return ""


def _read_workflow(
    path: pathlib.Path, root: pathlib.Path
) -> tuple[dict[str, Any] | None, str]:
    """One workflow, or the sentence saying why it could not be read.

    Three ways of not being readable, and each was a raw traceback once: bytes that are
    not UTF-8 (round 3), a file this scanner may not open (round 5), and a document the
    subset reader refuses. They all take the route this reader already had.
    """
    try:
        workflow = load(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as error:
        return None, f"{path.relative_to(root)}: not UTF-8 ({error.reason})"
    except OSError as error:
        return None, f"{path.relative_to(root)}: {error.strerror or error}"
    except SubsetError as error:
        return None, f"{path.relative_to(root)}: {error}"
    if not isinstance(workflow, dict):
        return None, f"{path.relative_to(root)}: not a mapping"
    return workflow, ""


def _teeth(
    workflow: dict[str, Any], name: str, job: object, steps: list[object]
) -> dict[str, str]:
    """What cannot fail here: the job itself, and any step a step gate could name."""
    found: dict[str, str] = {}
    why = _toothless(workflow, job) if isinstance(job, dict) else ""
    if why:
        found[name] = why
    for step in steps:
        if isinstance(step, dict) and step.get("continue-on-error") is True:
            found[f"{name}:{step.get('name')}"] = (
                "the step it names is `continue-on-error: true`, so it cannot fail"
            )
    return found


def workflow_jobs(
    root: pathlib.Path,
) -> tuple[dict[str, list[str]], list[str], list[str], dict[str, str]]:
    """job → the names of its named steps, the files that could not be read, the job
    names two workflow files both define — the platform runs both while a dict keyed by
    name kept one, so the second was covered by the first's gate in silence (outside
    audit, 2026-08-31) — and the jobs that cannot fail the build at all."""
    jobs: dict[str, list[str]] = {}
    unreadable: list[str] = []
    homes: dict[str, list[str]] = {}
    toothless: dict[str, str] = {}
    for path in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        workflow, why_not = _read_workflow(path, root)
        if workflow is None:
            unreadable.append(why_not)
            continue
        for name, job in (workflow.get("jobs") or {}).items():
            steps = (job or {}).get("steps") or [] if isinstance(job, dict) else []
            jobs[str(name)] = [
                str(s["name"]) for s in steps if isinstance(s, dict) and s.get("name")
            ]
            homes.setdefault(str(name), []).append(str(path.relative_to(root)))
            toothless |= _teeth(workflow, str(name), job, steps)
    clashes = [
        f"job {name} is defined in {' and '.join(files)} — one gate cannot hold two jobs"
        f" of one name; rename one"
        for name, files in sorted(homes.items())
        if len(files) > 1
    ]
    return jobs, unreadable, clashes, toothless


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
        if enforced.get("tests") and gate["kind"] != "test":
            # `kind` decides who runs the gate: only `test` is run by the harness,
            # and only `test` has its files looked for above. A row listing tests
            # under any other kind is a gate nothing runs, still counted by the
            # index — one word changed took the reference harness from 43 pass to
            # 42 with every reader green (self-audit round 2, 2026-08-31).
            findings.append(
                f"{gid}: kind {gate['kind']!r} lists tests — nothing runs them, "
                "and nothing checks that they are there"
            )
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

    # What pytest collects by default: `test_*.py` and `*_test.py`, in every
    # directory under the tests root — a file in `tests/unit/` ran on every push
    # and was in no gate's partition (self-audit, 2026-08-31).
    on_disk = {
        path.relative_to(root).as_posix()
        for path in tests_dir.rglob("*.py")
        if path.name.startswith("test_") or path.name.endswith("_test.py")
    }
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
    except UnicodeDecodeError as error:
        return [f"{registry.name} could not be read — not UTF-8 ({error.reason})"], []
    except OSError as error:
        return [f"{registry.name} could not be read — {error.strerror or error}"], []
    except SubsetError as error:
        return [f"{registry.name} could not be read — {error}"], []
    if not isinstance(document, dict) or not isinstance(document.get("gates"), list):
        return [f"{registry.name} must have a 'gates' key holding a list"], []
    return [], document["gates"]


MISCONFIGURED = (
    "scaffold.json names {key} {path}, which is not there — a configured path that "
    "is missing is a broken configuration, not nothing to check"
)


def _config_text(path: pathlib.Path) -> str:
    """`scaffold.json`'s text, or the third answer. Every scanner routes the files it
    judges around undecodable bytes; the configuration beside them was still read bare
    and died of a traceback (self-audit round 3, 2026-09-01)."""
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as problem:
        print(f"cannot read the tree: {path}: {problem}", file=sys.stderr)
        raise SystemExit(2) from problem


def main(root: pathlib.Path) -> int:
    if not root.is_dir():
        # NA means "this project has nothing of that kind"; a root that is not
        # there has no project to say it about, and answering the second with
        # the first is a green over nothing (self-audit round 2, 2026-08-31).
        print(f"cannot read the tree: {root} is not a directory", file=sys.stderr)
        return 2
    config_path = root / "scaffold.json"
    config = json.loads(_config_text(config_path)) if config_path.is_file() else {}
    declared = config.get("gates_path", "gates.yaml")
    registry = root / declared
    if not registry.is_file():
        # An index the project named and does not have is a broken configuration,
        # not "no index yet" — the same two answers every scaffold path gives.
        if "gates_path" in config:
            print("gates-registry-total: " + MISCONFIGURED.format(key="gates_path", path=declared))
            return 1
        print(f"NA: no {declared} — there is no index to check yet")
        return 0

    findings, rows = _read_registry(registry)
    if not findings:
        shape, gates = _gate_findings(rows)
        findings += shape
        if not gates and not shape:
            findings.append(f"{registry.name} lists no gates — an empty index enforces nothing")

        jobs, unreadable, clashes, toothless = workflow_jobs(root)
        findings += [f"a workflow could not be read — {problem}" for problem in unreadable]
        findings += clashes
        findings += _forward(gates, jobs, root)
        findings += [
            f"{gate['id']}: {toothless[str(gate['enforced_by']['job'])]} — a gate whose job "
            "cannot turn the build red is a row in the index and nothing else"
            for gate in gates
            if str(gate["enforced_by"]["job"]) in toothless
        ]
        findings += [
            f"{gate['id']}: {toothless[key]} — a gate whose step cannot turn the build "
            "red is a row in the index and nothing else"
            for gate in gates
            if gate["kind"] == "step"
            and (key := f"{gate['enforced_by']['job']}:{gate['enforced_by'].get('step')}")
            in toothless
        ]

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
