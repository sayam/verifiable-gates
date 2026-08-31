"""What the bundle ships, and the helpers that read it.

These constants and helpers are shared by more than one test file, and a shared
helper is normally a smell in a test suite. It earns its place here because every
one of them answers the same question — *what does this bundle actually install* —
and answering it twice is how two test files come to disagree about the bundle
they are both checking.

This is not a test file, so it has no gate of its own. What it holds is checked by
the files that import it.
"""

from __future__ import annotations

import ast
import json
import pathlib
import subprocess
import sys
from typing import Any

from verifiable_gates import install as install_module
from verifiable_gates import manifest as manifest_module

BUNDLE = pathlib.Path(__file__).resolve().parent.parent / "src" / "verifiable_gates"
CHECKS = BUNDLE / "checks"
DOCTOR = "tools/gates_doctor.py"

SCANNERS = sorted(path for path in CHECKS.glob("scan_*.py"))
# The doctor is shipped into `tools/` next to the scans and runs there, so it is
# under the same constraint. It is listed separately because it takes flags
# rather than a bare root, which the argv checks cannot assume.
SHIPPED_PYTHON = [*SCANNERS, BUNDLE / "gates_doctor.py"]
# Every Python file the bundle installs. `preflight.py` is here but not above:
# it is allowed a declared dependency, the others are not.
SHIPPED_ALL = [
    *SHIPPED_PYTHON,
    BUNDLE / "preflight.py",
    BUNDLE / "lint_commits.py",
    BUNDLE / "check_issue_handoff.py",
]

# Third-party imports would need installing; a relative import needs the package.
ALLOWED = frozenset(sys.stdlib_module_names)

# A shipped file's imports must be stdlib, or named here. The mapping lives in the
# manifest so a target project learns the requirement from the bundle rather than
# from a traceback in its own CI.
IMPORT_TO_DISTRIBUTION = {"yaml": "pyyaml"}


def scanner_ids() -> list[str]:
    return [path.name for path in SCANNERS]


def manifest() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((BUNDLE / "overlay.json").read_text(encoding="utf-8"))
    return loaded


def declared() -> dict[str, list[str]]:
    """What the manifest says each shipped file needs."""
    requires: dict[str, list[str]] = manifest().get("requires", {})
    return requires


def outside_stdlib(path: pathlib.Path) -> set[str]:
    """Every distribution a file imports that the standard library does not provide."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and not node.level:
            found.add((node.module or "").split(".")[0])
    return {name for name in found if name and name not in ALLOWED}


def do_install(dest: pathlib.Path, bundle: pathlib.Path) -> int:
    return install_module.install(dest, manifest_module.load(bundle / "overlay.json"), bundle)


def run_doctor(
    project: pathlib.Path, *args: str, one_stream: bool = False
) -> subprocess.CompletedProcess[str]:
    """The doctor as CI runs it; `one_stream` folds stderr into stdout the way a log does."""
    return subprocess.run(  # noqa: S603 — argv is built here, interpreter is sys.executable
        [sys.executable, str(project / DOCTOR), str(project), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT if one_stream else subprocess.PIPE,
        text=True,
        check=False,
        timeout=300,
    )
