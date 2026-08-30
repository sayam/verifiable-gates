"""gate: csp-no-inline — templates carry no inline handler, style, or script.

Under a `'self'`-only Content Security Policy the browser blocks these **silently**;
there is no server-side error to notice. So the check has to read the files rather
than wait for a symptom.

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

# HTML is case-insensitive and the browser blocks `ONCLICK=` exactly as it blocks
# `onclick=` — two of these four read lowercase only until an outside audit on
# 2026-08-30 planted uppercase attributes and a `<STYLE>` element and got exit 0.
PATTERNS = (
    (re.compile(r"\son\w+\s*=", re.IGNORECASE), "inline handler (on*=)"),
    (re.compile(r"\sstyle\s*=", re.IGNORECASE), "inline style="),
    (re.compile(r"<style[\s>]", re.IGNORECASE), "inline <style>"),
    (re.compile(r"<script(?![^>]*\bsrc\s*=)[^>]*>", re.IGNORECASE), "inline <script>"),
    (re.compile(r"javascript:", re.IGNORECASE), "javascript: URI"),
)


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
    for path in sorted(templates.rglob("*.html")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            findings += [
                f"{path.relative_to(root)}:{lineno} {label}"
                for pattern, label in PATTERNS
                if pattern.search(line)
            ]

    for finding in findings:
        print(f"csp-no-inline: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_templates_inline.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
