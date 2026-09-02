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
import pathlib
import shutil
import subprocess
from typing import TYPE_CHECKING, Any

import pytest
import yaml

from verifiable_gates import lint_commits

if TYPE_CHECKING:
    from collections.abc import Callable

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
        "fix: ok\n\nA body.\n\nSigned-off-by: A B <a@b.co>\nReviewed-by: C <c@d.io>\n",
    ],
)
def test_a_signed_commit_passes(message: str) -> None:
    """The shape `git commit -s` writes must not be caught."""
    assert lint_commits.check_sign_off(message) == []


# ---------------------------------------------------------------- the trailers


@pytest.mark.parametrize(
    "message",
    [
        "feat(x): ok\n\nSigned-off-by: A B <a@b.co>\n",
        "fix: ok\n\nSays co-authored-by in prose, not as a trailer.\n\nSigned-off-by: A <a@b.co>\n",
        "fix: ok\n\nSigned-off-by: A B <a@b.co>\nReviewed-by: C <c@d.io>\n",
    ],
)
def test_a_commit_with_one_author_passes(message: str) -> None:
    assert lint_commits.check_trailers(message) == []


@pytest.mark.parametrize(
    ("message", "why"),
    [
        ("feat: ok\n\nSigned-off-by: A <a@b.co>\nCo-Authored-By: C <c@d.io>\n", "capitalised key"),
        ("feat: ok\n\nSigned-off-by: A <a@b.co>\nCo-authored-by: C <c@d.io>\n", "git's own casing"),
        ("feat: ok\n\nSigned-off-by: A <a@b.co>\nClaude-Session: https://x/y\n", "session trailer"),
    ],
)
def test_a_co_author_trailer_is_caught(message: str, why: str) -> None:
    """Credit to an address that signed nothing — the platform would list it as a contributor."""
    found = lint_commits.check_trailers(message)

    assert found, why
    assert "drop the line" in found[0], "caught it, but did not say how to fix it"


def test_every_forbidden_trailer_is_named_once() -> None:
    """Two trailers, two findings — a message that names only the first hides the second."""
    message = "feat: ok\n\nSigned-off-by: A <a@b.co>\nCo-authored-by: C <c@d.io>\nClaude-Session: x"

    assert len(lint_commits.check_trailers(message)) == 2


@pytest.mark.parametrize(
    ("message", "why"),
    [
        ("feat(x): no signature at all\n\nbody\n", "no sign-off line"),
        ("feat(x): ok\n\nSigned-off-by: No Address\n", "a signature with no way to reply"),
        ("feat(x): ok\n\nsigned-off-by: a <a@b.co>\n", "lowercase — not what git writes"),
        ("feat(x): ok\n\nSigned-off-by: A B <a@b.co> and more\n", "trailing text"),
        ("feat(x): ok\n\nSigned-off-by:    <a@b.co>\n", "spaces where the name goes"),
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
        ("feat(x): ok\n\nSigned-off-by: A B <a@b.co>\nCo-authored-by: C <c@d.io>\n", "co-author"),
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
        ["git", "rev-parse", "HEAD"],  # noqa: S607 — a fixed git command, written out in a test
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
        ["git", "rev-parse", "HEAD"],  # noqa: S607 — a fixed git command, written out in a test
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert "FAIL" in out
    assert head[:9] in out, "went red without saying which commit"


def plant_a_message_that_is_not_utf8(root: pathlib.Path, message: bytes) -> str:
    """Rewrite HEAD with a message git itself refuses to write, and return its sha.

    `git commit` transliterates bytes that are not UTF-8 before storing them, so a
    commit really holding them has to be written as an object. That is not a contrived
    shape: it is what a repository contains once a client that was not speaking UTF-8
    has pushed to it — and this mode's whole reason to exist is the fork, where the
    commits were written by tools this project does not choose.
    """
    binary = shutil.which("git")
    assert binary, "this test reads a real history and needs git"
    # Annotated because `subprocess.run` with neither `text` nor `encoding` returns
    # bytes, which is the whole point here, and the overload mypy picks says otherwise.
    git: Callable[..., subprocess.CompletedProcess[Any]] = functools.partial(
        subprocess.run, cwd=root, check=True, capture_output=True, timeout=60
    )

    def out(*args: str) -> bytes:
        stdout: bytes = git([binary, *args]).stdout
        return stdout.strip()

    who = b"A B <a@b.co> 1756700000 +0000"
    obj = (
        b"tree " + out("rev-parse", "HEAD^{tree}") + b"\n"
        b"parent " + out("rev-parse", "HEAD^") + b"\n"
        b"author " + who + b"\ncommitter " + who + b"\n\n" + message
    )
    written = (
        git([binary, "hash-object", "-w", "-t", "commit", "--stdin"], input=obj)
        .stdout.decode()
        .strip()
    )
    git([binary, "reset", "--hard", "-q", written])
    return str(written)


def test_the_range_mode_refuses_a_message_it_cannot_read(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same answer the hook mode gives the same bytes: no verdict, and which commit.

    The hook mode reads the message from a file and has always answered exit 2 with
    "not UTF-8". The range mode took the same bytes through `subprocess(text=True)`,
    which decodes with the machine's locale and refuses anything else, so it answered
    a stranger's commit with a raw `UnicodeDecodeError` and **exit 1** — the code that
    means *these commit messages break the rules* (self-audit round 15, 2026-09-01).
    The exit code is asserted rather than the traceback: 1 and 2 are different claims.
    """
    base = a_repo(tmp_path, "fix: a well-formed one\n\nSigned-off-by: A B <a@b.co>")
    monkeypatch.chdir(tmp_path)
    sha = plant_a_message_that_is_not_utf8(
        tmp_path, b"fix: caf\xe9 from another client\n\nSigned-off-by: A B <a@b.co>\n"
    )

    code = run(monkeypatch, ["--range", f"{base}..HEAD"])

    assert code == 2, f"a message nobody can decode was answered with {code}, not the third answer"
    said = capsys.readouterr().err
    assert "not UTF-8" in said, f"refused without saying why: {said!r}"
    assert sha[:9] in said, f"refused without saying which commit: {said!r}"


def test_the_range_mode_still_reads_the_commits_beside_an_unreadable_one(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The control: the same repository one commit earlier is judged, not refused.

    Without this, a `return 2` at the top of the range mode would pass the test above.
    """
    base = a_repo(tmp_path, "fix: a well-formed one\n\nSigned-off-by: A B <a@b.co>")
    monkeypatch.chdir(tmp_path)
    plant_a_message_that_is_not_utf8(
        tmp_path, b"fix: caf\xe9 from another client\n\nSigned-off-by: A B <a@b.co>\n"
    )

    assert run(monkeypatch, ["--range", f"{base}..HEAD~1"]) == 0


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


# ---------------------------------------------------------------- the inline copy in CI

ROOT = pathlib.Path(__file__).resolve().parent.parent
CI = ROOT / ".github" / "workflows" / "ci.yml"


def the_ci_block() -> str:
    """The `run:` script of this repository's own `commit-lint` job."""
    jobs = yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]
    steps = jobs["commit-lint"]["steps"]
    return str(next(step["run"] for step in steps if "run" in step))


def test_the_ci_job_uses_the_module_type_list() -> None:
    """One rule, two enforcers — the inline copy must carry the module's exact list.

    The job is inline on purpose (the gate that guards the package must not
    import the package), which is precisely why a test has to hold the copy to
    the original: an outside audit on 2026-08-29 found the job accepting
    `feature:` and `fixup!` by prefix while the hook refused them.
    """
    assert f"TYPES='{lint_commits.TYPES}'" in the_ci_block()


def test_the_ci_job_skips_merge_commits_like_the_module() -> None:
    assert "git rev-list --no-merges" in the_ci_block()


@pytest.mark.parametrize(
    "title",
    [
        "feat: a plain one",
        "fix(scope): with a scope",
        "feat!: a breaking change",
        "fix(a/b-c.d)!: a scope with punctuation, breaking",
        "just a sentence",
        "feature: wrong word",
        "featuring a prefix without a colon",
        "fixup! a squash marker",
        "testing: not a type",
        "performance: not a type either",
        "feat missing colon",
        "feat:no space",
        "feat: ",
        "chore: " + "x" * 66,
    ],
)
def test_the_ci_regex_and_the_module_agree_on_a_subject(title: str) -> None:
    """The shell regex from `ci.yml`, run by bash, must give the module's verdict.

    Both directions on each subject: a subject the module refuses must be red in
    CI, and one it accepts must be green there — otherwise a branch passes the
    hook and fails the job, or the reverse, and one of the two gates is decorative.
    """
    block = the_ci_block()
    lines = block.splitlines()
    definitions = "\n".join(line for line in lines if line.startswith(("TYPES=", "SUBJECT=")))
    assert definitions.count("\n") == 1, "expected exactly one TYPES= and one SUBJECT= line"
    bash = shutil.which("bash")
    assert bash, "the CI block is written for bash"
    script = f'{definitions}\nprintf \'%s\' "$1" | grep -qE "$SUBJECT"'

    shell = subprocess.run(  # noqa: S603 — the script is this repository's own CI block
        [bash, "-c", script, "_", title], check=False
    )
    shell_says_ok = shell.returncode == 0
    problems = lint_commits.check_title(title)
    module_says_ok = not any("not a Conventional Commit" in p for p in problems)

    assert shell_says_ok == module_says_ok, (
        f"{title!r}: CI says {'pass' if shell_says_ok else 'fail'}, "
        f"the module says {'pass' if module_says_ok else 'fail'}"
    )


@pytest.mark.parametrize(
    "body",
    [
        "feat: ok\n\nSigned-off-by: A Person <a@b.co>\n",
        "feat: ok\n\nA body.\n\nSigned-off-by: A B <a@b.co>\nReviewed-by: C <c@d.io>\n",
        "feat: ok\n\nSigned-off-by: A B <a@b.co>   \n",
        "feat: ok\n\nSigned-off-by:  <@>\n",
        "feat: ok\n\nSigned-off-by:    <a@b.co>\n",
        "feat: ok\n\nSigned-off-by: \t <a@b.co>\n",
        "feat: ok\n\nSigned-off-by: <a@b.co>\n",
        "feat: ok\n\nSigned-off-by: No Address\n",
        "feat: ok\n\nSigned-off-by: A B <a@b.co> and more\n",
        "feat: ok\n\nSigned-off-by: A B <not an address>\n",
        "feat: ok\n\nSigned-off-by: A B <a@b.co>\nCo-authored-by: C <c@d.io>\n",
        "feat: ok\n\nno signature at all\n",
    ],
)
def test_the_ci_regex_and_the_module_agree_on_a_sign_off(body: str) -> None:
    """The sign-off half of the same gate, held the same way as the subject half.

    The first round bound only `SUBJECT`; a second outside audit (2026-08-29)
    fed `Signed-off-by:  <@>` through both and CI's `.* <.*@.*>` accepted a
    signature with no name and no address while the module refused it. A DCO
    line nobody can follow up on is the case the module's shape exists to refuse.
    """
    block = the_ci_block()
    definitions = [line for line in block.splitlines() if line.startswith("SIGNOFF=")]
    assert len(definitions) == 1, "expected exactly one SIGNOFF= line"
    assert 'grep -qE "$SIGNOFF"' in block, "the job must judge the body with SIGNOFF"
    bash = shutil.which("bash")
    assert bash, "the CI block is written for bash"
    script = f'{definitions[0]}\nprintf \'%s\' "$1" | grep -qE "$SIGNOFF"'

    shell = subprocess.run(  # noqa: S603 — the script is this repository's own CI block
        [bash, "-c", script, "_", body], check=False
    )
    shell_says_ok = shell.returncode == 0
    module_says_ok = not lint_commits.check_sign_off(body)

    assert shell_says_ok == module_says_ok, (
        f"{body!r}: CI says {'pass' if shell_says_ok else 'fail'}, "
        f"the module says {'pass' if module_says_ok else 'fail'}"
    )


def test_a_message_file_that_is_not_there_is_a_misuse(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The hook is handed a path by git; pointed at one that is not there it died of a
    traceback and exit 1 — the code that means the message is bad (round 2, 2026-08-31)."""
    assert run(monkeypatch, ["--msg-file", str(tmp_path / "COMMIT_EDITMSG")]) == 2
    assert "cannot read the message file" in capsys.readouterr().err


def test_a_message_file_this_hook_cannot_decode_is_a_misuse(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Round 2 gave the hook an answer for a path that is not there; a message an editor
    saved in another encoding — the likeliest of all, since the author writes it by hand —
    still died of a raw `UnicodeDecodeError` and exit 1, which reads as *your message is
    bad* (self-audit round 12, 2026-09-01)."""
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_bytes(b"fix: caf\xe9 in the title\n\nSigned-off-by: A <a@b.co>\n")

    assert run(monkeypatch, ["--msg-file", str(path)]) == 2
    printed = capsys.readouterr().err
    assert "cannot read the message file" in printed
    assert "not UTF-8" in printed


# ---------------------------------------------------------------- the answer at the ceiling


def test_a_history_that_does_not_answer_in_time_is_not_a_verdict(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`LOCAL_TIMEOUT_SECONDS` turned a `git log` that never returns into a
    `TimeoutExpired`, and nothing caught it: an unhandled exception is **exit 1**, which
    from this gate reads as *these commit messages are bad* out of a reader that read
    none of them (self-audit round 19, 2026-09-02). The ceiling is reached by quantity —
    a range wide enough over a history long enough."""

    def timed_out(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="git log", timeout=60)

    monkeypatch.setattr(subprocess, "run", timed_out)

    assert lint_commits.main(["--range", "HEAD~1..HEAD"]) == 2
    assert "did not answer within 60 seconds" in capsys.readouterr().err


def test_a_range_git_will_not_resolve_is_not_a_verdict(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The other way the same command does not answer, with the real git: a shallow clone
    whose base ref was never fetched is how a consumer's CI arrives here, and it too was a
    traceback and exit 1 — a reading of commits nobody had read."""
    assert lint_commits.main(["--range", "no-such-ref-here..HEAD"]) == 2
    assert "unknown revision" in capsys.readouterr().err
