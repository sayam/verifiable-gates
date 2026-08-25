"""The commit gate, proved on both sides of every rule it enforces.

This gate blocks every commit on a developer's machine and every pull request in
CI, which makes both directions expensive to get wrong: a false red teaches
people to reach for `--no-verify`, and a false green lets malformed history in
permanently.

The subject rules and the sign-off rule are checked as pure functions. The two
command-line modes are checked by driving `main()` through `argv`, because
correct pieces wired together wrongly give exactly the same signal as correct
pieces wired together rightly — until the day somebody types a bad subject and
nothing complains.
"""

from __future__ import annotations

import functools
import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import pathlib

from verifiable_gates import lint_commits

# ---------------------------------------------------------------- the subject


@pytest.mark.parametrize(
    "title",
    [
        "feat: a plain one",
        "fix(scope): with a scope",
        "feat!: a breaking change",
        "fix(a/b-c.d)!: a scope with punctuation, breaking",
        "chore: " + "x" * 63,
    ],
)
def test_a_well_formed_subject_passes(title: str) -> None:
    assert lint_commits.check_title(title) == [], f"a valid subject was caught: {title!r}"


@pytest.mark.parametrize(
    ("title", "why"),
    [
        ("just a sentence", "no type at all"),
        ("feature: wrong word", "a type nobody defined"),
        ("feat missing colon", "no colon"),
        ("feat:no space", "no space after the colon"),
        ("feat: ", "empty subject"),
        ("chore: " + "x" * 66, "one character over the limit"),
    ],
)
def test_a_malformed_subject_is_caught(title: str, why: str) -> None:
    assert lint_commits.check_title(title), f"not caught: {why} ({title!r})"


def test_the_limit_counts_characters_not_bytes() -> None:
    """A subject in a non-Latin script must not be rejected for its encoding.

    Counting bytes would make the limit roughly a third as long for anybody
    writing in Thai, Japanese or Greek — a rule that punishes a language.
    """
    title = "feat: " + "ก" * 60

    assert len(title) <= lint_commits.MAX_TITLE
    assert lint_commits.check_title(title) == []


# ---------------------------------------------------------------- the sign-off


@pytest.mark.parametrize(
    "message",
    [
        "feat(x): ok\n\nSigned-off-by: A Person <a@b.co>\n",
        "fix: ok\n\nA body.\n\nSigned-off-by: A B <a@b.co>\nCo-Authored-By: C <c@d.io>\n",
    ],
)
def test_a_signed_commit_passes(message: str) -> None:
    """The shape `git commit -s` writes must not be caught."""
    assert lint_commits.check_sign_off(message) == []


@pytest.mark.parametrize(
    ("message", "why"),
    [
        ("feat(x): no signature at all\n\nbody\n", "no sign-off line"),
        ("feat(x): ok\n\nSigned-off-by: No Address\n", "a signature with no way to reply"),
        ("feat(x): ok\n\nsigned-off-by: a <a@b.co>\n", "lowercase — not what git writes"),
        ("feat(x): ok\n\nSigned-off-by: A B <a@b.co> and more\n", "trailing text"),
    ],
)
def test_an_unsigned_commit_is_caught(message: str, why: str) -> None:
    found = lint_commits.check_sign_off(message)

    assert found, why
    assert "git commit -s" in found[0], "caught it, but did not say how to fix it"


# ---------------------------------------------------------------- reading git


def test_a_multiline_body_stays_one_commit() -> None:
    """A commit body may contain newlines; a line-based reader splits one into many.

    This direction matters more than it looks: if the reader splits, the sign-off
    lands in a different "commit" from its subject, and the gate goes red on
    correctly signed work — which is how people learn to skip it.

    The log output is fed in directly rather than calling git, because a shallow
    CI checkout has no `HEAD~1` and a test that assumes one is green locally and
    red in CI.
    """
    sep, field = lint_commits.RECORD_SEP, lint_commits.FIELD_SEP
    out = (
        f"aaaaaaaaaaaa{field}feat: base{field}Signed-off-by: A B <a@b.co>\n{sep}"
        f"bbbbbbbbbbbb{field}feat: several paragraphs{field}"
        f"First.\n\nSecond.\n\nSigned-off-by: A B <a@b.co>\n{sep}"
    )

    rows = lint_commits.parse_log(out)

    assert len(rows) == 2, f"a multiline body was split into several commits: {rows}"
    _sha, subject, body = rows[1]
    assert subject == "feat: several paragraphs"
    assert "Second." in body, "the body was truncated on the way through"
    assert lint_commits.check_sign_off(body) == []


def test_the_format_string_and_the_separators_agree() -> None:
    """Two copies of one fact — the test is what stops them drifting apart."""
    assert lint_commits.FIELD_SEP.encode().hex() == "00"
    assert lint_commits.RECORD_SEP.encode().hex() == "1e"
    assert lint_commits.LOG_FORMAT == "%H%x00%s%x00%b%x1e"


# ---------------------------------------------------------------- the two modes


def run(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> int:
    """Drive main() through argv — never reach past it to the functions inside."""
    monkeypatch.setattr("sys.argv", ["lint_commits.py", *argv])
    return lint_commits.main()


def test_the_hook_mode_passes_a_well_formed_message(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_text("feat(x): a good one\n\nSigned-off-by: A B <a@b.co>\n", encoding="utf-8")

    assert run(monkeypatch, ["--msg-file", str(path)]) == 0
    assert "passes" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("message", "why"),
    [
        ("fixed the bug\n\nSigned-off-by: A B <a@b.co>\n", "subject is not conventional"),
        ("feat(x): ok\n\nno signature\n", "no DCO line"),
    ],
)
def test_the_hook_mode_refuses_and_says_why(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    message: str,
    why: str,
) -> None:
    """This mode blocks every commit locally — silence when it should be red lets it in."""
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_text(message, encoding="utf-8")

    assert run(monkeypatch, ["--msg-file", str(path)]) == 1, why
    assert "FAIL" in capsys.readouterr().out


def a_repo(tmp_path: pathlib.Path, *messages: str) -> str:
    """A real repository with these commits — `commits_in_range` calls git for real."""
    git = functools.partial(subprocess.run, cwd=tmp_path, check=True, capture_output=True)
    git(["git", "init", "-q", "-b", "main"])
    git(["git", "config", "user.email", "a@b.co"])
    git(["git", "config", "user.name", "A B"])
    git(["git", "commit", "-q", "--allow-empty", "-m", "feat: base\n\nSigned-off-by: A B <a@b.co>"])
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"],  # noqa: S607
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    for message in messages:
        git(["git", "commit", "-q", "--allow-empty", "-m", message])
    return base


def test_the_range_mode_reads_real_commits(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    base = a_repo(tmp_path, "fix: the second one\n\nSigned-off-by: A B <a@b.co>")
    monkeypatch.chdir(tmp_path)

    assert run(monkeypatch, ["--range", f"{base}..HEAD"]) == 0
    assert "passes" in capsys.readouterr().out


def test_the_range_mode_names_the_commit_it_refused(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A report that does not say which commit leaves the author guessing on a long branch."""
    base = a_repo(tmp_path, "a malformed subject\n\nSigned-off-by: A B <a@b.co>")
    monkeypatch.chdir(tmp_path)

    assert run(monkeypatch, ["--range", f"{base}..HEAD"]) == 1
    out = capsys.readouterr().out
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],  # noqa: S607
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert "FAIL" in out
    assert head[:9] in out, "went red without saying which commit"


def test_the_range_mode_skips_merge_commits(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A merge commit's message is the platform's, not a person's.

    Holding it to a format makes the "Update branch" button turn this gate red
    every time with nobody having typed anything wrong — which is how people
    learn to skip the gate entirely.
    """
    base = a_repo(tmp_path)
    git = functools.partial(subprocess.run, cwd=tmp_path, check=True, capture_output=True)
    git(["git", "checkout", "-q", "-b", "side"])
    git(["git", "commit", "-q", "--allow-empty", "-m", "fix: side\n\nSigned-off-by: A B <a@b.co>"])
    git(["git", "checkout", "-q", "main"])
    git(["git", "commit", "-q", "--allow-empty", "-m", "feat: main\n\nSigned-off-by: A B <a@b.co>"])
    git(["git", "merge", "--no-ff", "-q", "-m", "Merge branch 'side' into main", "side"])
    monkeypatch.chdir(tmp_path)

    assert run(monkeypatch, ["--range", f"{base}..HEAD"]) == 0, (
        "a merge commit was held to the format, though its message is not a person's"
    )
    subjects = [row[1] for row in lint_commits.commits_in_range(f"{base}..HEAD")]
    assert not any(s.startswith("Merge branch") for s in subjects), subjects


def test_the_two_modes_are_mutually_exclusive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both at once, or neither, is a misuse — and argparse must say so, not guess."""
    with pytest.raises(SystemExit):
        run(monkeypatch, [])
    with pytest.raises(SystemExit):
        run(monkeypatch, ["--msg-file", "a", "--range", "b"])
