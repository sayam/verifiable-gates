"""gate: no-debug-entrypoint — an entrypoint cannot open a debug console, even run wrongly.

A dev server's debug console executes code from the browser, and entrypoint files
are exactly the ones that get copied into an image. This reads the **AST, not a
regex**, because these files like to explain in a comment or docstring why they do
*not* set `debug=True` — the same characters, the opposite meaning. Dogfooding
against the reference implementation caught that false positive on day one.

exit 0 = clean or N/A · 1 = findings · 2 = called wrongly

Role: decider — it answers pass or fail with an exit code, and it ships as a
standalone file; its evidence is a planted violation and a clean tree in
`tests/test_checks_behaviour.py`.
"""

from __future__ import annotations

import ast
import json
import pathlib
import sys


def _debug_run_calls(tree: ast.AST) -> list[int]:
    """Lines holding `<anything>.run(..., debug=True, ...)` — real constants only."""
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and any(
            keyword.arg == "debug"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        )
    ]


def main(root: pathlib.Path) -> int:
    config_path = root / "scaffold.json"
    # A project that has not configured the bundle is not a misuse — the paths
    # below fall back to their defaults, and a path that is not there reports NA.
    # Reading it unguarded turned "not configured yet" into a traceback.
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    names = config.get("entrypoints", ["run.py", "wsgi.py", "app.py", "main.py"])
    present = [root / n for n in names if (root / n).is_file()]
    if not present:
        print("NA: none of the declared entrypoints exist — nothing to check yet")
        return 0

    findings: list[str] = []
    for path in present:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        findings += [
            f"{path.relative_to(root)}:{line} .run(debug=True)" for line in _debug_run_calls(tree)
        ]
    for finding in findings:
        print(f"no-debug-entrypoint: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_entrypoint_debug.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
