"""gate: image-digest-pinned — a base image is pinned by digest, not only by tag.

A tag can be re-pointed, and then the image that passed the tests is not the image
that was deployed. Pinning also needs someone moving the pins — the title says
"and Dependabot moves it", so a judged Dockerfile with no `docker` ecosystem in
`.github/dependabot.yml` is a finding: a digest nobody moves is a vulnerability
kept on ice. That half was delegated to another gate and checked nowhere, and
`FROM scratch` — the empty image, which has no digest to pin — was a finding
(self-audit, 2026-08-31).

Dockerfile instructions are case-insensitive, and an image can enter a build
through `COPY --from=<image>` as well as `FROM` — an outside audit on 2026-08-29
found a lowercase `from` and an unpinned `COPY --from=` both passing a scanner
that read only uppercase `FROM` lines. So the instruction is matched in any case,
flags such as `--platform=` are stepped over so the token judged is the image, and
`COPY --from=` is judged by the same rule.

A project that has not named its Dockerfiles gets the default, `Dockerfile` at
the root — and when that is absent, any `Dockerfile*` elsewhere in the tree is
reported rather than passed over: an outside audit on 2026-08-30 planted an
unpinned `Dockerfile.prod` and an unpinned `docker/Dockerfile`, each alone, and
both answered "no Dockerfile". NA means nothing to check, not nothing looked at.
A project that *has* named its Dockerfiles has decided; other files are its own.

exit 0 = clean or N/A · 1 = findings · 2 = called wrongly

Role: decider — it answers pass or fail with an exit code, and it ships as a
standalone file; its evidence is a planted violation and a clean tree in
`tests/test_checks_behaviour.py`.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

# `FROM [--flag=value ...] <image> [AS <stage>]` — flags are skipped, not judged.
FROM_LINE = re.compile(r"^\s*FROM\s+(?:--\S+\s+)*(\S+)", re.MULTILINE | re.IGNORECASE)
STAGE = re.compile(r"^\s*FROM\s+.*?\s+AS\s+(\S+)", re.MULTILINE | re.IGNORECASE)
# `COPY --from=<image-or-stage>` pulls an image into the build exactly as FROM does.
COPY_FROM = re.compile(r"^\s*COPY\s+(?:--\S+\s+)*?--from=(\S+)", re.MULTILINE | re.IGNORECASE)
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")
# `scratch` is the empty starting image — nothing is pulled, so there is nothing to pin.
SCRATCH = "scratch"
DOCKER_ECOSYSTEM = re.compile(r"""package-ecosystem\s*:\s*["']?docker["']?\s*$""", re.MULTILINE)
NO_MOVER = (
    "no `package-ecosystem: docker` in .github/dependabot.yml — a digest nobody moves is a "
    "vulnerability kept on ice"
)


class _UnreadableError(Exception):
    """Bytes this scanner cannot decode. No verdict — never a clean one."""


def _text(path: pathlib.Path) -> str:
    """The file's text, or `_UnreadableError` naming it.

    A file that is not UTF-8 made every scanner but the two AST readers die of a raw
    `UnicodeDecodeError` and exit 1 — the code that means findings (self-audit round 3,
    2026-09-01). A byte sequence nobody can decode is the third answer, not a verdict.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as problem:
        # `OSError` too: a file the scanner is not allowed to read, or that turned into
        # a directory between the glob and the read, was still a raw traceback after the
        # decode guard landed — the guard was written for the exception in hand rather
        # than for the question (self-audit round 5, 2026-09-01).
        message = f"{path}: {problem}"
        raise _UnreadableError(message) from problem


def _nothing_moves_the_pins(root: pathlib.Path) -> bool:
    config = root / ".github" / "dependabot.yml"
    return not (config.is_file() and DOCKER_ECOSYSTEM.search(_text(config)))


UNNAMED = (
    "{path} is a Dockerfile scaffold.json does not name — name it under `dockerfiles`, "
    "or it is never judged"
)
MISCONFIGURED = (
    "scaffold.json names {key} {path}, which is not there — a configured path that "
    "is missing is a broken configuration, not nothing to check"
)


def _unnamed(root: pathlib.Path) -> list[str]:
    """Every `Dockerfile*` in the tree, when the project named none and has no default one.

    Hidden directories (`.git`, `.venv`) hold copies of other things.
    """
    return [
        UNNAMED.format(path=found.relative_to(root))
        for found in sorted(root.rglob("Dockerfile*"))
        if found.is_file() and not any(part.startswith(".") for part in found.parts)
    ]


def _unpinned(root: pathlib.Path, path: pathlib.Path) -> list[str]:
    """Every image one Dockerfile pulls in without a digest."""
    text = _text(path)
    stages = {stage.lower() for stage in STAGE.findall(text)}
    refs = [("FROM", ref) for ref in FROM_LINE.findall(text)]
    refs += [("COPY --from", ref) for ref in COPY_FROM.findall(text)]
    return [
        f"{path.relative_to(root)}: {how} {ref}"
        for how, ref in refs
        # A stage name is a local alias, not an image — and names are also
        # case-insensitive. A bare stage *index* (`--from=0`) is one too.
        if ref.lower() not in {*stages, SCRATCH} and not ref.isdigit() and not DIGEST.search(ref)
    ]


def _judge(root: pathlib.Path) -> int:
    if not root.is_dir():
        # NA means "this project has nothing of that kind"; a root that is not
        # there has no project to say it about, and answering the second with
        # the first is a green over nothing (self-audit round 2, 2026-08-31).
        print(f"cannot read the tree: {root} is not a directory", file=sys.stderr)
        return 2
    config_path = root / "scaffold.json"
    # A project that has not configured the bundle is not a misuse — the paths
    # below fall back to their defaults, and a default that is not there reports
    # NA. A path the project *named* and does not have is the opposite case: a
    # broken configuration, reported as a finding — an outside audit on
    # 2026-08-29 planted a `scaffold.json` pointing at a Dockerfile that did not
    # exist beside a dirty one that did, and the answer was "nothing to check".
    config = json.loads(_text(config_path)) if config_path.is_file() else {}
    names = config.get("dockerfiles", ["Dockerfile"])
    dockerfiles = [root / n for n in names if (root / n).is_file()]
    # A name the project wrote down and does not have is judged, not skipped.
    findings: list[str] = [
        MISCONFIGURED.format(key="dockerfiles", path=n)
        for n in names
        if "dockerfiles" in config and not (root / n).is_file()
    ]
    if not dockerfiles and "dockerfiles" not in config:
        findings += _unnamed(root)
    if not dockerfiles and not findings:
        print("NA: no Dockerfile — nothing to check yet")
        return 0

    for path in dockerfiles:
        findings += _unpinned(root, path)
    if dockerfiles and _nothing_moves_the_pins(root):
        findings.append(NO_MOVER)

    for finding in findings:
        print(f"image-digest-pinned: {finding}")
    return 1 if findings else 0


def main(root: pathlib.Path) -> int:
    """The verdict, or the third answer when a file cannot be decoded."""
    try:
        return _judge(root)
    except _UnreadableError as problem:
        print(f"cannot read the tree: {problem}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_dockerfile_digest.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
