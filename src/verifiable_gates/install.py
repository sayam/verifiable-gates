"""Copy a bundle into a project — by manifest, never by guessing.

    python3 -m verifiable_gates.install <destination> [--manifest path]

What the destination ends up with:

- `tools/` — the doctor, the scans, and the manifest that describes them
- `scaffold.json` — configuration, **never overwritten** if it is already there
- `gates.yaml` — the starting registry, also never overwritten
- `.github/workflows/gates.yml` — a starting workflow, also never overwritten

The three "never overwritten" cases are the ones holding decisions somebody made.
Everything else is ours and is replaced, because a half-updated bundle is worse
than an old one.

Keeping `gates.yaml` while writing the workflow leaves a seam: the workflow runs a
job the kept registry may not name, and the doctor is red from the first run
(an outside audit installed into the reference implementation on 2026-08-30 and
got `job with no gate in the index: scans`). The installer says so, with the row
to add — it does not fail, because the files did arrive and a consumer's CI
reinstalls on every run.

**The file list comes from the manifest and nowhere else.** A file the manifest
names but the bundle does not have makes the install **fail loudly** rather than
land half-complete — the success condition being that deleting one file from the
bundle turns the installer red, not quiet. Every problem `manifest.problems()`
can name is checked before the first copy, because `--manifest` lets a manifest
arrive from outside this package: one that ships `../x` used to write beside
the destination (outside audit, 2026-08-30).

Role: generator — it copies files that are committed in a consumer's tree. Its
evidence is that what arrives equals the manifest and the doctor reads it back.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import sys
from typing import Any

from verifiable_gates import __version__
from verifiable_gates import manifest as manifest_module

__all__ = ["install", "main"]

# Names that carry someone's decisions once they exist in the destination.
KEEP_IF_PRESENT = {
    "scaffold.json.default": "scaffold.json",
    "gates.yaml.default": "gates.yaml",
    "ci-template.yml": ".github/workflows/gates.yml",
}


# The job `ci-template.yml` runs the scans under; a test holds the two together.
TEMPLATE_JOB = "scans"
JOB_NAMED = re.compile(r"\bjob:\s*" + TEMPLATE_JOB + r"\b")


def _without_comments(text: str) -> str:
    """The registry's lines with every `#` comment cut — a comment that says `job: scans`
    is not a row (self-audit, 2026-08-31: it silenced the warning)."""
    return "\n".join(re.sub(r"(^|\s)#.*$", r"\1", line) for line in text.splitlines())


def _registry_names_the_job(dest: pathlib.Path) -> bool:
    """Does the kept `gates.yaml` give the template's job a gate? The workflow is always there."""
    registry = dest / KEEP_IF_PRESENT["gates.yaml.default"]
    return JOB_NAMED.search(_without_comments(registry.read_text(encoding="utf-8"))) is not None


def _target(dest: pathlib.Path, name: str) -> pathlib.Path:
    relative = KEEP_IF_PRESENT.get(name)
    return dest / relative if relative else dest / "tools" / name


def _destination_problems(dest: pathlib.Path, names: list[str]) -> list[str]:
    """What is wrong with the destination itself: a file where a directory should be,
    a directory nobody can write, or a directory on the way to a target that is a
    symlink leading outside — fourteen files landed outside `dest` through a
    `tools` symlink, exit 0 (self-audit, 2026-08-31)."""
    if dest.exists() and not dest.is_dir():
        return [f"{dest} exists and is not a directory"]
    if dest.is_dir() and not os.access(dest, os.W_OK):
        return [f"{dest} is not writable"]
    inside = dest.resolve()
    found: list[str] = []
    for name in names:
        parent = _target(dest, name).parent
        while parent != dest and parent.exists():
            if not parent.resolve().is_relative_to(inside):
                found.append(f"{parent.relative_to(dest)} leads outside the destination")
                break
            parent = parent.parent
    return sorted(set(found))


RECORD = "tools/installed.json"


def digest(path: pathlib.Path) -> str:
    """The sha256 of a file, as the record writes it."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _left_behind(dest: pathlib.Path, written: list[pathlib.Path]) -> list[str]:
    """What a previous install wrote and this one no longer ships.

    A bundle that renames or drops a scanner leaves the old file in the project's
    repository forever: nothing names it, the doctor never runs it, and `--installed`
    reports "every scan runs" because it checks only what the current record names. The
    project cannot tell dead code from live code in a directory this bundle owns
    (self-audit round 9, 2026-09-01). Said out loud, and not deleted: files in somebody
    else's repository are theirs to remove.
    """
    record = dest / RECORD
    if not record.is_file():
        return []
    try:
        before = set(json.loads(record.read_text(encoding="utf-8"))["files"])
    except (OSError, ValueError, KeyError, TypeError):
        return []
    now = {str(path.relative_to(dest)) for path in written}
    return sorted(before - now)


def _record(dest: pathlib.Path, written: list[pathlib.Path]) -> None:
    """Write down what this install put here, so the doctor can say whether it is still
    what arrived.

    `--installed` said "the bundle arrived intact" while checking only that each file is
    present and compiles: a scanner whose body had been replaced with `return 0` passed
    that check and then reported its gate as `pass` on a tree that violated it
    (self-audit round 4, 2026-09-01). Only the files this install *wrote* are recorded —
    the project's own `gates.yaml`, `scaffold.json` and workflow are its decisions to
    edit, and a record of them would be a check against the project rather than the
    bundle.
    """
    record = {
        "version": __version__,
        "files": {str(path.relative_to(dest)): digest(path) for path in sorted(written)},
    }
    target = dest / RECORD
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def install(
    dest: pathlib.Path,
    manifest: dict[str, Any],
    bundle: pathlib.Path,
    manifest_path: pathlib.Path | None = None,
) -> int:
    kept_registry = False
    written: list[pathlib.Path] = []
    names = manifest_module.shipped(manifest)

    # Refuse before touching the destination: the directories used to be made
    # first, so a refused install still left an empty `tools/checks/` behind
    # (outside audit, 2026-08-31) — and the destination is judged the same way,
    # before the first copy, so a refusal never lands half a bundle.
    wrong = manifest_module.problems(manifest, bundle)
    for problem in wrong:
        print(f"** the bundle is incomplete: {problem}", file=sys.stderr)
    for problem in _destination_problems(dest, names):
        print(f"** the destination is unusable: {problem}", file=sys.stderr)
        wrong.append(problem)
    if wrong:
        print("** refusing to install", file=sys.stderr)
        return 1
    try:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "tools" / "checks").mkdir(parents=True, exist_ok=True)
        for name in names:
            # The manifest travels under its shipped name whatever it was called
            # where it came from — `--manifest bundle.json` used to land sixteen
            # files and then die looking for `overlay.json` (self-audit, 2026-08-31).
            source = manifest_path if name == "overlay.json" and manifest_path else bundle / name
            target = _target(dest, name)
            if name in KEEP_IF_PRESENT and target.exists():
                print(f"kept: {target.relative_to(dest)} (already there)")
                kept_registry = kept_registry or name == "gates.yaml.default"
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            if name not in KEEP_IF_PRESENT:
                # The three files a project owns from the moment they land — its
                # registry, its scaffold and its workflow — are its decisions to edit,
                # so they are not recorded: a record of them would hold the project to
                # the bundle's defaults rather than hold the bundle to what it shipped.
                written.append(target)
    except OSError as error:
        print(f"** could not write to {dest}: {error} — the install is incomplete", file=sys.stderr)
        return 1

    for name in _left_behind(dest, written):
        print(
            f"left behind: {name} — this bundle no longer ships it; delete it or keep it on purpose"
        )
    _record(dest, written)

    if kept_registry and not _registry_names_the_job(dest):
        print(
            f"** kept gates.yaml names no gate for job `{TEMPLATE_JOB}`, which the"
            f" workflow runs — the doctor is red until it does. Add a row"
            f" `enforced_by: {{job: {TEMPLATE_JOB}}}` or drop the job.",
            file=sys.stderr,
        )
    scans = len(manifest_module.scripts(manifest))
    print(
        f"installed into {dest} — {len(manifest['gates'])} gates ({scans} scan) · "
        "check with: python3 tools/gates_doctor.py"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install a gate bundle into a project.")
    parser.add_argument("destination")
    parser.add_argument("--manifest", help="path to overlay.json (default: beside the package)")
    args = parser.parse_args(argv)

    here = pathlib.Path(__file__).resolve().parent
    manifest_path = (
        pathlib.Path(args.manifest).resolve() if args.manifest else here / "overlay.json"
    )
    try:
        manifest = manifest_module.load(manifest_path)
    except (OSError, ValueError, TypeError, KeyError) as error:
        # Unreadable is said plainly and is exit 2, like every other input this
        # package cannot read — eight malformed shapes were each a traceback
        # (self-audit, 2026-08-31).
        print(f"** cannot read the manifest: {error}", file=sys.stderr)
        return 2
    return install(
        pathlib.Path(args.destination).resolve(), manifest, manifest_path.parent, manifest_path
    )


if __name__ == "__main__":
    sys.exit(main())
