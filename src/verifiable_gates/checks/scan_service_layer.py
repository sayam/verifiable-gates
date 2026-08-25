"""gate: logic-knows-no-http — the service layer imports nothing from the request side.

Walks the AST of every file under `services_path`. Importing a request-side symbol
from the framework, or importing a user-session module, means the logic knows about
HTTP. (`current_app` is allowed — it is bound to the application, not to a request.)

exit 0 = clean or no such directory (N/A) · 1 = findings · 2 = called wrongly
"""

from __future__ import annotations

import ast
import json
import pathlib
import sys

FORBIDDEN_FLASK_SYMBOLS = {
    "request",
    "session",
    "g",
    "flash",
    "abort",
    "redirect",
    "render_template",
    "url_for",
    "jsonify",
    "make_response",
}
FORBIDDEN_MODULES = {"flask_login"}


def main(root: pathlib.Path) -> int:
    config = json.loads((root / "scaffold.json").read_text(encoding="utf-8"))
    services = root / config.get("services_path", "app/services")
    if not services.is_dir():
        print(f"NA: no {services.relative_to(root)} — nothing to check yet")
        return 0

    findings: list[str] = []
    for path in sorted(services.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            where = f"{path.relative_to(root)}:{getattr(node, 'lineno', 0)}"
            if isinstance(node, ast.ImportFrom) and node.module == "flask":
                bad = sorted({a.name for a in node.names} & FORBIDDEN_FLASK_SYMBOLS)
                if bad:
                    findings.append(f"{where} from flask import {', '.join(bad)}")
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                else:
                    names = [node.module or ""]
                bad = sorted({n.split(".")[0] for n in names} & FORBIDDEN_MODULES)
                if bad:
                    findings.append(f"{where} import {', '.join(bad)}")

    for finding in findings:
        print(f"logic-knows-no-http: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_service_layer.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
