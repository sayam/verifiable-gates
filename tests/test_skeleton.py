"""The surface reader answers "what does this file give me" without the bodies.

Its whole value is the ratio at the end — the figure that says which files are
worth asking about this way and which are faster to read whole. So the tests
care as much about that line being *interpretable* as about the symbols being
right: a number nobody can read the meaning of is not an answer.

Three of the checks below exist because a review caught the tool being subtly
wrong in ways nothing else would have shown: a doubled parse invisible on one
file, a denominator off by one on every file ending in a newline, and a
`UnicodeDecodeError` escaping an `except OSError` because it inherits from
`ValueError` instead.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest  # noqa: TC002 — fixtures come from it at run time

from verifiable_gates import skeleton

if TYPE_CHECKING:
    import pathlib

SAMPLE = '''\
"""A module that gives a few things."""


CONSTANT = 1


def public(a: int, b: str = "x") -> bool:
    """Say whether it holds."""
    return True


async def fetched(url: str) -> bytes:
    """Fetch it."""
    return b""


def _private() -> None:
    """Not on the surface."""


class Thing(Base):
    """A thing."""

    @property
    def name(self) -> str:
        """Its name."""
        return ""

    def _helper(self) -> None:
        """Not on the surface either."""

    def method(self, x: int) -> None:
        """Do it."""
        def nested() -> None:
            """One level too deep."""
'''


# ---------------------------------------------------------------- the surface


def test_public_functions_are_on_the_surface() -> None:
    found = [item.signature for item in skeleton.symbols(SAMPLE)]

    assert "def public(a: int, b: str='x') -> bool" in found
    assert "async def fetched(url: str) -> bytes" in found


def test_private_names_are_left_off_by_default() -> None:
    found = [item.signature for item in skeleton.symbols(SAMPLE)]

    assert not any("_private" in line for line in found)
    assert not any("_helper" in line for line in found)


def test_private_names_can_be_asked_for() -> None:
    found = [item.signature for item in skeleton.symbols(SAMPLE, private=True)]

    assert any("_private" in line for line in found)
    assert any("_helper" in line for line in found)


def test_a_class_brings_its_bases_and_its_methods() -> None:
    found = [item.signature for item in skeleton.symbols(SAMPLE)]

    assert "class Thing(Base)" in found
    assert "def method(self, x: int) -> None" in found


def test_decorators_are_surface_because_they_bind_the_caller() -> None:
    """`@property` changes how a caller reaches it; leaving it off would mislead."""
    found = [item.signature for item in skeleton.symbols(SAMPLE)]

    assert "@property" in found
    assert found.index("@property") < found.index("def name(self) -> str")


def test_nothing_deeper_than_one_level_is_taken() -> None:
    """A function inside a function is how it works, not something a caller reaches."""
    found = [item.signature for item in skeleton.symbols(SAMPLE)]

    assert not any("nested" in line for line in found)


def test_the_summary_is_the_first_docstring_line_only() -> None:
    source = 'def f() -> None:\n    """First line.\n\n    Second paragraph.\n    """\n'
    found = skeleton.symbols(source)

    assert found[0].summary == "First line."


def test_a_symbol_without_a_docstring_gets_an_empty_summary() -> None:
    assert skeleton.symbols("def f() -> None:\n    return None\n")[0].summary == ""


def test_a_wrapped_signature_is_rebuilt_not_read_as_text() -> None:
    """Formatters wrap long signatures; reading the source text would break on them."""
    source = "def f(\n    a: int,\n    b: str,\n) -> bool:\n    return True\n"

    assert skeleton.symbols(source)[0].signature == "def f(a: int, b: str) -> bool"


def test_the_surface_can_be_taken_from_an_already_parsed_tree() -> None:
    """`render()` needs the surface and the module docstring from one parse.

    The first version parsed twice per file, which is invisible on one file and
    doubles the tool's entire work when scanning a directory — which is what it
    is mostly used for.
    """
    tree = ast.parse(SAMPLE)

    assert skeleton.surface(tree) == skeleton.symbols(SAMPLE)


# ---------------------------------------------------------------- the report


def test_the_report_names_the_file_and_its_purpose(tmp_path: pathlib.Path) -> None:
    text = skeleton.render(tmp_path / "m.py", SAMPLE)

    assert text.splitlines()[0].endswith("— A module that gives a few things.")


def test_a_file_with_no_module_docstring_still_names_itself(tmp_path: pathlib.Path) -> None:
    text = skeleton.render(tmp_path / "m.py", "def f() -> None:\n    return None\n")

    assert text.splitlines()[0] == str(tmp_path / "m.py")


def test_a_file_with_no_surface_says_so(tmp_path: pathlib.Path) -> None:
    """Silence would read as "the tool failed", which is a different fact."""
    text = skeleton.render(tmp_path / "m.py", "CONSTANT = 1\n")

    assert "no symbols on the surface" in text


def test_the_last_line_counts_what_was_actually_printed(tmp_path: pathlib.Path) -> None:
    """The saving is the point of the tool, so the figure has to match the output."""
    text = skeleton.render(tmp_path / "m.py", SAMPLE)
    last = text.splitlines()[-1]

    assert f"{len(text.splitlines())} of" in last, "the figure disagrees with the report"
    assert f"of {len(SAMPLE.splitlines())} lines" in last, "the denominator is off by one"


def test_a_file_too_short_to_summarise_says_read_it_whole(tmp_path: pathlib.Path) -> None:
    """Over 100% is the answer, not an error — the report has a two-line floor.

    Clamping it would hide the one case the tool exists to identify, and make
    "100%" mean two different things at once.
    """
    text = skeleton.render(tmp_path / "m.py", "def f():\n    pass\n")

    assert "faster to read whole" in text


def test_a_file_worth_summarising_does_not_say_that(tmp_path: pathlib.Path) -> None:
    """The other direction — the verdict must distinguish, not always appear."""
    long_file = SAMPLE + "\n".join(f"# filler {n}" for n in range(200))

    assert "faster to read whole" not in skeleton.render(tmp_path / "m.py", long_file)


# ---------------------------------------------------------------- the command line


def test_one_file_is_read(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "m.py"
    path.write_text(SAMPLE, encoding="utf-8")

    assert skeleton.main([str(path)]) == 0
    assert "def public" in capsys.readouterr().out


def test_a_directory_is_read_in_a_repeatable_order(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Unsorted output makes two runs of the same tool look like a change."""
    for name in ("b.py", "a.py", "c.py"):
        (tmp_path / name).write_text("def f() -> None:\n    return None\n", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "junk.py").write_text("def x(): pass\n", encoding="utf-8")

    assert skeleton.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert out.index("a.py") < out.index("b.py") < out.index("c.py")
    assert "junk.py" not in out, "cache directories are not source"


def test_a_directory_with_no_python_says_so(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert skeleton.main([str(tmp_path)]) == 1
    assert "no .py files" in capsys.readouterr().err


def test_a_file_that_is_not_utf8_names_itself(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`UnicodeDecodeError` inherits from `ValueError`, not `OSError`.

    Handling only `OSError` lets it escape and print a traceback that never says
    which file was at fault — the one thing the person running it needs.
    """
    path = tmp_path / "m.py"
    path.write_bytes(b"\xff\xfe def f(): pass\n")

    assert skeleton.main([str(path)]) == 1
    assert "m.py" in capsys.readouterr().err


def test_a_file_that_does_not_parse_names_itself(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "m.py"
    path.write_text("def f(\n", encoding="utf-8")

    assert skeleton.main([str(path)]) == 1
    assert "cannot parse" in capsys.readouterr().err


def test_a_missing_file_is_reported_not_raised(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert skeleton.main([str(tmp_path / "gone.py")]) == 1
    assert "cannot read" in capsys.readouterr().err


def test_private_reaches_the_report_from_the_command_line(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "m.py"
    path.write_text(SAMPLE, encoding="utf-8")

    assert skeleton.main([str(path), "--private"]) == 0
    assert "_private" in capsys.readouterr().out
