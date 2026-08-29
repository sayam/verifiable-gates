"""This repository's own advertised numbers, held to what it measures — the gate, dogfooded.

The module under test exists because `advertised` had been proved only on
temporary files while the tree it lives in typed its version into four files
by hand. So the first test here is the dogfood: every place agrees, now, in this
checkout. The rest prove the measuring and the outside field on fakes.
"""

from __future__ import annotations

import pathlib
import re
from typing import Any

import pytest

from verifiable_gates import __version__, advertised, gh, own_numbers

ROOT = pathlib.Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- dogfood


def test_every_place_in_this_repository_says_what_it_measures() -> None:
    """The version, the date, the counts — in every file that quotes them, in both languages."""
    found = advertised.drift(ROOT, own_numbers.PLACES, own_numbers.facts(ROOT))

    assert found == [], "\n".join(
        f"{item.place.path}: says {item.said!r}, should say {item.want!r}" for item in found
    )


def test_every_fact_the_about_field_claims_is_one_that_is_measured() -> None:
    values = own_numbers.facts(ROOT)

    assert set(own_numbers.ABOUT) <= set(values)


def test_the_version_is_the_one_the_package_reports() -> None:
    assert own_numbers.facts(ROOT)["version"] == __version__


def test_the_release_date_is_the_newest_released_heading_of_the_changelog() -> None:
    """`[Unreleased]` does not count — a date has to have happened."""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = own_numbers.RELEASED.search(text)

    assert heading is not None
    assert own_numbers.facts(ROOT)["released"] == heading.group(2)
    assert heading.group(1) == __version__, (
        "the newest released heading is not the version the package reports — "
        "cut the release in the changelog and the package together"
    )


def test_every_released_heading_has_its_link_reference_and_no_link_is_orphaned() -> None:
    """Keep a Changelog's foot: `[x.y.z]: …/releases/tag/vx.y.z` per release. The headings
    for 0.1.4 and 0.1.5 had no line there and `[Unreleased]` compared against v0.1.3 —
    two releases' worth of drift that nothing read (2026-08-30)."""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = {m.group(1) for m in own_numbers.RELEASED.finditer(text)}
    pairs = re.findall(r"(?m)^\[(\d[^\]]*)\]: (\S+)$", text)
    links = dict(pairs)

    # Markdown renders the first definition of a reference; `dict` keeps the
    # last — a stray duplicate pointing at the wrong tag passed (review, 2026-08-30).
    versions = [version for version, _ in pairs]
    assert len(pairs) == len(links), sorted({v for v in versions if versions.count(v) > 1})
    assert set(links) == headings, set(links) ^ headings
    for version, url in links.items():
        assert url.endswith(f"/releases/tag/v{version}"), (version, url)


def test_the_counts_are_the_files_and_rows_on_disk() -> None:
    values = own_numbers.facts(ROOT)

    assert values["checkers"] == str(
        len(list((ROOT / "src/verifiable_gates/checks").glob("scan_*.py")))
    )
    assert values["checkers_word"] == own_numbers.as_word(int(values["checkers"]))
    assert int(values["rules"]) > 0
    assert int(values["gates"]) > 0


# ---------------------------------------------------------------- measuring


def test_a_changelog_with_no_released_heading_is_an_error_not_a_guess(
    tmp_path: pathlib.Path,
) -> None:
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="no released heading"):
        own_numbers.facts(tmp_path)


@pytest.mark.parametrize(("number", "word"), [(0, "zero"), (9, "nine"), (10, "ten"), (11, "11")])
def test_small_counts_are_words_and_larger_ones_stay_digits(number: int, word: str) -> None:
    assert own_numbers.as_word(number) == word


# ---------------------------------------------------------------- the command line

FIELD = "A catalogue of 92 production-discipline rules — latest v0.1.0, archived under a DOI."


def fake_platform(monkeypatch: pytest.MonkeyPatch, field: str) -> list[list[str]]:
    """Stand in for `gh`: answers the About read, records every write."""
    calls: list[list[str]] = []

    def record(args: list[str], **_kw: object) -> str:
        calls.append(args)
        return ""

    monkeypatch.setattr(gh, "api", lambda _path: {"description": field})
    monkeypatch.setattr(gh, "run", record)
    return calls


def test_the_tree_reports_clean_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert own_numbers.main(["--root", str(ROOT)]) == 0
    assert "every place inside the repository agrees" in capsys.readouterr().out


def test_drift_inside_is_reported_place_by_place_and_blocks(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(own_numbers, "facts", lambda _root: {"version": "9.9.9"})
    monkeypatch.setattr(
        own_numbers, "PLACES", {"version": [advertised.Place("a.md", r"v(\d[\w.]*)")]}
    )
    (tmp_path / "a.md").write_text("v1.0.0 shipped\n", encoding="utf-8")

    assert own_numbers.main(["--root", str(tmp_path)]) == 1
    assert "a.md: says '1.0.0', should say '9.9.9'" in capsys.readouterr().out


def test_write_fixes_the_place_and_leaves_the_sentence_alone(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(own_numbers, "facts", lambda _root: {"version": "9.9.9"})
    monkeypatch.setattr(
        own_numbers, "PLACES", {"version": [advertised.Place("a.md", r"v(\d[\w.]*)")]}
    )
    (tmp_path / "a.md").write_text("v1.0.0 shipped, and a badge\n", encoding="utf-8")

    assert own_numbers.main(["--root", str(tmp_path), "--write"]) == 0
    assert (tmp_path / "a.md").read_text(encoding="utf-8") == "v9.9.9 shipped, and a badge\n"


def test_the_about_field_that_agrees_is_said_so(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(own_numbers, "facts", lambda _root: {"rules": "92", "version": "0.1.0"})
    monkeypatch.setattr(own_numbers, "PLACES", {})
    calls = fake_platform(monkeypatch, FIELD)

    assert own_numbers.main(["--about"]) == 0
    assert "the About field agrees" in capsys.readouterr().out
    assert calls == [], "nothing to fix must mean nothing written"


def test_a_stale_about_field_blocks_and_names_the_claim(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(own_numbers, "facts", lambda _root: {"rules": "93", "version": "0.1.1"})
    monkeypatch.setattr(own_numbers, "PLACES", {})
    fake_platform(monkeypatch, FIELD)

    assert own_numbers.main(["--about"]) == 1
    out = capsys.readouterr().out
    assert "version: says '0.1.0', should say '0.1.1'" in out
    assert "rules: says '92', should say '93'" in out


def test_a_claim_missing_from_the_about_field_is_drift_not_agreement(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The live field on 2026-08-29 had no `latest v…` at all — that must read as red."""
    monkeypatch.setattr(own_numbers, "facts", lambda _root: {"rules": "92", "version": "0.1.0"})
    monkeypatch.setattr(own_numbers, "PLACES", {})
    fake_platform(monkeypatch, "A catalogue of 92 production-discipline rules.")

    assert own_numbers.main(["--about"]) == 1
    assert "version: says '(not found)'" in capsys.readouterr().out


def test_write_patches_the_about_field_in_place(monkeypatch: pytest.MonkeyPatch) -> None:
    """The prose around the numbers survives — a field outside leaves no diff to review."""
    monkeypatch.setattr(own_numbers, "facts", lambda _root: {"rules": "93", "version": "0.1.1"})
    monkeypatch.setattr(own_numbers, "PLACES", {})
    calls = fake_platform(monkeypatch, FIELD)

    assert own_numbers.main(["--about", "--write"]) == 0
    assert len(calls) == 1
    sent: Any = calls[0]
    assert sent[:4] == ["api", "-X", "PATCH", "repos/:owner/:repo"]
    assert sent[-1] == (
        "description=A catalogue of 93 production-discipline rules — latest v0.1.1, "
        "archived under a DOI."
    )
