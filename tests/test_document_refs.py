"""Every number a document points at, resolved — on fakes; the live read is posture's cron.

Role: the offline half of the gate `a-number-a-document-points-at-opens`. Nothing here
reaches GitHub: `proved_by_refs.resolve` is replaced with answers that say what the platform
said on 2026-09-06 (200 for a pull request that is there, 404 for the four this repository
had deleted at its own request), so the decider's three exit codes are pinned to the cases.
"""

from __future__ import annotations

import pathlib
import subprocess
from typing import TYPE_CHECKING

from verifiable_gates import document_refs, proved_by_refs

if TYPE_CHECKING:
    import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def only(*open_refs: str) -> object:
    """A `resolve` that answers for the refs named and 404s for everything else."""

    def _resolve(ref: proved_by_refs.Ref) -> str | None:
        if ref.text in open_refs:
            return None
        return f"{ref.text}: the platform answers 404 — nothing at {ref.path}"

    return _resolve


def repo(tmp_path: pathlib.Path, files: dict[str, str]) -> pathlib.Path:
    """A git repository with those files tracked, because the reader asks git what to read."""
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text, encoding="utf-8")
    run = ["git", "init", "-q"], ["git", "add", "-A"]
    for command in run:
        subprocess.run(command, cwd=tmp_path, check=True)  # noqa: S603 — git, from PATH
    return tmp_path


# ---------------------------------------------------------------- what counts as a ref


def test_a_bare_number_and_another_repositorys_number_are_both_refs() -> None:
    assert document_refs.refs_in("closed by #316 and sayam/flask-todolist#225") == [
        "#316",
        "sayam/flask-todolist#225",
    ]


def test_code_is_not_prose() -> None:
    """`echo "step #1"` and `&#10;` are in this repository's own documents and are not
    references to anything: a check that reported them is one nobody keeps."""
    text = "before\n```sh\necho 'step #1'\n```\nand `&#10;` inline, then #316\n"
    assert document_refs.refs_in(text) == ["#316"]


def test_what_is_not_a_ref_at_all() -> None:
    """A heading, a colour, an anchor, a number welded to a word."""
    assert document_refs.refs_in("# 1 heading\n#fff\n[a](#section)\nx#3\n#12345678\n") == []


def test_the_files_read_are_the_documents_git_tracks_and_no_python(
    tmp_path: pathlib.Path,
) -> None:
    """Not `*.py`: a fixture in the suite says `#1` and means a fixture."""
    root = repo(tmp_path, {"a.md": "#11\n", "b.yaml": "# see #12\n", "c.py": "# see #13\n"})
    assert document_refs.collect(root) == {"#11": ["a.md"], "#12": ["b.yaml"]}


def test_a_ref_in_two_documents_is_one_ref_that_names_both(tmp_path: pathlib.Path) -> None:
    root = repo(tmp_path, {"a.md": "#11 and #11 again\n", "b.md": "#11\n"})
    assert document_refs.collect(root) == {"#11": ["a.md", "b.md"]}


def test_every_number_this_repositorys_documents_point_at_can_be_asked_about() -> None:
    """The standing check on the real tree: a shape the resolver cannot ask about would be
    a finding nobody could act on."""
    cited = document_refs.collect(ROOT)
    assert cited, "no document points at anything — the scan stopped working"
    assert [text for text in cited if proved_by_refs.parse(text).path is None] == []


def test_the_registers_names_are_all_pointed_at_by_a_document() -> None:
    """The register can only excuse what something actually says."""
    cited = document_refs.collect(ROOT)
    assert set(document_refs.DELETED_ON_REQUEST) <= set(cited)


# ---------------------------------------------------------------- the three exit codes


def test_everything_that_opens_exits_zero_and_counts(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo(tmp_path, {"a.md": "#11 and #12\n", "b.md": "#12\n"})
    monkeypatch.setattr(document_refs, "DELETED_ON_REQUEST", {})
    monkeypatch.setattr(proved_by_refs, "resolve", only("#11", "#12"))
    assert document_refs.main(["--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "every number the documents point at opens: 2 of 2 across 2 files" in out
    assert "deleted on request" not in out


def test_a_number_that_does_not_open_is_a_finding_naming_the_documents(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo(tmp_path, {"a.md": "#11\n", "b.md": "#11 and #12\n"})
    monkeypatch.setattr(document_refs, "DELETED_ON_REQUEST", {})
    monkeypatch.setattr(proved_by_refs, "resolve", only("#12"))
    assert document_refs.main(["--root", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "FAIL #11: the platform answers 404" in err
    assert "pointed at by: a.md, b.md" in err


def test_a_number_the_register_excuses_is_not_a_finding_and_is_counted(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo(tmp_path, {"a.md": "#2 was deleted, #12 was not\n"})
    monkeypatch.setattr(document_refs, "DELETED_ON_REQUEST", {"#2": "deleted on request"})
    monkeypatch.setattr(proved_by_refs, "resolve", only("#12"))
    assert document_refs.main(["--root", str(tmp_path)]) == 0
    assert "1 of 2 across 1 files, 1 deleted on request" in capsys.readouterr().out


def test_an_excused_number_that_opens_again_is_a_finding_because_the_register_shrinks(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo(tmp_path, {"a.md": "#2\n"})
    monkeypatch.setattr(document_refs, "DELETED_ON_REQUEST", {"#2": "deleted on request"})
    monkeypatch.setattr(proved_by_refs, "resolve", only("#2"))
    assert document_refs.main(["--root", str(tmp_path)]) == 1
    assert "#2 opens after all — take it out of DELETED_ON_REQUEST" in capsys.readouterr().err


def test_a_register_entry_no_document_points_at_is_a_finding(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Otherwise the register is a place to park a number, which is what it must never be."""
    repo(tmp_path, {"a.md": "#12\n"})
    monkeypatch.setattr(document_refs, "DELETED_ON_REQUEST", {"#99": "not said anywhere"})
    monkeypatch.setattr(proved_by_refs, "resolve", only("#12"))
    assert document_refs.main(["--root", str(tmp_path)]) == 1
    assert "#99 is in DELETED_ON_REQUEST and no document points at it" in capsys.readouterr().err


def test_a_platform_that_cannot_be_asked_exits_two(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo(tmp_path, {"a.md": "#12\n"})

    def refused(_ref: proved_by_refs.Ref) -> str | None:
        raise PermissionError("gh: Bad credentials (HTTP 401)")

    monkeypatch.setattr(proved_by_refs, "resolve", refused)
    assert document_refs.main(["--root", str(tmp_path)]) == 2
    assert "could not ask the platform" in capsys.readouterr().err


def test_a_tree_git_cannot_be_asked_about_exits_two(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Not a repository, no git, a git that hangs: "could not look" is not a pass."""
    assert document_refs.main(["--root", str(tmp_path)]) == 2
    assert "cannot read what this project tracks" in capsys.readouterr().err


def test_posture_runs_the_document_reader_live_with_the_workflow_token() -> None:
    """The live half: a step in posture.yml, on the cron and on every push to main."""
    text = (ROOT / ".github" / "workflows" / "posture.yml").read_text(encoding="utf-8")
    assert "python -m verifiable_gates.document_refs --root ." in text
