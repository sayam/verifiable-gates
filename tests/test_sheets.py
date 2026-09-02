"""The committed sheets are what the catalogue renders — nothing else.

The skill under `skills/verifiable-gates/` — its front page `SKILL.md` and the two
reference sheets — is generated and lives in git, which is worth doing only while
something compares each file against a fresh render on every run. Without that, a
sheet edited by hand looks exactly like a sheet in step with the catalogue, and the
whole reason for generating it is gone.

The second thing checked here is that the sheets **partition** the catalogue: every
rule appears on exactly one of them, and every rule is on the index. A rule that
belongs to no layer's sheet is published nowhere while still counting as published,
which is the quietest way for a rule to disappear.

The third is the Agent Skills specification (agentskills.io), held **here rather than
by a CI step**: a `name` that matches the directory and is lowercase-hyphen within 64
characters, a non-empty `description` within 1024, and a front page under the 500
lines the specification recommends. Some forty products read that layout; a file
that misses it by one field is a skill none of them can see, and nothing about the
file would look wrong.
"""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

from verifiable_gates import rules, skill

ROOT = pathlib.Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "rules.yaml"

SKILL_DIR = "skills/verifiable-gates"
INDEX = f"{SKILL_DIR}/SKILL.md"
INDEX_PREAMBLE = "preambles/skill.md"

SHEETS = [
    (f"{SKILL_DIR}/references/baseline.md", "preambles/baseline.md", "baseline"),
    (f"{SKILL_DIR}/references/business.md", "preambles/business.md", "business"),
]

# The specification's limits, copied here because they are the contract with every
# reader of the layout, not a preference of this repository.
SPEC_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SPEC_NAME_MAX = 64
SPEC_DESCRIPTION_MAX = 1024
SPEC_BODY_LINES = 500


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


def test_the_committed_index_is_a_fresh_render() -> None:
    fresh = skill.render_index(
        rules.load(CATALOGUE), (ROOT / INDEX_PREAMBLE).read_text(encoding="utf-8")
    )
    committed = (ROOT / INDEX).read_text(encoding="utf-8")
    assert committed == fresh, f"{INDEX} drifted from the catalogue — regenerate it"


def test_the_index_names_every_rule_and_points_at_its_sheet() -> None:
    """An index line is a promise that the entry exists where the link says."""
    text = (ROOT / INDEX).read_text(encoding="utf-8")
    for rule in rules.load(CATALOGUE):
        link = f"[`{rule['id']}`](references/{rule['layer']}.md#{rule['id']})"
        assert link in text, f"{rule['id']} is missing from the index or points elsewhere"
        sheet = (ROOT / SKILL_DIR / "references" / f"{rule['layer']}.md").read_text(
            encoding="utf-8"
        )
        assert f"### `{rule['id']}`" in sheet, f"{rule['id']}: the index links to no entry"


# ---------------------------------------------------------------- the specification


def _frontmatter() -> tuple[dict[str, object], str]:
    text = (ROOT / INDEX).read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md must open with YAML frontmatter"
    head, _, body = text[4:].partition("\n---\n")
    loaded = yaml.safe_load(head)
    assert isinstance(loaded, dict), "the frontmatter is not a mapping"
    return loaded, body


def test_the_skill_name_is_the_directory_name_in_the_specifications_shape() -> None:
    front, _ = _frontmatter()
    name = front.get("name")
    assert isinstance(name, str), "`name` is required"
    assert name == pathlib.Path(SKILL_DIR).name, (
        "`name` must equal the directory the skill lives in"
    )
    assert len(name) <= SPEC_NAME_MAX, f"`name` is over {SPEC_NAME_MAX} characters"
    assert SPEC_NAME.match(name), (
        f"`name` {name!r} is not lowercase letters, digits and single hyphens"
    )


def test_the_skill_description_says_what_and_when_within_the_limit() -> None:
    front, _ = _frontmatter()
    description = front.get("description")
    assert isinstance(description, str), "`description` is required"
    assert description.strip(), "`description` is empty"
    assert len(description) <= SPEC_DESCRIPTION_MAX, "`description` is over 1024 characters"
    assert "Use when" in description, (
        "the specification asks a description to say when to use the skill, not only what it is"
    )


def test_the_skill_front_page_is_under_the_specifications_line_ceiling() -> None:
    lines = len((ROOT / INDEX).read_text(encoding="utf-8").splitlines())
    assert lines <= SPEC_BODY_LINES, (
        f"SKILL.md is {lines} lines; the specification recommends at most {SPEC_BODY_LINES} — "
        "move detail into references/"
    )


@pytest.mark.parametrize("sheet", [INDEX, *(s[0] for s in SHEETS)])
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
CEILING_LINES = {
    INDEX: 190,
    f"{SKILL_DIR}/references/baseline.md": 690,
    f"{SKILL_DIR}/references/business.md": 160,
}
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
    assert {INDEX, *(sheet for sheet, _p, _l in SHEETS)} == set(CEILING_LINES)
