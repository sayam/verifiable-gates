"""gate: csp-no-inline — templates carry no inline handler, style, or script.

Under a `'self'`-only Content Security Policy the browser blocks these **silently**;
there is no server-side error to notice. So the check has to read the files rather
than wait for a symptom.

exit 0 = clean or N/A · 1 = findings · 2 = called wrongly
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

PATTERNS = (
    (re.compile(r"\son\w+\s*="), "inline handler (on*=)"),
    (re.compile(r"\sstyle\s*="), "inline style="),
    (re.compile(r"<script(?![^>]*\bsrc\s*=)[^>]*>", re.IGNORECASE), "inline <script>"),
    (re.compile(r"javascript:", re.IGNORECASE), "javascript: URI"),
)


def main(root: pathlib.Path) -> int:
    config = json.loads((root / "scaffold.json").read_text(encoding="utf-8"))
    templates = root / config.get("templates_path", "app/templates")
    if not templates.is_dir():
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
