"""gate: no-debug-entrypoint — an entrypoint cannot open a debug console, even run wrongly.

A dev server's debug console executes code from the browser, and entrypoint files
are exactly the ones that get copied into an image. This reads the **AST, not a
regex**, because these files like to explain in a comment or docstring why they do
*not* set `debug=True` — the same characters, the opposite meaning. Dogfooding
against the reference implementation caught that false positive on day one.

`debug=True` is one spelling of five. Flask's `run()` does `self.debug = bool(debug)`
and hands werkzeug `use_debugger=self.debug`, so `debug=1`, `app.debug = True` before
the run, `app.config["DEBUG"] = True`, `run(use_debugger=True)` and `run(**{"debug":
True})` all open the same console — and all five passed a scanner that read only the
literal keyword (self-audit, 2026-08-31, each proved live against Flask 3.1.3). Every
spelling with a real constant behind it is judged; a value computed at runtime is not,
because a scanner that guesses at `os.environ` is a scanner that lies.

exit 0 = clean or N/A · 1 = findings · 2 = called wrongly

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


DEBUG_KEYWORDS = ("debug", "use_debugger")


def _truthy_constant(node: ast.AST) -> bool:
    """A literal the interpreter would call true — `True`, `1`, `"yes"`; nothing computed."""
    return isinstance(node, ast.Constant) and bool(node.value) and node.value is not Ellipsis


def _run_call_debug(node: ast.Call) -> tuple[int, str] | None:
    """`<x>.run(debug=1)`, `.run(use_debugger=True)` or `.run(**{"debug": True})`."""
    if not (isinstance(node.func, ast.Attribute) and node.func.attr == "run"):
        return None
    for keyword in node.keywords:
        if keyword.arg in DEBUG_KEYWORDS and _truthy_constant(keyword.value):
            return node.lineno, f".run({keyword.arg}={ast.unparse(keyword.value)})"
        if keyword.arg is None and isinstance(keyword.value, ast.Dict):
            for key, value in zip(keyword.value.keys, keyword.value.values, strict=True):
                if (
                    isinstance(key, ast.Constant)
                    and key.value in DEBUG_KEYWORDS
                    and _truthy_constant(value)
                ):
                    return node.lineno, f".run(**{{{key.value!r}: {ast.unparse(value)}}})"
    return None


def _assignment_debug(node: ast.Assign) -> tuple[int, str] | None:
    """`<x>.debug = True` or `<x>.config["DEBUG"] = True` — the switch flipped before the run."""
    if not _truthy_constant(node.value):
        return None
    for target in node.targets:
        if isinstance(target, ast.Attribute) and target.attr == "debug":
            return node.lineno, f".debug = {ast.unparse(node.value)}"
        if (
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Attribute)
            and target.value.attr == "config"
            and isinstance(target.slice, ast.Constant)
            and target.slice.value == "DEBUG"
        ):
            return node.lineno, f'.config["DEBUG"] = {ast.unparse(node.value)}'
    return None


def _shape(node: ast.AST) -> tuple[int, str] | None:
    if isinstance(node, ast.Call):
        return _run_call_debug(node)
    if isinstance(node, ast.Assign):
        return _assignment_debug(node)
    return None


def _debug_findings(tree: ast.AST) -> list[tuple[int, str]]:
    """Every line that opens the debugger with a real constant — and how it spells it."""
    return sorted(found for node in ast.walk(tree) if (found := _shape(node)))


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
    config_path = root / "scaffold.json"
    # A project that has not configured the bundle is not a misuse — the paths
    # below fall back to their defaults, and a default that is not there reports
    # NA. A path the project *named* and does not have is the opposite case: a
    # broken configuration, reported as a finding — an outside audit on
    # 2026-08-29 planted a `scaffold.json` pointing at a Dockerfile that did not
    # exist beside a dirty one that did, and the answer was "nothing to check".
    config = json.loads(_config_text(config_path)) if config_path.is_file() else {}
    names = config.get("entrypoints", ["run.py", "wsgi.py", "app.py", "main.py"])
    outside = [n for n in names if not _inside(root, root / n)]
    if outside:
        print("no-debug-entrypoint: " + OUTSIDE.format(key="entrypoints", path=outside))
        return 1
    present = [root / n for n in names if (root / n).is_file()]
    if not present:
        # The list is candidates, so one missing name is fine; none present when
        # the project wrote the list itself is a broken configuration.
        if "entrypoints" in config:
            print("no-debug-entrypoint: " + MISCONFIGURED.format(key="entrypoints", path=names))
            return 1
        print("NA: none of the declared entrypoints exist — nothing to check yet")
        return 0

    findings: list[str] = []
    for path in present:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, ValueError) as error:
            # A file Python cannot parse is not a verdict either way — said plainly,
            # exit 2, the way every other unreadable input is refused (self-audit,
            # 2026-08-31: a traceback and exit 1, which reads as "findings").
            print(
                f"no-debug-entrypoint: cannot read {path.relative_to(root)} — {error}",
                file=sys.stderr,
            )
            return 2
        findings += [
            f"{path.relative_to(root)}:{line} {shape}" for line, shape in _debug_findings(tree)
        ]
    for finding in findings:
        print(f"no-debug-entrypoint: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_entrypoint_debug.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
