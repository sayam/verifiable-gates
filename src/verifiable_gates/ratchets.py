"""A threshold that travels one way, held against what is true today.

A ratchet is a number in a config file that a project promises only to improve:
a coverage floor that rises, a suppression ceiling that falls. The promise is
usually written as a comment, and a comment is not a mechanism. **The failure is
not that someone lowers the number — it is that nobody raises it.** A floor left
behind by a codebase that got better is a floor that quietly permits the codebase
to get worse again, all the way back down to it, with nothing red at any point.

The reference implementation measured the size of that gap. Six days after
setting a coverage floor of 96 at a measured 96.31%, the real figure had reached
97.11% while the floor had not moved — a full point of slack, which is roughly
fifty covered lines that could have been deleted without a single check
complaining.

Four things this module keeps apart, because they fail differently and the advice
that fixes one is wrong for the others:

- **A floor** may only rise. Reality above it by more than its slack means the
  floor is stale; reality below it means a regression that nothing else will see.
- **A ceiling** may only fall — the mirror image, used for things that are
  allowed to exist but not to grow, such as the count of switched-off checkers.
  Going over it must be a signed decision; coming under it must be banked in the
  same change, or the space just won is refilled in silence.
- **A removal guard** is a floor whose upward direction is deliberately free. It
  exists to catch deletion, not growth. Forcing a project to bump a number every
  time it adds a row is a cost with nothing bought, and cost is what makes people
  stop reading a check at all.
- **A tool-owned floor** is one whose downward direction some other tool already
  enforces (`fail_under` in a coverage config refuses to pass beneath itself).
  Reporting the fall here too would hand the reader two messages telling them to
  do two different things about one problem.

**The wording of every message is an input.** The mechanism is portable; the
prose is not — a project reports to its own people in its own language, and the
reason a particular number exists belongs beside that number in the project's own
config, not here. English defaults ship so that the module is usable as it
stands.

Role: decider — it answers pass or fail. What it decides on is measured
elsewhere; this module never reads a file.
"""

from __future__ import annotations

import dataclasses
import math
import sys

__all__ = [
    "CEILING",
    "DEFAULT_SLACK",
    "FLOOR",
    "KINDS",
    "MESSAGES",
    "REMOVAL_GUARD",
    "Ratchet",
    "problems",
]

FLOOR = "floor"
CEILING = "ceiling"
REMOVAL_GUARD = "removal-guard"
KINDS = frozenset({FLOOR, CEILING, REMOVAL_GUARD})

# How far a floor may sit below reality before it counts as stale.
#
# **Not zero.** A threshold that has to be edited every time the measurement moves
# is a threshold people stop editing, and then stop reading. One point is wide
# enough to absorb the ordinary wobble of a percentage — a line gaining or losing
# a coverage pragma — and narrow enough that a real improvement gets banked.
#
# **A count uses zero instead**, and the difference is not a matter of taste: a
# percentage moves on its own, a count moves only when a person edits a list.
DEFAULT_SLACK = 1.0

MESSAGES = {
    "ceiling_exceeded": (
        "{name}: ceiling {declared:.0f} but actually {actual:.0f} — **more is switched off "
        "than the ceiling allows** · if it is genuinely needed, raise the ceiling in the "
        "same change with the reason in the commit: switching a checker off is a decision "
        "somebody signs"
    ),
    "ceiling_slack": (
        "{name}: ceiling {declared:.0f} but only {actual:.0f} left — lower the ceiling to "
        "{actual:.0f} in the same change that earned it, or the space just won gets refilled "
        "with nobody noticing"
    ),
    "floor_slack": (
        "{name}: floor {declared} but actually {actual} — {gap:.2f} above it (slack is "
        "{slack}) · raise the floor to {actual:.0f} in the same change that earned it, or "
        "the space just won gets spent with nobody noticing"
    ),
    "removal": (
        "{name}: declared {declared:.0f} but only {actual:.0f} left — **something was "
        "removed** · if the removal is intended, lower the number in the same change with "
        "the reason in the commit: taking a check away is a decision somebody signs, not a "
        "side effect of tidying up"
    ),
    "regression": (
        "{name}: actually {actual}, below the declared floor of {declared} — **this is a "
        "regression** · no tool enforces this direction, so this check is the only thing "
        "that sees it · the fix is to put back what was taken out, not to lower the floor"
    ),
}


@dataclasses.dataclass(frozen=True)
class Ratchet:
    """One number and the direction it is allowed to travel.

    The default is the common case: a floor, with the slack a percentage needs and
    no other tool watching it.
    """

    name: str
    kind: str = FLOOR
    slack: float = DEFAULT_SLACK
    owned_by_a_tool: bool = False

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"{self.name}: unknown kind {self.kind!r} — one of {sorted(KINDS)}")

    @property
    def allowed_gap(self) -> float:
        """Slack in the permitted direction — infinite for a removal guard.

        A removal guard's whole point is that growth is free, so its slack is a
        property of its kind rather than a number somebody sets. Reading it from
        the field instead would mean every removal guard had to say `math.inf` out
        loud, and the one that forgot would look exactly like a floor.
        """
        return math.inf if self.kind == REMOVAL_GUARD else self.slack


def _fields(ratchet: Ratchet, declared: float, actual: float) -> dict[str, object]:
    return {
        "name": ratchet.name,
        "declared": declared,
        "actual": actual,
        "gap": actual - declared,
        "slack": ratchet.allowed_gap,
    }


def _ceiling_problems(
    ratchet: Ratchet, declared: float, actual: float, text: dict[str, str]
) -> str:
    """A ceiling travels one way too, in the other direction — and both ways are wrong."""
    key = "ceiling_exceeded" if actual > declared else "ceiling_slack"
    return text[key].format(**_fields(ratchet, declared, actual))


def _floor_problems(
    ratchet: Ratchet, declared: float, actual: float, text: dict[str, str]
) -> list[str]:
    found = []
    fields = _fields(ratchet, declared, actual)
    if actual - declared > ratchet.allowed_gap:
        found.append(text["floor_slack"].format(**fields))
    if actual < declared and not ratchet.owned_by_a_tool:
        key = "removal" if ratchet.kind == REMOVAL_GUARD else "regression"
        found.append(text[key].format(**fields))
    return found


def problems(
    ratchets: dict[str, Ratchet],
    declared: dict[str, float],
    measured: dict[str, float],
    messages: dict[str, str] | None = None,
) -> list[str]:
    """Every declared threshold that no longer sits against reality.

    A name with no entry in `ratchets` is treated as an ordinary floor, so a
    project can declare a number and get the common behaviour without saying
    anything else about it.
    """
    text = {**MESSAGES, **(messages or {})}
    found: list[str] = []
    for name in sorted(declared):
        ratchet = ratchets.get(name, Ratchet(name))
        if ratchet.kind == CEILING:
            if measured[name] != declared[name]:
                found.append(_ceiling_problems(ratchet, declared[name], measured[name], text))
            continue
        found.extend(_floor_problems(ratchet, declared[name], measured[name], text))
    return found


if __name__ == "__main__":
    # A helper is not a command. Run as one, these modules imported cleanly and exited 0
    # with nothing done — a wrong call that looked like a pass, which `gates.yaml` forbids
    # in as many words ("A misuse must exit 2, never 0"). Round 11 gave seven modules this
    # guard from a list written by hand, and the list was seven short (self-audit round 12,
    # 2026-09-01); the test now reads the package instead of remembering it.
    sys.stderr.write(
        "verifiable_gates.ratchets is a helper, not a command — it has no entry point of\n"
        "its own; the readers that answer for themselves are listed in CONTRIBUTING.\n"
    )
    sys.exit(2)
