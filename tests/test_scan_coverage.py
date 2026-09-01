"""A scan that found nothing and a scan that ran on nothing look identical.

Every test here is about a way a run can pass green while checking less than it
claims — a directory that dropped out, a rule set that never loaded, a rule the
tool could not parse, an error it swallowed. None of those change the exit code,
and none of them change what the output looks like.

The measurement is a set difference rather than a floor, because a floor catches
"everything vanished" and misses "one directory vanished" — and the second is the
shape the bug actually took in the reference implementation: 61 of 136 files
silently excluded by a default nobody had read.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import pathlib

from verifiable_gates import scan_coverage

EVERYTHING = {"app/a.py", "app/b.py", "tests/test_a.py"}


def only(found: list[str]) -> str:
    assert len(found) == 1, f"expected exactly one problem, got {found}"
    return found[0]


def clean(scanned: set[str]) -> scan_coverage.Report:
    return scan_coverage.Report(scanned=scanned, rules=42)


# ------------------------------------------------------- what was not read


def test_a_run_that_read_everything_is_quiet() -> None:
    assert scan_coverage.problems(clean(EVERYTHING), EVERYTHING) == []


def test_one_directory_dropping_out_is_red() -> None:
    """**The shape the real bug took**, and the shape a minimum count cannot see."""
    found = scan_coverage.problems(clean({"app/a.py", "app/b.py"}), EVERYTHING)

    assert "tests/test_a.py" in only(found)


def test_reading_more_than_expected_is_not_a_fault() -> None:
    """Files not yet tracked get read on a developer's machine, and extra is safety."""
    report = clean(EVERYTHING | {"scratch.py"})

    assert scan_coverage.problems(report, EVERYTHING) == []


def test_the_message_says_what_to_do_about_it() -> None:
    """ "Declare it" and "it vanished" are different outcomes, and only one is fine."""
    found = only(scan_coverage.problems(clean(set()), EVERYTHING))

    assert "declare it" in found


# ----------------------------------------------- what the report says about itself


def test_a_run_with_no_rules_is_red() -> None:
    """An empty rule set finds nothing, and finding nothing is the passing answer."""
    found = scan_coverage.problems(scan_coverage.Report(EVERYTHING, rules=0), EVERYTHING)

    assert "no rules" in only(found)


def test_a_skipped_rule_is_red() -> None:
    """A rule the tool could not load stops checking without anybody deciding it should."""
    report = scan_coverage.Report(EVERYTHING, rules=42, skipped_rules=["broken.yml"])

    assert "skipped" in only(scan_coverage.problems(report, EVERYTHING))


def test_an_error_the_scanner_reported_about_itself_is_red() -> None:
    """A file it failed to read is a file it did not scan, whatever the exit code said."""
    report = scan_coverage.Report(EVERYTHING, rules=42, errors=["cannot parse app/a.py"])

    assert "error" in only(scan_coverage.problems(report, EVERYTHING))


def test_every_way_a_run_can_be_hollow_is_reported_at_once() -> None:
    """One push, one list — otherwise the second problem waits for the next one."""
    report = scan_coverage.Report(set(), rules=0, errors=["x"], skipped_rules=["y"])

    assert len(scan_coverage.problems(report, EVERYTHING)) == 4


# ------------------------------------------------------- the expected set


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A real repository — "what is our code" is a question the history answers."""
    binary = shutil.which("git")
    assert binary, "these tests ask git what is tracked"
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "nobody@example.invalid"],
        ["config", "user.name", "Nobody"],
    ):
        subprocess.run(  # noqa: S603 — git from shutil.which, args are test literals
            [binary, *args], cwd=tmp_path, check=True, capture_output=True, timeout=60
        )
    for name in ("app/a.py", "tests/test_a.py", "migrations/m.py", "app/notes.md"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n", encoding="utf-8")
    subprocess.run(  # noqa: S603 — git from shutil.which, a fixed argv
        [binary, "add", "-A"], cwd=tmp_path, check=True, capture_output=True, timeout=60
    )
    subprocess.run(  # noqa: S603 — git from shutil.which, a fixed argv
        [binary, "commit", "-q", "-m", "first"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        timeout=60,
    )
    return tmp_path


def test_the_expected_set_comes_from_what_is_tracked(repo: pathlib.Path) -> None:
    """Something not committed is not code the pipeline is answerable for."""
    (repo / "app" / "untracked.py").write_text("x\n", encoding="utf-8")

    found = scan_coverage.tracked_files(repo, "*.py")

    assert found == {"app/a.py", "tests/test_a.py", "migrations/m.py"}


def test_a_tracked_name_that_is_not_utf8_is_read_rather_than_refused(
    repo: pathlib.Path,
) -> None:
    """git quotes such a name by default — so this pipe was ASCII by git's configuration.

    A project that has set `core.quotePath=false` gets the raw bytes instead, and
    `subprocess(text=True)` decodes them with the machine's locale and refuses anything
    else: a `UnicodeDecodeError` from a reader whose whole job is to say what is tracked
    (self-audit round 15, 2026-09-01). The name is carried through, not escaped, because
    these names are compared rather than printed.
    """
    binary = shutil.which("git")
    assert binary, "these tests ask git what is tracked"
    name = "app/caf\udce9.py"
    (repo / name).write_text("x\n", encoding="utf-8")
    for args in (["config", "core.quotePath", "false"], ["add", "-A"]):
        subprocess.run(  # noqa: S603 — git from shutil.which, args are test literals
            [binary, *args], cwd=repo, check=True, capture_output=True, timeout=60
        )

    assert name in scan_coverage.tracked_files(repo, "*.py")


def test_a_declared_skip_is_taken_out_of_the_expected_set(repo: pathlib.Path) -> None:
    found = scan_coverage.expected_files(repo, "*.py", ["migrations"])

    assert found == {"app/a.py", "tests/test_a.py"}


def test_the_pattern_decides_what_counts_as_code(repo: pathlib.Path) -> None:
    """A markdown file next to the code is not something a code scanner missed."""
    assert "app/notes.md" not in scan_coverage.expected_files(repo, "*.py", [])


def test_skips_are_read_from_the_project_s_own_file(tmp_path: pathlib.Path) -> None:
    path = tmp_path / ".ignore"
    path.write_text("# what we do not scan\n\nmigrations/\n.venv\n", encoding="utf-8")

    assert scan_coverage.skipped_prefixes(path) == ["migrations", ".venv"]


def test_a_skip_matches_a_directory_not_a_prefix_of_a_name(repo: pathlib.Path) -> None:
    """Skipping `app` must not also skip `application/` — a prefix is not a directory."""
    (repo / "apple").mkdir()
    (repo / "apple" / "c.py").write_text("x\n", encoding="utf-8")
    binary = shutil.which("git")
    assert binary
    subprocess.run(  # noqa: S603 — git from shutil.which, a fixed argv
        [binary, "add", "-A"], cwd=repo, check=True, capture_output=True, timeout=60
    )
    subprocess.run(  # noqa: S603 — git from shutil.which, a fixed argv
        [binary, "commit", "-q", "-m", "more"],
        cwd=repo,
        check=True,
        capture_output=True,
        timeout=60,
    )

    found = scan_coverage.expected_files(repo, "*.py", ["app"])

    assert "apple/c.py" in found
    assert "app/a.py" not in found


def test_a_machine_without_git_says_so(repo: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    with pytest.raises(RuntimeError, match="git is not on this machine"):
        scan_coverage.tracked_files(repo, "*.py")


def test_the_command_declares_a_time_budget(
    repo: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a timeout the wait is forever, which in CI is a job that never ends."""
    budget: dict[str, object] = {}
    real = subprocess.run

    def watched(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        budget.update(kwargs)
        return real(argv, **kwargs)  # type: ignore[call-overload,no-any-return]  # kwargs are typed object to be recorded, not called

    monkeypatch.setattr(subprocess, "run", watched)
    scan_coverage.tracked_files(repo, "*.py")

    assert budget["timeout"] == scan_coverage.GIT_TIMEOUT_SECONDS


# --------------------------------------------------------------- the wording


def test_the_wording_is_an_input() -> None:
    found = scan_coverage.problems(
        clean(set()), EVERYTHING, messages={"missed": "{count} not read"}
    )

    assert only(found) == "3 not read"
