"""An id this project has published is never taken away — additions are free, removals are not.

The id is the one thing about a rule that leaves this repository and does not come back.
Measured on a scratch project (round 25, `probes/what-id-reaches-the-outside.txt`): the SARIF
the doctor writes labels every result with the **rule id**, and that is the string GitHub code
scanning stores per alert — the string a dismissal is attached to, a dashboard groups by, and a
consumer's own `gates.yaml` row names. Rename it and every one of those points at nothing, in
somebody else's repository, at a moment nobody here is watching.

Seventeen releases have never removed one: 92 rule ids at every tag from `v0.1.0` to `v0.4.0`,
gate ids only ever added, the nine shipped scan ids identical throughout
(`probes/ids-across-versions.txt`). **Nothing held that.** Renaming a rule id was red only
because the committed sheets stopped matching a fresh render — regenerate them in the same
change and it is green — and renaming a gate id left all 2 312 tests passing
(`probes/id-rename-mutations.txt`). The stability was a practice by one hand.

This is the register that makes it a promise, and it costs nothing to keep, because the way a
rule leaves already exists: **`retracted:`** (2026-09-05) withdraws it *in place*, with the date
and the reason, and the entry — and therefore the id — stays. A removal is refused here; a
withdrawal is not a removal.

**Our own `gates.yaml` ids are deliberately not held.** They are this repository's enforcement
of the published rules, they are not shipped, and no consumer ever sees one; a gate goes when
the test that was it goes, which `scan_gates_registry` already refuses to let happen silently.
What ships is `rules.yaml`, `working.yaml` and the overlay — and the overlay's scan ids are rule
ids, held to the catalogue by `tests/test_manifest.py`.

The comparison is against **every released tag**, not only the newest: a consumer may be on any
of them, and an id dropped three releases ago is as broken for them as one dropped today.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
# Found on PATH, like every other git call in this package — and kept in a name so that "git
# is not installed" is a sentence this file can say rather than an exception it raises.
GIT = shutil.which("git")
# The whole comparison — twenty files across seventeen tags — costs about two seconds of a
# hundred-second suite, and `git show` is 0.06 s of that; the rest is PyYAML (measured
# 2026-09-05). Fast enough not to buy the speed with a loader that would need explaining.
# What ships, and what a consumer can therefore have keyed something to.
PUBLISHED = (("rules.yaml", "rules"), ("working.yaml", "practices"))


def released_tags() -> list[str]:
    """Every version tag, oldest first, as git reports them."""
    if GIT is None:
        return []
    listed = subprocess.run(  # noqa: S603 — a fixed argv from PATH, no shell, no caller input
        [GIT, "tag", "--sort=creatordate"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return [tag for tag in listed.stdout.split() if tag.startswith("v")]


def ids_at(tag: str, path: str, key: str) -> set[str] | None:
    """The ids that file carried at that tag — or `None` if the file was not there yet."""
    if GIT is None:  # pragma: no cover — the guard test refuses this state first
        return None
    shown = subprocess.run(  # noqa: S603 — argv built here from a tag this repository owns
        [GIT, "show", f"{tag}:{path}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if shown.returncode != 0:
        return None
    loaded = yaml.safe_load(shown.stdout) or {}
    return {str(entry["id"]) for entry in loaded.get(key, []) if isinstance(entry, dict)}


def ids_now(path: str, key: str) -> set[str]:
    loaded = yaml.safe_load((ROOT / path).read_text(encoding="utf-8")) or {}
    return {str(entry["id"]) for entry in loaded.get(key, []) if isinstance(entry, dict)}


def test_the_tags_can_be_read_at_all() -> None:
    """A guard on the guard: with no tags in the clone, the checks below compare nothing and
    pass. The `test` job checks out with `fetch-depth: 0` for exactly this class of check."""
    assert GIT is not None, "git is not on PATH, so nothing below compared anything"
    tags = released_tags()
    assert len(tags) > 10, (
        f"only {len(tags)} version tags are readable here, so nothing below is being compared"
        " — in a shallow clone run `git fetch --tags --unshallow`"
    )


@pytest.mark.parametrize(("path", "key"), PUBLISHED)
def test_every_id_this_project_has_published_is_still_here(path: str, key: str) -> None:
    """Additions are free. A removal — and a rename, which is a removal with an addition
    beside it — is refused: the entry stays and carries `retracted:` instead."""
    here = ids_now(path, key)
    gone: dict[str, list[str]] = {}
    compared = 0
    for tag in released_tags():
        released = ids_at(tag, path, key)
        if released is None:  # the file did not exist at that tag yet
            continue
        compared += 1
        missing = sorted(released - here)
        if missing:
            gone[tag] = missing

    assert compared, f"{path} was in no released tag — this check compared nothing"
    assert not gone, (
        f"{path}: ids that were released and are not here now: {gone}. An id is what a"
        " consumer's alerts, dismissals and gates.yaml rows point at. To take a rule out of"
        " force, keep the entry and give it `retracted: {date, reason, replaced_by}` — the id"
        " stays, and the sheet says it was withdrawn."
    )
