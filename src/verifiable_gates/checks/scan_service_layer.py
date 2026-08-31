"""gate: logic-knows-no-http — the service layer imports nothing from the request side.

Walks the AST of every file under `services_path`. Importing a request-side symbol
from the framework, or importing a user-session module, means the logic knows about
HTTP. (`current_app` is allowed — it is bound to the application, not to a request.)

The symbol arrives by more roads than `from flask import request`: `import flask`
and then `flask.request.args`, `from flask import *`, `from flask.globals import
request`, and werkzeug's own request side (`werkzeug.wrappers`, `.local`,
`.exceptions`, `.routing` — not `werkzeug.security`, which a service may use to
hash a password). Each road was open (self-audit, 2026-08-31, all four exited 0).

exit 0 = clean or no such directory (N/A) · 1 = findings · 2 = called wrongly

Role: decider — it answers pass or fail with an exit code, and it ships as a
standalone file; its evidence is a planted violation and a clean tree in
`tests/test_checks_behaviour.py`.
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
FORBIDDEN_MODULES = {
    "flask_login",
    "werkzeug.wrappers",
    "werkzeug.local",
    "werkzeug.exceptions",
    "werkzeug.routing",
}


def _forbidden_module(name: str) -> str | None:
    """The forbidden module `name` is or sits under, if any."""
    return next((m for m in FORBIDDEN_MODULES if name == m or name.startswith(m + ".")), None)


def _flask_aliases(tree: ast.AST) -> set[str]:
    """The names `import flask [as x]` binds in this file."""
    return {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "flask"
    }


def _findings_in(tree: ast.AST, where: str) -> list[str]:
    """Every road a request-side symbol takes into one file."""
    found: list[str] = []
    aliases = _flask_aliases(tree)
    for node in ast.walk(tree):
        at = f"{where}:{getattr(node, 'lineno', 0)}"
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "flask":
            names = {a.name for a in node.names}
            bad = sorted(names & FORBIDDEN_FLASK_SYMBOLS) + (["*"] if "*" in names else [])
            if bad:
                found.append(f"{at} from {node.module} import {', '.join(bad)}")
        if isinstance(node, ast.Import | ast.ImportFrom):
            modules = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            bad = sorted({m for n in modules if (m := _forbidden_module(n))})
            if bad:
                found.append(f"{at} import {', '.join(bad)}")
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in aliases
            and node.attr in FORBIDDEN_FLASK_SYMBOLS
        ):
            found.append(f"{at} {node.value.id}.{node.attr}")
    return found


MISCONFIGURED = (
    "scaffold.json names {key} {path}, which is not there — a configured path that "
    "is missing is a broken configuration, not nothing to check"
)


def _services_dir(root: pathlib.Path) -> tuple[pathlib.Path | None, int]:
    """Where to look, or why there is nothing to look at — with the exit code for that."""
    config_path = root / "scaffold.json"
    # A project that has not configured the bundle is not a misuse — the paths
    # below fall back to their defaults, and a default that is not there reports
    # NA. A path the project *named* and does not have is the opposite case: a
    # broken configuration, reported as a finding — an outside audit on
    # 2026-08-29 planted a `scaffold.json` pointing at a Dockerfile that did not
    # exist beside a dirty one that did, and the answer was "nothing to check".
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    services = root / config.get("services_path", "app/services")
    if services.is_dir():
        return services, 0
    if "services_path" in config:
        print(
            "logic-knows-no-http: "
            + MISCONFIGURED.format(key="services_path", path=services.relative_to(root))
        )
        return None, 1
    print(f"NA: no {services.relative_to(root)} — nothing to check yet")
    return None, 0


def main(root: pathlib.Path) -> int:
    services, code = _services_dir(root)
    if services is None:
        return code

    findings: list[str] = []
    for path in sorted(services.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, ValueError) as error:
            # A file Python cannot parse is not a verdict either way — said plainly,
            # exit 2, the way every other unreadable input is refused (self-audit,
            # 2026-08-31: a traceback and exit 1, which reads as "findings").
            print(
                f"logic-knows-no-http: cannot read {path.relative_to(root)} — {error}",
                file=sys.stderr,
            )
            return 2
        findings += _findings_in(tree, str(path.relative_to(root)))

    for finding in findings:
        print(f"logic-knows-no-http: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_service_layer.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
