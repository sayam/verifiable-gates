"""Every number a threshold is held against comes from the thing itself.

A reader that guesses, or that quietly reports zero when it cannot answer, turns
a red check into a green one at exactly the moment the check was needed. So each
reader here is tested twice over: that it reports the truth when it can see it,
and that it is **loud** when it cannot.

The suppression counter gets more attention than the rest because its total
cannot prove its own logic — a test that watches only the count stays green
through a change that stops telling "which rule is off" from "why it is off",
and those are the two questions the count exists to keep apart.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from typing import TYPE_CHECKING

import pytest

from verifiable_gates import measure

if TYPE_CHECKING:
    import pathlib

# Written without the leading marker so the counter under test does not count
# this file's own examples. Assembled at use, which is the same trick the module
# itself has to use in its prose.
HASH = "#"


def write(root: pathlib.Path, name: str, body: str) -> pathlib.Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def fake_tool(monkeypatch: pytest.MonkeyPatch, stdout: str, code: int = 0) -> list[list[str]]:
    """Answer for whatever binary the reader runs, and record what it asked for.

    Patched at `subprocess.run` rather than at the module's own wrapper, so every
    test here drives the real one — the wrapper is where the timeout and the
    binary lookup live, and a fake standing in for it would leave both unproven.
    """
    seen: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(argv)
        return subprocess.CompletedProcess(argv, code, stdout, "no data collected")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    return seen


# --------------------------------------------------- switched-off checkers


@pytest.mark.parametrize(
    ("line", "is_suppression", "has_reason"),
    [
        (f"x = 1  {HASH} noqa: F401 — the import is the seam being tested", True, True),
        (f"x = 1  {HASH} noqa: F401", True, False),
        (f"x = 1  {HASH} noqa", True, False),
        (f"x = 1  {HASH} noqa: E402,F401 — two at once", True, True),
        (f"x = 1  {HASH} type: ignore[attr-defined] — the stub is wrong here", True, True),
        (f"x = 1  {HASH} type: ignore", True, False),
        (f"x = 1  {HASH} a plain comment", False, False),
        ("x = 1", False, False),
    ],
)
def test_a_line_is_classified_by_whether_it_says_why(
    line: str, *, is_suppression: bool, has_reason: bool
) -> None:
    """Two questions, not one — and a bare code answers only the first."""
    assert measure.classify_suppression(line) == (is_suppression, has_reason)


def test_punctuation_alone_is_not_a_reason() -> None:
    """A dash after the code is decoration; a register accepting it would count nothing."""
    _, has_reason = measure.classify_suppression(f"x = 1  {HASH} noqa: F401 —")

    assert not has_reason


def test_the_counts_come_from_the_lines_themselves(tmp_path: pathlib.Path) -> None:
    write(
        tmp_path,
        "a.py",
        f"""
        one = 1  {HASH} noqa: F401 — kept for the side effect
        two = 2  {HASH} noqa: F401
        three = 3
        """,
    )
    write(tmp_path, "b.py", f"four = 4  {HASH} type: ignore\n")

    counts = measure.suppression_counts(tmp_path, ("*.py",))

    assert counts == {"suppressions": 3, "suppressions_without_reason": 2}


def test_a_skipped_name_and_a_skipped_directory_are_both_honoured(
    tmp_path: pathlib.Path,
) -> None:
    """Generated files and excluded trees are named once, not once per line.

    The two patterns overlap on purpose: a file matched twice must be counted
    once, or a ceiling jumps on a change that switched nothing off.
    """
    write(tmp_path, "real.py", f"a = 1  {HASH} noqa: F401\n")
    write(tmp_path, "generated.py", f"b = 1  {HASH} noqa: F401\n")
    write(tmp_path, "vendor/c.py", f"c = 1  {HASH} noqa: F401\n")

    counts = measure.suppression_counts(
        tmp_path, ("*.py", "**/*.py"), skip=("generated.py", "vendor")
    )

    assert counts["suppressions"] == 1


# ------------------------------------------------------- a measurement file


def test_a_percentage_is_read_from_the_report_that_was_written(tmp_path: pathlib.Path) -> None:
    report = tmp_path / "cov.json"
    report.write_text(json.dumps({"totals": {"percent_covered": 62.11}}), encoding="utf-8")

    assert measure.coverage_json_percent(report) == pytest.approx(62.11)


def test_a_missing_measurement_is_loud(tmp_path: pathlib.Path) -> None:
    """No file means the step before it did not run — louder than passing in silence."""
    with pytest.raises(RuntimeError, match="has not run"):
        measure.coverage_json_percent(tmp_path / "absent.json")


def test_the_caller_supplies_the_command_that_would_produce_it(tmp_path: pathlib.Path) -> None:
    """How to make the file is the project's business, so the hint is the caller's."""
    with pytest.raises(RuntimeError, match="run the suite with --cov"):
        measure.coverage_json_percent(tmp_path / "absent.json", hint=" — run the suite with --cov")


# --------------------------------------------------------- a register in code


def test_a_register_kept_as_a_list_is_counted_without_importing_it(
    tmp_path: pathlib.Path,
) -> None:
    """Importing would drag in whatever else the module does at import time."""
    module = write(
        tmp_path,
        "register.py",
        """
        import sys

        sys.exit("importing this file would end the process")

        RULES = [
            ("a", "one"),
            ("b", "two"),
            ("c", "three"),
        ]
        """,
    )

    assert measure.list_literal_length(module, "RULES") == 3


def test_a_register_that_is_not_there_is_loud(tmp_path: pathlib.Path) -> None:
    module = write(tmp_path, "register.py", "OTHER = [1, 2]\n")

    with pytest.raises(RuntimeError, match="cannot find the register"):
        measure.list_literal_length(module, "RULES")


def test_a_register_that_stopped_being_a_literal_is_loud(tmp_path: pathlib.Path) -> None:
    """A register built at runtime cannot be counted from the text, and zero would lie."""
    module = write(tmp_path, "register.py", "RULES = build_them()\n")

    with pytest.raises(TypeError, match="not a literal sequence"):
        measure.list_literal_length(module, "RULES")


# ------------------------------------------------------ mypy's strict list


STRICT_CONFIG = """
[tool.mypy]
python_version = "3.11"

[[tool.mypy.overrides]]
module = ["other.*"]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = ["app.services.*", "app.audit"]
disallow_untyped_defs = true
"""


def test_the_strict_list_is_counted_from_the_files_that_exist(tmp_path: pathlib.Path) -> None:
    """One pattern covers many modules, so counting the list's lines measures the config.

    A floor set from the length of the list would move when somebody merged two
    patterns into one, and not move when a module was added — a number about the
    shape of the config rather than about the strictness of the project.
    """
    write(tmp_path, "pyproject.toml", STRICT_CONFIG)
    for name in ("app/services/todos.py", "app/services/teams.py", "app/audit.py", "app/tz.py"):
        write(tmp_path, name, "")

    counted = measure.strict_modules(tmp_path, tmp_path / "pyproject.toml", tmp_path / "app")

    assert counted == 3, "two patterns, three modules matched, one outside"


def test_a_package_init_is_matched_by_the_package_name(tmp_path: pathlib.Path) -> None:
    """`app/services/__init__.py` is the module `app.services`, not `app.services.__init__`."""
    write(tmp_path, "pyproject.toml", STRICT_CONFIG.replace('"app.services.*"', '"app.services"'))
    write(tmp_path, "app/services/__init__.py", "")
    write(tmp_path, "app/services/todos.py", "")

    counted = measure.strict_modules(tmp_path, tmp_path / "pyproject.toml", tmp_path / "app")

    assert counted == 1


def test_a_skipped_part_keeps_a_tree_out_of_the_count(tmp_path: pathlib.Path) -> None:
    """A tree mypy itself excludes must not move the number by being copied in."""
    write(tmp_path, "pyproject.toml", STRICT_CONFIG.replace('"app.services.*"', '"app.*"'))
    write(tmp_path, "app/tz.py", "")
    write(tmp_path, "app/plugins/enhancements/provide.py", "")

    counted = measure.strict_modules(
        tmp_path,
        tmp_path / "pyproject.toml",
        tmp_path / "app",
        skip_parts=("__pycache__", "enhancements"),
    )

    assert counted == 1


def test_a_config_with_no_strict_list_is_loud(tmp_path: pathlib.Path) -> None:
    """No strict list means the shape changed — zero would read as "none are strict"."""
    write(tmp_path, "pyproject.toml", "[tool.mypy]\noverrides = []\n")

    with pytest.raises(RuntimeError, match="cannot find mypy's strict list"):
        measure.strict_modules(tmp_path, tmp_path / "pyproject.toml", tmp_path / "app")


# ------------------------------------------------------------- running a tool


def test_coverage_is_read_by_running_the_tool(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The figure comes from the coverage data, never from a number written down."""
    seen = fake_tool(monkeypatch, "97.18\n")

    assert measure.coverage_total(tmp_path) == pytest.approx(97.18)
    assert "--precision=2" in seen[0], "a whole number swallows the slack this exists to see"


def test_coverage_with_no_data_behind_it_is_loud(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_tool(monkeypatch, "", code=1)

    with pytest.raises(RuntimeError, match="cannot read coverage"):
        measure.coverage_total(tmp_path)


def test_coverage_that_answered_with_prose_is_loud(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exit zero and a non-number is the shape of a tool that changed its output."""
    fake_tool(monkeypatch, "No data\n")

    with pytest.raises(RuntimeError, match="cannot read coverage"):
        measure.coverage_total(tmp_path)


# What the tool really prints: a table of counts, then the verdict. The counts
# come first, so a reader taking "the first number" gets the wrong one.
INTERROGATE_OUTPUT = """\
|      Name       | Total | Miss | Cover | Cover% |
|-----------------|-------|------|-------|--------|
| app/tz.py       |    39 |    2 |    37 |  94.9% |
| TOTAL           |   612 |   88 |   524 |  85.7% |
RESULT: PASSED (minimum: 85.0%, actual: 85.70%)
"""


def test_docstring_coverage_is_read_from_the_tool_s_own_label(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anchored on the tool's own label, not on "the first number in the output".

    Its report is a table of counts followed by the verdict, so a loose reader
    finds a row total long before it reaches the figure it was asked for — and
    reports that one with the same confidence.
    """
    seen = fake_tool(monkeypatch, INTERROGATE_OUTPUT)

    assert measure.docstring_coverage(tmp_path, "app") == pytest.approx(85.70)
    assert seen[0][1] == "app", "the package asked about has to reach the command"


def test_docstring_coverage_that_no_longer_prints_a_figure_is_loud(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_tool(monkeypatch, "PASSED\n")

    with pytest.raises(RuntimeError, match="output format has changed"):
        measure.docstring_coverage(tmp_path, "app")


def test_a_command_declares_a_time_budget(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a timeout the wait is forever, which in CI is a job that never ends."""
    budget: dict[str, object] = {}

    def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        budget.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, "97.18\n", "")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    measure.coverage_total(tmp_path)

    assert budget["timeout"] == measure.TOOL_TIMEOUT_SECONDS
    assert budget["cwd"] == tmp_path, "the reader has to run where the project is"


def test_a_tool_that_is_not_installed_is_named(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Which binary is missing is the whole of the answer a reader needs."""
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    with pytest.raises(RuntimeError, match="coverage is not on this machine"):
        measure.coverage_total(tmp_path)


def test_the_reader_actually_reaches_a_real_process(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Proof the wrapper starts something, rather than only shaping arguments.

    Every other test here replaces `subprocess.run`, so on its own the suite
    proves the arguments and never proves a process. Here a real executable stands
    in for the tool and the figure has to come back through its actual stdout.
    """
    stub = tmp_path / "stub-coverage"
    stub.write_text("#!/bin/sh\necho 97.18\n", encoding="utf-8")
    stub.chmod(0o755)
    monkeypatch.setattr(shutil, "which", lambda _name: str(stub))

    assert measure.coverage_total(tmp_path) == pytest.approx(97.18)
