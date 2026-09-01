"""A number a project advertises in several places, kept true by one command.

Every number worth advertising already has a test holding it against reality —
that part is right and stays. What stays manual is **making it true again**. The
reference implementation measured the bill: adding one decision record turned
three files red, adding one gate turned two more, and **25 of its last 200
commits were nothing but numbers being copied from one file into another.**

This weakens no check. The tests still decide; this does the typing.

Two shapes of the same problem:

- **Inside the repository** — a count that several documents quote. A change
  makes them wrong, some test goes red, and a person walks the list by hand.
- **Outside it** — a field on a hosting platform: a description, a summary, an
  About box. **Nothing there produces a diff**, so no test ever runs and nobody
  notices it aged. The reference implementation got this wrong twice in one
  session, each time by exactly one, because the step was one somebody had to
  remember.

**The first capture group is the thing that should be true**, everywhere here.
That single convention removes the need for lookbehind-and-lookahead gymnastics
in every pattern, and it lets one primitive replace a value in place without
rewriting the sentence around it. Rewriting the whole field instead would delete
whatever prose a person had put there — which is the same silent loss this module
exists to stop.

**A pattern that matches nothing is reported, never skipped.** A synchroniser
that goes quiet when it cannot find what it was looking for is one that says
"everything agrees" on the day it read nothing at all.

Role: generator — it writes files that are committed. Its evidence is that what
it produces matches what is committed; coverage is not the measure for this kind.
"""

from __future__ import annotations

import dataclasses
import re
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pathlib

__all__ = [
    "Drift",
    "Expectation",
    "Place",
    "drift",
    "field_drift",
    "field_patched",
    "replace_group_one",
    "write",
]

MISSING = "(not found)"


@dataclasses.dataclass(frozen=True)
class Place:
    """One file, and the pattern whose first group should hold the value."""

    path: str
    pattern: str


@dataclasses.dataclass(frozen=True)
class Drift:
    """One place that does not say what it should."""

    place: Place
    said: str
    want: str

    @property
    def is_missing(self) -> bool:
        """Nothing in the file matched — the sentence that quoted this is gone."""
        return self.said == MISSING


@dataclasses.dataclass(frozen=True)
class Expectation:
    """One claim inside a free-text field, and what it should say.

    `label` is what a person is told changed; `pattern`'s first group is the part
    that must equal `want`.
    """

    label: str
    pattern: str
    want: str


def replace_group_one(text: str, pattern: str, want: str, count: int = 1) -> str:
    """Put `want` where the first group is, leaving every other character alone.

    The obvious alternative — substituting the whole match — forces every pattern
    to push its context into lookbehind and lookahead, which is where these
    patterns become unreadable and then wrong.
    """

    def swap(found: re.Match[str]) -> str:
        start, end = found.span(1)
        whole = found.group(0)
        offset = found.start()
        return whole[: start - offset] + want + whole[end - offset :]

    return re.sub(pattern, swap, text, count=count)


def drift(
    root: pathlib.Path, targets: dict[str, list[Place]], values: dict[str, str]
) -> list[Drift]:
    """Every place whose first group does not already equal the value it advertises.

    `values` maps a fact to what it should read as. **A string, not a number**, so
    a fact whose value is a whole line — a tally, a version — needs no special
    case here; the reference implementation carried one for exactly that, in two
    functions, and it was the only branch either of them had.
    """
    found = []
    for fact, places in targets.items():
        want = values[fact]
        for place in places:
            body = (root / place.path).read_text(encoding="utf-8")
            said = re.search(place.pattern, body)
            if said is None:
                found.append(Drift(place, MISSING, want))
            elif said.group(1) != want:
                found.append(Drift(place, said.group(1), want))
    return found


def write(root: pathlib.Path, items: list[Drift]) -> None:
    """Fix each place, touching nothing else.

    A diff wider than it needs to be is a diff nobody reads, and a synchroniser
    whose changes nobody reads is one nobody will trust to run unattended.

    **A place that could not be found needs no guard here.** An earlier version
    skipped those explicitly; a planted defect removing that skip changed nothing
    a test could see, because substituting into text that does not match is
    already no change at all. A branch nothing can observe is a branch that will
    be believed to do something it does not, so it is gone: `drift` is what
    reports the miss, and this only types.
    """
    for item in items:
        path = root / item.place.path
        body = path.read_text(encoding="utf-8")
        path.write_text(replace_group_one(body, item.place.pattern, item.want), encoding="utf-8")


def field_drift(text: str, expectations: list[Expectation]) -> list[tuple[str, str, str]]:
    """(what, what it says, what it should say) for a free-text field.

    A claim that has gone missing from the field entirely **is reported**, not
    passed over — a field that lost the sentence is not a field that agrees.
    """
    found = []
    for expected in expectations:
        said = re.search(expected.pattern, text)
        if said is None:
            found.append((expected.label, MISSING, expected.want))
        elif said.group(1) != expected.want:
            found.append((expected.label, said.group(1), expected.want))
    return found


def field_patched(text: str, expectations: list[Expectation]) -> str:
    """The same field with each claim corrected in place, the prose untouched.

    Rebuilding the field from the values would be shorter and would delete
    whatever else a person wrote there — and nobody would see it go, because a
    field outside the repository leaves no diff behind.
    """
    patched = text
    for expected in expectations:
        patched = replace_group_one(patched, expected.pattern, expected.want)
    return patched


if __name__ == "__main__":
    # A helper is not a command. Run as one, these modules imported cleanly and exited 0
    # with nothing done — a wrong call that looked like a pass, which `gates.yaml` forbids
    # in as many words ("A misuse must exit 2, never 0") and which `gates_doctor` had
    # already decided once, by accepting `--root` as the spelling an operator reaches for
    # (self-audit round 2, owner decision B6, 2026-09-01). `sys.stderr.write` rather than
    # `print`, because a helper may not print and the suppression ceiling only falls.
    sys.stderr.write(
        "verifiable_gates.advertised is a helper, not a command — it has no entry point of\\n"
        "its own; the readers that answer for themselves are listed in CONTRIBUTING.\\n"
    )
    sys.exit(2)
