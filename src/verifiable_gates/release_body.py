"""The release notes, read back: what each release says, against the section it was cut from.

A release body is the one part of a cut that lives entirely on the platform. Nothing in
the tree holds it, and on 2026-09-05 that cost this project a release: **v0.3.1 shipped
with the body `v0.3.1`** — one word — because the runbook that session handed over said
`gh release create --notes-from-tag` and the tag message was the one word the same runbook
had asked for. Every earlier cut had carried the CHANGELOG's `## [x.y.z]` section: the
summary paragraph and the entries, which is what Zenodo archives and what a reader on the
releases page is given. The rule that came out of it — *the body is the CHANGELOG section,
handed over as a file, never typed* — was kept by hand for two cuts (v0.4.0 and v0.5.0,
each verified byte for byte) before this reader replaced the hand.

**Line endings are half the check.** GitHub stores a body with CRLF, so a body uploaded
from a file comes back with a `\\r` on every line: a naive comparison reports every line
different on two texts that are identical on screen (measured 2026-09-05 —
`gh release view v0.4.0 --json body | grep -c $'\\r'` answered 144; v0.5.0 answered 268).
A check that cannot tell "wrong" from "wrong line endings" reports neither.

Three answers: 0 every release says what its section says · 1 one does not, and the
difference is named · 2 the platform could not be asked.

Role: decider — it answers pass or fail with an exit code, and a job blocks on it
(`posture.yml`'s cron). What it decides on is the releases read live and the CHANGELOG in
the tree; the tests feed it the releases as a file.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Any

from verifiable_gates import gh

__all__ = [
    "BODY_PREDATES_THE_RULE",
    "body_of",
    "main",
    "problems",
    "sections",
]

# `## [0.4.0] - 2026-09-05` — the heading `own_numbers` already holds the version to.
HEADING = re.compile(r"^## \[(\d[^\]]*)\] - \d{4}-\d{2}-\d{2}", re.MULTILINE)
# A link definition at the foot of the file: `[0.5.0]: https://…`, and `[Unreleased]: …`
# with it. It belongs to the file, not to any release — and the `[Unreleased]` line is
# **rewritten at every cut**, so a section that keeps it puts the oldest release's body out
# of step the moment the next version is cut. Measured 2026-09-06, an hour after this reader
# said 18 of 18 held: the v0.6.0 cut moved that one line and v0.1.0 — the last section in the
# file, the only one the block follows — went red with two texts of 19 711 characters each.
LINKS = re.compile(r"^\[[^\]]+\]:\s*\S+\s*$", re.MULTILINE)
# A release this reader judges. `evidence-freeze-1` is a tag, not a version, and it is a
# different commit from `v0.1.0` on purpose (`DECISIONS.md` `freeze-tag-vs-release`);
# there is no section for it to equal.
VERSION_TAG = re.compile(r"^v(\d+\.\d+\.\d+.*)$")

# Releases whose body predates the rule and is allowed to differ. **Shrink only, and empty
# since 2026-09-06**: v0.1.0, v0.1.6 and v0.1.7 carried hand-written announcements from
# before the convention, and on that day they were each given their section with
# `gh release edit vX.Y.Z --notes-file …` — which starts no workflow and mints nothing at
# Zenodo (measured 2026-09-05, and again on the three edits themselves). It is kept rather
# than deleted because the mechanism is what makes emptying it visible: an entry here is
# held both ways below, so a name cannot be parked to hide a body that drifted afterwards.
BODY_PREDATES_THE_RULE: dict[str, str] = {}


def sections(text: str) -> dict[str, str]:
    """Every released section of a CHANGELOG, by version, as the release body should read.

    The heading itself is not part of the body — the release page carries the version in
    its title — and neither is the link block at the foot, which belongs to the file.
    """
    heads = list(HEADING.finditer(text))
    found: dict[str, str] = {}
    for index, head in enumerate(heads):
        end = heads[index + 1].start() if index + 1 < len(heads) else len(text)
        found[head.group(1)] = without_the_link_block(text[head.end() : end])
    return found


def without_the_link_block(text: str) -> str:
    """`text` with the trailing run of link definitions, and the blank lines above it, gone.

    Applied to **both** sides of every comparison: to the section, because those lines are
    the file's plumbing and no reader wants them in release notes; and to the published
    body, because three bodies were written from an extraction that kept them, and the block
    changes at every cut. Stripping it on one side only would make every one of those a
    finding forever, about a line nobody reads.
    """
    lines = text.split("\n")
    while lines and (not lines[-1].strip() or LINKS.match(lines[-1])):
        lines.pop()
    return "\n".join(lines).strip("\n")


def body_of(release: dict[str, Any]) -> str:
    """A release's body as text to compare: CRLF folded, blank ends trimmed.

    Folding `\\r\\n` is not tidying. It is the difference between a check that answers
    "these two texts differ" and one that answers "these two texts differ in a way a
    reader can see".
    """
    folded = str(release.get("body") or "").replace("\r\n", "\n").replace("\r", "\n")
    return without_the_link_block(folded)


def problems(written: dict[str, str], releases: list[dict[str, Any]]) -> list[str]:
    """Every release whose body is not the section it was cut from, said in one line each."""
    found: list[str] = []
    seen: set[str] = set()
    for release in releases:
        tag = str(release.get("tag_name", ""))
        version = VERSION_TAG.match(tag)
        if version is None:
            continue
        seen.add(tag)
        section = written.get(version.group(1))
        if section is None:
            found.append(
                f"{tag} is a release with no `## [{version.group(1)}]` section in"
                " CHANGELOG.md — a release nobody can read the notes of twice"
            )
            continue
        if body_of(release) == section:
            if tag in BODY_PREDATES_THE_RULE:
                found.append(
                    f"{tag} now says what its section says — take it out of"
                    " BODY_PREDATES_THE_RULE, the register only shrinks"
                )
            continue
        if tag in BODY_PREDATES_THE_RULE:
            continue
        found.append(
            f"{tag}: the release body is not the CHANGELOG section ({len(body_of(release))}"
            f" characters against {len(section)}) — publish it with"
            f" `gh release edit {tag} --notes-file <the section>`, never --notes-from-tag"
        )
    found += [
        f"{tag} is in BODY_PREDATES_THE_RULE and is not a release here — the register names"
        " something that is not there"
        for tag in sorted(set(BODY_PREDATES_THE_RULE) - seen)
    ]
    return found


def _releases(path: str | None) -> list[dict[str, Any]]:
    if path is not None:
        loaded = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        return [row for row in loaded if isinstance(row, dict)]
    return [row for row in gh.api_pages("repos/:owner/:repo/releases") if isinstance(row, dict)]


def main(argv: list[str] | None = None) -> int:
    """Read the releases and the CHANGELOG, hold them to each other, return the code."""
    parser = argparse.ArgumentParser(
        description="The release notes, read back against the CHANGELOG sections."
    )
    parser.add_argument("--root", default=".", help="the checkout (default: here)")
    parser.add_argument("--releases", help="a JSON file of releases (offline)")
    args = parser.parse_args(argv)
    try:
        text = (pathlib.Path(args.root) / "CHANGELOG.md").read_text(encoding="utf-8")
        releases = _releases(args.releases)
    except (OSError, RuntimeError, ValueError) as problem:
        print(f"cannot read the releases or the CHANGELOG: {problem}", file=sys.stderr)
        return 2
    written = sections(text)
    if not written:
        print("CHANGELOG.md has no released section — nothing was compared", file=sys.stderr)
        return 2
    found = problems(written, releases)
    for line in found:
        print(line, file=sys.stderr)
    if found:
        return 1
    judged = sum(1 for r in releases if VERSION_TAG.match(str(r.get("tag_name", ""))))
    excused = len(BODY_PREDATES_THE_RULE)
    said = f"every release says what its section says: {judged - excused} of {judged} held"
    print(said + (f", {excused} whose body predates the rule" if excused else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
