"""The two identity cards agree with each other, and with the licence on disk.

This repository has two files at its root that describe it to **readers who are
not us**:

- `CITATION.cff` — what citation software and GitHub's "Cite this repository"
  button read;
- `.zenodo.json` — what Zenodo reads when it archives a release and publishes a
  record under a permanent DOI, which by the definition of archiving cannot be
  corrected afterwards.

A third arrived on 2026-09-02, `.claude-plugin/plugin.json`, which Claude Code's
marketplace and the Skills CLI read when somebody installs the skill without
cloning — a card for the same reader in a third shape, held here to the other two
for the same reason.

A fourth, the same day: `AGENTS.md`, read by the sixty-odd coding agents that
follow the agents.md convention, with `CLAUDE.md` importing it for the one that
does not. It describes the repository to a reader who will act on what it says,
so every path, module and section it names is held to exist — and it is held to
point rather than copy, because a copied rule is the one that goes stale.

All three name the work, the author, the licence and the keywords. Nothing but this
file compares them, and the reference implementation measured what happens
without such a check: on 2026-08-22 its two cards and its register gave **three
different numbers for one fact**, and the value published under the DOI was the
oldest of the three.

The shape of the failure is that **the further a statement travels from the
repository, the fewer machines watch it** — while the furthest destination is the
one place it cannot be fixed. So the direction that matters is not "is the card
well-formed" but "does it still say what the repository says".

The licence is checked against `LICENSE` rather than only across the two cards,
because two cards agreeing with each other and both being wrong is exactly the
failure mode a cross-check between them cannot see.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import tomllib
from typing import Any

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CITATION = ROOT / "CITATION.cff"
ZENODO = ROOT / ".zenodo.json"
LICENCE = ROOT / "LICENSE"
README = ROOT / "README.md"
PLUGIN = ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
SKILL = ROOT / "skills" / "verifiable-gates" / "SKILL.md"
AGENTS = ROOT / "AGENTS.md"
CLAUDE_MD = ROOT / "CLAUDE.md"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"

# What Claude Code documents as the size at which adherence starts to drop, and
# the import loads at launch beside the file that imports it — so the two are
# measured together.
INSTRUCTION_LINES = 200
BACKTICKED = re.compile(r"`([^`\s<>]+)`")
FILE_LIKE = re.compile(r"/|\.(md|py|yaml|yml|json|toml|txt|cff)$")
MODULE = re.compile(r"python -m (verifiable_gates\.[a-z_]+)")
SECTION = re.compile(r"`CONTRIBUTING\.md`\s+§ \"([^\"]+)\"")

TAG = re.compile(r"<[^>]+>")
# A Zenodo concept DOI: the prefix is fixed, the record number is not.
DOI = re.compile(r"10\.5281/zenodo\.\d+")

# Hosts whose badge images GitHub's camo proxy was **measured** to fetch, with
# the reason each one earned its place. See the test at the end of this file.
BADGE_HOSTS = {
    "https://img.shields.io/": "every badge in use: 200 on all three fetches",
}
IMAGE = re.compile(r"!\[[^\]]*\]\((https?://[^)\s]+)\)")


def citation() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(CITATION.read_text(encoding="utf-8"))
    return loaded


def zenodo() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(ZENODO.read_text(encoding="utf-8"))
    return loaded


def plugin() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(PLUGIN.read_text(encoding="utf-8"))
    return loaded


def marketplace() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    return loaded


def skill_frontmatter() -> dict[str, Any]:
    text = SKILL.read_text(encoding="utf-8")
    head = text[4:].partition("\n---\n")[0]
    loaded: dict[str, Any] = yaml.safe_load(head)
    return loaded


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", TAG.sub(" ", text)).strip()


def test_both_cards_exist() -> None:
    """A guard on the guard: a missing file would make every check below vacuous."""
    assert CITATION.is_file(), "CITATION.cff is gone — GitHub's cite button reads it"
    assert ZENODO.is_file(), ".zenodo.json is gone — Zenodo reads it when archiving"


def test_the_two_cards_name_the_same_work() -> None:
    assert zenodo()["title"] == citation()["title"].strip()


def test_the_two_cards_name_the_same_author() -> None:
    """One work with two authors on two cards is a citation nobody can resolve."""
    person = citation()["authors"][0]
    expected = f"{person['family-names']}, {person['given-names']}"
    creators = zenodo()["creators"]

    assert len(creators) == len(citation()["authors"]), "the cards list different authors"
    assert creators[0]["name"] == expected
    assert creators[0]["affiliation"] == person["affiliation"]


def test_the_two_cards_carry_the_same_keywords() -> None:
    """Order included — these are what a search surfaces the record by."""
    assert zenodo()["keywords"] == list(citation()["keywords"])


def test_the_two_cards_declare_the_same_licence() -> None:
    """Zenodo has one licence field; the citation card lists both. The first is the code's.

    The second licence cannot fit Zenodo's field, so the abstract the two cards
    share is where it travels — checked below, because a reader of the archived
    record has nothing else to go on.
    """
    assert zenodo()["license"] == citation()["license"][0]


def test_both_licences_reach_the_cards_and_the_wheel() -> None:
    """The rules are CC BY 4.0 and the code Apache-2.0 — the cards must say both.

    An outside audit on 2026-08-29 found every card, the GitHub record and the
    archived DOI declaring Apache-2.0 for the whole, while `LICENSE-docs` on disk
    and the README said otherwise: the furthest copy is the one that cannot be
    corrected, so it is the one a check has to reach before publication.
    """
    assert citation()["license"] == ["Apache-2.0", "CC-BY-4.0"]
    assert "CC BY 4.0" in citation()["abstract"]
    assert "CC BY 4.0" in zenodo()["description"]
    docs = (ROOT / "LICENSE-docs").read_text(encoding="utf-8")
    assert "Attribution 4.0" in docs
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'license-files = ["LICENSE", "LICENSE-docs"]' in pyproject


def test_the_declared_licence_is_the_one_on_disk() -> None:
    """Two cards can agree with each other and both be wrong — check the real file.

    Publishing a record that names a licence the repository does not carry is a
    statement about somebody's rights, made in the one place that cannot be
    edited later.
    """
    declared = citation()["license"][0]
    body = LICENCE.read_text(encoding="utf-8")

    assert declared == "Apache-2.0", f"the cards declare {declared!r} — is that still true?"
    assert "Apache License" in body
    assert "Version 2.0" in body


def test_the_description_says_what_the_abstract_says() -> None:
    """Zenodo's description is the abstract in HTML — not a second piece of prose.

    A description written separately drifts from the abstract the moment either
    is edited, and only one of the two can be corrected after publication.
    """
    assert flat(zenodo()["description"]) == flat(citation()["abstract"])


@pytest.mark.parametrize(
    "field",
    ["title", "upload_type", "license", "creators", "description", "version", "publication_date"],
)
def test_zenodo_carries_every_field_it_needs(field: str) -> None:
    """A missing field is filled in by Zenodo's guesses, which nobody reviewed."""
    assert zenodo().get(field), f".zenodo.json has no {field}"


def test_the_upload_is_declared_as_software() -> None:
    assert zenodo()["upload_type"] == "software"


# ------------------------------------------------------------------ the DOI


def test_the_citation_card_carries_a_doi() -> None:
    """Without it, citation software has only a URL, which is not a citation."""
    doi = citation().get("doi", "")
    assert DOI.fullmatch(str(doi)), f"CITATION.cff has no usable DOI: {doi!r}"


def test_every_doi_printed_in_the_readme_is_the_one_on_the_card() -> None:
    """A DOI is a number that lives outside this repository, advertised inside it.

    Nothing about a stale one looks wrong: it resolves, it renders, and it points
    at somebody's work — just not necessarily at the state being claimed. The
    reference implementation had four such numbers stale at once before anything
    read them, so every occurrence is compared rather than only the first.
    """
    declared = str(citation()["doi"])
    found = set(DOI.findall(README.read_text(encoding="utf-8")))

    assert found, "the README advertises no DOI at all"
    assert found == {declared}, (
        f"the README prints {sorted(found)} while the citation card says {declared!r} — "
        "one of them is pointing at a different record"
    )


def test_every_badge_image_comes_from_a_host_camo_was_measured_to_fetch() -> None:
    """A badge is not fetched from where the markup says, and that is the whole trap.

    GitHub does not embed a README image from its origin: it proxies every one
    through **camo**, so "I fetched the URL and got 200" answers a question
    nobody asked. The reference implementation misdiagnosed this twice — first
    blaming a deprecated URL shape, then adopting the shape Zenodo's own settings
    page hands out — and the badge went on flickering both times, because the
    fetch that decides is camo's::

        HTTP/2 502 · Invalid upstream response (429)

    Zenodo rate-limits camo. Measured here on 2026-09-01, three fetches per URL:
    this repository's Zenodo badge answered **504 · 504 · 504** through camo
    while answering 200 from a laptop, and shields.io answered 200 · 200 · 200.
    A 200 through camo is only evidence when the response is not a cache hit.

    This test does not touch the network — a gate that needs the network is a
    gate that goes red when the network does. It enforces the one thing that
    outlives the measurement: **a new host is a decision somebody signs**, with
    its reason recorded in ``BADGE_HOSTS``, not markdown copied off a web page.
    """
    images = IMAGE.findall(README.read_text(encoding="utf-8"))
    assert images, "the README shows no badge at all — if that is deliberate, delete this test"

    strangers = sorted(
        {url for url in images if not any(url.startswith(host) for host in BADGE_HOSTS)}
    )
    assert not strangers, (
        f"badge images from unmeasured hosts: {strangers} — fetch each one through "
        "GitHub's camo proxy several times, then record it in BADGE_HOSTS with the reason"
    )


# ---------------------------------------------------------------- the third card


def test_the_plugin_manifest_and_its_marketplace_exist() -> None:
    """A guard on the guard, as for the other two cards."""
    assert PLUGIN.is_file(), "plugin.json is gone — Claude Code and the Skills CLI read it"
    assert MARKETPLACE.is_file(), "marketplace.json is gone — `plugin marketplace add` reads it"


def test_the_plugin_is_named_after_the_package() -> None:
    """One name on the wheel, the skill and the plugin, or three things to search for."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert plugin()["name"] == pyproject["project"]["name"]
    assert plugin()["name"] == skill_frontmatter()["name"]


def test_the_plugin_points_at_a_skills_directory_that_holds_the_skill() -> None:
    """A `skills` path is a promise; the directory it names must hold a SKILL.md."""
    declared = plugin()["skills"]
    assert declared.startswith("./"), "the manifest wants a path relative to the plugin root"
    where = ROOT / declared
    assert where.is_dir(), f"{declared} is not a directory"
    assert (where / SKILL.parent.name / "SKILL.md").is_file(), "the skill is not under it"


def test_the_plugin_does_not_declare_the_hooks_file_claude_code_loads_by_itself() -> None:
    """`hooks/hooks.json` is loaded from its standard path; declaring it too is a duplicate.

    Measured on Claude Code 2.1.261 (round 23, D3): with `"hooks": "./hooks/hooks.json"`
    in the manifest, `plugin install` reported *failed to load — Duplicate hooks file
    detected*, and neither the skill nor the hook was available; `plugin validate`
    passed. So the standard file exists, and the manifest does not name it a second
    time. A hooks file at another path may still be declared — that is not a duplicate.
    """
    standard = ROOT / "hooks" / "hooks.json"
    assert standard.is_file(), "hooks/hooks.json is gone — Claude Code loads the hook from there"
    declared = plugin().get("hooks")
    assert declared is None or (ROOT / declared).resolve() != standard.resolve(), (
        f"plugin.json declares hooks {declared!r}, the file Claude Code loads by itself — "
        "on 2.1.261 that second declaration failed the whole plugin as a duplicate"
    )


def test_the_plugin_carries_the_cards_keywords() -> None:
    assert plugin()["keywords"] == list(citation()["keywords"])


def test_the_plugin_licence_is_both_because_the_plugin_lands_the_whole_repository() -> None:
    """The manifest declared the sheets' licence alone while what the marketplace pipe lands
    is the repository — its plugin is the root, code included (measured on Claude Code
    2.1.261, round 23, D3). A manifest naming one licence for a thing that carries two is
    the overclaim the cards were audited for on 2026-08-29, one card further out. So the
    plugin declares both, as an SPDX expression, in the order the citation card lists them;
    the sheet's own frontmatter still names the sheets' licence, and it is one of the two.
    Owner's decision, 2026-09-05.
    """
    declared = plugin()["license"]
    assert declared == " AND ".join(citation()["license"]), declared
    assert skill_frontmatter()["license"] in declared.split(" AND ")


def test_the_plugin_names_the_cards_repository() -> None:
    assert plugin()["repository"] == citation()["repository-code"]
    assert plugin()["homepage"] == citation()["url"]


def test_the_marketplace_lists_this_plugin_at_the_root_and_nothing_else() -> None:
    """One entry, sourced from the directory the marketplace file sits in."""
    entries = marketplace()["plugins"]
    assert len(entries) == 1, "this marketplace exists to list one plugin"
    assert entries[0]["name"] == plugin()["name"]
    assert entries[0]["source"] == "./"
    assert marketplace()["name"] == plugin()["name"], (
        "install is `plugin@marketplace`; two names would be two things to remember"
    )
    assert entries[0]["description"] == plugin()["description"]


def test_the_plugin_says_what_installing_it_does() -> None:
    """The description is the one text Claude Code shows before `plugin install`.

    Round 24 (2026-09-05) read it as a stranger: it said what the rules are and nothing
    about what installing does — that the plugin lands the whole repository (D3) and adds
    a PostToolUse hook, off until `VERIFIABLE_GATES_AT_EDIT=1`, that reports and refuses
    nothing. Each of those is a DECISIONS row; the description is where a stranger reads it.
    """
    said = plugin()["description"]
    for phrase in (
        "lands the whole repository",
        "PostToolUse hook",
        "off by default",
        "VERIFIABLE_GATES_AT_EDIT=1",
        "refuses nothing",
        "python -m verifiable_gates.install",
    ):
        assert phrase in said, f"the plugin description does not say: {phrase}"


# ---------------------------------------------------------------- the fourth card


def agents() -> str:
    return AGENTS.read_text(encoding="utf-8")


def test_the_agents_file_exists_and_claude_md_imports_it_first() -> None:
    """One file for every agent; Claude Code reads the other and is told to import."""
    assert AGENTS.is_file(), "AGENTS.md is gone — sixty-odd agents read it"
    first = next(
        line for line in CLAUDE_MD.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    assert first == "@AGENTS.md", "CLAUDE.md must begin by importing AGENTS.md, not restating it"


def test_every_path_the_agents_file_names_exists() -> None:
    """A pointer at nothing teaches an agent a layout the repository does not have."""
    named = [token for token in BACKTICKED.findall(agents()) if FILE_LIKE.search(token)]
    assert named, "the file names no path at all — it points at nothing"
    missing = [token for token in named if not (ROOT / token.rstrip("/")).exists()]
    assert not missing, f"AGENTS.md names paths that are not there: {missing}"


def test_every_module_the_agents_file_names_can_be_imported() -> None:
    named = MODULE.findall(agents())
    assert named, "the file names no command — an agent is told how to run nothing"
    absent = [name for name in named if importlib.util.find_spec(name) is None]
    assert not absent, f"AGENTS.md names modules that do not exist: {absent}"


def test_every_contributing_section_the_agents_file_cites_exists() -> None:
    """A section title is a pointer too, and a renamed heading breaks it silently."""
    # A title wrapped across a line break in the prose is still one title.
    cited = [" ".join(title.split()) for title in SECTION.findall(agents())]
    assert cited, "the file cites no CONTRIBUTING section"
    headings = {
        line[3:].strip()
        for line in CONTRIBUTING.read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    }
    gone = [title for title in cited if title not in headings]
    assert not gone, f"AGENTS.md cites CONTRIBUTING sections that are not there: {gone}"


def test_the_agents_file_points_and_does_not_copy() -> None:
    """A rule entry pasted here is the copy that lags the sheet."""
    text = agents()
    assert "### `" not in text, "a rule heading in the sheets' shape — point at the skill instead"
    assert "**Rule:**" not in text, "a rule line pasted in — point at the skill instead"
    assert "**Born from:**" not in text, "a lesson line pasted in — point at the skill instead"


def test_the_two_instruction_files_together_stay_short() -> None:
    """Both load at launch, every session; past 200 lines adherence drops."""
    lines = len(agents().splitlines()) + len(CLAUDE_MD.read_text(encoding="utf-8").splitlines())
    assert lines <= INSTRUCTION_LINES, f"AGENTS.md + CLAUDE.md are {lines} lines"
