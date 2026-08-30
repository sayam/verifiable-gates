"""The one reader every census sees its history through — proved on each way of not seeing.

Three censuses used to read their history separately, each catching a different
set of failures, and the differences were the finding: a missing file was a
traceback, malformed JSON was a traceback, and a valid empty file was a pass.
One reader, one contract, one test file that holds it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from verifiable_gates import history

if TYPE_CHECKING:
    import pathlib


def test_a_file_is_read_when_given_and_the_fetcher_is_not_called(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "runs.json"
    path.write_text('[{"id": 1}]', encoding="utf-8")

    def must_not_run() -> list[object]:
        pytest.fail("offline mode reached for the platform")

    assert history.read(str(path), must_not_run, shape=list) == [{"id": 1}]


def test_the_fetcher_answers_when_there_is_no_file() -> None:
    assert history.read(None, lambda: [{"id": 2}], shape=list) == [{"id": 2}]


def test_the_fetcher_raising_is_let_through_unchanged() -> None:
    """The platform's own words reach the caller's message — not a rewording."""

    def refuse() -> list[object]:
        raise PermissionError("HTTP 403")

    with pytest.raises(PermissionError, match="403"):
        history.read(None, refuse, shape=list)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("[", "not JSON"),
        ("{}", "not a list"),
        ("[]", "history is empty"),
    ],
)
def test_each_way_of_not_seeing_is_unreadable(
    tmp_path: pathlib.Path, text: str, expected: str
) -> None:
    path = tmp_path / "runs.json"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(history.UnreadableError, match=expected):
        history.read(str(path), list, shape=list)


def test_a_missing_file_is_unreadable_not_a_traceback(tmp_path: pathlib.Path) -> None:
    with pytest.raises(history.UnreadableError, match="No such file"):
        history.read(str(tmp_path / "absent.json"), list, shape=list)


def test_unreadable_is_a_runtime_error_so_every_caller_catches_it() -> None:
    """The censuses catch `RuntimeError`; a new class outside it would slip past all three."""
    assert issubclass(history.UnreadableError, RuntimeError)


def test_empty_is_allowed_when_the_caller_says_it_means_something(tmp_path: pathlib.Path) -> None:
    """For the schedule census `{}` is a real answer — "no scheduled run ever"."""
    path = tmp_path / "state.json"
    path.write_text("{}", encoding="utf-8")

    assert history.read(str(path), dict, shape=dict, must_hold_something=False) == {}


def test_a_record_without_the_fields_the_caller_named_is_unreadable() -> None:
    """A list of the wrong records is not this history — said with the record and the field."""
    with pytest.raises(history.UnreadableError, match=r"record 1 has no \['created_at'\]"):
        history.read(
            None, lambda: [{"created_at": "x"}, {"other": 1}], shape=list, fields=("created_at",)
        )


def test_a_record_that_is_not_a_mapping_is_unreadable() -> None:
    with pytest.raises(history.UnreadableError, match="record 0 is a int, not a mapping"):
        history.read(None, lambda: [1], shape=list, fields=("id",))


def test_the_output_of_gh_run_list_is_named_as_such() -> None:
    """`databaseId`/`createdAt` is the shape people have to hand; the message says what to do."""
    record = {"databaseId": 1, "createdAt": "2026-08-30T00:00:00Z", "conclusion": "failure"}
    with pytest.raises(history.UnreadableError, match="looks like `gh run list --json`"):
        history.read(None, lambda: [record], shape=list, fields=("id", "failures"))


def test_fields_are_not_asked_of_a_mapping_history() -> None:
    assert history.read(None, lambda: {"a": 1}, shape=dict, fields=("x",)) == {"a": 1}
