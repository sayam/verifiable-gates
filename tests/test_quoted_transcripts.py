"""A catalogue sentence quoted in a document is the sentence the catalogue carries.

`reads:` and `born_from:` live in `rules.yaml`, and three copies of each are already
held to it: the scanner's own `READS` (`tests/test_rules_catalogue.py`), the shipped
`overlay.json` (`tests/test_manifest.py`), and the `NA` line the scanner prints
(`tests/test_checks_behaviour.py`). So a change to one sentence moves all four
together, which is what happened on 2026-09-06 when the sweep for an unnamed
Dockerfile learned to ask git.

**Four documents quoted the old sentence in a transcript, and nothing looked**:
`README.md`, `README.th.md`, `docs/checker-reference.md` and `docs/output-semantics.md`
each showed a reader output the tool no longer produces — the quickstart among them.
Measured the same day: 59 catalogue sentences are quoted across the tree, 55 of them
right by hand, and the four that were wrong were exactly the ones the change touched.
A copy that is right by hand is a copy that is right until the day it matters.

What is held here is the part that has a source: the rule id and the sentence beside
it. What is not held is the rest of a transcript — the counts, the summary lines, the
findings themselves — which is re-run from the published artefacts at every release
(`CONTRIBUTING.md` § Releasing) rather than parsed here.

`CHANGELOG.md` is excluded on purpose: each of its sections is a published release
body, byte for byte, and `verifiable_gates.release_body` holds eighteen of eighteen.
An entry describes what was true at that release; rewriting one to follow a later
catalogue change would put the tree and the platform out of step to fix a sentence
that was never wrong.
"""

from __future__ import annotations

import collections
import pathlib
import re
from typing import NamedTuple

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXCLUDED = ("CHANGELOG.md",)
# How many sentences of each kind each document quotes today — a register, held both ways.
# A count rather than a list of files, because *one* pattern going blind still leaves the
# others matching: with only "does this file yield anything" to satisfy, blinding the `NA`
# pattern left every check green while six quotations per README went unread (measured
# 2026-09-06, the mutation that was supposed to prove the guard). A transcript that gains
# or loses a line moves a number here, in the diff, where a reviewer sees it.
QUOTED_PER_DOCUMENT: dict[str, dict[str, int]] = {
    "README.md": {"title": 2, "reads": 6, "born_from": 2},
    "README.th.md": {"title": 2, "reads": 6, "born_from": 2},
    "docs/checker-reference.md": {"title": 9, "reads": 9, "born_from": 9},
    "docs/output-semantics.md": {"title": 3, "reads": 6, "born_from": 3},
}

# `[found] <id> — <title>` and, under it, `  born from: <sentence>`.
FOUND = re.compile(r"^\[found\] (?P<id>[a-z0-9-]+) — (?P<text>.+?)\s*$")
# `[   NA] <id> — <why> — this rule reads <sentence>`.
NA = re.compile(r"^\[\s*NA\] (?P<id>[a-z0-9-]+) —.*?— this rule reads (?P<text>.+?)\s*$")
# The `--rules` transcript: `<id> [<layer>]`, then indented `rule:`, `born from:`, `reads:`.
HEADING = re.compile(r"^(?P<id>[a-z0-9-]+) \[(?:baseline|business)\]\s*$")
FIELD = re.compile(r"^\s{2,}(?P<key>rule|reads|born from):\s+(?P<text>.+?)\s*$")
FIELD_TO_KEY = {"rule": "title", "reads": "reads", "born from": "born_from"}


class Quotation(NamedTuple):
    """One catalogue sentence as a document prints it."""

    where: str
    line: int
    gid: str
    key: str
    text: str


def documents() -> list[pathlib.Path]:
    """The pages a reader is pointed at: the root, `docs/` and `.github/`.

    The sheets under `skills/` are generated from the same catalogue and held to it by
    `tests/test_sheets.py`; `.local/` is not part of the repository.
    """
    found = [*ROOT.glob("*.md"), *(ROOT / "docs").rglob("*.md"), *(ROOT / ".github").rglob("*.md")]
    return sorted(path for path in found if path.name not in EXCLUDED)


def quotations() -> list[Quotation]:
    """Every catalogue sentence quoted in those pages, with where it is."""
    found: list[Quotation] = []
    for path in documents():
        where = str(path.relative_to(ROOT))
        current = None
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            printed = FOUND.match(line) or NA.match(line)
            if printed:
                current = printed["id"]
                key = "title" if line.startswith("[found]") else "reads"
                found.append(Quotation(where, number, current, key, printed["text"]))
                continue
            heading = HEADING.match(line)
            if heading:
                current = heading["id"]
                continue
            field = FIELD.match(line)
            if field and current and field["key"] in FIELD_TO_KEY:
                key = FIELD_TO_KEY[field["key"]]
                found.append(Quotation(where, number, current, key, field["text"]))
    return found


def catalogue() -> dict[str, dict[str, object]]:
    return {r["id"]: r for r in yaml.safe_load((ROOT / "rules.yaml").read_text("utf-8"))["rules"]}


def test_the_excluded_name_is_a_file_that_is_here() -> None:
    """An exclusion for a file that has moved excludes nothing and says it excluded it."""
    for name in EXCLUDED:
        assert (ROOT / name).is_file(), f"{name} is excluded here and is not in the tree"


@pytest.mark.parametrize("name", QUOTED_PER_DOCUMENT)
def test_each_document_quotes_what_this_register_says_it_does(name: str) -> None:
    """The guard on the guard, and the only one that survives a blinded pattern.

    Every check below is only as good as what the patterns match; a green over nothing
    reads exactly like a green over everything. So the count of each kind is held here,
    per document, and a pattern that stops matching takes a number to zero.
    """
    counted = collections.Counter(q.key for q in quotations() if q.where == name)

    assert dict(counted) == QUOTED_PER_DOCUMENT[name], (
        f"{name} quotes {dict(counted)}, this file says {QUOTED_PER_DOCUMENT[name]} — if the"
        " transcript changed, move the number in the same pull request; if it did not, a"
        " pattern here has gone blind"
    )


def test_the_register_names_documents_that_are_here() -> None:
    """A count for a page that has moved is a count nothing can fail."""
    for name in QUOTED_PER_DOCUMENT:
        assert (ROOT / name).is_file(), f"{name} is held here and is not in the tree"


def test_every_quoted_sentence_is_the_one_the_catalogue_carries() -> None:
    """The four that were wrong on 2026-09-06 were the four the change had touched."""
    rules = catalogue()
    drifted = [
        f"{q.where}:{q.line} {q.gid}.{q.key}\n     doc:  {q.text}\n     yaml: {rules[q.gid][q.key]}"
        for q in quotations()
        if q.gid in rules and rules[q.gid].get(q.key) != q.text
    ]
    assert not drifted, (
        "a document quotes a sentence the catalogue no longer carries:\n" + "\n".join(drifted)
    )


def test_every_rule_a_document_quotes_is_a_rule_that_exists() -> None:
    """A transcript naming a rule id the catalogue does not have shows output nobody
    can get — the same failure as a stale sentence, one step worse."""
    rules = catalogue()
    unknown = sorted({q.gid for q in quotations() if q.gid not in rules})

    assert not unknown, f"documents quote {unknown}, which rules.yaml does not carry"
