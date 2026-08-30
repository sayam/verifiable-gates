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
import pathlib
import re
import shutil
import sys
from typing import Any

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


def _registry_names_the_job(dest: pathlib.Path) -> bool:
    """Does the kept `gates.yaml` give the template's job a gate? The workflow is always there."""
    registry = dest / KEEP_IF_PRESENT["gates.yaml.default"]
    return JOB_NAMED.search(registry.read_text(encoding="utf-8")) is not None


def _target(dest: pathlib.Path, name: str) -> pathlib.Path:
    relative = KEEP_IF_PRESENT.get(name)
    return dest / relative if relative else dest / "tools" / name


def install(dest: pathlib.Path, manifest: dict[str, Any], bundle: pathlib.Path) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "tools" / "checks").mkdir(parents=True, exist_ok=True)
    kept_registry = False

    wrong = manifest_module.problems(manifest, bundle)
    if wrong:
        for problem in wrong:
            print(f"** the bundle is incomplete: {problem}", file=sys.stderr)
        print("** refusing to install", file=sys.stderr)
        return 1
    for name in manifest_module.shipped(manifest):
        source = bundle / name
        target = _target(dest, name)
        if name in KEEP_IF_PRESENT and target.exists():
            print(f"kept: {target.relative_to(dest)} (already there)")
            kept_registry = kept_registry or name == "gates.yaml.default"
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

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
    manifest = manifest_module.load(manifest_path)
    return install(pathlib.Path(args.destination).resolve(), manifest, manifest_path.parent)


if __name__ == "__main__":
    sys.exit(main())
