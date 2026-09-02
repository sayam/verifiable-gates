"""The archive, read back — fed both lists as files, and the paging and the refusals on fakes.

Nothing here reaches Zenodo or GitHub. The live step is `posture.yml`'s cron.
"""

from __future__ import annotations

import io
import json
import pathlib
import urllib.error
import urllib.request
from typing import Any, Self

import pytest

from verifiable_gates import gh, zenodo

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONCEPT = "10.5281/zenodo.22103110"


def record(version: str, doi: str, concept: str = CONCEPT) -> dict[str, Any]:
    return {"doi": doi, "conceptdoi": concept, "metadata": {"version": version}}


def a_tree(tmp_path: pathlib.Path, records: list[dict[str, Any]], releases: list[str]) -> list[str]:
    (tmp_path / "CITATION.cff").write_text(f"title: x\ndoi: {CONCEPT}\n", encoding="utf-8")
    (tmp_path / "records.json").write_text(json.dumps(records), encoding="utf-8")
    (tmp_path / "releases.json").write_text(json.dumps(releases), encoding="utf-8")
    return [
        "--root", str(tmp_path),
        "--records", str(tmp_path / "records.json"),
        "--releases", str(tmp_path / "releases.json"),
    ]  # fmt: skip


def test_the_concept_doi_comes_from_the_citation_card() -> None:
    doi, record_id = zenodo.concept_doi(ROOT / "CITATION.cff")

    assert doi == CONCEPT
    assert record_id == "22103110"


def test_a_card_without_a_doi_is_refused(tmp_path: pathlib.Path) -> None:
    (tmp_path / "CITATION.cff").write_text("title: x\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="no `doi:"):
        zenodo.concept_doi(tmp_path / "CITATION.cff")


def test_an_archive_that_says_what_the_releases_say_is_green(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    records = [
        record("0.1.6", "10.5281/zenodo.22166207"),
        record("evidence-freeze-1", "10.5281/zenodo.22103111"),
    ]

    assert zenodo.main(a_tree(tmp_path, records, ["v0.1.6", "evidence-freeze-1"])) == 0
    assert "2 versions under 10.5281/zenodo.22103110, 2 releases" in capsys.readouterr().out


def test_a_release_the_archive_does_not_hold_is_red_and_named(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The direction that matters most: a release published and never archived — the DOI
    the README promises for every version does not exist for this one."""
    records = [record("0.1.5", "10.5281/zenodo.22164151")]

    assert zenodo.main(a_tree(tmp_path, records, ["v0.1.5", "v0.1.6"])) == 1
    assert "release 0.1.6 has no archived version" in capsys.readouterr().err


def test_an_archived_version_with_no_release_is_red_too(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    records = [record("0.1.5", "10.5281/zenodo.22164151"), record("0.9.0", "10.5281/zenodo.1")]

    assert zenodo.main(a_tree(tmp_path, records, ["v0.1.5"])) == 1
    assert (
        "archived version 0.9.0 (10.5281/zenodo.1) has no release here" in capsys.readouterr().err
    )


def test_a_record_under_another_concept_is_red(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two cards agreeing with each other and both wrong is what a cross-check cannot see —
    so the concept the archive answers with is held to the one the card advertises."""
    records = [record("0.1.5", "10.5281/zenodo.22164151", concept="10.5281/zenodo.999")]

    assert zenodo.main(a_tree(tmp_path, records, ["v0.1.5"])) == 1
    assert (
        "sits under concept 10.5281/zenodo.999, but CITATION.cff advertises"
        in capsys.readouterr().err
    )


def test_a_record_without_a_version_is_skipped_by_the_map_and_reported_by_problems() -> None:
    """The map cannot hold it; the check must still say it is there."""
    records: list[dict[str, Any]] = [
        {"doi": "x", "conceptdoi": CONCEPT, "metadata": {}},
        {"doi": "y", "conceptdoi": CONCEPT},
    ]

    assert zenodo.versions(records) == {}
    assert zenodo.problems({}, set(), CONCEPT, []) == []
    found = zenodo.problems({}, set(), CONCEPT, records)
    assert found == [
        "record x carries no version — it cannot be matched to a release",
        "record y carries no version — it cannot be matched to a release",
    ]


def test_two_records_under_one_version_are_red_not_collapsed(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A dict keyed by version keeps the last record: the review of 2026-08-30 fed two
    `0.1.6` records and one without a version and got "the archive says what the releases
    say". Both are named now, and the exit is 1."""
    records = [
        record("0.1.6", "10.5281/zenodo.1"),
        record("0.1.6", "10.5281/zenodo.2"),
        {"doi": "10.5281/zenodo.3", "conceptdoi": CONCEPT, "metadata": {}},
    ]

    assert zenodo.main(a_tree(tmp_path, records, ["v0.1.6"])) == 1
    err = capsys.readouterr().err
    assert "records 10.5281/zenodo.1 and 10.5281/zenodo.2 both claim version 0.1.6" in err
    assert "record 10.5281/zenodo.3 carries no version" in err


def test_a_tag_is_spelled_as_the_archive_spells_it() -> None:
    assert zenodo.bare("v0.1.6") == "0.1.6"
    assert zenodo.bare("evidence-freeze-1") == "evidence-freeze-1"


@pytest.mark.parametrize(
    "records",
    [{"hits": []}, ["a string", "another"], "just text"],
    ids=["dict", "list-of-strings", "string"],
)
def test_a_records_file_of_the_wrong_shape_is_refused_not_a_traceback(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], records: object
) -> None:
    """A wrong shape got an AttributeError where every other bad input gets exit 2."""
    argv = a_tree(tmp_path, [], ["v0.1.0"])
    (tmp_path / "records.json").write_text(json.dumps(records), encoding="utf-8")

    assert zenodo.main(argv) == 2
    assert "does not hold a list of record mappings" in capsys.readouterr().err


def test_a_releases_file_of_the_wrong_shape_is_refused_too(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`str()` coerced any shape into a tag silently; a dict is not a list of tags."""
    argv = a_tree(tmp_path, [record("0.1.0", "10.5281/zenodo.1")], [])
    (tmp_path / "releases.json").write_text(json.dumps({"tag": "v0.1.0"}), encoding="utf-8")

    assert zenodo.main(argv) == 2
    assert "does not hold a list of tag strings" in capsys.readouterr().err


def test_an_archive_that_cannot_be_asked_is_exit_2(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "CITATION.cff").write_text(f"doi: {CONCEPT}\n", encoding="utf-8")

    def refuse(_url: str, **_kwargs: Any) -> Any:  # noqa: ANN401 — never returns; mirrors urlopen
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)

    assert zenodo.main(["--root", str(tmp_path), "--releases", str(tmp_path / "none.json")]) == 2
    assert "cannot read the archive or the releases" in capsys.readouterr().err


def test_the_releases_that_cannot_be_asked_are_exit_2(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "CITATION.cff").write_text(f"doi: {CONCEPT}\n", encoding="utf-8")
    (tmp_path / "records.json").write_text("[]", encoding="utf-8")

    def refuse(path: str, **_kwargs: Any) -> Any:  # noqa: ANN401 — never returns
        raise PermissionError(path)

    monkeypatch.setattr(gh, "api_pages", refuse)

    assert zenodo.main(["--root", str(tmp_path), "--records", str(tmp_path / "records.json")]) == 2
    assert "cannot read the archive or the releases" in capsys.readouterr().err


def test_release_tags_lose_their_v_and_nothing_else(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        gh,
        "api_pages",
        lambda _p: [{"tag_name": "v0.1.6"}, {"tag_name": "evidence-freeze-1"}, "junk"],
    )

    assert zenodo._released() == {"0.1.6", "evidence-freeze-1"}  # noqa: SLF001 — the shape is the point


class _Answer(io.BytesIO):
    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def test_the_archive_is_paged_at_25_until_a_short_page(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zenodo refuses `size=100` with a 400 (measured 2026-08-30); 25 is the page, and a
    full page is followed by the next one."""
    asked: list[str] = []

    def answer(url: str, **_kwargs: Any) -> _Answer:  # noqa: ANN401 — mirrors urlopen
        asked.append(url)
        page = int(url.rsplit("page=", 1)[1])
        n = 25 if page == 1 else 3
        hits = [record(f"0.{page}.{i}", f"d{page}{i}") for i in range(n)]
        return _Answer(json.dumps({"hits": {"hits": hits}}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", answer)

    records = zenodo.fetch_records("22103110")

    assert len(records) == 28
    assert [u.rsplit("page=", 1)[1] for u in asked] == ["1", "2"]
    assert all(f"size={zenodo.PAGE_SIZE}&" in u for u in asked)
    assert zenodo.PAGE_SIZE == 25


def test_an_archive_answer_without_a_list_is_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda _u, **_k: _Answer(json.dumps({"message": "x"}).encode()),
    )

    with pytest.raises(RuntimeError, match="without a record list"):
        zenodo.fetch_records("22103110")


def test_an_archive_that_never_ends_is_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    full = json.dumps({"hits": {"hits": [record("x", "y")] * 25}}).encode()
    monkeypatch.setattr(urllib.request, "urlopen", lambda _u, **_k: _Answer(full))

    with pytest.raises(RuntimeError, match="kept answering full pages"):
        zenodo.fetch_records("22103110")


def test_the_call_declares_the_wrappers_time_budget() -> None:
    assert zenodo.NETWORK_TIMEOUT_SECONDS == gh.NETWORK_TIMEOUT_SECONDS


def test_the_archive_is_asked_with_a_time_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """`urlopen` without `timeout=` waits forever on a socket that never answers — the one
    network call here that no test held; dropping the argument left the suite green
    (self-audit, 2026-08-31)."""
    asked: list[dict[str, object]] = []

    class Empty(io.BytesIO):
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    def capture(_url: str, **kwargs: object) -> Empty:
        asked.append(kwargs)
        return Empty(b'{"hits": {"hits": []}}')

    monkeypatch.setattr(urllib.request, "urlopen", capture)
    zenodo.fetch_records("22103110")
    assert asked, "the archive was never asked"
    budgets = [k.get("timeout") for k in asked]
    assert all(isinstance(b, int) and b > 0 for b in budgets), asked
    assert asked[0]["timeout"] == gh.NETWORK_TIMEOUT_SECONDS


# ------------------------------------------------------------ the ceiling on the answer


class _Clock:
    """A clock that jumps an hour every time it is asked — a drip feed, without the wait."""

    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        self.now += 3600.0
        return self.now


def test_an_answer_that_never_ends_is_refused_by_the_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`urlopen(timeout=N)` bounds the gap between packets, not the download: measured
    against a server writing 1KB every 0.5s with the ceiling at **1 second**, the reader was
    held for **12.0 seconds** and stopped because the server did, not because the ceiling
    fired (self-audit round 19, 2026-09-02). The answer now has a deadline of its own."""
    monkeypatch.setattr(zenodo, "time", _Clock())
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_k: _Answer(b"[" + b"0," * 100))

    with pytest.raises(RuntimeError, match="still arriving"):
        zenodo.fetch_records("22103110")


def test_an_answer_longer_than_the_ceiling_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """And the other ceiling `json.load(response)` never had: how large it may be. Without
    one, a reader on a CI job holds whatever the other end decides to send."""
    monkeypatch.setattr(zenodo, "MAX_ANSWER_BYTES", 64)
    monkeypatch.setattr(zenodo, "READ_CHUNK", 16)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_k: _Answer(b"x" * 4096))

    with pytest.raises(RuntimeError, match="longer than 64 bytes"):
        zenodo.fetch_records("22103110")
