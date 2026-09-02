"""One reader for `on:`, because a parser is a command and copies of it drift.

The reference implementation had this idiom copied in five places, three of them
broken the same way — and they had already drifted apart: one guarded itself with
`isinstance`, two did not. So the tests here are mostly about the shapes that
broke, and about the one nobody expects.

The shape nobody expects is that the key is often the boolean `True`. YAML 1.1
reads an unquoted `on:` as a boolean, so a reader looking only for the string
`"on"` finds nothing in almost every real workflow — while looking, and while
returning an answer that reads like "no triggers declared".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import yaml

from verifiable_gates import workflows

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Callable


def parsed(text: str) -> workflows.Workflow:
    """Go through YAML rather than building the dict, so the quirks are real.

    The return type is the reader's own — keys are not all strings, which is the
    quirk these tests exist for.
    """
    loaded: workflows.Workflow = yaml.safe_load(text)
    return loaded


# ---------------------------------------------------------------- the three shapes


def test_a_single_event_as_a_string() -> None:
    assert workflows.triggers(parsed("on: push\njobs: {}\n")) == {"push"}


def test_a_list_of_events() -> None:
    """The shape that raised TypeError in three of the five copies."""
    assert workflows.triggers(parsed("on: [push, pull_request]\njobs: {}\n")) == {
        "push",
        "pull_request",
    }


def test_a_mapping_of_events() -> None:
    text = "on:\n  pull_request:\n  schedule:\n    - cron: '0 3 * * *'\njobs: {}\n"

    assert workflows.triggers(parsed(text)) == {"pull_request", "schedule"}


def test_an_unquoted_on_really_arrives_as_a_boolean_key() -> None:
    """The premise the reader is built on — if YAML ever stops doing this, say so here."""
    assert True in parsed("on: push\njobs: {}\n"), "unquoted on: no longer parses as a boolean"


def test_a_quoted_on_is_read_too() -> None:
    """Some projects quote it. Both must work, or the reader is right by luck."""
    assert workflows.triggers(parsed('"on": push\njobs: {}\n')) == {"push"}


def test_a_workflow_with_no_triggers_answers_empty_not_none() -> None:
    assert workflows.triggers({"jobs": {}}) == set()


# ---------------------------------------------------------------- asking about one event


@pytest.mark.parametrize(
    ("text", "event", "expected"),
    [
        ("on: push\njobs: {}\n", "push", True),
        ("on: push\njobs: {}\n", "pull_request", False),
        ("on: [push, pull_request]\njobs: {}\n", "pull_request", True),
        ("on:\n  pull_request:\njobs: {}\n", "pull_request", True),
    ],
)
def test_runs_on_answers_for_every_shape(text: str, event: str, expected: bool) -> None:  # noqa: FBT001 — the expected value, not a flag
    assert workflows.runs_on(parsed(text), event) is expected


def test_a_shapeless_declaration_has_no_config() -> None:
    """`on: [schedule]` can name the event but cannot carry a cron — GitHub agrees.

    "No config" is the correct answer here, not a surrender to a shape the reader
    could not handle.
    """
    assert workflows.event_config(parsed("on: [schedule]\njobs: {}\n"), "schedule") is None


def test_the_config_under_an_event_is_returned() -> None:
    text = "on:\n  schedule:\n    - cron: '0 3 * * *'\njobs: {}\n"

    assert workflows.event_config(parsed(text), "schedule") == [{"cron": "0 3 * * *"}]


# ---------------------------------------------------------------- schedules


def test_every_cron_line_is_returned() -> None:
    text = "on:\n  schedule:\n    - cron: '0 3 * * *'\n    - cron: '0 4 * * 1'\njobs: {}\n"

    assert workflows.schedules(parsed(text)) == ["0 3 * * *", "0 4 * * 1"]


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("on: push\njobs: {}\n", "no schedule at all"),
        ("on: [schedule]\njobs: {}\n", "the event named without config"),
        ("on:\n  schedule:\n    - {}\njobs: {}\n", "an entry with no cron key"),
    ],
)
def test_a_workflow_without_usable_crons_answers_empty(text: str, why: str) -> None:
    assert workflows.schedules(parsed(text)) == [], why


# ---------------------------------------------------------------- files on disk


def test_an_empty_file_reads_as_an_empty_dict(tmp_path: pathlib.Path) -> None:
    """`yaml.safe_load("")` is None, and None would break every caller downstream."""
    path = tmp_path / "empty.yml"
    path.write_text("", encoding="utf-8")

    assert workflows.load(path) == {}


def test_a_directory_is_read_by_name_in_order(tmp_path: pathlib.Path) -> None:
    for name in ("b.yml", "a.yaml", "c.yml"):
        (tmp_path / name).write_text("on: push\njobs: {}\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("not a workflow\n", encoding="utf-8")

    found = workflows.all_workflows(tmp_path)

    assert list(found) == ["a.yaml", "b.yml", "c.yml"], "both extensions, sorted"
    assert "notes.md" not in found


# A workflow this reader cannot read is `RuntimeError`, which every caller already
# answers with "cannot read" and exit 2. It was whatever the read raised, and one
# workflow nobody could open ended `posture --settings` and the rerun census in a
# traceback with exit 1 — the code that means findings (self-audit round 20, 2026-09-03).


def test_a_workflow_nobody_can_read_is_a_sentence_not_a_traceback(
    tmp_path: pathlib.Path,
) -> None:
    (tmp_path / "ci.yml").write_text("on: push\n", encoding="utf-8")
    locked = tmp_path / "locked.yml"
    locked.write_text("on: push\n", encoding="utf-8")
    locked.chmod(0o000)
    try:
        with pytest.raises(RuntimeError, match=r"cannot read the workflow locked\.yml: Permission"):
            workflows.all_workflows(tmp_path)
    finally:
        locked.chmod(0o644)
    assert list(workflows.all_workflows(tmp_path)) == ["ci.yml", "locked.yml"], "the control"


@pytest.mark.parametrize(
    ("plant", "reason"),
    [
        (lambda p: p.symlink_to(p.parent / "gone.yml"), "No such file"),
        (lambda p: p.write_bytes(b"name: caf\xe9\n"), "not UTF-8|invalid"),
        (lambda p: p.write_text("on: [\n", encoding="utf-8"), "while parsing"),
    ],
    ids=["a symlink whose target is gone", "not UTF-8", "YAML the parser rejects"],
)
def test_every_way_a_workflow_cannot_be_read_is_the_same_sentence(
    tmp_path: pathlib.Path, plant: Callable[[pathlib.Path], None], reason: str
) -> None:
    path = tmp_path / "w.yml"
    plant(path)

    with pytest.raises(RuntimeError, match=rf"cannot read the workflow w\.yml: .*({reason})"):
        workflows.load(path)


def test_the_directory_is_an_input_not_a_constant(tmp_path: pathlib.Path) -> None:
    """Baking one project's layout in would make this readable only from that checkout."""
    assert workflows.workflow_dir(tmp_path) == tmp_path / ".github" / "workflows"


def test_jobs_are_returned_and_a_workflow_without_any_answers_empty() -> None:
    assert workflows.jobs({"jobs": {"test": {"runs-on": "x"}}}) == {"test": {"runs-on": "x"}}
    assert workflows.jobs({}) == {}
    assert workflows.jobs({"jobs": None}) == {}
