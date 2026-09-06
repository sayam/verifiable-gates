"""`release_body` — the release notes read back against the sections they were cut from.

The body of a release lives only on the platform. On 2026-09-05 v0.3.1 shipped with the
body `v0.3.1`, one word, because a runbook said `--notes-from-tag` and the tag message was
that word. The rule that followed was kept by hand for two cuts before this reader replaced
the hand, and these tests are what hold the reader.

Two of them matter more than the rest. **CRLF**: GitHub stores a body with `\r\n`, so a
comparison that does not fold them reports every line different on two texts that are
identical on screen — a check that cannot tell "wrong" from "wrong line endings" reports
neither. And **the register**: `BODY_PREDATES_THE_RULE` names three releases published
before the rule existed, and it is held in both directions by the reader itself, so a name
cannot be parked there to hide a body that drifted afterwards.

No test here reaches the network. The releases are fed in as data, which is the shape the
`--releases` flag exists for.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

from verifiable_gates import gh, release_body

ROOT = pathlib.Path(__file__).resolve().parent.parent

CHANGELOG = """# Changelog

Notable changes.

## [Unreleased]

## [0.2.0] - 2026-09-04

The second one.

### Added

- something

## [0.1.0] - 2026-08-28

The first one.

[Unreleased]: https://example.invalid/compare/v0.2.0...HEAD
[0.2.0]: https://example.invalid/2
[0.1.0]: https://example.invalid/1
"""

SECOND = "The second one.\n\n### Added\n\n- something"
FIRST = "The first one."


def a_release(tag: str, body: str) -> dict[str, Any]:
    return {"tag_name": tag, "body": body}


def both_match() -> list[dict[str, Any]]:
    return [a_release("v0.2.0", SECOND), a_release("v0.1.0", FIRST)]


@pytest.fixture
def unexcused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Most cases below are about the comparison, not about the three real exceptions."""
    monkeypatch.setattr(release_body, "BODY_PREDATES_THE_RULE", {})


# ---------------------------------------------------------------- reading the file


def test_a_section_is_its_entries_without_the_heading_or_the_link_block() -> None:
    """The release page carries the version in its title, and the link block belongs to
    the file — neither is part of what a reader is given."""
    found = release_body.sections(CHANGELOG)
    assert set(found) == {"0.2.0", "0.1.0"}
    assert found["0.2.0"] == SECOND
    assert found["0.1.0"] == FIRST
    assert "[0.1.0]: https" not in found["0.1.0"]
    assert "## [" not in found["0.2.0"]


def test_the_unreleased_link_is_part_of_the_block_not_of_the_oldest_section() -> None:
    """The line that is rewritten at every cut.

    `[Unreleased]: …compare/vX.Y.Z...HEAD` sits at the top of the link block, and the block
    follows the **oldest** section — so a reader that stopped at the first `[0.` kept that
    line inside it. Measured on the real file 2026-09-06, an hour after this reader said
    18 of 18 held: the v0.6.0 cut moved that one line and v0.1.0 went red, two texts of
    19 711 characters each differing in the line nobody reads.
    """
    found = release_body.sections(CHANGELOG)

    assert found["0.1.0"] == FIRST
    assert "Unreleased" not in found["0.1.0"]
    assert "compare" not in found["0.1.0"]


@pytest.mark.usefixtures("unexcused")
def test_a_body_published_with_the_link_block_still_matches_its_section() -> None:
    """Three bodies were written from an extraction that kept the block. Stripping it on
    the file's side only would make each of them a finding forever, about a line that is
    the file's plumbing — so both sides are read the same way."""
    published = (
        FIRST
        + "\n\n[Unreleased]: https://example.invalid/compare/v0.1.0...HEAD\n[0.1.0]: https://example.invalid/1"
    )

    assert (
        release_body.problems(release_body.sections(CHANGELOG), [a_release("v0.1.0", published)])
        == []
    )


@pytest.mark.usefixtures("unexcused")
def test_a_body_that_differs_above_the_link_block_is_still_a_finding() -> None:
    """The control: the stripping must not swallow the prose it protects."""
    published = "The first one, edited by hand.\n\n[0.1.0]: https://example.invalid/1"

    assert release_body.problems(release_body.sections(CHANGELOG), [a_release("v0.1.0", published)])


def test_unreleased_is_not_a_section() -> None:
    """`## [Unreleased]` has no date and is not a release; a reader given it would be
    given the notes of a cut that has not happened."""
    assert "Unreleased" not in release_body.sections(CHANGELOG)


# ---------------------------------------------------------------- the line endings


@pytest.mark.parametrize("newline", ["\r\n", "\r"])
@pytest.mark.usefixtures("unexcused")
def test_a_body_stored_with_carriage_returns_matches_the_section(newline: str) -> None:
    """The measured trap: `gh release view v0.4.0 --json body -q .body | grep -c $'\\r'`
    answered 144 on a body that was uploaded from the file it is compared against."""
    stored = SECOND.replace("\n", newline)
    assert release_body.body_of(a_release("v0.2.0", stored)) == SECOND
    assert release_body.problems({"0.2.0": SECOND}, [a_release("v0.2.0", stored)]) == []


@pytest.mark.parametrize("body", ["\n\n" + FIRST + "\n\n\n", FIRST])
@pytest.mark.usefixtures("unexcused")
def test_blank_lines_at_either_end_are_not_a_difference(body: str) -> None:
    """`gh` appends a trailing newline; a diff without this was one empty line long on a
    body that matched (measured 2026-09-05)."""
    assert release_body.problems({"0.1.0": FIRST}, [a_release("v0.1.0", body)]) == []


# ---------------------------------------------------------------- what it refuses


@pytest.mark.usefixtures("unexcused")
def test_a_body_that_is_not_the_section_is_named_with_both_lengths() -> None:
    """The v0.3.1 shape: a body of one word where the section is a page."""
    (said,) = release_body.problems({"0.1.0": FIRST}, [a_release("v0.1.0", "v0.1.0")])
    assert "v0.1.0: the release body is not the CHANGELOG section" in said
    assert "(6 characters against 14)" in said
    assert "gh release edit v0.1.0 --notes-file" in said
    assert "never --notes-from-tag" in said


@pytest.mark.usefixtures("unexcused")
def test_a_release_with_no_section_is_a_finding() -> None:
    (said,) = release_body.problems({"0.1.0": FIRST}, [a_release("v9.9.9", "anything")])
    assert "v9.9.9 is a release with no `## [9.9.9]` section" in said


@pytest.mark.parametrize("tag", ["evidence-freeze-1", "nightly", "", "0.1.0"])
@pytest.mark.usefixtures("unexcused")
def test_a_tag_that_is_not_a_version_is_not_judged(tag: str) -> None:
    """`evidence-freeze-1` is a different commit from `v0.1.0` on purpose (`DECISIONS.md`
    `freeze-tag-vs-release`). There is no section for it to equal, and saying so would be
    a finding about a decision that was made."""
    assert release_body.problems({"0.1.0": FIRST}, [a_release(tag, "whatever")]) == []


# ---------------------------------------------------------------- the register, both ways


def test_a_release_in_the_register_may_differ(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release_body, "BODY_PREDATES_THE_RULE", {"v0.1.0": "hand-written"})
    assert release_body.problems({"0.1.0": FIRST}, [a_release("v0.1.0", "old text")]) == []


def test_a_register_entry_that_now_matches_must_be_taken_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The register only shrinks. A body that has since been given its section is a name
    to remove, not a permission to keep."""
    monkeypatch.setattr(release_body, "BODY_PREDATES_THE_RULE", {"v0.1.0": "hand-written"})
    (said,) = release_body.problems({"0.1.0": FIRST}, [a_release("v0.1.0", FIRST)])
    assert "v0.1.0 now says what its section says — take it out" in said


def test_a_register_entry_that_is_not_a_release_is_a_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A name parked here for a release that does not exist excuses nothing and hides the
    fact that it excuses nothing."""
    monkeypatch.setattr(release_body, "BODY_PREDATES_THE_RULE", {"v9.9.9": "never existed"})
    (said,) = release_body.problems({"0.1.0": FIRST}, [a_release("v0.1.0", FIRST)])
    assert "v9.9.9 is in BODY_PREDATES_THE_RULE and is not a release here" in said


def test_the_shipped_register_is_empty() -> None:
    """**Shrink only, and empty since 2026-09-06.** v0.1.0, v0.1.6 and v0.1.7 carried
    hand-written announcements from before the rule; each was given its section that day.
    An entry appearing here is a body somebody chose not to fix, and it should have to be
    argued for in a pull request rather than added quietly."""
    assert release_body.BODY_PREDATES_THE_RULE == {}, (
        f"releases excused from saying what their section says: "
        f"{sorted(release_body.BODY_PREDATES_THE_RULE)} — give each one its section with"
        " `gh release edit <tag> --notes-file …`, or argue for the entry here"
    )


def test_a_name_in_the_register_must_be_a_version_with_a_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The shape the register would have to keep if it ever filled again: a version tag and
    a reason that says something. Held on a planted entry, because the shipped one is empty
    and a test over nothing proves nothing."""
    monkeypatch.setattr(
        release_body,
        "BODY_PREDATES_THE_RULE",
        {"v0.1.0": "a hand-written announcement from before the rule"},
    )
    for tag, why in release_body.BODY_PREDATES_THE_RULE.items():
        assert release_body.VERSION_TAG.match(tag), f"{tag} is not a version tag"
        assert len(why.split()) >= 4, f"{tag} is excused by {why!r}, which says nothing"


# ---------------------------------------------------------------- the three answers


def _run(tmp_path: pathlib.Path, changelog: str, releases: list[dict[str, Any]]) -> int:
    (tmp_path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    feed = tmp_path / "releases.json"
    feed.write_text(json.dumps(releases), encoding="utf-8")
    return release_body.main(["--root", str(tmp_path), "--releases", str(feed)])


@pytest.mark.usefixtures("unexcused")
def test_every_release_matching_is_exit_zero_and_says_how_many(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(tmp_path, CHANGELOG, both_match()) == 0
    said = capsys.readouterr().out
    assert "every release says what its section says: 2 of 2 held" in said
    assert "predates" not in said, "with nothing excused the report should not mention it"


def test_the_count_says_how_many_are_excused(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(release_body, "BODY_PREDATES_THE_RULE", {"v0.1.0": "hand-written"})
    assert _run(tmp_path, CHANGELOG, [a_release("v0.2.0", SECOND), a_release("v0.1.0", "old")]) == 0
    assert "1 of 2 held, 1 whose body predates the rule" in capsys.readouterr().out


@pytest.mark.usefixtures("unexcused")
def test_a_drifted_body_is_exit_one_on_stderr(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(tmp_path, CHANGELOG, [a_release("v0.2.0", "v0.2.0")]) == 1
    said = capsys.readouterr()
    assert "the release body is not the CHANGELOG section" in said.err
    assert said.out == "", "a finding goes to stderr, not to the report"


def test_a_changelog_with_no_released_section_is_exit_two(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Nothing was compared, and a run that compared nothing is not a clean run."""
    assert _run(tmp_path, "# Changelog\n\n## [Unreleased]\n", both_match()) == 2
    assert "no released section — nothing was compared" in capsys.readouterr().err


def test_a_changelog_that_cannot_be_read_is_exit_two(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    feed = tmp_path / "releases.json"
    feed.write_text("[]", encoding="utf-8")
    assert release_body.main(["--root", str(tmp_path), "--releases", str(feed)]) == 2
    assert "cannot read the releases or the CHANGELOG" in capsys.readouterr().err


def test_a_releases_file_that_is_not_json_is_exit_two(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    feed = tmp_path / "releases.json"
    feed.write_text("{not json", encoding="utf-8")
    assert release_body.main(["--root", str(tmp_path), "--releases", str(feed)]) == 2
    assert "cannot read the releases or the CHANGELOG" in capsys.readouterr().err


@pytest.mark.usefixtures("unexcused")
def test_a_row_that_is_not_an_object_is_skipped(tmp_path: pathlib.Path) -> None:
    """The platform's shape is whatever that endpoint returns; a string in the list is not
    a release and must not become a traceback."""
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    feed = tmp_path / "releases.json"
    feed.write_text(json.dumps(["not a release", *both_match()]), encoding="utf-8")
    assert release_body.main(["--root", str(tmp_path), "--releases", str(feed)]) == 0


@pytest.mark.usefixtures("unexcused")
def test_with_no_file_it_asks_the_platform(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The road the cron takes. Without this the live branch is only ever described, and a
    reader that could not fetch would be found by the cron rather than by the suite."""
    asked: list[str] = []

    def releases(path: str) -> list[Any]:
        asked.append(path)
        return [*both_match(), "not a release"]

    monkeypatch.setattr(gh, "api_pages", releases)
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    assert release_body.main(["--root", str(tmp_path)]) == 0
    assert asked == ["repos/:owner/:repo/releases"]
    assert "2 of 2 held" in capsys.readouterr().out


def test_this_repositorys_own_changelog_parses_into_every_released_version() -> None:
    """The reader against the real file: every `## [x.y.z]` heading becomes a section with
    something in it. A parser that silently returned nothing would pass every case above."""
    found = release_body.sections((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    assert len(found) >= 18, f"only {len(found)} sections parsed out of this CHANGELOG"
    assert all(text.strip() for text in found.values()), "a section parsed as empty"
    assert "0.5.0" in found
