"""GOVERNANCE.md — the page says one maintainer and promises nothing, and both stay true.

Round 28 asked the question an adopter asks first — who maintains this, and what happens if
they stop — and found no answer in the repository. The page is the answer. This file is what
keeps it from drifting into a page that says something kinder than the truth.

Three kinds of claim are held here. **Who** the maintainer is, against the identity the
project already publishes, so the page and the citation cannot name different people. **What
the page points at**, because a document citing a test that has been renamed is a document
that lies quietly. And **what the page must not acquire**: a promise of how long, which is the
one sentence its first section exists to refuse.
"""

from __future__ import annotations

import pathlib
import re

import yaml

from verifiable_gates import rules

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = ROOT / "GOVERNANCE.md"
TEXT = PAGE.read_text(encoding="utf-8")

# Every path the page names as something a reader can go and open.
CITED = (
    "tests/test_checks_are_standalone.py",
    "tests/test_released_ids.py",
    "rules.yaml",
    "working.yaml",
    "SECURITY.md",
    "DECISIONS.md",
)


def test_the_page_names_the_maintainer_the_project_already_publishes() -> None:
    """`CITATION.cff` is the identity card. A governance page naming somebody else — or a
    surname the citation does not carry — is two answers to "who decides"."""
    card = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    (author,) = card["authors"]
    name = f"{author['given-names']} {author['family-names']}"
    assert name in TEXT, f"GOVERNANCE.md does not name {name}, whom CITATION.cff names"


def test_every_path_the_page_cites_is_here() -> None:
    for cited in CITED:
        assert cited in TEXT, f"this test holds {cited}, which the page no longer names"
        assert (ROOT / cited).exists(), f"GOVERNANCE.md points at {cited}, which is not here"


def test_the_page_promises_no_period_of_maintenance() -> None:
    """The first section's whole content is that there is no such promise. A number of days,
    weeks, months or years in this file would be one, whatever sentence surrounded it — and
    it would be the exact overclaim this repository refuses everywhere else."""
    periods = re.findall(r"\b\d+\s*(?:day|week|month|year)s?\b", TEXT, re.IGNORECASE)
    assert not periods, f"GOVERNANCE.md quotes a period of time: {periods}"


def test_the_posture_cadence_the_page_quotes_is_the_one_in_the_workflow() -> None:
    """The page tells a reader to watch the weekly posture run as a sign of life. If the
    schedule moves, the sign moves with it."""
    assert "every Monday" in TEXT
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "posture.yml").read_text("utf-8"))
    crons = [str(entry["cron"]) for entry in workflow[True]["schedule"]]
    assert crons == ["0 3 * * 1"], f"posture runs on {crons}, and the page says every Monday"


def test_the_withdrawal_path_the_page_describes_is_in_the_schema() -> None:
    """`retracted:` is the page's whole deprecation policy. It has to be a key the catalogue
    accepts, or the policy is a paragraph."""
    assert "retracted" in rules.KEYS, (
        "GOVERNANCE.md describes retracted: as the whole withdrawal path, and the rule"
        " schema no longer knows that key"
    )


def test_there_is_no_codeowners_while_the_page_explains_its_absence() -> None:
    """The page has a section saying why there is no `CODEOWNERS`, and what would replace it.
    A repository that grows one while that section stands is a repository whose governance
    page describes a different repository."""
    assert "Why there is no CODEOWNERS file" in TEXT
    everywhere_github_looks = ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS")
    for name in everywhere_github_looks:
        where = ROOT / name
        assert not where.exists(), (
            f"{where.relative_to(ROOT)} exists while GOVERNANCE.md explains its absence —"
            " the section goes in the same change that adds the file"
        )
