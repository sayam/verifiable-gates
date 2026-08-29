"""Every module declares its role — so the right kind of evidence can be asked of it.

The rule `scripts-declare-their-role` this repository publishes: coverage is the
wrong instrument for half the files (a generator is proved by its output, a
reader by its numbers matching the source), and only a declared kind lets a
reviewer demand the right sort. Every module here wrote a `Role:` line by habit —
until ten did not, and nothing noticed (2026-08-29).
"""

from __future__ import annotations

import pathlib
import re

import pytest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "verifiable_gates"
KINDS = ("decider", "generator", "reader", "helper")
ROLE = re.compile(rf"^Role: ({'|'.join(KINDS)}) — ", re.MULTILINE)


def modules() -> list[pathlib.Path]:
    """Every module in the package except the package's own `__init__`, which is not a script."""
    return sorted(p for p in SRC.rglob("*.py") if p.name != "__init__.py")


def test_there_are_modules_to_hold() -> None:
    assert len(modules()) > 20


@pytest.mark.parametrize("path", modules(), ids=lambda p: str(p.relative_to(SRC)))
def test_a_module_declares_one_of_the_four_roles(path: pathlib.Path) -> None:
    text = path.read_text(encoding="utf-8")
    docstring_end = text.index('"""', 3)

    found = ROLE.findall(text[:docstring_end])
    assert len(found) == 1, (
        f"{path.name}: expected exactly one `Role: <kind> — …` line in the module "
        f"docstring, kinds {KINDS}; found {found}"
    )
