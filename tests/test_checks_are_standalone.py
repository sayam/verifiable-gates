"""Every scanner has to survive being copied out of here on its own.

`install.py` puts a single scanner file into a project that has installed nothing
yet, where it runs under a bare `python3`. That works only while each file imports
**stdlib only** and nothing from this package. The property is invisible in normal
use — the tests here import the modules, so a relative import or a shared helper
would pass locally and fail in every target project instead.

This is exactly the shape of change a well-meaning refactor makes: three scanners
repeat six lines of argv handling, someone lifts it into `checks/_cli.py`, the
suite stays green, and every copied file breaks. So the property is checked
directly, from the AST, for every file in the directory — a list of names would
go stale the first time somebody adds a scanner.
"""

from __future__ import annotations

import ast
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "src" / "verifiable_gates"
CHECKS = PACKAGE / "checks"
SCANNERS = sorted(p for p in CHECKS.glob("scan_*.py"))
# The doctor is shipped into `tools/` next to the scans and runs there, so it is
# under the same constraint. It is listed separately because it takes flags
# rather than a bare root, which the argv checks below cannot assume.
SHIPPED_PYTHON = [*SCANNERS, PACKAGE / "gates_doctor.py"]
# Third-party imports would need installing; a relative import needs the package.
ALLOWED = frozenset(sys.stdlib_module_names)


def scanner_ids() -> list[str]:
    return [path.name for path in SCANNERS]


def test_there_are_scanners_to_check() -> None:
    """A guard on the guard: an empty glob would make every test below vacuous."""
    assert SCANNERS, f"no scan_*.py found under {CHECKS} — the checks below would prove nothing"


@pytest.mark.parametrize("path", SHIPPED_PYTHON, ids=lambda p: p.name)
def test_a_shipped_file_imports_stdlib_only(path: pathlib.Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    outside = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            outside += [
                a.name.split(".")[0] for a in node.names if a.name.split(".")[0] not in ALLOWED
            ]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                outside.append(f"relative import (level {node.level})")
            elif (node.module or "").split(".")[0] not in ALLOWED:
                outside.append(node.module or "?")
    assert not outside, (
        f"{path.name} imports {sorted(set(outside))}, which a copied file cannot resolve. "
        "Scanners are shipped one file at a time into projects that have installed "
        "nothing — keep the duplication rather than sharing a helper."
    )


@pytest.mark.parametrize("path", SCANNERS, ids=scanner_ids())
def test_a_scanner_can_be_run_as_a_file(path: pathlib.Path) -> None:
    """It needs `main(root)` and a `__main__` block, or copying it out gives you a no-op."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert "main" in functions, f"{path.name} has no main() — nothing to call"

    has_main_block = any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
        for node in tree.body
    )
    assert has_main_block, (
        f"{path.name} has no `if __name__ == '__main__'` block — copied out and run "
        "directly it would do nothing and exit 0, which reads as 'clean'."
    )


# ---------------------------------------------------------------- run it for real
#
# The checks above read the source. These copy a scanner somewhere the package
# cannot be imported from and run it with the interpreter, which is the claim
# itself rather than a proxy for it: this is what `install.py` does to a target
# project, and what that project's CI then executes.

# A tree that every scanner is either unhappy about or has nothing to say about,
# so one fixture serves all of them: a floating action tag, an unpinned base
# image, a debug entrypoint, an unpinned pip install, and a hard delete.
DIRTY_TREE = {
    ".github/workflows/ci.yml": (
        "jobs:\n  a:\n    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - run: pip install ruff\n"
    ),
    "Dockerfile": "FROM python:3.13-slim\n",
    "run.py": "app = object()\napp.run(debug=True)\n",
    "app/services/todos.py": "from flask import request\n",
    "app/templates/x.html": '<button onclick="go()">go</button>\n',
    "app/routes.py": "db.session.delete(row)\n",
    "docs/adr/0001-a.md": "# 0001\n",
}
CONFIG = {
    "src_path": "app",
    "services_path": "app/services",
    "templates_path": "app/templates",
    "adr_path": "docs/adr",
    "entrypoints": ["run.py"],
    "dockerfiles": ["Dockerfile"],
    "purge_paths": ["app/purge.py"],
}


def _project(root: pathlib.Path) -> pathlib.Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "scaffold.json").write_text(json.dumps(CONFIG), encoding="utf-8")
    for name, text in DIRTY_TREE.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _run(scanner: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — argv is built here, interpreter is sys.executable
        [sys.executable, str(scanner), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


@pytest.mark.parametrize("path", SCANNERS, ids=scanner_ids())
def test_a_copied_scanner_runs_and_reports(tmp_path: pathlib.Path, path: pathlib.Path) -> None:
    """Copied out, away from the package, it still finds what it is for."""
    elsewhere = tmp_path / "installed"
    elsewhere.mkdir()
    copied = shutil.copy2(path, elsewhere / path.name)
    project = _project(tmp_path / "project")

    done = _run(pathlib.Path(copied), str(project))
    assert done.returncode == 1, (
        f"{path.name} exited {done.returncode} on a tree that violates it "
        f"(stderr: {done.stderr.strip()[:200]})"
    )
    assert done.stdout.strip(), "it exited 1 without saying what it found"


@pytest.mark.parametrize("path", SCANNERS, ids=scanner_ids())
def test_a_copied_scanner_refuses_to_guess_its_argument(
    tmp_path: pathlib.Path, path: pathlib.Path
) -> None:
    """Exit 2 for a misuse, never 0 — a wrong call must not be filed as a pass."""
    elsewhere = tmp_path / "installed"
    elsewhere.mkdir()
    copied = pathlib.Path(shutil.copy2(path, elsewhere / path.name))

    assert _run(copied).returncode == 2, "no argument should be a misuse, not a clean run"
    assert _run(copied, "a", "b").returncode == 2, "too many arguments should be a misuse"
