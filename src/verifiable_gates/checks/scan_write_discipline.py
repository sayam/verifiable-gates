"""gate: delete-means-soft-delete — a real delete outside the declared purge modules is a finding.

Deleting for real belongs where the project declared it (`purge_paths`, which takes
globs); everywhere else has to be a soft delete. This matches the ORM's
`session.delete(` rather than every `.delete(`, because a cache client's
`.delete(key)` is not the removal of somebody's data — dogfooding against the
reference implementation caught that false positive.

The deeper cases (bulk operations, Core DML, raw SQL) belong to the project's own
test suite. This scan is the first layer, not the only one.

It reads code, not prose: comments and string literals — a docstring that says
"never call session.delete( here" — are blanked before the match, and the session
may carry a prefix (`db_session.delete(`, the plain SQLAlchemy `scoped_session`
name), which is still `session.delete(` to the eye and was unseen behind a word
boundary (self-audit, 2026-08-31: the docstring was a finding, `db_session` was not).

exit 0 = clean or N/A · 1 = findings · 2 = called wrongly

Role: decider — it answers pass or fail with an exit code, and it ships as a
standalone file; its evidence is a planted violation and a clean tree in
`tests/test_checks_behaviour.py`.
"""

from __future__ import annotations

import fnmatch
import io
import json
import os
import pathlib
import re
import sys
import tokenize


def _shown(path: str | pathlib.Path) -> str:
    """A path as text that can always be printed.

    A file name here is bytes, not characters. One that is not UTF-8 arrives from the
    directory listing carrying surrogates, and printing it raises `UnicodeEncodeError`:
    a traceback and exit 1 — the code that means *findings* — from a scanner that had a
    verdict to give, losing every finding it had already collected (self-audit round 15,
    2026-09-01). A name nobody can decode is still a name; it is shown with its bytes
    escaped, and the verdict stands.
    """
    return os.fsencode(str(path)).decode("utf-8", "backslashreplace")


class _UnreadableError(Exception):
    """Bytes this scanner cannot decode. No verdict — never a clean one."""


def _text(path: pathlib.Path) -> str:
    """The file's text, or `_UnreadableError` naming it.

    A file that is not UTF-8 made every scanner but the two AST readers die of a raw
    `UnicodeDecodeError` and exit 1 — the code that means findings (self-audit round 3,
    2026-09-01). A byte sequence nobody can decode is the third answer, not a verdict.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as problem:
        # `OSError` too: a file the scanner is not allowed to read, or that turned into
        # a directory between the glob and the read, was still a raw traceback after the
        # decode guard landed — the guard was written for the exception in hand rather
        # than for the question (self-audit round 5, 2026-09-01).
        message = f"{_shown(path)}: {problem}"
        raise _UnreadableError(message) from problem


DELETE_CALL = re.compile(r"\w*session\.delete\s*\(|synchronize_session")
# The middle of an f-string is its own token from Python 3.12 on; older tokenizers
# have no such name and yield the whole literal as STRING.
PROSE_TOKENS = {tokenize.COMMENT, tokenize.STRING, getattr(tokenize, "FSTRING_MIDDLE", -1)}


def _code_lines(text: str) -> list[str]:
    """The file's lines with every comment and string literal blanked, newlines kept —
    the words in a docstring are not a call. A file Python cannot tokenize is read
    as written."""
    lines = text.splitlines()
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError):
        return lines
    for token in tokens:
        if token.type not in PROSE_TOKENS:
            continue
        (first, start), (last, end) = token.start, token.end
        for lineno in range(first, last + 1):
            line = lines[lineno - 1]
            head = start if lineno == first else 0
            tail = end if lineno == last else len(line)
            lines[lineno - 1] = line[:head] + " " * (tail - head) + line[tail:]
    return lines


OUTSIDE = (
    "scaffold.json names {key} {path}, which leads outside the project — a checker "
    "pointed out of the tree judges files this project does not own"
)


def _inside(root: pathlib.Path, path: pathlib.Path) -> bool:
    """Is `path` still inside the tree this scanner was pointed at?

    The installer was taught this in an earlier round — fourteen files landed outside the
    destination through a `tools` symlink — and the readers were never asked the same
    question. A `scaffold.json` path starting with `/` or climbing with `..` walked out of
    the project, judged files it does not own, and printed them under a path no reviewer
    can open; an absolute one also made `relative_to` raise, so the misconfiguration
    answered with a traceback (self-audit round 13, 2026-09-01).
    """
    return path.resolve().is_relative_to(root.resolve())


MISCONFIGURED = (
    "scaffold.json names {key} {path}, which is not there — a configured path that "
    "is missing is a broken configuration, not nothing to check"
)


MISSHAPEN = (
    "scaffold.json gives {key} {value}, which is not {want} — a configured value of the "
    "wrong shape is a broken configuration, not a value"
)


def _configured_path(config: dict[str, object], key: str, default: str) -> tuple[str | None, str]:
    """The path configured under `key`, or `None` and the finding saying it is not a path.

    `scaffold.json.default` ships the shape of every key it declares and nothing held a
    project to it. A path written as a list, a number or `null` reached `root / value`
    and left a raw `TypeError` and exit 1 — the code that means *findings* — out of a
    scanner that had judged nothing (self-audit round 17, 2026-09-01).
    """
    value = config.get(key, default)
    if isinstance(value, str):
        return value, ""
    return None, MISSHAPEN.format(key=key, value=json.dumps(value)[:40], want="a string")


def _configured_list(
    config: dict[str, object], key: str, default: list[str]
) -> tuple[list[str] | None, str]:
    """The names configured under `key`, or `None` and the finding saying they are not names.

    A list written as a single string was iterated **one character at a time**, so the
    project's configuration was read as a set of one-letter names: nonsense findings at
    best, and where the list is a set of exemptions, the `*` among those letters matched
    every path there is and the gate answered `pass` over a tree with a real violation in
    it (self-audit round 17, 2026-09-01).
    """
    value = config.get(key, default)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value, ""
    return None, MISSHAPEN.format(key=key, value=json.dumps(value)[:40], want="a list of strings")


def _src_dir(root: pathlib.Path, config: dict[str, object]) -> tuple[pathlib.Path | None, int]:
    """Where to look, or why there is nothing to look at — with the exit code for that."""
    named, wrong = _configured_path(config, "src_path", "app")
    if named is None:
        print(f"delete-means-soft-delete: {wrong}")
        return None, 1
    src = root / named
    if not _inside(root, src):
        print("delete-means-soft-delete: " + OUTSIDE.format(key="src_path", path=named))
        return None, 1
    if not src.is_dir():
        if "src_path" in config:
            print(
                "delete-means-soft-delete: "
                + MISCONFIGURED.format(key="src_path", path=src.relative_to(root))
            )
            return None, 1
        print(f"NA: no {src.relative_to(root)} — nothing to check yet")
        return None, 0
    return src, 0


def _judge(root: pathlib.Path) -> int:
    if not root.is_dir():
        # NA means "this project has nothing of that kind"; a root that is not
        # there has no project to say it about, and answering the second with
        # the first is a green over nothing (self-audit round 2, 2026-08-31).
        print(f"cannot read the tree: {_shown(root)} is not a directory", file=sys.stderr)
        return 2
    config_path = root / "scaffold.json"
    # A project that has not configured the bundle is not a misuse — the paths
    # below fall back to their defaults, and a default that is not there reports
    # NA. A path the project *named* and does not have is the opposite case: a
    # broken configuration, reported as a finding — an outside audit on
    # 2026-08-29 planted a `scaffold.json` pointing at a Dockerfile that did not
    # exist beside a dirty one that did, and the answer was "nothing to check".
    config = json.loads(_text(config_path)) if config_path.is_file() else {}
    # Read before `src_path` is resolved, so that a project whose source directory is
    # not there yet is still told its exemptions are unreadable — an NA over a broken
    # configuration is the shape round 13 refused everywhere else.
    patterns, wrong = _configured_list(config, "purge_paths", ["app/purge.py"])
    if patterns is None:
        print(f"delete-means-soft-delete: {wrong}")
        return 1
    src, code = _src_dir(root, config)
    if src is None:
        return code

    readable = sorted(src.rglob("*.py"))
    # A directory that is there and holds nothing this scanner reads is not a
    # clean project — it is a project this scanner cannot see, which the manifest's
    # own words forbid reporting as checked: "A rule the tool cannot check must not
    # look like a rule it checked." A Go project's `app/` came back `[ pass]`
    # (self-audit round 8, 2026-09-01).
    if not readable:
        print(f"NA: no Python under {src.relative_to(root)} — nothing to check yet")
        return 0

    findings: list[str] = []
    for path in readable:
        relative = path.relative_to(root)
        if any(fnmatch.fnmatch(str(relative), pattern) for pattern in patterns):
            continue
        text = _text(path)
        shown = text.splitlines()
        for lineno, line in enumerate(_code_lines(text), 1):
            if DELETE_CALL.search(line):
                findings.append(
                    f"{_shown(path.relative_to(root))}:{lineno} {shown[lineno - 1].strip()[:70]}"
                )

    for finding in findings:
        print(f"delete-means-soft-delete: {finding}")
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
        print("usage: scan_write_discipline.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
