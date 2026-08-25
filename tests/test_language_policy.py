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

Why that exception exists at all: a licence or an agreement has to be understood
by the person bound by it, and the maintainer's first language is Thai. English
first, Thai below — both halves saying the same thing.

There is a **second** kind of exception, and it is a different shape. The catalogue
keeps each rule's original wording alongside the published English, because a
translation of an incident report is a retelling and the retelling is not the
record. That Thai is *data*, not prose, so it is not excused by file: it is
excused only where it belongs — in the value of a `*_th` field, or inside a string
literal in the code that renders and tests those fields. Thai in a comment, a key,
or an identifier stays forbidden everywhere, in every file, which is the leak this
whole check exists to catch.
"""

from __future__ import annotations

import pathlib
import subprocess
import tokenize

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Files kept bilingual on purpose: anything that binds someone legally.
# Adding to this list is a decision, not a convenience — see CONTRIBUTING.md.
BILINGUAL = ("README.md", "CLA.md")

# The catalogue keeps every rule's original wording. Thai is allowed in it only as
# the value of a `*_th` field — never in a comment, a key, or any other field.
CATALOGUE = "rules.yaml"

# Generated from the catalogue. Any Thai in them comes from a cited step name,
# and `test_the_only_thai_in_a_sheet_is_a_cited_step_name` holds that boundary.
SHEETS = ("SKILL.md", "SKILL-BUSINESS.md")

# The one other place Thai belongs: the name of a CI step in the reference
# implementation. `reference` is a citation, and a citation keeps the name the
# thing actually has — translating it would point the evidence at a step that
# does not exist. Filenames are cited the same way; they simply happen to be
# ASCII.
CITED_NAMES = ("reference.step",)

# Code that renders or tests the catalogue's second language. Thai is allowed in
# these only inside a string literal, so a Thai comment or identifier still fails.
THAI_IN_LITERALS = (
    "src/verifiable_gates/skill.py",
    "tests/test_skill_renderer.py",
    "tests/test_rules_catalogue.py",
    # A subject line in Thai is the test data that proves the length limit counts
    # characters rather than bytes. In Latin script the test cannot fail, so the
    # non-Latin string is the evidence, not decoration.
    "tests/test_lint_commits.py",
)

THAI = range(0x0E01, 0x0E5C)  # Thai block, U+0E01..U+0E5B

# Token types whose text may hold Thai. FSTRING_MIDDLE exists from Python 3.12,
# where an f-string is tokenised in pieces rather than as one STRING.
STRING_TOKENS = frozenset(
    {tokenize.STRING} | {getattr(tokenize, "FSTRING_MIDDLE", tokenize.STRING)}
)


def has_thai(text: str) -> bool:
    return any(ord(char) in THAI for char in text)


def tracked_files() -> list[pathlib.Path]:
    """What git tracks — not what happens to be on disk.

    Walking the filesystem was the first version, and it failed on
    `verifiable_gates.egg-info/PKG-INFO`: a build artefact that embeds the
    bilingual README, is ignored by git, and exists only on machines where the
    package was installed in editable mode. A check that fails on files the
    repository does not contain fails for whoever happens to have built locally.

    Reading only *tracked* files was the second version, and it let a **new** file
    pass locally and fail in CI — which is what happened while this stage was being
    written. Untracked-but-not-ignored is the set a developer is one `git add` away
    from committing, so that is the set worth judging.
    """
    listed = subprocess.run(
        # `--cached --others --exclude-standard`: tracked, plus new files that are
        # not ignored. Ignored files stay out, which is what fixed the first version.
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],  # noqa: S607 — git is required here
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
        if relative in BILINGUAL or relative == CATALOGUE or relative in THAI_IN_LITERALS:
            continue
        if relative in SHEETS:  # bounded by its own check below, not exempt
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if has_thai(text):
            offenders.append(relative)
    assert not offenders, (
        "Thai outside the places that allow it — translate it. If it belongs to a "
        "document that binds someone legally, add it to BILINGUAL; if it is a rule's "
        f"preserved wording, it belongs in a `*_th` field of the catalogue: {offenders}"
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


# ---------------------------------------------------------- Thai kept as data


def _thai_outside_th_fields(node: object, path: str = "") -> list[str]:
    """Walk the parsed catalogue and report Thai anywhere but a `*_th` value."""
    if isinstance(node, dict):
        found = []
        for key, value in node.items():
            here = f"{path}.{key}" if path else str(key)
            if isinstance(key, str) and has_thai(key):
                found.append(f"{here} (in a key)")
            if isinstance(key, str) and key.endswith("_th"):
                continue
            if here.split("].", 1)[-1] in CITED_NAMES:
                continue
            found += _thai_outside_th_fields(value, here)
        return found
    if isinstance(node, list):
        return [
            problem
            for index, item in enumerate(node)
            for problem in _thai_outside_th_fields(item, f"{path}[{index}]")
        ]
    if isinstance(node, str) and has_thai(node):
        return [path]
    return []


def test_the_catalogue_keeps_thai_only_in_its_th_fields() -> None:
    """Thai is preserved wording, so it lives in the field named for it — nowhere else."""
    data = yaml.safe_load((ROOT / CATALOGUE).read_text(encoding="utf-8"))
    offenders = _thai_outside_th_fields(data)
    assert not offenders, (
        "Thai in the catalogue outside a `*_th` field. The published text is "
        f"English; the original belongs beside it, not instead of it: {offenders}"
    )


def test_the_catalogue_carries_no_thai_in_its_comments() -> None:
    """A comment is prose, and prose here is English — the parser cannot see these."""
    offenders = [
        line.strip()[:60]
        for line in (ROOT / CATALOGUE).read_text(encoding="utf-8").splitlines()
        if line.lstrip().startswith("#") and has_thai(line)
    ]
    assert not offenders, f"Thai in a catalogue comment: {offenders}"


def test_the_catalogue_still_carries_the_original_wording() -> None:
    """The other direction — if the Thai is gone, the record became a retelling."""
    assert has_thai((ROOT / CATALOGUE).read_text(encoding="utf-8")), (
        f"{CATALOGUE} has no Thai left. Either the original wording was dropped — "
        "which loses the record — or this exception no longer excuses anything."
    )


def test_the_only_thai_in_a_sheet_is_a_cited_step_name() -> None:
    """The sheets are English. The one exception is bounded here rather than assumed.

    A cited step name reaches the rendered sheet, because the sheet prints the
    citation. That is correct — but it is also the single way Thai can arrive in
    a published English document, so the boundary is checked rather than trusted:
    Thai on a rule line or a lesson line means a translation was missed.
    """
    offenders = []
    for sheet in ("SKILL.md", "SKILL-BUSINESS.md"):
        for number, line in enumerate((ROOT / sheet).read_text(encoding="utf-8").splitlines(), 1):
            if has_thai(line) and not line.startswith("**Enforced in the reference:**"):
                offenders.append(f"{sheet}:{number}: {line.strip()[:60]}")
    assert not offenders, (
        "Thai in a rendered sheet outside a cited step name — the rule and the "
        f"lesson are published in English: {offenders}"
    )


@pytest.mark.parametrize("name", THAI_IN_LITERALS)
def test_thai_in_code_stays_inside_string_literals(name: str) -> None:
    """A file on this list is not exempt; only its string literals are.

    Without this the list would be an exemption by filename, and the next Thai
    comment somebody pastes into one of these files would pass unnoticed — which
    is the failure the whole check exists to prevent.
    """
    path = ROOT / name
    with path.open(encoding="utf-8") as handle:
        offenders = [
            f"line {token.start[0]}: {token.string.strip()[:50]}"
            for token in tokenize.generate_tokens(handle.readline)
            if token.type not in STRING_TOKENS and has_thai(token.string)
        ]
    assert not offenders, f"Thai outside a string literal in {name}: {offenders}"


@pytest.mark.parametrize("name", THAI_IN_LITERALS)
def test_every_file_allowed_thai_literals_still_has_some(name: str) -> None:
    """The other direction, again — an exception that excuses nothing must go."""
    assert has_thai((ROOT / name).read_text(encoding="utf-8")), (
        f"{name} is listed as carrying Thai string literals but has none left. "
        "Drop it from THAI_IN_LITERALS — an exception that excuses nothing is a "
        "hole with a label on it."
    )
