"""The API surface of a Python file — signatures only, no bodies.

**Why it exists**: the question a reader (or an agent) asks most often about a
file is *"what does this give me"*, which is answered by the signatures and the
first line of each docstring. The only way to ask it was to open the whole file.
A 300-line service module is less than a tenth surface; the rest is how it works,
which nobody wants while they are still finding out *what to call*.

The idea comes from `graft`, which separates the structural layer — deterministic
and model-free — from the explanatory layer, which needs a model. **Only the
first layer is taken here**, because it is answerable entirely with stdlib `ast`:
no dependency, no cache to keep warm, nothing to go stale. It reads the real file
every time it is asked.

    python skeleton.py app/models.py            # one file
    python skeleton.py app/services             # a directory, sorted
    python skeleton.py app/models.py --private  # include leading-underscore names

Role: reader — it reports; it decides nothing and changes nothing.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import sys
from dataclasses import dataclass

__all__ = ["Symbol", "main", "render", "surface", "symbols"]

INDENT = "    "


@dataclass(frozen=True)
class Symbol:
    """One symbol on the surface — how deep, what it says, what it is for."""

    depth: int
    signature: str
    summary: str


def _is_private(name: str) -> bool:
    """A single leading underscore means "not surface"; `__init__` and friends count."""
    return name.startswith("_") and not name.startswith("__")


Documented = ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef


def _first_line(node: Documented) -> str:
    """The docstring's first line — the rest is detail the asker does not want yet."""
    text = ast.get_docstring(node)
    if not text or not text.strip():
        return ""
    return text.strip().splitlines()[0].strip()


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """`def name(args) -> return`, rebuilt from the AST rather than from the text.

    Reading the text breaks on signatures that wrap across lines, which any
    formatter produces as soon as one runs past the line limit.
    """
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"{prefix} {node.name}({ast.unparse(node.args)}){returns}"


def _decorators(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> list[str]:
    """A decorator always means something to the caller, so it is part of the surface."""
    return [f"@{ast.unparse(item)}" for item in node.decorator_list]


def symbols(source: str, *, private: bool = False) -> list[Symbol]:
    """The surface of one module — top level, and methods one level under a class."""
    return surface(ast.parse(source), private=private)


def surface(tree: ast.Module, *, private: bool = False) -> list[Symbol]:
    """As `symbols()`, but taking a tree that is already parsed.

    Separate because `render()` needs both the surface and the module docstring,
    which come from the same tree. The first version called `ast.parse` twice per
    file — invisible when reading one file, and a doubling of the tool's entire
    work when scanning a directory, which is what it is mostly used for.

    Nothing deeper than one level: a function nested in a function is how
    something works, not something an outside caller can reach.
    """
    found: list[Symbol] = []

    def take(node: ast.AST, depth: int) -> None:
        """Keep one symbol if it belongs on the surface."""
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            return
        if not private and _is_private(node.name):
            return
        found.extend(Symbol(depth, line, "") for line in _decorators(node))
        if isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(base) for base in node.bases)
            found.append(
                Symbol(
                    depth,
                    f"class {node.name}({bases})" if bases else f"class {node.name}",
                    _first_line(node),
                )
            )
            for child in node.body:
                take(child, depth + 1)
            return
        found.append(Symbol(depth, _signature(node), _first_line(node)))

    for node in tree.body:
        take(node, 0)
    return found


def render(path: pathlib.Path, source: str, *, private: bool = False) -> str:
    """One file's surface, ending with a line saying how much was saved.

    That last number is not decoration — it is the reason the tool exists, and the
    only thing that says which files are worth asking about this way and which are
    faster to read whole.

    **A figure over 100% is not a bug, and the ceiling must not be clamped.** The
    report has a fixed floor of two lines (the file header and this summary), so a
    file shorter than that genuinely cannot be summarised — and saying so *is* the
    answer this tool exists to give. Clamping to 100% would hide it and make
    "100%" mean two different things.
    """
    tree = ast.parse(source)
    found = surface(tree, private=private)
    header = _first_line(tree)
    lines = [f"{path} — {header}" if header else str(path)]
    for item in found:
        lines.append(f"{INDENT * (item.depth + 1)}{item.signature}")
        if item.summary:
            lines.append(f"{INDENT * (item.depth + 2)}— {item.summary}")
    if not found:
        lines.append(f"{INDENT}(no symbols on the surface)")
    # `count("\n") + 1` is always one line too many for a file ending in a
    # newline, which is very nearly every Python file. Fixed at the denominator.
    whole = len(source.splitlines())
    shown = len(lines) + 1  # +1 is this summary line — the figure must match what prints
    share = shown * 100 // whole if whole else 0
    verdict = " — faster to read whole" if shown >= whole else ""
    lines.append(f"{INDENT}— {len(found)} symbols · {shown} of {whole} lines ({share}%){verdict}")
    return "\n".join(lines)


def _targets(raw: str) -> list[pathlib.Path]:
    """One file or a whole directory — always sorted, so the output repeats."""
    path = pathlib.Path(raw)
    if path.is_dir():
        return sorted(item for item in path.rglob("*.py") if "__pycache__" not in item.parts)
    return [path]


def main(argv: list[str] | None = None) -> int:
    """Read, then print. Returns 1 only when a file genuinely could not be read."""
    parser = argparse.ArgumentParser(description="The API surface of a Python file.")
    parser.add_argument("path", help="a .py file or a directory")
    parser.add_argument("--private", action="store_true", help="include leading-underscore names")
    args = parser.parse_args(argv)

    targets = _targets(args.path)
    if not targets:
        print(f"no .py files under {args.path}", file=sys.stderr)
        return 1

    blocks = []
    for path in targets:
        try:
            source = path.read_text(encoding="utf-8")
        # `UnicodeDecodeError` inherits from `ValueError`, **not `OSError`** — a
        # file the system can read but that is not UTF-8 would otherwise escape
        # this handler and print a traceback without saying which file it was.
        except (OSError, UnicodeDecodeError) as problem:
            print(f"cannot read {path}: {problem}", file=sys.stderr)
            return 1
        try:
            blocks.append(render(path, source, private=args.private))
        except SyntaxError as problem:
            print(f"{path} — cannot parse: {problem}", file=sys.stderr)
            return 1
    print("\n\n".join(blocks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
