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
import os
import pathlib
import re
import sys


def _shown(path: str | pathlib.Path) -> str:
    """A path as text that can always be printed.

    A file name here is bytes, not characters. One that is not UTF-8 arrives from the
    directory listing carrying surrogates, and printing it raises `UnicodeEncodeError`:
    a traceback and exit 1 — the code that means *findings* — from a scanner that had a
    verdict to give, losing every finding it had already collected (self-audit round 15,
    2026-09-01). A name nobody can decode is still a name; it is shown with its bytes
    escaped, and the verdict stands.
    """
    return os.fsencode(str(path)).decode("utf-8", "backslashreplace")


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
    """Bytes nobody can decode, or a tree nobody can walk. No verdict — never a clean one."""


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
        message = f"{_shown(path)}: {problem}"
        raise _UnreadableError(message) from problem


def _walk(top: pathlib.Path) -> list[pathlib.Path]:
    """Every file under `top`, sorted — or `_UnreadableError` naming what stopped the walk.

    `rglob` **throws away the `OSError`s it meets on the way**: a directory this scanner
    may not open, and any path past the system's length limit, are simply absent from the
    result, with nothing raised and nothing printed — and the silence lands on the *pass*
    side. Measured on one tree, changing nothing but a permission bit: readable, the
    scanner printed the violation inside it and exited 1; with `chmod 000` on that one
    directory it printed **nothing** and exited 0. A tree whose only source file sat 5,147
    characters deep answered `NA: nothing to check yet` while `find` saw the file
    (self-audit round 19, 2026-09-02). Both are the sentence the manifest forbids — "A rule
    the tool cannot check must not look like a rule it checked" — so a walk that could not
    see the whole tree has no verdict to give.

    This scanner is the one that walks a whole project, so it **prunes** dotted directories
    instead of filtering them out afterwards. `.git` and `.venv` hold copies of other
    people's Dockerfiles, and a directory nobody judges must not be able to refuse the
    verdict. The filter this replaces read the **absolute** path, so a project checked out
    under any dotted directory — `~/.local/src/app`, and every runner whose workspace has
    one — had every unnamed Dockerfile filtered away and was told `NA: no Dockerfile`
    (self-audit round 19, 2026-09-02).
    """
    trouble: list[OSError] = []
    found: list[pathlib.Path] = []
    for parent, directories, names in os.walk(top, onerror=trouble.append):
        directories[:] = [name for name in directories if not name.startswith(".")]
        found += [pathlib.Path(parent) / name for name in names]
    # A `top` that is not there is nothing to walk, which the caller reports as N/A — the
    # answer it gave before. "Not there" and "there and closed to me" are different things.
    blocked = [problem for problem in trouble if not isinstance(problem, FileNotFoundError)]
    if blocked:
        raise _UnreadableError(
            "; ".join(f"{_shown(bad.filename)}: {bad.strerror}" for bad in blocked)
        )
    return sorted(found)


def _config(path: pathlib.Path) -> dict[str, object]:
    """The project's `scaffold.json`, or the third answer saying why it is not one.

    Round 3 wrapped the *read* of this file and stopped one line short of the parse, so a
    configuration that is malformed, empty, or saved with a byte-order mark — and one that
    parses to a list, a string or `null` rather than an object — was still a raw traceback
    and exit 1, the code that means *findings*, out of a scanner that had judged nothing
    (self-audit round 17, 2026-09-01). A file nobody can read as a configuration is the
    same answer as one nobody can decode: no verdict, said plainly.
    """
    if not path.is_file():
        return {}
    try:
        config = json.loads(_text(path))
    except json.JSONDecodeError as problem:
        raise _UnreadableError(
            f"{_shown(path)}: not JSON — {problem.msg}, line {problem.lineno}"
        ) from problem
    if not isinstance(config, dict):
        raise _UnreadableError(
            f"{_shown(path)}: not an object — a configuration names keys, "
            f"and this one holds {json.dumps(config)[:40]}"
        )
    return config


def _nothing_moves_the_pins(root: pathlib.Path) -> bool:
    config = root / ".github" / "dependabot.yml"
    return not (config.is_file() and DOCKER_ECOSYSTEM.search(_text(config)))


UNNAMED = (
    "{path} is a Dockerfile scaffold.json does not name — name it under `dockerfiles`, "
    "or it is never judged"
)
OUTSIDE = (
    "scaffold.json names {key} {path}, which leads outside the project — a checker "
    "pointed out of the tree judges files this project does not own"
)


def _inside(root: pathlib.Path, path: pathlib.Path) -> bool:
    """Is `path` still inside the tree this scanner was pointed at?

    The installer was taught this in an earlier round — fourteen files landed outside the
    destination through a `tools` symlink — and the readers were never asked the same
    question. A `scaffold.json` path starting with `/` or climbing with `..` walked out of
    the project, judged files it does not own, and printed them under a path no reviewer
    can open; an absolute one also made `relative_to` raise, so the misconfiguration
    answered with a traceback (self-audit round 13, 2026-09-01).
    """
    return path.resolve().is_relative_to(root.resolve())


MISCONFIGURED = (
    "scaffold.json names {key} {path}, which is not there — a configured path that "
    "is missing is a broken configuration, not nothing to check"
)


MISSHAPEN = (
    "scaffold.json gives {key} {value}, which is not {want} — a configured value of the "
    "wrong shape is a broken configuration, not a value"
)


def _configured_list(
    config: dict[str, object], key: str, default: list[str]
) -> tuple[list[str] | None, str]:
    """The names configured under `key`, or `None` and the finding saying they are not names.

    A list written as a single string was iterated **one character at a time**, so the
    project's configuration was read as a set of one-letter names: nonsense findings at
    best, and where the list is a set of exemptions, the `*` among those letters matched
    every path there is and the gate answered `pass` over a tree with a real violation in
    it (self-audit round 17, 2026-09-01).
    """
    value = config.get(key, default)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value, ""
    return None, MISSHAPEN.format(key=key, value=json.dumps(value)[:40], want="a list of strings")


def _unnamed(root: pathlib.Path) -> list[str]:
    """Every `Dockerfile*` in the tree, when the project named none and has no default one.

    Hidden directories (`.git`, `.venv`) hold copies of other things.
    """
    return [
        UNNAMED.format(path=_shown(found.relative_to(root)))
        for found in _walk(root)
        if found.is_file() and found.name.startswith("Dockerfile")
    ]


def _unpinned(root: pathlib.Path, path: pathlib.Path) -> list[str]:
    """Every image one Dockerfile pulls in without a digest."""
    text = _text(path)
    stages = {stage.lower() for stage in STAGE.findall(text)}
    refs = [("FROM", ref) for ref in FROM_LINE.findall(text)]
    refs += [("COPY --from", ref) for ref in COPY_FROM.findall(text)]
    return [
        f"{_shown(path.relative_to(root))}: {how} {ref}"
        for how, ref in refs
        # A stage name is a local alias, not an image — and names are also
        # case-insensitive. A bare stage *index* (`--from=0`) is one too.
        if ref.lower() not in {*stages, SCRATCH} and not ref.isdigit() and not DIGEST.search(ref)
    ]


def _declared(root: pathlib.Path) -> tuple[list[str] | None, bool, int]:
    """The names to judge, whether the project chose them, and the code when there are none.

    A project that has not configured the bundle is not a misuse — the names below fall
    back to their default, and a default that is not there reports NA. A name the project
    *wrote* and does not have is the opposite case: a broken configuration, reported as a
    finding — an outside audit on 2026-08-29 planted a `scaffold.json` pointing at a
    Dockerfile that did not exist beside a dirty one that did, and the answer was
    "nothing to check".
    """
    config_path = root / "scaffold.json"
    config = _config(config_path)
    names, wrong = _configured_list(config, "dockerfiles", ["Dockerfile"])
    if names is None:
        print(f"image-digest-pinned: {wrong}")
        return None, False, 1
    outside = [n for n in names if not _inside(root, root / n)]
    if outside:
        print("image-digest-pinned: " + OUTSIDE.format(key="dockerfiles", path=outside))
        return None, False, 1
    return names, "dockerfiles" in config, 0


def _judge(root: pathlib.Path) -> int:
    if not root.is_dir():
        # NA means "this project has nothing of that kind"; a root that is not
        # there has no project to say it about, and answering the second with
        # the first is a green over nothing (self-audit round 2, 2026-08-31).
        print(f"cannot read the tree: {_shown(root)} is not a directory", file=sys.stderr)
        return 2
    names, chosen, code = _declared(root)
    if names is None:
        return code
    dockerfiles = [root / n for n in names if (root / n).is_file()]
    # A name the project wrote down and does not have is judged, not skipped.
    findings: list[str] = [
        MISCONFIGURED.format(key="dockerfiles", path=n)
        for n in names
        if chosen and not (root / n).is_file()
    ]
    if not dockerfiles and not chosen:
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
