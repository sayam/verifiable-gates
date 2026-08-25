"""This repository is in English, except where a document binds someone legally.

`CONTRIBUTING.md` states the rule; this file is what makes it a rule rather than
a sentence. It checks **both directions**, because an allowlist decays in two
ways and only one of them is obvious:

- **Thai outside the allowed files** is the obvious failure — it arrives quietly
  when code is moved in from the reference implementation, which is written in
  Thai throughout, and that is exactly what stages 2–5 do repeatedly.
- **An allowed file with no Thai left in it** is the quiet failure. If someone
  strips the Thai half of `CLA.md`, the exception stops describing anything and
  becomes a hole the next Thai file can walk through unnoticed. The exception
  must expire with the thing it excused.

Why the exception exists at all: a licence or an agreement has to be understood
by the person bound by it, and the maintainer's first language is Thai. English
first, Thai below — both halves saying the same thing.
"""

from __future__ import annotations

import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Files kept bilingual on purpose: anything that binds someone legally.
# Adding to this list is a decision, not a convenience — see CONTRIBUTING.md.
BILINGUAL = ("README.md", "CLA.md")

THAI = range(0x0E01, 0x0E5C)  # Thai block, U+0E01..U+0E5B


def has_thai(text: str) -> bool:
    return any(ord(char) in THAI for char in text)


def tracked_files() -> list[pathlib.Path]:
    """What git tracks — not what happens to be on disk.

    Walking the filesystem was the first version, and it failed on
    `verifiable_gates.egg-info/PKG-INFO`: a build artefact that embeds the
    bilingual README, is ignored by git, and exists only on machines where the
    package was installed in editable mode. A check that fails on files the
    repository does not contain fails for whoever happens to have built locally.
    """
    listed = subprocess.run(
        ["git", "ls-files", "-z"],  # noqa: S607 — git is a hard requirement of this repo
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout
    return sorted(ROOT / name for name in listed.split("\0") if name)


def test_the_allowlist_names_files_that_exist() -> None:
    missing = [name for name in BILINGUAL if not (ROOT / name).is_file()]
    assert not missing, f"the bilingual allowlist names files that are gone: {missing}"


def test_no_thai_outside_the_bilingual_files() -> None:
    offenders = []
    for path in tracked_files():
        relative = path.relative_to(ROOT).as_posix()
        if relative in BILINGUAL:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if has_thai(text):
            offenders.append(relative)
    assert not offenders, (
        "Thai outside the bilingual files — translate it, or if it belongs to a "
        f"document that binds someone legally, add it to BILINGUAL with a reason: {offenders}"
    )


@pytest.mark.parametrize("name", BILINGUAL)
def test_every_bilingual_file_really_is_bilingual(name: str) -> None:
    """The other direction — an exception that no longer excuses anything must go."""
    text = (ROOT / name).read_text(encoding="utf-8")
    assert has_thai(text), (
        f"{name} is on the bilingual allowlist but has no Thai left in it. "
        "Either restore the Thai half or drop the file from BILINGUAL — an "
        "exception that excuses nothing is a hole with a label on it."
    )
