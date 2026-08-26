"""What left and stayed gone, told apart from what was merely reworded.

Every test here builds a real repository and makes real commits, because the
claim under test is about what the history says — and a fake history is one
written by the same understanding that wrote the reader, so it agrees with it by
construction.

The distinction that matters is the one no eye can make in a raw diff: a removal
and a rewrite both appear as a line leaving and a line arriving. Get it wrong and
the report fills with entries that never went anywhere, which is indistinguishable
from a report nobody can use.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import pathlib

from verifiable_gates import removals

OLD = "2020-01-01T00:00:00+00:00"
GATES = removals.Pile("gates.yaml", re.compile(r"^  - id: (\S+)"))
FILES = removals.Pile("tests/", re.compile(r"^(tests/test_\w+\.py)$"))


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A real repository — the history is the thing being read."""
    run(tmp_path, "init", "-q", "-b", "main")
    run(tmp_path, "config", "user.email", "nobody@example.invalid")
    run(tmp_path, "config", "user.name", "Nobody")
    return tmp_path


def run(root: pathlib.Path, *args: str, when: str = "") -> None:
    binary = shutil.which("git")
    assert binary, "these tests read a real history and need git"
    # **`--since` filters on the committer date, not the author date.** Setting
    # only `--date` moves the line the log prints and not the line it filters on,
    # so a test written that way passes whatever the window says.
    env = {**os.environ, "GIT_COMMITTER_DATE": when} if when else None
    subprocess.run(  # noqa: S603
        [binary, *args], cwd=root, check=True, capture_output=True, timeout=60, env=env
    )


def commit(root: pathlib.Path, subject: str, files: dict[str, str], when: str = "") -> None:
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    run(root, "add", "-A")
    run(root, "commit", "-q", "-m", subject, "--date", when or "now", when=when)


def rows(*ids: str) -> str:
    return "gates:\n" + "".join(f"  - id: {name}\n    title: something\n" for name in ids)


# ----------------------------------------------------------- what really left


def test_an_entry_that_was_taken_away_is_reported(repo: pathlib.Path) -> None:
    commit(repo, "feat: three gates", {"gates.yaml": rows("alpha", "beta", "gamma")})
    commit(repo, "chore: drop beta", {"gates.yaml": rows("alpha", "gamma")})

    found, edits = removals.removed_entries(repo, GATES, "1.year")

    assert [item for _commit, _subject, item in found] == ["beta"]
    assert edits == 0


def test_the_commit_subject_travels_with_the_entry(repo: pathlib.Path) -> None:
    """A removal carries its reason in its own subject — a report without it sends you digging."""
    commit(repo, "feat: two gates", {"gates.yaml": rows("alpha", "beta")})
    commit(repo, "chore: beta was folded into alpha", {"gates.yaml": rows("alpha")})

    found, _edits = removals.removed_entries(repo, GATES, "1.year")

    assert found[0][1] == "chore: beta was folded into alpha"
    assert found[0][0], "the commit's hash has to be there too"


def test_nothing_removed_is_an_empty_answer_not_a_missing_one(repo: pathlib.Path) -> None:
    """Lines around the entries change constantly; the pattern must ignore all of it."""
    commit(repo, "feat: two gates", {"gates.yaml": rows("alpha", "beta")})
    commit(
        repo,
        "docs: reword the titles",
        {"gates.yaml": rows("alpha", "beta").replace("something", "something clearer")},
    )

    found, edits = removals.removed_entries(repo, GATES, "1.year")

    assert (found, edits) == ([], 0)


# --------------------------------------------------- what only looked like it left


def test_a_rename_is_not_a_removal(repo: pathlib.Path) -> None:
    """**The difference no eye can make in a raw diff.**

    Both entries that ever vanished from the reference implementation's own gate
    register over its whole lifetime were renames. Counting every line beginning
    with a minus would have reported both as losses.
    """
    commit(repo, "feat: two gates", {"gates.yaml": rows("alpha", "gates-carry-red-evidence")})
    commit(
        repo,
        "refactor: rename the gate",
        {"gates.yaml": rows("alpha", "gates-carry-red-proof")},
    )

    found, edits = removals.removed_entries(repo, GATES, "1.year")

    assert found == []
    assert edits == 1, "a rename is an interpretation and has to be counted where it can be seen"


def test_a_rename_too_far_from_the_old_name_reads_as_a_removal(repo: pathlib.Path) -> None:
    """**The honest limit of this reader**, stated rather than hidden.

    It compares text, so a rename that keeps almost none of the old name is
    indistinguishable from taking one entry out and putting a different one in.
    Reported as a removal is the safe direction: somebody reads the commit and
    dismisses it, which beats a real loss being filed as a rewrite.
    """
    commit(repo, "feat: two gates", {"gates.yaml": rows("alpha", "beta")})
    commit(repo, "refactor: rename beta", {"gates.yaml": rows("alpha", "beta-renamed")})

    found, edits = removals.removed_entries(repo, GATES, "1.year")

    assert [item for _c, _s, item in found] == ["beta"]
    assert edits == 0


def test_a_rewrite_that_is_not_alike_enough_counts_as_a_removal(repo: pathlib.Path) -> None:
    """The threshold has to bite in both directions, or it is not a threshold."""
    commit(repo, "feat: two gates", {"gates.yaml": rows("alpha", "beta")})
    commit(repo, "feat: swap beta out", {"gates.yaml": rows("alpha", "something-entirely-other")})

    found, edits = removals.removed_entries(repo, GATES, "1.year")

    assert [item for _c, _s, item in found] == ["beta"]
    assert edits == 0


def test_an_entry_removed_and_restored_in_one_commit_is_not_a_loss(repo: pathlib.Path) -> None:
    """Reordering a register moves lines without taking anything away."""
    commit(repo, "feat: two gates", {"gates.yaml": rows("alpha", "beta")})
    commit(repo, "chore: reorder", {"gates.yaml": rows("beta", "alpha")})

    found, _edits = removals.removed_entries(repo, GATES, "1.year")

    assert found == []


# ---------------------------------------------------------------- whole files


def test_a_deleted_file_is_reported(repo: pathlib.Path) -> None:
    commit(repo, "test: two files", {"tests/test_a.py": "a\n", "tests/test_b.py": "b\n"})
    (repo / "tests" / "test_b.py").unlink()
    run(repo, "add", "-A")
    run(repo, "commit", "-q", "-m", "chore: drop test_b")

    found = removals.deleted_files(repo, "tests/", "1.year")

    assert [item for _c, _s, item in found] == ["tests/test_b.py"]


def test_a_renamed_file_is_not_a_deleted_one(repo: pathlib.Path) -> None:
    commit(repo, "test: one file", {"tests/test_a.py": "a\n" * 40})
    run(repo, "mv", "tests/test_a.py", "tests/test_renamed.py")
    run(repo, "commit", "-q", "-m", "refactor: rename the file")

    found = removals.deleted_files(repo, "tests/", "1.year")

    assert found == []


# ------------------------------------------------------------------- the census


def test_the_census_covers_both_kinds_of_pile(repo: pathlib.Path) -> None:
    commit(
        repo,
        "feat: a register and a test",
        {"gates.yaml": rows("alpha", "beta"), "tests/test_a.py": "a\n"},
    )
    (repo / "tests" / "test_a.py").unlink()
    (repo / "gates.yaml").write_text(rows("alpha"), encoding="utf-8")
    run(repo, "add", "-A")
    run(repo, "commit", "-q", "-m", "chore: drop both")

    found, _edits = removals.census(repo, {"gate": GATES, "test file": FILES}, "1.year")

    assert [item for _c, _s, item in found["gate"]] == ["beta"]
    assert [item for _c, _s, item in found["test file"]] == ["tests/test_a.py"]


def test_a_window_that_excludes_the_change_reports_nothing(repo: pathlib.Path) -> None:
    """The span is the question being asked — a reader ignoring it answers a different one."""
    commit(repo, "feat: two gates", {"gates.yaml": rows("alpha", "beta")}, when=OLD)
    commit(repo, "chore: drop beta", {"gates.yaml": rows("alpha")}, when=OLD)

    inside, _edits = removals.removed_entries(repo, GATES, "10.years")
    outside, _edits = removals.removed_entries(repo, GATES, "30.days")

    assert [item for _c, _s, item in inside] == ["beta"]
    assert outside == [], "a change older than the window asked about is not in the answer"


# -------------------------------------------------------------- the report


def test_an_empty_pile_says_it_is_empty() -> None:
    """A pile that leaves the report reads exactly like a pile nobody watches any more."""
    page = removals.report(
        {"gate": [], "test file": [("abc1234", "chore: x", "t.py")]}, 0, "30.days"
    )

    assert "## gate — 0" in page
    assert "(none)" in page


def test_what_was_dismissed_as_a_rewrite_is_printed() -> None:
    """It is an interpretation, and an interpretation nobody sees is one nobody can dispute."""
    page = removals.report({"gate": []}, 7, "30.days")

    assert "7" in page
    assert "rewrites" in page


def test_a_project_can_add_its_own_closing_note() -> None:
    page = removals.report({"gate": []}, 0, "30.days", epilogue="see pyproject.toml")

    assert page.rstrip().endswith("see pyproject.toml")


# --------------------------------------------------------------- the command


def test_running_it_with_no_manifest_is_loud(capsys: pytest.CaptureFixture[str]) -> None:
    """An empty manifest and a quiet month print the same page, so they must not.

    "0 in total" from a reader that was told nothing to watch is the worst kind of
    green: it is the answer everybody hopes for, produced by reading nothing.
    """
    code = removals.main([])

    assert code == 2
    assert "no piles declared" in capsys.readouterr().err


def test_the_command_reads_the_repository_it_is_pointed_at(
    repo: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    commit(repo, "feat: two gates", {"gates.yaml": rows("alpha", "beta")})
    commit(repo, "chore: drop beta", {"gates.yaml": rows("alpha")})

    code = removals.main(["--root", str(repo), "--since", "1.year"], watched={"gate": GATES})

    assert code == 0
    assert "beta" in capsys.readouterr().out


def test_a_machine_without_git_says_so(repo: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    with pytest.raises(RuntimeError, match="git is not on this machine"):
        removals.deleted_files(repo, "tests/", "1.year")


def test_the_command_declares_a_time_budget(
    repo: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a timeout the wait is forever, which in CI is a job that never ends."""
    budget: dict[str, object] = {}
    real = subprocess.run

    def watched(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        budget.update(kwargs)
        return real(argv, **kwargs)  # type: ignore[call-overload,no-any-return]

    monkeypatch.setattr(subprocess, "run", watched)
    removals.deleted_files(repo, "tests/", "1.year")

    assert budget["timeout"] == removals.GIT_TIMEOUT_SECONDS
