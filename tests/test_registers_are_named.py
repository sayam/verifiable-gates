"""The list of registers is a register: what a two-way copy is, and where it is named.

`CONTRIBUTING.md` § "The rules this repository holds itself to" says a register is held
by a copy in a test, two-way, and then **enumerates them** — and `docs/auditing.md` § 8
turns that enumeration into a command an outside auditor runs. An auditor who runs it
believes they checked every register in the tree.

Two registers were added on 2026-09-06 (the anti-moves and the quoted transcripts) and
neither reached either page; a third, the Marketplace categories, had been missing since
it arrived. The enumeration was prose, and prose is what goes stale while every test
around it stays green — which is the failure this repository exists to name, committed
here, about the sentence that describes the mechanism.

So the enumeration is held: every register below has to exist where it says, be named in
`CONTRIBUTING.md`, and be run by the guide's command. What this cannot do is notice a
register that nobody declared — except by the naming convention below, which catches the
common shape (`HELD`, `HELD_STEP_GATES`): a module-level constant in `tests/` whose name
starts with `HELD` has to be in this list. A register named some other way is caught by
the reviewer, or by the next person who reads this docstring.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
GUIDE = ROOT / "docs" / "auditing.md"
BULLET = "- **A register is held by a copy in a test, two-way.**"
GUIDE_HEADING = "### 8. A register is held by a copy in a test, two-way."

# (the test file that holds the copy, the constant that is the copy, what it is a copy of)
REGISTERS: tuple[tuple[str, str, str], ...] = (
    (
        "tests/test_posture.py",
        "HELD",
        "the branch-protection switches in pins/dev/posture-declared.json",
    ),
    ("tests/test_decisions.py", "HELD", "the row ids of DECISIONS.md, in order"),
    (
        "tests/test_instruments_dogfood.py",
        "HELD_STEP_GATES",
        "the gates each named CI step enforces",
    ),
    (
        "tests/test_instruments_dogfood.py",
        "SUPPRESSED_LINES",
        "the number of suppression lines under src/ and tests/",
    ),
    ("tests/test_manifest.py", "", "the shipped overlay's scan gates, held to rules.yaml"),
    ("tests/test_marketplace.py", "HELD", "the categories the Marketplace listing declares"),
    ("tests/test_anti_moves.py", "HELD", "the five anti-moves and the holders each names"),
    (
        "tests/test_quoted_transcripts.py",
        "QUOTED_PER_DOCUMENT",
        "how many catalogue sentences each document quotes",
    ),
)


def bullet() -> str:
    text = CONTRIBUTING.read_text(encoding="utf-8")
    assert BULLET in text, "the register bullet moved — the enumeration below is held to it"
    return text.split(BULLET, 1)[1].split("\n- **", 1)[0]


def guide_section() -> str:
    text = GUIDE.read_text(encoding="utf-8")
    assert GUIDE_HEADING in text, "the guide's section 8 moved"
    return text.split(GUIDE_HEADING, 1)[1].split("\n### ", 1)[0]


@pytest.mark.parametrize(
    ("where", "constant"),
    [(where, constant) for where, constant, _ in REGISTERS],
    ids=[f"{where.split('/')[-1]}:{constant or 'file'}" for where, constant, _ in REGISTERS],
)
def test_every_register_is_where_this_list_says(where: str, constant: str) -> None:
    """A copy that has been renamed leaves the page pointing at a name nobody holds."""
    path = ROOT / where
    assert path.is_file(), f"{where} is not in the tree"
    if not constant:
        return
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    } | {
        node.target.id
        for node in tree.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert constant in names, f"{where} has no module-level {constant}"


def test_the_contributing_bullet_names_every_register() -> None:
    """The enumeration a reader takes as the list of registers is the list of registers."""
    said = bullet()
    missing = [
        f"{where} ({constant})"
        for where, constant, _ in REGISTERS
        if where.split("/")[-1] not in said
    ]

    assert not missing, f"CONTRIBUTING's register bullet does not name {missing}"


def test_the_guide_runs_every_register_it_can() -> None:
    """Section 8 is a command an auditor runs believing it covers every register."""
    said = guide_section()
    missing = [where for where, _, _ in REGISTERS if where not in said]

    assert not missing, f"the audit guide's section 8 does not run {missing}"


def test_a_held_constant_in_a_test_is_declared_here() -> None:
    """The convention half: a copy called `HELD…` that nobody declared is a register
    nothing points at. It is not every shape a register can take, and the docstring says
    so — it is the shape four of the eight already use."""
    declared = {(where, constant) for where, constant, _ in REGISTERS}
    found = set()
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            targets = (
                [t for t in node.targets if isinstance(t, ast.Name)]
                if isinstance(node, ast.Assign)
                else [node.target]
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                else []
            )
            for target in targets:
                if re.fullmatch(r"HELD(_[A-Z_]+)?", target.id):
                    found.add((str(path.relative_to(ROOT)), target.id))

    assert found <= declared, f"undeclared registers: {sorted(found - declared)}"
