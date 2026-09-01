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
import os
import pathlib
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


def _services_dir(root: pathlib.Path) -> tuple[pathlib.Path | None, int]:
    """Where to look, or why there is nothing to look at — with the exit code for that."""
    config_path = root / "scaffold.json"
    # A project that has not configured the bundle is not a misuse — the paths
    # below fall back to their defaults, and a default that is not there reports
    # NA. A path the project *named* and does not have is the opposite case: a
    # broken configuration, reported as a finding — an outside audit on
    # 2026-08-29 planted a `scaffold.json` pointing at a Dockerfile that did not
    # exist beside a dirty one that did, and the answer was "nothing to check".
    config = json.loads(_config_text(config_path)) if config_path.is_file() else {}
    services = root / config.get("services_path", "app/services")
    if not _inside(root, services):
        print(
            "logic-knows-no-http: "
            + OUTSIDE.format(key="services_path", path=config["services_path"])
        )
        return None, 1
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


def _config_text(path: pathlib.Path) -> str:
    """`scaffold.json`'s text, or the third answer. Every scanner routes the files it
    judges around undecodable bytes; the configuration beside them was still read bare
    and died of a traceback (self-audit round 3, 2026-09-01)."""
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as problem:
        print(f"cannot read the tree: {_shown(path)}: {problem}", file=sys.stderr)
        raise SystemExit(2) from problem


def main(root: pathlib.Path) -> int:
    if not root.is_dir():
        # NA means "this project has nothing of that kind"; a root that is not
        # there has no project to say it about, and answering the second with
        # the first is a green over nothing (self-audit round 2, 2026-08-31).
        print(f"cannot read the tree: {_shown(root)} is not a directory", file=sys.stderr)
        return 2
    services, code = _services_dir(root)
    if services is None:
        return code

    readable = sorted(services.rglob("*.py"))
    # A directory that is there and holds nothing this scanner reads is not a clean
    # project — it is one this scanner cannot see, which the manifest's own words
    # forbid reporting as checked: "A rule the tool cannot check must not look like
    # a rule it checked." A Go project came back `[ pass]` (round 8, 2026-09-01).
    if not readable:
        print(f"NA: no Python under {services.relative_to(root)} — nothing to check yet")
        return 0

    findings: list[str] = []
    for path in readable:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, ValueError) as error:
            # A file Python cannot parse is not a verdict either way — said plainly,
            # exit 2, the way every other unreadable input is refused (self-audit,
            # 2026-08-31: a traceback and exit 1, which reads as "findings").
            print(
                f"logic-knows-no-http: cannot read {_shown(path.relative_to(root))} — {error}",
                file=sys.stderr,
            )
            return 2
        findings += _findings_in(tree, _shown(path.relative_to(root)))

    for finding in findings:
        print(f"logic-knows-no-http: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_service_layer.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
