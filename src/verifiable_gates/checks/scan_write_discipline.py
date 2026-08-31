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
import pathlib
import re
import sys
import tokenize

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


MISCONFIGURED = (
    "scaffold.json names {key} {path}, which is not there — a configured path that "
    "is missing is a broken configuration, not nothing to check"
)


def main(root: pathlib.Path) -> int:
    if not root.is_dir():
        # NA means "this project has nothing of that kind"; a root that is not
        # there has no project to say it about, and answering the second with
        # the first is a green over nothing (self-audit round 2, 2026-08-31).
        print(f"cannot read the tree: {root} is not a directory", file=sys.stderr)
        return 2
    config_path = root / "scaffold.json"
    # A project that has not configured the bundle is not a misuse — the paths
    # below fall back to their defaults, and a default that is not there reports
    # NA. A path the project *named* and does not have is the opposite case: a
    # broken configuration, reported as a finding — an outside audit on
    # 2026-08-29 planted a `scaffold.json` pointing at a Dockerfile that did not
    # exist beside a dirty one that did, and the answer was "nothing to check".
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    src = root / config.get("src_path", "app")
    if not src.is_dir():
        if "src_path" in config:
            print(
                "delete-means-soft-delete: "
                + MISCONFIGURED.format(key="src_path", path=src.relative_to(root))
            )
            return 1
        print(f"NA: no {src.relative_to(root)} — nothing to check yet")
        return 0
    patterns = config.get("purge_paths", ["app/purge.py"])

    findings: list[str] = []
    for path in sorted(src.rglob("*.py")):
        relative = path.relative_to(root)
        if any(fnmatch.fnmatch(str(relative), pattern) for pattern in patterns):
            continue
        text = path.read_text(encoding="utf-8")
        shown = text.splitlines()
        for lineno, line in enumerate(_code_lines(text), 1):
            if DELETE_CALL.search(line):
                findings.append(
                    f"{path.relative_to(root)}:{lineno} {shown[lineno - 1].strip()[:70]}"
                )

    for finding in findings:
        print(f"delete-means-soft-delete: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_write_discipline.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
