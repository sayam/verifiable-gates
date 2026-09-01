"""The two identity cards agree with each other, and with the licence on disk.

This repository has two files at its root that describe it to **readers who are
not us**:

- `CITATION.cff` — what citation software and GitHub's "Cite this repository"
  button read;
- `.zenodo.json` — what Zenodo reads when it archives a release and publishes a
  record under a permanent DOI, which by the definition of archiving cannot be
  corrected afterwards.

Both name the work, the author, the licence and the keywords. Nothing but this
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

import json
import pathlib
import re
from typing import Any

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CITATION = ROOT / "CITATION.cff"
ZENODO = ROOT / ".zenodo.json"
LICENCE = ROOT / "LICENSE"
README = ROOT / "README.md"

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
