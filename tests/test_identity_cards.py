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

TAG = re.compile(r"<[^>]+>")


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
    assert zenodo()["license"] == citation()["license"]


def test_the_declared_licence_is_the_one_on_disk() -> None:
    """Two cards can agree with each other and both be wrong — check the real file.

    Publishing a record that names a licence the repository does not carry is a
    statement about somebody's rights, made in the one place that cannot be
    edited later.
    """
    declared = citation()["license"]
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


@pytest.mark.parametrize("field", ["title", "upload_type", "license", "creators", "description"])
def test_zenodo_carries_every_field_it_needs(field: str) -> None:
    """A missing field is filled in by Zenodo's guesses, which nobody reviewed."""
    assert zenodo().get(field), f".zenodo.json has no {field}"


def test_the_upload_is_declared_as_software() -> None:
    assert zenodo()["upload_type"] == "software"
