"""What this repository says about itself, held to what it measures — inside and out.

The gate `an-advertised-number-is-made-true-by-one-command` shipped with a
module and a test that proved the module on temporary files, and this repository
kept advertising its own numbers by hand: the version in four files, the release
date in three, the rule count in two languages, the checker count as a word in
three places, and a description on the hosting platform that no test had ever
read. That is the rule `contributor-docs-truthful` taught to others and not kept
here — found on 2026-08-29, before the second release, which is the moment it
would have gone wrong exactly the way the rule's own incident describes.

**The facts are measured, never typed.** The version is what the package
reports; the date is the newest released heading in the changelog; the counts
are the files and rows on disk. Every place that quotes one is a `Place` here,
and `tests/test_own_numbers.py` holds every place to its fact on every run.

**The field outside the repository is read live**, by CI, through the same
`gh` wrapper — because a field that produces no diff is one nobody sees age.
`--about` reads it; `--about --write` patches the claims in place and leaves
the prose alone. (The platform caps the field at 350 characters — a patch only
ever changes digits, so a field that fits keeps fitting.)

    python -m verifiable_gates.own_numbers            # report drift inside the tree
    python -m verifiable_gates.own_numbers --write    # fix it, touching nothing else
    python -m verifiable_gates.own_numbers --about    # and read the platform's About

Role: generator — it writes files that are committed. Its evidence is that what
it produces matches what is committed.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

import yaml

from verifiable_gates import __version__, advertised, gh, rules

__all__ = ["ABOUT", "PLACES", "as_word", "expectations", "facts", "main"]

# A number that appears in prose appears as a word; the counts here are small.
WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
# The Thai half of README writes the same small counts out in words too — zero to
# ten, as escapes, because this file is held to the language policy like every other.
WORDS_TH = (
    "\u0e28\u0e39\u0e19\u0e22\u0e4c",  # 0
    "\u0e2b\u0e19\u0e36\u0e48\u0e07",  # 1
    "\u0e2a\u0e2d\u0e07",  # 2
    "\u0e2a\u0e32\u0e21",  # 3
    "\u0e2a\u0e35\u0e48",  # 4
    "\u0e2b\u0e49\u0e32",  # 5
    "\u0e2b\u0e01",  # 6
    "\u0e40\u0e08\u0e47\u0e14",  # 7
    "\u0e41\u0e1b\u0e14",  # 8
    "\u0e40\u0e01\u0e49\u0e32",  # 9
    "\u0e2a\u0e34\u0e1a",  # 10
)
# The Thai words around a count of checkers in README — "purely" before, the
# classifier after — as escapes for the same reason.
PURELY_TH = "\u0e25\u0e49\u0e27\u0e19"
CLASSIFIER_TH = "\u0e15\u0e31\u0e27"

# The DECISIONS row that states the rules/bundle split, up to its decision column.
SPLIT_ROW = r"\| rules-vs-bundle \| [^|]+ \| "
DECIDES = r"\d+ rules are published; the bundle decides "

RELEASED = re.compile(r"^## \[(\d[^\]]*)\] - (\d{4}-\d{2}-\d{2})", re.MULTILINE)

PLACES: dict[str, list[advertised.Place]] = {
    "version": [
        advertised.Place("pyproject.toml", r'(?m)^version = "([^"]+)"'),
        advertised.Place("CITATION.cff", r"(?m)^version: (\S+)"),
        advertised.Place(".zenodo.json", r'"version": "([^"]+)"'),
        advertised.Place("CHANGELOG.md", r"(?m)^## \[(\d[^\]]*)\] - \d{4}-\d{2}-\d{2}"),
        # The compare link at the foot: `[Unreleased]` is measured against the
        # newest release, or it shows two releases' worth of changes as pending
        # (it pointed at v0.1.3 through v0.1.5 — found 2026-08-30).
        advertised.Place(
            "CHANGELOG.md", r"(?m)^\[Unreleased\]: \S+/compare/v([\w.+-]+?)\.\.\.HEAD$"
        ),
    ],
    "released": [
        advertised.Place("CITATION.cff", r"(?m)^date-released: '([^']+)'"),
        advertised.Place(".zenodo.json", r'"publication_date": "([^"]+)"'),
    ],
    "rules": [
        advertised.Place("README.md", r"— (\d+) rules, each carrying"),
        advertised.Place("DECISIONS.md", SPLIT_ROW + r"(\d+) rules are published"),
        advertised.Place("README.md", r"Of the (\d+) rules"),
        # The Thai half is matched by its shape — bold phrase, number, phrase —
        # because this file is held to the language policy like every other.
        advertised.Place("README.md", r"\*\*\S+ (\d+) \S+\*\* \(`rules\.yaml`\)"),
        advertised.Place("README.md", r"\*\*\S+ \d+ \S+ (\d+)\*\* —"),
    ],
    "checkers": [
        advertised.Place("README.md", r"\*\*\S+ (\d+) \S+ \d+\*\* —"),
    ],
    # The decision row that states the split quotes three counts by hand; the
    # third is the difference, measured as its own fact so the row cannot say
    # 92, 9 and 84 at once (re-audit round 13, 2026-08-30).
    "rules_scripted": [
        advertised.Place("DECISIONS.md", SPLIT_ROW + DECIDES + r"(\d+)"),
    ],
    "rules_sheet_only": [
        advertised.Place(
            "DECISIONS.md",
            SPLIT_ROW + DECIDES + r"\d+ of them\. The other (\d+)",
        ),
        # README says the split too, in both halves — three places `--write` never
        # reached, so a rule added left "The other 83" behind (self-audit, 2026-08-31).
        advertised.Place("README.md", r"The other (\d+) are the rule sheets"),
        # The Thai half by its shape — a word, the count, a word, then `agent`.
        advertised.Place("README.md", r"\S+ (\d+) \S+ agent "),
    ],
    "checkers_word": [
        advertised.Place("README.md", r"the (\w+) stdlib-only checkers"),
        advertised.Place("README.md", r"Of the \d+ rules, \*\*(\w+)\*\* have"),
        advertised.Place("README.md", r"\| The (\w+) checks · the doctor"),
        advertised.Place("CITATION.cff", r"ships (\w+) standalone checkers"),
        advertised.Place(".zenodo.json", r"ships (\w+) standalone checkers"),
    ],
    "checkers_word_th": [
        advertised.Place("README.md", r"stdlib " + PURELY_TH + r"(\S+?)" + CLASSIFIER_TH + r" "),
    ],
}

# The claims the About field on the hosting platform makes. Patterns, not the
# whole sentence: the field is patched in place so a person's prose survives.
ABOUT = {
    "rules": r"(\d+) production-discipline rules",
    "version": r"latest v(\d[\w.+-]*)",
}


def as_word(number: int, words: tuple[str, ...] = WORDS) -> str:
    """`9` → `nine`, for the counts small enough to be written out in prose."""
    return words[number] if number < len(words) else str(number)


def facts(root: pathlib.Path) -> dict[str, str]:
    """Every advertised fact, measured from the tree — strings, as `advertised` wants them."""
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    newest = RELEASED.search(changelog)
    if newest is None:
        raise RuntimeError("CHANGELOG.md has no released heading `## [x.y.z] - YYYY-MM-DD`")
    catalogue = rules.load(root / "rules.yaml")
    gates = yaml.safe_load((root / "gates.yaml").read_text(encoding="utf-8"))["gates"]
    checkers = sorted((root / "src" / "verifiable_gates" / "checks").glob("scan_*.py"))
    scripted = sum(1 for rule in catalogue if rule.get("script"))
    return {
        "rules_scripted": str(scripted),
        "rules_sheet_only": str(len(catalogue) - scripted),
        "version": __version__,
        "released": newest.group(2),
        "rules": str(len(catalogue)),
        "gates": str(len(gates)),
        "checkers": str(len(checkers)),
        "checkers_word": as_word(len(checkers)),
        "checkers_word_th": as_word(len(checkers), WORDS_TH),
    }


def expectations(values: dict[str, str]) -> list[advertised.Expectation]:
    return [advertised.Expectation(fact, pattern, values[fact]) for fact, pattern in ABOUT.items()]


def _report(found: list[advertised.Drift]) -> None:
    for item in found:
        said = "nothing matched" if item.is_missing else f"says {item.said!r}"
        print(f"  {item.place.path}: {said}, should say {item.want!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hold what this repository advertises to reality.")
    parser.add_argument("--root", default=".", help="the checkout (default: here)")
    parser.add_argument("--write", action="store_true", help="fix drift instead of reporting it")
    parser.add_argument("--about", action="store_true", help="also read the platform's About field")
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root)
    values = facts(root)

    status = 0
    inside = advertised.drift(root, PLACES, values)
    if inside:
        print("inside the repository:")
        _report(inside)
        if args.write:
            advertised.write(root, inside)
            print(f"  fixed {len(inside)} place(s) — review the diff, then commit it")
        else:
            status = 1
    else:
        print(f"every place inside the repository agrees ({sum(map(len, PLACES.values()))} places)")

    if args.about:
        try:
            field = str(gh.api("repos/:owner/:repo").get("description") or "")
        except (PermissionError, RuntimeError) as problem:
            # Could not look is its own answer; a traceback out of a CI step
            # reads as the step's bug (review, 2026-08-30).
            print(f"could not read the About field: {problem}", file=sys.stderr)
            return 2
        outside = advertised.field_drift(field, expectations(values))
        if outside:
            print("the About field on the platform:")
            for label, said, want in outside:
                print(f"  {label}: says {said!r}, should say {want!r}")
            if args.write:
                patched = advertised.field_patched(field, expectations(values))
                gh.run(["api", "-X", "PATCH", "repos/:owner/:repo", "-f", f"description={patched}"])
                print("  patched in place — the prose around the numbers is untouched")
            else:
                status = 1
        else:
            print("the About field agrees")
    return status


if __name__ == "__main__":
    sys.exit(main())
