"""Every scanner this bundle ships is pointed at this repository.

Audit round 23 of the reference implementation measured the gap between the rules
a project exports and the rules it keeps, and the answer was 2.7%. The cheapest
defence is to point every scanner that *can* apply here at here, from the day it
lands.

**The list is computed, not written.** The first version of this file named the
two scanners that applied and said so in its docstring — "only two apply today" —
which was true when `gates.yaml` was empty and stopped being true the moment it
got its first row. Nothing noticed for four stages, because a hand-kept list of
what applies decays exactly like every other hand-kept list, and the registry
handover found it by running the scanner by hand. So there is no list any more:
every scanner runs, and each one answers for itself whether it had anything to
check.

That gives three outcomes, and keeping them apart is the point:

- **a finding** — this repository breaks a rule it exports, and the test fails;
- **not applicable** — the scanner found nothing of its kind here, which is honest
  and is *not* a pass;
- **clean** — it found things of its kind and they were all right.

The floor at the bottom is what stops the second outcome swallowing the others. If
this repository lost its workflows, its pinned tools and its registry, every
scanner would go not-applicable and this file would be green while checking
nothing at all.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

import pytest
from bundle import BUNDLE

import verifiable_gates.checks

# How many scanners must find something of their kind here. Not a target — a
# floor, so an all-N/A suite cannot pass as a clean one. Raise it when this
# repository grows something a further scanner can read.
APPLICABLE_FLOOR = 3


def shipped_scanners() -> list[str]:
    """Every scan module in the package, found rather than listed."""
    return sorted(
        module.name
        for module in pkgutil.iter_modules([str(BUNDLE / "checks")])
        if module.name.startswith("scan_")
    )


def load(name: str) -> Any:  # noqa: ANN401 — a module object
    return importlib.import_module(f"{verifiable_gates.checks.__name__}.{name}")


def test_there_are_scanners_to_run() -> None:
    """A guard on the guard: an empty list would make everything below vacuous."""
    assert shipped_scanners(), "no scanners found — the checks below would prove nothing"


@pytest.mark.parametrize("name", shipped_scanners())
def test_this_repository_passes_the_rules_it_ships(
    name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    result = load(name).main(BUNDLE.parent.parent)
    output = capsys.readouterr().out
    assert result == 0, f"this repository breaks a rule it exports:\n{output}"


def test_enough_scanners_actually_find_something_here(capsys: pytest.CaptureFixture[str]) -> None:
    """N/A is honest, and it is not a pass — so at least some must have real work."""
    applied = []
    for name in shipped_scanners():
        load(name).main(BUNDLE.parent.parent)
        if not capsys.readouterr().out.startswith("NA:"):
            applied.append(name)
    assert len(applied) >= APPLICABLE_FLOOR, (
        f"only {len(applied)} scanners found anything to check here ({applied}); "
        f"the floor is {APPLICABLE_FLOOR}. Either this repository lost something a "
        "scanner reads, or the suite is now green without checking anything."
    )
