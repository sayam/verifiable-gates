"""The committed sheets are what the catalogue renders — nothing else.

`SKILL.md` and `SKILL-BUSINESS.md` are generated files that live in git, which is
worth doing only while something compares them against a fresh render on every
run. Without that, a sheet edited by hand looks exactly like a sheet in step with
the catalogue, and the whole reason for generating it is gone.

The second thing checked here is that the sheets **partition** the catalogue: every
rule appears on exactly one of them. A rule that belongs to no layer's sheet is
published nowhere while still counting as published, which is the quietest way for
a rule to disappear.
"""

from __future__ import annotations

import pathlib

import pytest

from verifiable_gates import rules, skill

ROOT = pathlib.Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "rules.yaml"

SHEETS = [
    ("SKILL.md", "preambles/baseline.md", "baseline"),
    ("SKILL-BUSINESS.md", "preambles/business.md", "business"),
]


@pytest.mark.parametrize(("sheet", "preamble", "layer"), SHEETS, ids=[s[2] for s in SHEETS])
def test_the_committed_sheet_is_a_fresh_render(sheet: str, preamble: str, layer: str) -> None:
    fresh = skill.render(
        rules.load(CATALOGUE),
        (ROOT / preamble).read_text(encoding="utf-8"),
        layer,
    )
    committed = (ROOT / sheet).read_text(encoding="utf-8")
    assert committed == fresh, f"{sheet} drifted from the catalogue — regenerate it"


def test_the_sheets_between_them_publish_every_rule() -> None:
    """A rule on no sheet is published nowhere while still counting as published."""
    catalogue = rules.load(CATALOGUE)
    on_sheets: set[str] = set()
    for sheet, _, layer in SHEETS:
        text = (ROOT / sheet).read_text(encoding="utf-8")
        ids = {rule["id"] for rule in rules.by_layer(catalogue, layer)}
        assert ids, f"{sheet} covers no rule at all"
        for rule_id in ids:
            assert f"### `{rule_id}`" in text, f"{rule_id} is missing from {sheet}"
        assert not (ids & on_sheets), "a rule appears on more than one sheet"
        on_sheets |= ids
    assert on_sheets == {rule["id"] for rule in catalogue}


@pytest.mark.parametrize("sheet", [s[0] for s in SHEETS])
def test_a_sheet_says_it_is_generated(sheet: str) -> None:
    """Somebody will open it and start typing otherwise."""
    head = (ROOT / sheet).read_text(encoding="utf-8")[:1200]
    assert "generated" in head.lower()
    assert "do not edit" in head.lower()


# ---------------------------------------------------------------- the ceiling

# A sheet is read in full by an agent every session, so its size is a cost paid
# over and over. The ceiling is a two-way ratchet: the sheet may not exceed it,
# and the ceiling may not float more than SLACK lines above the sheet — on the
# day content moves out, the ceiling comes down with it. Raise a number here only
# in the same change that adds the content, and say why in the commit.
CEILING_LINES = {"SKILL.md": 700, "SKILL-BUSINESS.md": 150}
SLACK = 40


@pytest.mark.parametrize("sheet", sorted(CEILING_LINES))
def test_a_sheet_sits_under_its_declared_ceiling_and_the_ceiling_sits_on_the_sheet(
    sheet: str,
) -> None:
    lines = len((ROOT / sheet).read_text(encoding="utf-8").splitlines())
    ceiling = CEILING_LINES[sheet]

    assert lines <= ceiling, f"{sheet} is {lines} lines, over its ceiling of {ceiling}"
    assert ceiling - lines <= SLACK, (
        f"{sheet} is {lines} lines but the ceiling is {ceiling} — bring it down; "
        f"space left above reality is space that gets filled unseen"
    )


def test_every_sheet_has_a_ceiling() -> None:
    assert {sheet for sheet, _p, _l in SHEETS} == set(CEILING_LINES)
