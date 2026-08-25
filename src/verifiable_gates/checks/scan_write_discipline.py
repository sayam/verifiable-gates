"""gate: delete-means-soft-delete — a real delete outside the declared purge modules is a finding.

Deleting for real belongs where the project declared it (`purge_paths`, which takes
globs); everywhere else has to be a soft delete. This matches the ORM's
`session.delete(` rather than every `.delete(`, because a cache client's
`.delete(key)` is not the removal of somebody's data — dogfooding against the
reference implementation caught that false positive.

The deeper cases (bulk operations, Core DML, raw SQL) belong to the project's own
test suite. This scan is the first layer, not the only one.

exit 0 = clean or N/A · 1 = findings · 2 = called wrongly
"""

from __future__ import annotations

import fnmatch
import json
import pathlib
import re
import sys

DELETE_CALL = re.compile(r"\bsession\.delete\s*\(|synchronize_session")


def main(root: pathlib.Path) -> int:
    config = json.loads((root / "scaffold.json").read_text(encoding="utf-8"))
    src = root / config.get("src_path", "app")
    if not src.is_dir():
        print(f"NA: no {src.relative_to(root)} — nothing to check yet")
        return 0
    patterns = config.get("purge_paths", ["app/purge.py"])

    findings: list[str] = []
    for path in sorted(src.rglob("*.py")):
        relative = path.relative_to(root)
        if any(fnmatch.fnmatch(str(relative), pattern) for pattern in patterns):
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if DELETE_CALL.search(line) and not line.lstrip().startswith("#"):
                findings.append(f"{path.relative_to(root)}:{lineno} {line.strip()[:70]}")

    for finding in findings:
        print(f"delete-means-soft-delete: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_write_discipline.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
