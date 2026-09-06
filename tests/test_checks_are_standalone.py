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
import ipaddress
import json
import pathlib
import shutil
import subprocess
import sys

import pytest
from bundle import (
    ALLOWED,
    CHECKS,
    SCANNERS,
    SHIPPED_ALL,
    SHIPPED_PYTHON,
    manifest,
    scanner_ids,
)

from verifiable_gates import preflight


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


NETWORK = frozenset(
    {
        "socket",
        "socketserver",
        "ssl",
        "selectors",
        "urllib",
        "http",
        "ftplib",
        "smtplib",
        "poplib",
        "imaplib",
        "nntplib",
        "telnetlib",
        "xmlrpc",
        "webbrowser",
    }
)


# The one file the installer writes that carries a network module, and the whole of what
# it does with it. Round 28 (2026-09-06) measured the holder below and found it walked
# `SHIPPED_PYTHON` — the nine scanners and the doctor, ten files — while the installer
# writes **thirteen**; and the one file outside its reach, `preflight.py`, is the one that
# imports `socket`. The sentence was true of what the test read and not of what shipped.
# What preflight does with it is a 0.25 s connect to `127.0.0.1` to ask whether a local
# service container is up before running a step that needs it. That is allowed, named
# here, and held to loopback by the test below — so the exception cannot quietly grow into
# a fetch.
LOOPBACK_ONLY = {"preflight.py": {"socket"}}


def network_imports(path: pathlib.Path) -> set[str]:
    """Every network module that file imports, by the name at the top of the import."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names if a.name.split(".")[0] in NETWORK}
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in NETWORK:
            found.add((node.module or "").split(".")[0])
    return found


@pytest.mark.parametrize("path", SHIPPED_ALL, ids=lambda p: p.name)
def test_a_shipped_file_opens_no_network(path: pathlib.Path) -> None:
    """The README says the bundle reaches nothing off the machine; this is its holder.

    Stdlib-only (above) still admits `urllib` and `socket`. A scanner that fetched a
    rule, a checksum or a template at run time would be a gate downloading its own
    judgement — and from the outside it would look exactly like a scanner that read
    the tree (round 23, A1). So the network modules are named and refused at the
    import, file by file, before any of them can be reached for.
    """
    found = network_imports(path)
    assert found <= LOOPBACK_ONLY.get(path.name, set()), (
        f"{path.name} imports {sorted(found - LOOPBACK_ONLY.get(path.name, set()))} — the"
        " bundle reaches nothing off the machine. The README says so beside the install"
        " commands, and this test is what holds the sentence. A file that genuinely needs a"
        " socket goes in LOOPBACK_ONLY above with what it does, and gets a test that holds"
        " it to loopback."
    )


def test_the_network_check_reads_every_python_file_the_bundle_ships() -> None:
    """A guard on the guard, and it was missing. The check above walked `SHIPPED_PYTHON` —
    the nine scanners and the doctor — while the installer writes **thirteen** files, and
    the one outside its reach was the one that imports `socket` (round 28, F3). So the list
    is read back off the decorator itself, not merely believed: pointing this check at a
    narrower list is now as red as shipping a file that fetches."""
    # pytest attaches `pytestmark` at decoration, and reading it is the whole point of
    # this guard: it checks the decorator rather than trusting it. Read with `getattr`
    # and a default, which needs no suppression — the ratchet on those is one-way, and a
    # guard is not worth spending it on.
    marks: list[pytest.MarkDecorator] = getattr(
        test_a_shipped_file_opens_no_network, "pytestmark", []
    )
    (parametrise,) = [mark for mark in marks if mark.name == "parametrize"]
    walked = {pathlib.Path(path).name for path in parametrise.args[1]}
    ships = {name.rsplit("/", 1)[-1] for name in manifest()["ship"] if name.endswith(".py")}
    assert walked == ships, (
        f"the bundle ships Python this check does not read: {sorted(ships - walked)}"
        f" (and reads what it does not ship: {sorted(walked - ships)})"
    )


def test_every_named_exception_is_one_that_file_really_needs() -> None:
    """`LOOPBACK_ONLY` is a permission, and a permission nobody trims is a hole with a
    comment in front of it. Every name in it must be a module that file actually imports,
    so the list cannot grow past what is true."""
    for name, allowed in LOOPBACK_ONLY.items():
        (path,) = [p for p in SHIPPED_ALL if p.name == name]
        assert network_imports(path) == allowed, (
            f"LOOPBACK_ONLY allows {sorted(allowed)} for {name}, which imports "
            f"{sorted(network_imports(path))}"
        )


def test_the_one_socket_the_bundle_ships_only_asks_about_this_machine() -> None:
    """`preflight.py` is allowed `socket` above. This is the other half of that permission:
    what it may connect to. Without it, `LOOPBACK_ONLY` would be a hole with a comment in
    front of it — the exception would cover any host at all (round 28, F3)."""
    host = ipaddress.ip_address(preflight.PROBE_HOST)
    assert host.is_loopback, (
        f"preflight probes {preflight.PROBE_HOST}, which is not loopback — the bundle's one"
        " socket asks whether a service is listening on this machine and nothing else"
    )
    assert preflight.PROBE_TIMEOUT_SECONDS <= 5, "a probe that waits is a probe that hangs a run"


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
    # An index that enforces nothing, next to a job that no gate claims.
    "gates.yaml": "version: 1\ngates: []\n",
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


# ---------------------------------------------------------------- one guard, ten copies
#
# `_shown` and its `_ESCAPED` table are copied into every scanner and into the doctor,
# because each is shipped alone into a project that has installed nothing and may import
# no helper. Round 21 measured what happens when one copy is weaker than the others: a
# file name carrying a newline turned one finding into two, and an ANSI escape erased the
# finding printed above it. A copy is only as good as the test that holds it (L-0119), so
# the *code* of the ten is compared here — the docstrings differ on purpose, since the
# doctor's says why it is a second layer.

GUARDED = [*SCANNERS, CHECKS.parent / "gates_doctor.py"]


def _guard_source(path: pathlib.Path) -> tuple[str, str]:
    """The escape table and the body of `_shown`, as AST rather than as text."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    table = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(getattr(t, "id", "") == "_ESCAPED" for t in node.targets)
    )
    shown = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_shown"
    )
    body = [
        n for n in shown.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))
    ]
    return ast.dump(table.value), ast.dump(ast.Module(body=body, type_ignores=[]))


def test_every_shipped_file_that_prints_a_finding_carries_the_guard() -> None:
    """A scanner added without it would print a name straight from the tree."""
    without = [p.name for p in GUARDED if "def _shown(" not in p.read_text(encoding="utf-8")]
    assert without == [], f"shipped files with no _shown: {without}"


@pytest.mark.parametrize("path", GUARDED[1:], ids=lambda p: p.name)
def test_the_copies_of_the_guard_are_the_same_code(path: pathlib.Path) -> None:
    """Byte-for-byte would be too strong (the docstrings differ) and "it exists" too weak:
    what has to match is the table of escapes and the two operations `_shown` performs."""
    assert _guard_source(path) == _guard_source(GUARDED[0]), (
        f"{path.name}'s copy of _shown differs from {GUARDED[0].name}'s. The duplication is "
        "deliberate — every copy changes in the same pull request, or one shipped file is "
        "weaker than the rest (self-audit round 21, 2026-09-03)."
    )


@pytest.mark.parametrize("path", GUARDED, ids=lambda p: p.name)
def test_the_guard_makes_one_line_of_whatever_it_is_given(path: pathlib.Path) -> None:
    """Run each copy for real, not read: the property is what it returns."""
    namespace: dict[str, object] = {}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)  # noqa: S102 — our own shipped file, read from disk
    shown = namespace["_shown"]
    assert callable(shown)

    for raw, why in [
        ("a\nb", "a newline forges a second finding line"),
        ("a\rb", "a carriage return rewrites the line on a terminal"),
        ("a\x1b[2K\x1b[Ab", "an ANSI escape erases the finding above"),
        ("a\x00b", "a NUL truncates the line for some readers"),
        ("a\x9bb", "a C1 byte is an escape to an 8-bit terminal"),
        ("a\u202eb", "a bidi override reverses what is read"),
        ("a\u200bb", "a zero-width space hides a difference"),
    ]:
        out = shown(raw)
        assert "\n" not in out, why
        assert "\r" not in out, why
        assert out.isprintable(), f"{why}: {out!r}"
        assert out.startswith("a"), out
        assert out.endswith("b"), out

    assert shown("docs/adr/0001-a.md") == "docs/adr/0001-a.md", "an ordinary name is untouched"
    # Not Thai, deliberately: `tests/test_language_policy.py` keeps Thai to the two
    # bilingual files, and a fixture is not a reason to make an exception.
    assert shown("informe-año.md") == "informe-año.md", "an accented letter is not escaped"
    assert shown("報告.md") == "報告.md", "letters outside Latin are not escaped either"
    assert shown("0001-\udcff.md") == "0001-\\xff.md", "round 15's property still holds"
