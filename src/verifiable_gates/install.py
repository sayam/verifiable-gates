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

**The file list comes from the manifest and nowhere else.** A file the manifest
names but the bundle does not have makes the install **fail loudly** rather than
land half-complete — the success condition being that deleting one file from the
bundle turns the installer red, not quiet.

Role: generator — it copies files that are committed in a consumer's tree. Its
evidence is that what arrives equals the manifest and the doctor reads it back.
"""

from __future__ import annotations

import argparse
import pathlib
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


def _target(dest: pathlib.Path, name: str) -> pathlib.Path:
    relative = KEEP_IF_PRESENT.get(name)
    return dest / relative if relative else dest / "tools" / name


def install(dest: pathlib.Path, manifest: dict[str, Any], bundle: pathlib.Path) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "tools" / "checks").mkdir(parents=True, exist_ok=True)

    for name in manifest_module.shipped(manifest):
        source = bundle / name
        if not source.is_file():
            print(f"** the bundle is incomplete: no {name} — refusing to install", file=sys.stderr)
            return 1
        target = _target(dest, name)
        if name in KEEP_IF_PRESENT and target.exists():
            print(f"kept: {target.relative_to(dest)} (already there)")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

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
