"""SECURITY.md — one set of timeframes, no address, and the channel it names is live.

The rule `security-policy-consistent` this repository publishes: numbers that
disagree across copies let a reporter pick whichever suits them, and an email
address in the file is one more copy to keep. This repository had no policy at
all until 2026-08-29.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
POLICY = ROOT / "SECURITY.md"

# The declared timeframes — acknowledgement, assessment, coordinated disclosure.
DECLARED = {3, 14, 90}
DAYS = re.compile(r"\*\*(\d+) days\*\*")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def policy() -> str:
    return POLICY.read_text(encoding="utf-8")


def test_every_timeframe_quoted_is_one_of_the_declared_set() -> None:
    quoted = {int(days) for days in DAYS.findall(policy())}

    assert quoted == DECLARED, f"the file quotes {sorted(quoted)}, declared {sorted(DECLARED)}"


def test_no_email_address_appears() -> None:
    assert EMAIL.search(policy()) is None, "an address in the file is a copy nobody answers"


def test_the_channel_named_is_private_vulnerability_reporting() -> None:
    assert "security/advisories/new" in policy()


def test_no_other_file_quotes_a_timeframe_in_days() -> None:
    """Three numbers in one place. A second copy anywhere is the drift the rule is about."""
    others = [
        path
        for path in (ROOT / "README.md", ROOT / "CONTRIBUTING.md", ROOT / "CLA.md")
        if DAYS.search(path.read_text(encoding="utf-8"))
    ]

    assert others == [], f"timeframes quoted outside SECURITY.md: {others}"
