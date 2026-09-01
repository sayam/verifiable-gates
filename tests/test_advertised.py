"""A number several places advertise has to be made true by one command.

The tests still decide whether a number is right; this only does the typing. So
what has to be proven here is narrow and unforgiving: it changes exactly the
characters it claims to, it reports what it could not find instead of passing
over it, and it never rewrites the sentence around the value.

The field outside the repository gets its own section because it fails
differently: nothing there produces a diff, so no test ever runs against it and
nobody sees it age.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import pathlib

from verifiable_gates import advertised

GATES = r"(\d+) machine-checked gates"
PLACE = advertised.Place("README.md", GATES)


def write(root: pathlib.Path, name: str, body: str) -> pathlib.Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


# ------------------------------------------------------- the one primitive


def test_only_the_first_group_moves() -> None:
    """The context around the value has to survive, character for character."""
    patched = advertised.replace_group_one(
        "This repository has 112 machine-checked gates today.",
        r"(\d+) machine-checked gates",
        "114",
    )

    assert patched == "This repository has 114 machine-checked gates today."


def test_a_value_that_is_a_whole_line_needs_no_special_case() -> None:
    """A tally is a value like any other — the reference implementation branched for it.

    That branch lived in two functions and was the only branch either of them
    had, which is the shape of a special case that should have been a type.
    """
    patched = advertised.replace_group_one(
        "the split is security 40 · devx 30 and nothing else",
        r"the split is (security \d+ · devx \d+)",
        "security 41 · devx 31",
    )

    assert patched == "the split is security 41 · devx 31 and nothing else"


def test_only_the_first_occurrence_is_touched_by_default() -> None:
    """Two sentences quoting the same fact are two places, each with its own pattern."""
    patched = advertised.replace_group_one("say 1 and say 1", r"say (\d+)", "2")

    assert patched == "say 2 and say 1"


# ------------------------------------------------- inside the repository


def test_a_place_that_already_agrees_is_not_reported(tmp_path: pathlib.Path) -> None:
    write(tmp_path, "README.md", "114 machine-checked gates\n")

    assert advertised.drift(tmp_path, {"gates": [PLACE]}, {"gates": "114"}) == []


def test_a_place_that_fell_behind_is_reported_with_both_numbers(
    tmp_path: pathlib.Path,
) -> None:
    write(tmp_path, "README.md", "112 machine-checked gates\n")

    found = advertised.drift(tmp_path, {"gates": [PLACE]}, {"gates": "114"})

    assert [(item.said, item.want) for item in found] == [("112", "114")]


def test_a_pattern_that_matches_nothing_is_reported_not_skipped(
    tmp_path: pathlib.Path,
) -> None:
    """Going quiet on a missing match means saying "all agree" having read nothing.

    This is the failure mode that matters: the sentence gets reworded, the
    pattern stops matching, and the synchroniser reports success forever after.
    """
    write(tmp_path, "README.md", "the gate count now lives somewhere else\n")

    found = advertised.drift(tmp_path, {"gates": [PLACE]}, {"gates": "114"})

    assert len(found) == 1
    assert found[0].is_missing


def test_writing_fixes_the_value_and_nothing_around_it(tmp_path: pathlib.Path) -> None:
    path = write(tmp_path, "README.md", "It has 112 machine-checked gates, and a badge.\n")

    advertised.write(tmp_path, advertised.drift(tmp_path, {"gates": [PLACE]}, {"gates": "114"}))

    assert path.read_text(encoding="utf-8") == "It has 114 machine-checked gates, and a badge.\n"


def test_writing_leaves_a_place_it_could_not_find_alone(tmp_path: pathlib.Path) -> None:
    """There is nowhere to put the value, and inventing a sentence is not the fix."""
    path = write(tmp_path, "README.md", "the gate count now lives somewhere else\n")
    before = path.read_text(encoding="utf-8")

    advertised.write(tmp_path, advertised.drift(tmp_path, {"gates": [PLACE]}, {"gates": "114"}))

    assert path.read_text(encoding="utf-8") == before


def test_a_write_that_stops_partway_carries_the_places_that_landed(
    tmp_path: pathlib.Path,
) -> None:
    """A correction that stopped halfway has to be able to say what it already changed.

    This synchroniser rewrites the claims a repository publishes, one file at a time. A
    place that cannot be written after two others already have leaves a checkout that is
    neither what it was nor what it should be, and the caller could only say "cannot
    write the fix" — which reads as *nothing was written* (self-audit round 16,
    2026-09-01). Nothing here is atomic and nothing needs to be: every place is a tracked
    file, so the bytes are recoverable from the history. Being told is what was missing.
    """
    first = write(tmp_path, "README.md", "It has 112 machine-checked gates.\n")
    second = write(tmp_path, "CITATION.cff", "It has 112 machine-checked gates.\n")
    places = [advertised.Place("README.md", GATES), advertised.Place("CITATION.cff", GATES)]
    second.chmod(0o444)
    try:
        drifting = advertised.drift(tmp_path, {"gates": places}, {"gates": "114"})

        with pytest.raises(advertised.PartialWriteError) as stopped:
            advertised.write(tmp_path, drifting)
    finally:
        second.chmod(0o644)

    assert [item.place.path for item in stopped.value.written] == ["README.md"], (
        "the places that landed were not carried out with the failure"
    )
    assert isinstance(stopped.value.problem, OSError)
    assert "114" in first.read_text(encoding="utf-8"), "the first place was not written after all"


def test_a_write_with_nothing_written_yet_still_names_the_failure(tmp_path: pathlib.Path) -> None:
    """The control: when the **first** place cannot be written, nothing landed and the
    error says so with an empty list — a caller must be able to tell the two apart."""
    only = write(tmp_path, "README.md", "It has 112 machine-checked gates.\n")
    drifting = advertised.drift(tmp_path, {"gates": [PLACE]}, {"gates": "114"})
    only.chmod(0o444)
    try:
        with pytest.raises(advertised.PartialWriteError) as stopped:
            advertised.write(tmp_path, drifting)
    finally:
        only.chmod(0o644)

    assert stopped.value.written == []


def test_every_place_of_every_fact_is_visited(tmp_path: pathlib.Path) -> None:
    """One fact quoted in three files is three places, and a partial fix is a red test tomorrow."""
    write(tmp_path, "README.md", "112 machine-checked gates\n")
    write(tmp_path, "docs/GUIDE.md", "there are 112 gates\n")
    write(tmp_path, "CHANGELOG.md", "release with 7 records\n")

    found = advertised.drift(
        tmp_path,
        {
            "gates": [PLACE, advertised.Place("docs/GUIDE.md", r"there are (\d+) gates")],
            "records": [advertised.Place("CHANGELOG.md", r"with (\d+) records")],
        },
        {"gates": "114", "records": "8"},
    )

    assert sorted(item.place.path for item in found) == [
        "CHANGELOG.md",
        "README.md",
        "docs/GUIDE.md",
    ]


def test_a_fact_with_no_value_is_an_error_not_a_silent_pass(tmp_path: pathlib.Path) -> None:
    """A manifest naming a fact nobody measures must not read as "nothing to do"."""
    write(tmp_path, "README.md", "112 machine-checked gates\n")

    with pytest.raises(KeyError):
        advertised.drift(tmp_path, {"gates": [PLACE]}, {})


# ------------------------------------------------ the field outside the repository

DESCRIPTION = "v2.2.0 · 112 machine-checked gates, 77 ADRs — governance you can run"
EXPECTATIONS = [
    advertised.Expectation("version", r"v(\d[\w.+-]*)", "2.3.0"),
    advertised.Expectation("gates", r"(\d+) machine-checked gates", "114"),
    advertised.Expectation("records", r"(\d+) ADRs", "78"),
]


def test_a_field_outside_the_repository_is_read_the_same_way() -> None:
    found = advertised.field_drift(DESCRIPTION, EXPECTATIONS)

    assert found == [
        ("version", "2.2.0", "2.3.0"),
        ("gates", "112", "114"),
        ("records", "77", "78"),
    ]


def test_a_field_that_agrees_says_nothing() -> None:
    agreed = advertised.field_patched(DESCRIPTION, EXPECTATIONS)

    assert advertised.field_drift(agreed, EXPECTATIONS) == []


def test_patching_a_field_keeps_the_prose_somebody_wrote() -> None:
    """Rebuilding the field from the values would be shorter and would delete the rest.

    Nobody would see it go: a field outside the repository leaves no diff behind,
    which is the whole reason it drifted in the first place.
    """
    patched = advertised.field_patched(DESCRIPTION, EXPECTATIONS)

    assert patched == "v2.3.0 · 114 machine-checked gates, 78 ADRs — governance you can run"


def test_a_claim_missing_from_the_field_is_reported() -> None:
    """A field that lost the sentence is not a field that agrees."""
    found = advertised.field_drift("just some words", EXPECTATIONS)

    assert [label for label, said, _ in found if said == advertised.MISSING] == [
        "version",
        "gates",
        "records",
    ]


def test_patching_cannot_invent_a_claim_that_is_not_there() -> None:
    """With nowhere to put the value, the text comes back untouched rather than rewritten."""
    assert advertised.field_patched("just some words", EXPECTATIONS) == "just some words"
