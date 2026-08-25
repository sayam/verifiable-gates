"""A shipped file has no silent dependencies — it declares what it needs.

The rule is not "no dependencies". It is "no *undeclared* ones". A file that
needs something outside the standard library says so in the manifest, and the
declaration is held to what the file actually imports in **both** directions.
An import nobody declared is a surprise a target project finds in a traceback;
a declaration nothing imports is a requirement that outlived its reason and
gets copied forward forever.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import bundle
import pytest

if TYPE_CHECKING:
    import pathlib


@pytest.mark.parametrize("path", bundle.SHIPPED_ALL, ids=lambda p: p.name)
def test_a_shipped_file_declares_anything_it_needs(path: pathlib.Path) -> None:
    """Undeclared dependencies fail in someone else's project, where nobody here can see it.

    The rule is not "no dependencies" — it is "no *silent* ones". A file that needs
    something says so in the manifest, and this holds the declaration to what the
    file actually imports, in **both** directions: an import nobody declared is a
    surprise for a target project, and a declaration nothing imports is a
    requirement that outlived its reason and will be copied forward forever.
    """
    name = path.relative_to(bundle.BUNDLE).as_posix()
    imported = bundle.outside_stdlib(path)
    needed = {bundle.IMPORT_TO_DISTRIBUTION.get(module, module) for module in imported}
    declared = set(bundle.declared().get(name, []))

    assert needed <= declared, (
        f"{name} imports {sorted(needed - declared)} without declaring it in overlay.json "
        "under 'requires' — a target project would find out from a traceback"
    )
    assert declared <= needed, (
        f"{name} declares {sorted(declared - needed)} but does not import it — "
        "a requirement nobody needs is one every project carries for no reason"
    )


def test_only_the_files_that_ship_are_listed_as_requiring_anything() -> None:
    """A `requires` entry for a file nobody installs points at nothing."""
    manifest = bundle.manifest()
    shipped = set(manifest["ship"])
    listed = set(bundle.declared())
    assert listed <= shipped, (
        f"requires names files the bundle does not ship: {sorted(listed - shipped)}"
    )


def test_everything_the_bundle_ships_that_is_python_is_checked_here() -> None:
    """A guard on the guard: a new shipped file must join one of the two lists above."""
    manifest = bundle.manifest()
    shipped_python = {name for name in manifest["ship"] if name.endswith(".py")}
    checked = {path.relative_to(bundle.BUNDLE).as_posix() for path in bundle.SHIPPED_ALL}
    assert shipped_python == checked, (
        "the bundle ships Python this file does not check: "
        f"{sorted(shipped_python - checked)} (and checks what it does not ship: "
        f"{sorted(checked - shipped_python)})"
    )
