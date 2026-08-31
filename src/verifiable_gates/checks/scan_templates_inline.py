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
import pathlib
import re
import sys

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


MISCONFIGURED = (
    "scaffold.json names {key} {path}, which is not there — a configured path that "
    "is missing is a broken configuration, not nothing to check"
)


def main(root: pathlib.Path) -> int:
    config_path = root / "scaffold.json"
    # A project that has not configured the bundle is not a misuse — the paths
    # below fall back to their defaults, and a default that is not there reports
    # NA. A path the project *named* and does not have is the opposite case: a
    # broken configuration, reported as a finding — an outside audit on
    # 2026-08-29 planted a `scaffold.json` pointing at a Dockerfile that did not
    # exist beside a dirty one that did, and the answer was "nothing to check".
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    templates = root / config.get("templates_path", "app/templates")
    if not templates.is_dir():
        if "templates_path" in config:
            print(
                "csp-no-inline: "
                + MISCONFIGURED.format(key="templates_path", path=templates.relative_to(root))
            )
            return 1
        print(f"NA: no {templates.relative_to(root)} — nothing to check yet")
        return 0

    findings: list[str] = []
    paths = sorted(p for p in templates.rglob("*") if p.suffix in TEMPLATE_SUFFIXES)
    for path in paths:
        text = _values_decoded(_without_comments(path.read_text(encoding="utf-8")))
        hits = {
            (_line(text, match.start("at")), label)
            for pattern, label in PATTERNS
            for match in pattern.finditer(text)
        }
        hits |= {(lineno, "inline <script>") for lineno in _script_lines(text)}
        findings += [f"{path.relative_to(root)}:{lineno} {label}" for lineno, label in sorted(hits)]

    for finding in findings:
        print(f"csp-no-inline: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_templates_inline.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
