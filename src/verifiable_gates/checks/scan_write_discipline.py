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

# Characters a finding line may not carry, and what is printed instead. The C0 controls
# and DEL break the line grammar or the terminal; the C1 range does the same through a
# terminal that reads 8-bit escapes; the bidi and zero-width formats reorder or hide what
# a reader is looking at. Anything else — every language's letters — is left alone.

# What this scanner reads, in one sentence — the catalogue's `reads:` for its rule is
# held equal to this, `--rules` prints it, and every NA below is built from it. A Go
# project read `nothing to check yet` about files it would never have (self-audit
# round 22, 2026-09-04): an NA says what the rule reads, and "yet" is not a word in it.
READS = (
    "Python modules under app (scaffold.json src_path) — session.delete calls outside the "
    "purge_paths"
)
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


def _walk(top: pathlib.Path) -> list[pathlib.Path]:
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
    for parent, _directories, names in os.walk(top, onerror=trouble.append):
        found += [pathlib.Path(parent) / name for name in names]
    # A `top` that is not there is nothing to walk, which the caller reports as N/A — the
    # answer it gave before. "Not there" and "there and closed to me" are different things.
    blocked = [problem for problem in trouble if not isinstance(problem, FileNotFoundError)]
    if blocked:
        raise _UnreadableError(
            "; ".join(f"{_shown(bad.filename)}: {bad.strerror}" for bad in blocked)
        )
    return sorted(found)


def _config(path: pathlib.Path) -> dict[str, object]:
    """The project's `scaffold.json`, or the third answer saying why it is not one.

    Round 3 wrapped the *read* of this file and stopped one line short of the parse, so a
    configuration that is malformed, empty, or saved with a byte-order mark — and one that
    parses to a list, a string or `null` rather than an object — was still a raw traceback
    and exit 1, the code that means *findings*, out of a scanner that had judged nothing
    (self-audit round 17, 2026-09-01). A file nobody can read as a configuration is the
    same answer as one nobody can decode: no verdict, said plainly.
    """
    if not path.is_file():
        return {}
    try:
        config = json.loads(_text(path))
    except json.JSONDecodeError as problem:
        raise _UnreadableError(
            f"{_shown(path)}: not JSON — {problem.msg}, line {problem.lineno}"
        ) from problem
    if not isinstance(config, dict):
        raise _UnreadableError(
            f"{_shown(path)}: not an object — a configuration names keys, "
            f"and this one holds {json.dumps(config)[:40]}"
        )
    return config


# A `.pyw` is a Python module; the suffix only tells Windows to run it without a console.
# The walk kept `.py` alone, so a module named that way was not read at all — and where one
# was the only module present the answer was `NA: no Python under …`, a scanner reporting
# that a tree it could not see holds nothing (round 31, 2026-09-07). `.pyi` is deliberately
# not here: a stub declares names and runs none of them.
PYTHON_SUFFIXES = frozenset({".py", ".pyw"})


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
        print(f"NA: no {src.relative_to(root)} — this rule reads {READS}")
        return None, 0
    return src, 0


# `session.delete(...)` is not the only spelling of the call. A session bound to a local name
# first — `s = db.session` — and then deleted through that name carries no `session.delete`
# text anywhere, so the gate answered `pass` over a real hard delete (round 31, 2026-09-07).
# The binding is read out of the same file, so an alias counts only where that file made it:
# a name is not a session because some other module used it for one.
SESSION_BOUND = re.compile(r"^\s*(?P<alias>\w+)\s*=\s*[\w.]*\bsession\s*$")


def _session_aliases(code: list[str]) -> set[str]:
    """The names this file binds to a session, so that `<name>.delete(` is a delete too."""
    bound = {found.group("alias") for line in code if (found := SESSION_BOUND.match(line))}
    return {alias for alias in bound if alias != "session"}


# The SQLAlchemy 2.0 way to delete rows names no `session.delete(` and no
# `synchronize_session`: `session.execute(delete(Model).where(...))`. Matching every
# `delete(` would flag the cache clients that made the textual match the choice in the first
# place (DECISIONS.md `write-scanner-reads-session-delete`), so two narrower reads flag only
# the rows. First, a name this file bound to SQLAlchemy's construct — `from sqlalchemy import
# delete [as d]`, on one line or in parentheses, or the module itself, `import sqlalchemy
# [as sa]` — called bare (`delete(Model)`, `sa.delete(Model)`) is the construct, whichever
# line executes it. Second, a `delete(` **inside an `.execute(`** on the same line is a row
# delete whatever bound it: that is the shape `db.session.execute(db.delete(Model))` takes
# in Flask-SQLAlchemy, where `db` is imported from elsewhere and this file holds no evidence
# of what it is. A letter or `_` before `delete` is not a match, so a project's own
# `soft_delete(obj)` — the function this rule asks for — stays what it is (round 31,
# 2026-09-07).
FROM_SQLALCHEMY = re.compile(
    r"^[ \t]*from[ \t]+sqlalchemy(?:\.\w+)*[ \t]+import[ \t]+(?P<names>\([^)]*\)|[^\n]+)",
    re.MULTILINE,
)
IMPORT_SQLALCHEMY = re.compile(
    r"^[ \t]*import[ \t]+sqlalchemy(?:[ \t]+as[ \t]+(?P<alias>\w+))?[ \t]*$", re.MULTILINE
)
EXECUTES_A_DELETE = re.compile(r"\.execute\s*\(.*(?<![\w.])(?:\w+\.)?delete\s*\(")


def _delete_constructs(code: list[str]) -> tuple[set[str], set[str]]:
    """The names this file binds to SQLAlchemy's `delete` construct, and to the module."""
    text = "\n".join(code)
    constructs: set[str] = set()
    for found in FROM_SQLALCHEMY.finditer(text):
        for item in found.group("names").strip("()").split(","):
            words = item.split()
            if words and words[0] == "delete":
                constructs.add(words[-1])  # `delete`, or what `as` renamed it to
    modules = {found.group("alias") or "sqlalchemy" for found in IMPORT_SQLALCHEMY.finditer(text)}
    return constructs, modules


# The 1.x bulk delete was read only when it spelled `synchronize_session=`; the bare form —
# `session.query(Model).filter(...).delete()`, and Flask-SQLAlchemy's
# `Model.query.filter_by(...).delete()` — exited 0 (measured, round 31, 2026-09-07). What
# marks it is `query` in the receiver chain of `.delete(` — `.query`/`query(` then a method
# chain — never `query` sitting in the args (`cache.delete(query)`); a cache client has none, so the
# read stays as narrow as the row that chose the textual match asks. A name bound to a query
# *call* on its own line — `q = session.query(Model)` — makes `q.delete(` the same call one
# line later; a bare `.query` attribute (`s = db.query`) is not a query object and is not
# bound. Like a session alias, the binding counts only in the file that made it.
QUERY_DELETE = re.compile(r"\bquery\b(?:[\w.]|\([^()]*\))*\.delete\s*\(")
QUERY_BOUND = re.compile(r"^\s*(?P<alias>\w+)\s*=.*\bquery\s*\(")


def _query_aliases(code: list[str]) -> set[str]:
    """The names this file binds to a query, so that `<name>.delete(` is a bulk delete."""
    return {found.group("alias") for line in code if (found := QUERY_BOUND.match(line))}


def _deletes_a_row(line: str, receivers: set[str], constructs: set[str], modules: set[str]) -> bool:
    """Does this line delete rows — through the session by its name or an alias, through
    SQLAlchemy's `delete` construct by a name this file bound to it, or inside an `.execute(`?"""
    if DELETE_CALL.search(line) or EXECUTES_A_DELETE.search(line) or QUERY_DELETE.search(line):
        return True
    if any(re.search(rf"\b{re.escape(name)}\.delete\s*\(", line) for name in receivers):
        return True
    if any(re.search(rf"(?<![\w.]){re.escape(name)}\s*\(", line) for name in constructs):
        return True
    return any(re.search(rf"\b{re.escape(name)}\.delete\s*\(", line) for name in modules)


def _segments_match(parts: list[str], globs: list[str]) -> bool:
    """One path against one pattern, segment by segment.

    `**` is the only glob that crosses a separator, and it stands for zero or more whole
    segments — the meaning every developer already has from `.gitignore` and `pathlib`.
    """
    if not globs:
        return not parts
    head, rest = globs[0], globs[1:]
    if head == "**":
        return any(_segments_match(parts[at:], rest) for at in range(len(parts) + 1))
    return bool(parts) and fnmatch.fnmatch(parts[0], head) and _segments_match(parts[1:], rest)


def _exempt(relative: pathlib.PurePath, patterns: list[str]) -> bool:
    """Is this module one the project declared as the place that may purge?

    Matched **segment by segment**, so a `*` stops at a separator. Over the whole path it
    does not: `purge_paths: ["app/*"]` reads as *the files directly under app* and exempted
    `app/services/models.py` and every other module in the tree, so the gate answered `pass`
    over a real `session.delete` (round 31, 2026-09-07). It is round 17's shape a second
    time — there a list written as one string was read a character at a time and the `*`
    among those characters exempted everything, refused by checking the value's *shape*;
    here the value is well formed and the pattern did not mean what it looked like.
    """
    parts = relative.as_posix().split("/")
    return any(_segments_match(parts, pattern.strip("/").split("/")) for pattern in patterns)


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
    config = _config(config_path)
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

    readable = [path for path in _walk(src) if path.suffix in PYTHON_SUFFIXES]
    # A directory that is there and holds nothing this scanner reads is not a
    # clean project — it is a project this scanner cannot see, which the manifest's
    # own words forbid reporting as checked: "A rule the tool cannot check must not
    # look like a rule it checked." A Go project's `app/` came back `[ pass]`
    # (self-audit round 8, 2026-09-01).
    if not readable:
        print(
            f"NA: no Python under {src.relative_to(root)} — this rule reads {READS};"
            " another language is not read"
        )
        return 0

    findings: list[str] = []
    for path in readable:
        relative = path.relative_to(root)
        if _exempt(relative, patterns):
            continue
        text = _text(path)
        shown = text.splitlines()
        lines = _code_lines(text)
        receivers = _session_aliases(lines) | _query_aliases(lines)
        constructs, modules = _delete_constructs(lines)
        for lineno, line in enumerate(lines, 1):
            if _deletes_a_row(line, receivers, constructs, modules):
                findings.append(
                    f"{_shown(path.relative_to(root))}:{lineno} {shown[lineno - 1].strip()[:70]}"
                )

    for finding in findings:
        print(f"delete-means-soft-delete: {_shown(finding)}")
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
