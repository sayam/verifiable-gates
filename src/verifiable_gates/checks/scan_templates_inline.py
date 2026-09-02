"""gate: csp-no-inline — templates carry no inline handler, style, or script.

Under a `'self'`-only Content Security Policy the browser blocks these **silently**;
there is no server-side error to notice. So the check has to read the files rather
than wait for a symptom — the way a browser reads them: attributes in any case,
at a line's start as after a space, a tag read to its `>` on whatever line that
is, and comments blanked first, because a comment explains rather than runs.

exit 0 = clean or N/A · 1 = findings · 2 = called wrongly

Role: decider — it answers pass or fail with an exit code, and it ships as a
standalone file; its evidence is a planted violation and a clean tree in
`tests/test_checks_behaviour.py`.
"""

from __future__ import annotations

import html
import json
import os
import pathlib
import re
import sys


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


# HTML is case-insensitive and the browser blocks `ONCLICK=` exactly as it blocks
# `onclick=` — two of these four read lowercase only until an outside audit on
# 2026-08-30 planted uppercase attributes and a `<STYLE>` element and got exit 0.
# An attribute can open a line — `<button` then `onclick=` on the next, at
# column 0 — or follow a `/`; a pattern that wanted whitespace before it read
# neither (outside audit, 2026-08-31). Text merely *mentioning* the words stays
# a finding on purpose: without parsing, reading it as safe is the wrong guess.
# The browser also lets the `=` sit on the line after the attribute's name
# (`onclick` ⏎ `="go()"`), reads `&#106;avascript:` in an `href` as `javascript:`
# (entities are decoded inside an attribute value — and only there: `&lt;script&gt;`
# in text is text), and treats a `<!--` that never closes as a comment to the end
# of the file. Each was misread by a per-line pattern on the raw text (self-audit,
# 2026-08-31). Patterns run on the whole file; a finding's line is the line its
# attribute name starts on.
PATTERNS = (
    (
        re.compile(r"(?:^|[\s\"'/])(?P<at>on\w+)\s*=", re.IGNORECASE | re.MULTILINE),
        "inline handler (on*=)",
    ),
    (re.compile(r"(?:^|[\s\"'/])(?P<at>style)\s*=", re.IGNORECASE | re.MULTILINE), "inline style="),
    (re.compile(r"(?P<at><style\b)", re.IGNORECASE), "inline <style>"),
    (re.compile(r"(?P<at>javascript:)", re.IGNORECASE), "javascript: URI"),
)
# A `<script` tag can close on a later line — `<script` then `type="module">` —
# and a per-line pattern that wanted the `>` on the same line read past it
# (outside audit, 2026-08-31). The tag is read to its `>` wherever that is.
SCRIPT_OPEN = re.compile(r"<script\b", re.IGNORECASE)
SRC_IN_TAG = re.compile(r"\bsrc\s*=", re.IGNORECASE)
COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)
ATTRIBUTE_VALUE = re.compile(r"""=\s*(?:"[^"]*"|'[^']*')""")
# What a browser serves as a template: the suffixes Jinja and Flask projects use.
TEMPLATE_SUFFIXES = frozenset({".html", ".htm", ".jinja", ".jinja2", ".j2"})


class _UnreadableError(Exception):
    """Bytes nobody can decode, or a tree nobody can walk. No verdict — never a clean one."""


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


def _without_comments(text: str) -> str:
    """Comments blanked, newlines kept — `<!-- onclick= -->` explains, it does not run."""
    return COMMENT.sub(lambda match: re.sub(r"[^\n]", " ", match.group()), text)


def _values_decoded(text: str) -> str:
    """Every quoted attribute value with its entities decoded, the way the browser reads
    it before it looks for a scheme — control characters dropped, so a `&#10;` cannot
    move a line, and the text outside the quotes untouched."""

    def decode(match: re.Match[str]) -> str:
        value = html.unescape(match.group())
        return re.sub(r"[\x00-\x1f]", "", value)

    return ATTRIBUTE_VALUE.sub(decode, text)


def _line(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def _script_lines(text: str) -> list[int]:
    """The line of every `<script` whose tag, read to its `>`, names no `src=`."""
    found: list[int] = []
    for match in SCRIPT_OPEN.finditer(text):
        close = text.find(">", match.end())
        tag = text[match.end() : close] if close != -1 else text[match.end() :]
        if not SRC_IN_TAG.search(tag):
            found.append(text.count("\n", 0, match.start()) + 1)
    return found


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


def _templates_dir(root: pathlib.Path) -> tuple[pathlib.Path | None, int]:
    """Where to look, or why there is nothing to look at — with the exit code for that."""
    config_path = root / "scaffold.json"
    # A project that has not configured the bundle is not a misuse — the paths
    # below fall back to their defaults, and a default that is not there reports
    # NA. A path the project *named* and does not have is the opposite case: a
    # broken configuration, reported as a finding — an outside audit on
    # 2026-08-29 planted a `scaffold.json` pointing at a Dockerfile that did not
    # exist beside a dirty one that did, and the answer was "nothing to check".
    config = _config(config_path)
    named, wrong = _configured_path(config, "templates_path", "app/templates")
    if named is None:
        print(f"csp-no-inline: {wrong}")
        return None, 1
    templates = root / named
    if not _inside(root, templates):
        print("csp-no-inline: " + OUTSIDE.format(key="templates_path", path=named))
        return None, 1
    if templates.is_dir():
        return templates, 0
    if "templates_path" in config:
        print(
            "csp-no-inline: "
            + MISCONFIGURED.format(key="templates_path", path=templates.relative_to(root))
        )
        return None, 1
    print(f"NA: no {templates.relative_to(root)} — nothing to check yet")
    return None, 0


def _judge(root: pathlib.Path) -> int:
    if not root.is_dir():
        # NA means "this project has nothing of that kind"; a root that is not
        # there has no project to say it about, and answering the second with
        # the first is a green over nothing (self-audit round 2, 2026-08-31).
        print(f"cannot read the tree: {_shown(root)} is not a directory", file=sys.stderr)
        return 2
    templates, code = _templates_dir(root)
    if templates is None:
        return code

    paths = [path for path in _walk(templates) if path.suffix in TEMPLATE_SUFFIXES]
    # A directory that is there and holds nothing this scanner reads is not a
    # clean project — it is a project this scanner cannot see, which the manifest's
    # own words forbid reporting as checked: "A rule the tool cannot check must not
    # look like a rule it checked." A Go project's `app/` came back `[ pass]`
    # (self-audit round 8, 2026-09-01).
    if not paths:
        print(f"NA: no template under {templates.relative_to(root)} — nothing to check yet")
        return 0

    findings: list[str] = []
    for path in paths:
        text = _values_decoded(_without_comments(_text(path)))
        hits = {
            (_line(text, match.start("at")), label)
            for pattern, label in PATTERNS
            for match in pattern.finditer(text)
        }
        hits |= {(lineno, "inline <script>") for lineno in _script_lines(text)}
        findings += [
            f"{_shown(path.relative_to(root))}:{lineno} {label}" for lineno, label in sorted(hits)
        ]

    for finding in findings:
        print(f"csp-no-inline: {finding}")
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
        print("usage: scan_templates_inline.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
