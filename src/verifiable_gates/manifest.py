"""The overlay manifest: what a bundle ships, and which gates it can decide itself.

**The manifest is an input, not a constant.** In the reference implementation the
doctor read `overlay.json` from the directory beside it, which is fine while one
tool serves one registry — and wrong the moment the tool is a package that several
projects install. Passing the path in is the seam that lets one doctor answer for
many catalogues, and it is the difference between a tool and a copy of a tool.

Two kinds of entry, and the distinction is the honest part:

- **`scan`** — a script in this bundle decides it, here and now.
- **`suite`** — the bundle names the rule but *cannot* decide it; the project has
  to write its own test and register it. These are counted and reported, never
  silently passed. A rule the tool cannot check must not look like a rule it
  checked, which is the failure this whole project is organised against.

Role: helper — shared machinery for reading the overlay. Its evidence is its
callers and their tests.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

__all__ = ["KINDS", "load", "problems", "scripts", "shipped"]

KINDS = frozenset({"scan", "suite"})


def load(path: str | pathlib.Path) -> dict[str, Any]:
    """Read a manifest. Raises if it is unusable; `problems()` reports the rest."""
    raw = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"{path}: a manifest must be a JSON object")
    for key in ("ship", "gates"):
        if key not in raw:
            raise KeyError(f"{path}: manifest has no '{key}'")
    if not isinstance(raw["ship"], list):
        raise TypeError(f"{path}: 'ship' must be a list of file names")
    if not isinstance(raw["gates"], dict):
        raise TypeError(f"{path}: 'gates' must be an object keyed by gate id")
    return raw


def shipped(manifest: dict[str, Any]) -> list[str]:
    """File names the bundle installs, the manifest itself included.

    The manifest travels with the files it describes: a target project that has
    the scripts but not the catalogue has no way to know what it is holding.
    """
    return [*manifest["ship"], "overlay.json"]


def scripts(manifest: dict[str, Any]) -> dict[str, str]:
    """gate id → script path, for the entries this bundle can decide by itself."""
    return {
        gid: entry["script"]
        for gid, entry in sorted(manifest["gates"].items())
        if entry.get("kind") == "scan"
    }


def _entry_problems(
    gid: str,
    entry: Any,  # noqa: ANN401 — the shape of the entry is exactly what is being checked
    manifest: dict[str, Any],
    bundle: pathlib.Path,
) -> list[str]:
    if not isinstance(entry, dict):
        return [f"{gid}: entry must be an object"]

    found: list[str] = []
    kind = entry.get("kind")
    if kind not in KINDS:
        found.append(f"{gid}: kind {kind!r} is not one of {sorted(KINDS)}")
    if not str(entry.get("title", "")).strip():
        found.append(f"{gid}: no title — an id alone tells a reader nothing")

    script = entry.get("script")
    if kind == "scan":
        if not script:
            found.append(f"{gid}: kind 'scan' with no script — nothing would run")
        elif script not in manifest["ship"]:
            found.append(f"{gid}: script {script} is not in ship, so it never arrives")
        elif not (bundle / script).is_file():
            found.append(f"{gid}: script {script} is missing from the bundle")
    elif kind == "suite" and script:
        found.append(
            f"{gid}: kind 'suite' with a script — a suite gate is one this bundle "
            "cannot decide, and a script here would let it look decided"
        )
    return found


def _leaves(name: str) -> bool:
    """A ship name that would land outside the destination — absolute, or climbing with `..`.

    `install.py` joins each name under `dest/tools/`; an outside audit on 2026-08-30
    shipped `../../outside/PLANTED.txt` through `--manifest` and the file landed
    beside the destination, exit 0.
    """
    parts = pathlib.PurePosixPath(name).parts
    return pathlib.PurePosixPath(name).is_absolute() or ".." in parts


def problems(manifest: dict[str, Any], bundle: pathlib.Path) -> list[str]:
    """Everything wrong with a manifest, given the directory it describes."""
    escaping = [
        f"ship lists {name}, which would land outside the destination"
        for name in manifest["ship"]
        if _leaves(name)
    ]
    missing = [
        f"ship lists {name}, which is not in the bundle"
        for name in manifest["ship"]
        if not (bundle / name).is_file()
    ]
    entries = [
        problem
        for gid, entry in sorted(manifest["gates"].items())
        for problem in _entry_problems(gid, entry, manifest, bundle)
    ]
    return escaping + missing + entries
