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
WORKING_CATALOGUE = ROOT / "working.yaml"

SKILL_DIR = "skills/verifiable-gates"
INDEX = f"{SKILL_DIR}/SKILL.md"
INDEX_PREAMBLE = "preambles/skill.md"

SHEETS = [
    (f"{SKILL_DIR}/references/baseline.md", "preambles/baseline.md", "baseline"),
    (f"{SKILL_DIR}/references/business.md", "preambles/business.md", "business"),
]
# The working sheet is rendered from the other catalogue, under its own labels, so it is
# held here separately rather than by adding a fourth field to every row above.
WORKING_SHEET = f"{SKILL_DIR}/references/working.md"
WORKING_PREAMBLE = "preambles/working.md"
WORKING_LABELS = ("Practice", "Born from", "Held by")

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


def test_the_committed_working_sheet_is_a_fresh_render() -> None:
    """The same contract as the rule sheets: the file on disk is what the catalogue says,
    and a hand edit is red on the next run."""
    fresh = skill.render(
        rules.load(WORKING_CATALOGUE, key="practices"),
        (ROOT / WORKING_PREAMBLE).read_text(encoding="utf-8"),
        rules.WORKING,
        labels=WORKING_LABELS,
    )
    committed = (ROOT / WORKING_SHEET).read_text(encoding="utf-8")
    assert committed == fresh, f"{WORKING_SHEET} drifted from working.yaml — regenerate it"


def test_the_working_sheet_publishes_every_practice_with_its_holder_and_its_apply() -> None:
    """Three things a reader must not have to guess: which practice, what held it, and
    what to do. The holder is on every entry because a practice held by nothing but
    reading must never look like one a checker refuses."""
    practices = rules.load(WORKING_CATALOGUE, key="practices")
    sheet = (ROOT / WORKING_SHEET).read_text(encoding="utf-8")
    for practice in practices:
        assert f"### `{practice['id']}`" in sheet
        assert practice["born_from"].split(" · ")[0] in sheet, "the ledger id travels"
        assert "**Apply:**" in sheet
    assert sheet.count("**Held by:**") == len(practices)
    assert sheet.count("reading this line — nothing here refuses it for you") == sum(
        1 for p in practices if p["held_by"] == "reading"
    )
    for practice in practices:
        named = practice.get(practice["held_by"])
        if named:
            assert f"`{named}`" in sheet


def test_the_working_sheet_carries_no_lesson_of_ours() -> None:
    """`the-ledger-ships-empty-and-private`: our entries name this repository, its owner,
    its tickets and its tooling. What travels is the practice and one sentence of what it
    cost — never an entry.

    The sheet *does* name the ledger's fields, and must: teaching the shape is what it is
    for. So the check is on the entries themselves — no heading of one, no title of one —
    and the ledger is read from disk rather than remembered, which also means this test
    says nothing in a clone that has none, as a consumer's will not.
    """
    sheet = (ROOT / WORKING_SHEET).read_text(encoding="utf-8")
    assert "**Context:**" not in sheet, "a ledger entry's own body reached the sheet"
    assert not re.search(r"^## L-\d{4} — ", sheet, re.MULTILINE), "an entry was copied whole"

    ledger = ROOT / ".local" / "LESSONS.md"
    if not ledger.is_file():  # pragma: no cover — a fresh clone has none, which is the point
        return
    titles = [
        line.split(" — ", 1)[1].strip()
        for line in ledger.read_text(encoding="utf-8").splitlines()
        if line.startswith("## L-") and " — " in line
    ]
    assert titles, "the ledger is there but no entry was read — the check would be vacuous"
    leaked = [title for title in titles if title in sheet]
    assert leaked == [], f"a ledger entry's title travelled: {leaked}"


def test_the_committed_index_is_a_fresh_render() -> None:
    fresh = skill.render_index(
        rules.load(CATALOGUE),
        (ROOT / INDEX_PREAMBLE).read_text(encoding="utf-8"),
        practices=rules.load(WORKING_CATALOGUE, key="practices"),
    )
    committed = (ROOT / INDEX).read_text(encoding="utf-8")
    assert committed == fresh, f"{INDEX} drifted from either catalogue — regenerate it"


def test_the_index_lists_the_practices_apart_from_the_rules() -> None:
    """A reader who took a practice for a rule would think the bundle could decide it.
    The section is counted in practices, says no scanner decides one, and every line
    points into the working sheet."""
    text = (ROOT / INDEX).read_text(encoding="utf-8")
    practices = rules.load(WORKING_CATALOGUE, key="practices")
    assert f"### working — {len(practices)} practices" in text
    assert "`gates_doctor --rules` never prints one" in text
    for practice in practices:
        assert f"[`{practice['id']}`](references/working.md#{practice['id']})" in text
    for rule in rules.load(CATALOGUE):
        assert f"references/working.md#{rule['id']}" not in text, "a rule listed as a practice"


def test_the_index_without_practices_is_the_index_as_it_was() -> None:
    """The argument is optional, and a caller that omits it gets no empty heading — the
    sheet generator is used by hand as well as by the test above."""
    without = skill.render_index(
        rules.load(CATALOGUE), (ROOT / INDEX_PREAMBLE).read_text(encoding="utf-8")
    )
    assert "### working" not in without
    assert "### baseline" in without


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


@pytest.mark.parametrize("sheet", [INDEX, WORKING_SHEET, *(s[0] for s in SHEETS)])
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
    # 190 → 200 on 2026-09-04: the index gained a `working` section, ten lines of
    # practices under their own heading.
    INDEX: 200,
    f"{SKILL_DIR}/references/baseline.md": 690,
    f"{SKILL_DIR}/references/business.md": 160,
    # New on 2026-09-04 with the sheet itself: ten practices, each with its lesson,
    # its holder and what to do.
    WORKING_SHEET: 170,
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
    assert {INDEX, WORKING_SHEET, *(sheet for sheet, _p, _l in SHEETS)} == set(CEILING_LINES)
