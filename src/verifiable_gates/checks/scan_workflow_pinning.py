"""gate: actions-sha-pinned — every action in a workflow is pinned to a commit SHA, with
the version in a comment beside it.

A tag can be moved; a commit cannot. And an action runs with the permissions of
the project's own workflow, reading its source and whatever token that job holds.

A composite action under `.github/actions/<name>/action.yml` runs its `uses:`
steps with those same permissions, and moving a step into one used to move it
out of this scanner's sight — an outside audit on 2026-08-29 planted a floating
action there and got a clean exit. Both places are read, and so is every local
action a read file names with `uses: ./<path>`, wherever it lives.

exit 0 = clean or N/A · 1 = findings · 2 = called wrongly

Role: decider — it answers pass or fail with an exit code, and it ships as a
standalone file; its evidence is a planted violation and a clean tree in
`tests/test_checks_behaviour.py`.
"""

from __future__ import annotations

import os
import pathlib
import re
import sys

# Characters a finding line may not carry, and what is printed instead. The C0 controls
# and DEL break the line grammar or the terminal; the C1 range does the same through a
# terminal that reads 8-bit escapes; the bidi and zero-width formats reorder or hide what
# a reader is looking at. Anything else — every language's letters — is left alone.

# What this scanner reads, in one sentence — the catalogue's `reads:` for its rule is
# held equal to this, `--rules` prints it, and every NA below is built from it. A Go
# project read `nothing to check yet` about files it would never have (self-audit
# round 22, 2026-09-04): an NA says what the rule reads, and "yet" is not a word in it.
READS = "the uses: steps of workflows and composite actions under .github"
_ESCAPED = {
    **{c: f"\\x{c:02x}" for c in (*range(0x20), 0x7F)},
    **{
        c: f"\\u{c:04x}"
        for c in (
            *range(0x80, 0xA0),
            *range(0x200B, 0x2010),
            *range(0x202A, 0x202F),
            *range(0x2066, 0x206A),
            0xFEFF,
        )
    },
}


def _shown(text: str | pathlib.Path) -> str:
    """Text that can always be printed, and is always **one line**.

    Two properties, and the second was learnt after the first. A file name here is bytes,
    not characters: one that is not UTF-8 arrives from the directory listing carrying
    surrogates, and printing it raised `UnicodeEncodeError` — a traceback and exit 1, the
    code that means *findings*, from a scanner that had a verdict to give (self-audit
    round 15, 2026-09-01). That is the `backslashreplace` below.

    The name then stood for "safe to print", which it was not. A file name on Linux may
    carry a newline, and this scanner's caller reads one line as one finding: a file named
    `wipe\ndelete-means-soft-delete: forged\nx.py` turned one finding into two in the
    report, one SARIF result into three, and put a line no scanner wrote into an agent's
    context. An ANSI escape in a name (`\x1b[2K\x1b[A`) erased the finding printed above
    it (self-audit round 21, 2026-09-03). So a control character, a C1 byte, a bidi
    override and a zero-width format are shown escaped as well, and what is printed is one
    line whatever it was made of.

    This function is **copied into all nine scanners and the doctor on purpose** — each is
    shipped alone into a project that has installed nothing — and the copies are held
    byte-identical by `tests/test_checks_are_standalone.py`.
    """
    return os.fsencode(str(text)).decode("utf-8", "backslashreplace").translate(_ESCAPED)


# The value may be quoted — YAML allows it and people do it — and the quotes are
# not part of the action: a pinned `uses: "actions/checkout@<sha>"` was reported
# as unpinned because the closing quote sat where the digit had to be.
# YAML allows a space before the colon (`uses :`) and a flow-style step
# (`- {uses: actions/checkout@v4}`) — the platform reads both, and both were
# unread here (outside audit, 2026-08-31).
# The key may be quoted (`"uses":`), the value may be an alias (`uses: *co`) of an
# anchor set anywhere in the file — its version comment travelling with it — or
# carry a tag (`!!str`) or an anchor of its own, and a `uses` under `with:` is an
# input, not a step. Every one is YAML the platform reads; every one was misread
# here (self-audit, 2026-08-31: an alias to a pinned action was the finding `*co`,
# an alias to `@v4` was clean, an input named `uses` was a finding).
USES = re.compile(
    r"""^(\s*)-?\s*\{?\s*["']?uses["']?\s*:\s*["']?([^\s"',}]+)["']?(.*)$""", re.MULTILINE
)
ANCHOR = re.compile(r"""^\s*(?:-\s*)?(?:["']?[\w.-]+["']?\s*:\s*)?&([\w-]+)\s+(.+?)\s*$""")
ALIAS = re.compile(r"^\*([\w-]+)$")
TAG = re.compile(r"^!!?[\w:/.-]*\s+")
OWN_ANCHOR = re.compile(r"^&[\w-]+\s+")
BARE = re.compile(r"^(?:!!?[\w:/.-]*|&[\w-]+)$")
WITH = re.compile(r"^(\s*)with\s*:\s*$")
# The rule is a SHA *with the version in a comment* — `@<sha> # v7.0.1` — because
# a bare SHA is a pin nobody can read or move. The comment half went unjudged
# until an outside audit on 2026-08-30 planted a bare SHA and got exit 0.
VERSION_COMMENT = re.compile(r"#\s*v?\d")
# YAML lets the value fold onto the next line — `uses: >` then the action — and
# the regex above reported the fold marker as the action: `actions-sha-pinned:
# ci.yml: >`, red for the right reason with a finding that named nothing (outside
# audit, 2026-08-30). The marker is followed to the line that carries the value.
BLOCK = re.compile(r"^[|>][-+]?$")


class _UnreadableError(Exception):
    """Bytes nobody can decode, or a tree nobody can walk. No verdict — never a clean one."""


# **A ceiling on what one file may be.** Nothing here declared one, and the memory a
# scanner uses is a multiple of the largest file it is handed: measured on one 16 MB Python
# file, `list(tokenize.generate_tokens(...))` took 8.7s and **1,010 MB** (2.7 million
# tokens) and `ast.parse` of the same file **1,457 MB** — ×64 and ×90 (self-audit round 19,
# 2026-09-02). A standard runner has 7 GB, so one generated file of about 100 MB ends the
# job by being killed, which CI reports as *the gate failed* — blaming the project for a
# file the tool could not hold. A file above the ceiling is named and gets no verdict, the
# same answer as one nobody can decode; it is read up to the ceiling and no further, so the
# refusal costs the ceiling and never the file.
MAX_FILE_CHARS = 8 * 1024 * 1024


def _text(path: pathlib.Path) -> str:
    """The file's text, or `_UnreadableError` naming it.

    A file that is not UTF-8 made every scanner but the two AST readers die of a raw
    `UnicodeDecodeError` and exit 1 — the code that means findings (self-audit round 3,
    2026-09-01). A byte sequence nobody can decode is the third answer, not a verdict.

    A file **larger than the ceiling** is the same answer for the same reason: it is read up
    to `MAX_FILE_CHARS` and no further, so the refusal costs the ceiling and never the file.
    """
    try:
        with path.open(encoding="utf-8") as handle:
            text = handle.read(MAX_FILE_CHARS + 1)
    except (UnicodeDecodeError, OSError) as problem:
        # `OSError` too: a file the scanner is not allowed to read, or that turned into
        # a directory between the glob and the read, was still a raw traceback after the
        # decode guard landed — the guard was written for the exception in hand rather
        # than for the question (self-audit round 5, 2026-09-01).
        message = f"{_shown(path)}: {problem}"
        raise _UnreadableError(message) from problem
    if len(text) > MAX_FILE_CHARS:
        message = (
            f"{_shown(path)}: larger than the {MAX_FILE_CHARS // 1024 // 1024} MiB this"
            " scanner reads whole"
        )
        raise _UnreadableError(message)
    return text


def _walk(top: pathlib.Path, *, deep: bool = True) -> list[pathlib.Path]:
    """Every file under `top`, sorted — or `_UnreadableError` naming what stopped the walk.

    `rglob` **throws away the `OSError`s it meets on the way**: a directory this scanner
    may not open, and any path past the system's length limit, are simply absent from the
    result, with nothing raised and nothing printed — and the silence lands on the *pass*
    side. Measured on one tree, changing nothing but a permission bit: readable, the
    scanner printed the violation inside it and exited 1; with `chmod 000` on that one
    directory it printed **nothing** and exited 0. A tree whose only source file sat 5,147
    characters deep answered `NA: nothing to check yet` while `find` saw the file
    (self-audit round 19, 2026-09-02). Both are the sentence the manifest forbids — "A rule
    the tool cannot check must not look like a rule it checked" — so a walk that could not
    see the whole tree has no verdict to give.
    """
    trouble: list[OSError] = []
    found: list[pathlib.Path] = []
    for parent, directories, names in os.walk(top, onerror=trouble.append):
        if not deep:
            directories[:] = []
        found += [pathlib.Path(parent) / name for name in names]
    # A `top` that is not there is nothing to walk, which the caller reports as N/A — the
    # answer it gave before. "Not there" and "there and closed to me" are different things.
    blocked = [problem for problem in trouble if not isinstance(problem, FileNotFoundError)]
    if blocked:
        raise _UnreadableError(
            "; ".join(f"{_shown(bad.filename)}: {bad.strerror}" for bad in blocked)
        )
    return sorted(found)


def _yaml_files(directory: pathlib.Path, *, deep: bool = True) -> list[pathlib.Path]:
    """Every YAML file under `directory`, sorted — the walk above, filtered by suffix."""
    return [path for path in _walk(directory, deep=deep) if path.suffix in {".yml", ".yaml"}]


def _anchors(text: str) -> dict[str, tuple[str, str]]:
    """Every scalar anchor in the file — `&name value  # comment` — by name: the value
    with quotes and tag stripped, and the rest of its line (the version comment)."""
    found: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        match = ANCHOR.match(line)
        if not match or BLOCK.match(match.group(2)):
            continue
        value, _, rest = match.group(2).partition(" #")
        value = TAG.sub("", value).strip().strip("\"'")
        found[match.group(1)] = (value, f"#{rest}" if rest else "")
    return found


def _resolved(ref: str, after: str, anchors: dict[str, tuple[str, str]]) -> tuple[str, str]:
    """The value as the platform reads it: tag and own anchor dropped, an alias replaced
    by its anchor's value with the anchor line's comment beside it."""
    while BARE.match(ref) and after.strip():
        ref, _, after = after.strip().partition(" ")
        ref = ref.strip("\"'")
    ref = OWN_ANCHOR.sub("", TAG.sub("", ref.strip())).strip()
    alias = ALIAS.match(ref)
    if alias and alias.group(1) in anchors:
        value, comment = anchors[alias.group(1)]
        return value, f"{after} {comment}".strip()
    return ref, after


def _under_with(lines: list[str]) -> list[bool]:
    """For each line, whether it sits inside a `with:` block — an input, not a step."""
    inside: list[bool] = []
    with_indent = -1
    for line in lines:
        indent = len(line) - len(line.lstrip())
        if line.strip() and with_indent >= 0 and indent <= with_indent:
            with_indent = -1
        inside.append(with_indent >= 0 and indent > with_indent)
        match = WITH.match(line)
        if match:
            with_indent = len(match.group(1))
    return inside


def _uses_lines(text: str) -> list[tuple[str, str]]:
    """Every `uses:` step in the file with what follows it on its line — a folded or
    literal one read from its next line, an alias read from its anchor."""
    lines = text.splitlines()
    anchors = _anchors(text)
    nested = _under_with(lines)
    found: list[tuple[str, str]] = []
    for index, line in enumerate(lines):
        match = USES.match(line)
        if not match or nested[index]:
            continue
        ref, after = match.group(2), match.group(3)
        if BLOCK.match(ref):
            # The version comment may sit beside the marker (`uses: > # v4`) or
            # beside the value on the next line — both are the same step to the
            # platform, so both count (outside audit, 2026-08-31: a comment on
            # the marker line was "no version comment").
            marker_side = after
            rest = [later.strip() for later in lines[index + 1 :] if later.strip()]
            ref, _, after = rest[0].partition(" ") if rest else (ref, "", "")
            ref = ref.strip("\"'")
            after = f"{after} {marker_side}".strip()
        found.append(_resolved(ref, after, anchors))
    return found


def _uses_refs(text: str) -> list[str]:
    """Every `uses:` value in the file, a folded or literal one read from its next line."""
    return [ref for ref, _ in _uses_lines(text)]


PINNED = re.compile(r"@[0-9a-f]{40}$")
# A `docker://` step runs an image with the job's permissions, and a tag can be
# re-pointed exactly as an action tag can — so it is held to a digest, not
# exempted (an outside audit on 2026-08-29 planted `docker://alpine:latest`
# and the whole prefix was excused). Only a path in this checkout is local.
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")
LOCAL = ("./",)

# The bundle's own starting workflow, as `install.py` writes `ci-template.yml`:
# one pinned checkout and one run of the doctor. A tree where every workflow is
# that has nothing of the project's to judge yet, and the answer is NA — so
# "every scan NA" can mean what README says it means. An outside audit on
# 2026-08-30 installed into an empty directory and three scans said `pass` on
# the file the bundle had just written. Any line added or changed makes the
# workflow the project's, and it is judged like any other.
STEP = re.compile(r"^\s*-?\s*(uses|run):\s*(.+?)\s*$", re.MULTILINE)
TEMPLATE_STEPS = (("uses", re.compile(r"^actions/checkout@[0-9a-f]{40}$")), ("run", None))
DOCTOR_RUN = "python3 tools/gates_doctor.py"


def _bundles_own(text: str) -> bool:
    """Is this workflow the untouched starting one — a pinned checkout, then the doctor?"""
    steps = [(kind, value.split(" #")[0].strip()) for kind, value in STEP.findall(text)]
    if len(steps) != len(TEMPLATE_STEPS):
        return False
    (uses_kind, uses), (run_kind, run) = steps
    return (
        uses_kind == "uses"
        and TEMPLATE_STEPS[0][1] is not None
        and TEMPLATE_STEPS[0][1].match(uses) is not None
        and run_kind == "run"
        and run == DOCTOR_RUN
    )


# A local action is whatever `uses: ./<path>` names — GitHub reads
# `<path>/action.yml` wherever it lives, so reading `.github/actions/` alone left
# `uses: ./ci/actions/setup` unread: an outside audit on 2026-08-30 planted one
# there and both pinning scanners exited 0 while CHANGELOG said composite actions
# were read. Every file read is followed, so an action calling an action is read.
# The path is read the way every `uses:` is, so `uses: >` with `./ci/action` on
# the next line is followed too — a folded *remote* action was named after the
# 2026-08-30 audit while a folded local one was still unread (outside audit,
# 2026-08-30: a nested `@v4` behind it exited 0).


def _local_uses(text: str) -> list[str]:
    """The paths of every local action the file names, folded or not."""
    return [ref[2:] for ref in _uses_refs(text) if ref.startswith("./")]


def _followed(root: pathlib.Path, targets: list[pathlib.Path]) -> list[pathlib.Path]:
    """`targets` plus every local action a read file points at, wherever it lives."""
    seen = list(targets)
    queue = list(targets)
    while queue:
        for relative in _local_uses(_text(queue.pop())):
            for name in ("action.yml", "action.yaml"):
                candidate = root / relative / name
                if candidate.is_file() and candidate not in seen:
                    seen.append(candidate)
                    queue.append(candidate)
    return seen


def _pinned(ref: str) -> bool:
    if ref.startswith("docker://"):
        return DIGEST.search(ref) is not None
    return PINNED.search(ref) is not None


def _verdicts(root: pathlib.Path, workflows: list[pathlib.Path]) -> tuple[list[str], int]:
    """The findings, and how many `uses:` references were read to reach them — a
    count of zero is the difference between pass and NA."""
    findings: list[str] = []
    judged = 0
    for path in _followed(root, workflows):
        for ref, after in _uses_lines(_text(path)):
            if ref.startswith(LOCAL):
                continue
            judged += 1
            if not _pinned(ref):
                findings.append(f"{_shown(path.relative_to(root))}: {ref}")
            elif PINNED.search(ref) and not VERSION_COMMENT.search(after):
                findings.append(
                    f"{_shown(path.relative_to(root))}: {ref} — pinned with no version comment"
                )
    return findings, judged


def _judge(root: pathlib.Path) -> int:
    if not root.is_dir():
        # NA means "this project has nothing of that kind"; a root that is not
        # there has no project to say it about, and answering the second with
        # the first is a green over nothing (self-audit round 2, 2026-08-31).
        print(f"cannot read the tree: {_shown(root)} is not a directory", file=sys.stderr)
        return 2
    actions = _yaml_files(root / ".github" / "actions")
    workflows = _yaml_files(root / ".github" / "workflows", deep=False)
    workflows += [path for path in actions if path.stem == "action"]
    if not workflows:
        print(f"NA: no workflows or composite actions — this rule reads {READS}")
        return 0
    if all(_bundles_own(_text(path)) for path in workflows):
        print("NA: only the bundle's own starting workflow, untouched — nothing of yours to read")
        return 0

    findings, judged = _verdicts(root, workflows)

    # A workflow of `run:` steps alone has nothing this rule pins, and a `uses: ./…`
    # is a path, not a reference. Read and judged nothing is said as NA, not pass —
    # the same hole `ci-tools-hash-pinned` had on a Go workflow (self-audit round
    # 22, 2026-09-04).
    if not findings and not judged:
        print(
            f"NA: read {len(workflows)} workflow{'s' if len(workflows) != 1 else ''}"
            " and found no `uses:` step naming an action — nothing this rule pins"
        )
        return 0
    for finding in findings:
        print(f"actions-sha-pinned: {_shown(finding)}")
    return 1 if findings else 0


def main(root: pathlib.Path) -> int:
    """The verdict, or the third answer when a file cannot be decoded."""
    try:
        return _judge(root)
    except _UnreadableError as problem:
        print(f"cannot read the tree: {problem}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_workflow_pinning.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
