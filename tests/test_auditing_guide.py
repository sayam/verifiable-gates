"""The audit guide names every rule this repository states about itself, and its commands run.

`docs/auditing.md` is written for a stranger with an hour: eleven rules, the command that
decides each one, and what is not checkable from outside. That makes it a **register** —
the same eleven bullets as `CONTRIBUTING.md` § "The rules this repository holds itself to",
in a second file — and a register nothing holds is the failure this repository exists to
catch. So the two are held to each other in both directions, and every command the guide
prints is checked to name something that is there.

Why both directions: a rule added to `CONTRIBUTING.md` and not to the guide leaves an
outside auditor checking ten of eleven while believing they checked all of them; a heading
in the guide with no rule behind it invents a criterion nobody agreed to.

What this file cannot check is whether the commands *pass* — that is what running them is
for, and `.local/work/2026-09-05-auditing-guide/` holds the transcript of the guide being
run from a fresh clone, which is the record the local rule asks for.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
GUIDE = ROOT / "docs" / "auditing.md"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"

# The lead phrase of each bullet in CONTRIBUTING's list, which the guide repeats as a
# heading. Bold, because that is how the list writes the rule and the rest is its reason.
BULLET = re.compile(r"^- \*\*(.+?)\*\*", re.MULTILINE | re.DOTALL)
HEADING = re.compile(r"^### \d+\. (.+?)$", re.MULTILINE)
MODULE = re.compile(r"python -m (verifiable_gates\.[a-z_]+)")
# Anywhere in the page, not only inside backticks: half the paths the guide names are
# arguments in a command block (`pytest -q tests/test_own_ratchets.py`), and a check that
# read only the backticked ones passed a misspelt one straight through — measured
# 2026-09-05, when the mutation that renamed it came back green.
PATH_LIKE = re.compile(
    r"(?<![\w/.-])([a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)+\.(?:py|md|yaml|yml|json|cff|toml))"
)


# `[`DECISIONS.md`](DECISIONS.md)` in one file and `` `DECISIONS.md` `` in the other are
# the same words to a reader; the link is markup, and comparing markup would make the two
# files drift on a link nobody reads differently.
LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", LINK.sub(r"\1", text)).strip().rstrip(".")


def rules_in_contributing() -> list[str]:
    section = (
        CONTRIBUTING.read_text(encoding="utf-8")
        .split("## The rules this repository holds itself to", 1)[1]
        .split("\n## ", 1)[0]
    )
    return [flat(bullet) for bullet in BULLET.findall(section)]


def test_the_guide_names_every_rule_this_repository_states_about_itself_and_no_other() -> None:
    """Both directions, in one comparison, in order.

    A rule added to `CONTRIBUTING.md` and not here leaves an outside auditor checking ten
    of eleven while believing they checked all of them. A heading here with no rule behind
    it invents a criterion nobody agreed to. Order too: the guide is walked top to bottom
    in an hour, and a reader who loses their place in it loses the mapping.
    """
    stated = rules_in_contributing()
    walked = [flat(heading) for heading in HEADING.findall(GUIDE.read_text(encoding="utf-8"))]

    assert stated, "CONTRIBUTING.md's list of rules did not parse — the section moved"
    assert walked == stated, (
        f"the guide walks {walked}\nCONTRIBUTING states {stated}\n"
        "— a rule and its check are one register in two files; change both together"
    )


def test_every_command_the_guide_prints_names_something_that_is_here() -> None:
    """A guide is instructions, and an instruction that names a module or a file which is
    not there fails on the reader's machine, which is where nobody here is watching. The
    modules are resolved as files rather than imported: this test decides a document."""
    text = GUIDE.read_text(encoding="utf-8")
    package = ROOT / "src" / "verifiable_gates"

    modules = sorted(set(MODULE.findall(text)))
    assert modules, "the guide gives no command at all — if that is deliberate, delete this test"
    missing = [name for name in modules if not (package / f"{name.split('.')[-1]}.py").is_file()]
    assert not missing, f"the guide runs {missing}, which this package does not ship"

    named = sorted(set(PATH_LIKE.findall(text)))
    assert len(named) > 5, f"the guide names almost no file ({named}) — this check reads nothing"
    # Resolved from the guide's own directory first — it sits in `docs/`, so a link back
    # up (`../CONTRIBUTING.md`) is right where a reader clicks it and wrong from the root.
    absent = [
        path for path in named if not ((GUIDE.parent / path).exists() or (ROOT / path).exists())
    ]
    assert not absent, f"the guide names {absent}, which is not in the tree"
