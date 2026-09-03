"""gate: no-debug-entrypoint — an entrypoint cannot open a debug console, even run wrongly.

A dev server's debug console executes code from the browser, and entrypoint files
are exactly the ones that get copied into an image. This reads the **AST, not a
regex**, because these files like to explain in a comment or docstring why they do
*not* set `debug=True` — the same characters, the opposite meaning. Dogfooding
against the reference implementation caught that false positive on day one.

`debug=True` is one spelling of five. Flask's `run()` does `self.debug = bool(debug)`
and hands werkzeug `use_debugger=self.debug`, so `debug=1`, `app.debug = True` before
the run, `app.config["DEBUG"] = True`, `run(use_debugger=True)` and `run(**{"debug":
True})` all open the same console — and all five passed a scanner that read only the
literal keyword (self-audit, 2026-08-31, each proved live against Flask 3.1.3). Every
spelling with a real constant behind it is judged; a value computed at runtime is not,
because a scanner that guesses at `os.environ` is a scanner that lies.

exit 0 = clean or N/A · 1 = findings · 2 = called wrongly

Role: decider — it answers pass or fail with an exit code, and it ships as a
standalone file; its evidence is a planted violation and a clean tree in
`tests/test_checks_behaviour.py`.
"""

from __future__ import annotations

import ast
import json
import os
import pathlib
import sys

# Characters a finding line may not carry, and what is printed instead. The C0 controls
# and DEL break the line grammar or the terminal; the C1 range does the same through a
# terminal that reads 8-bit escapes; the bidi and zero-width formats reorder or hide what
# a reader is looking at. Anything else — every language's letters — is left alone.
_ESCAPED = {
    **{c: f"\\x{c:02x}" for c in (*range(0x20), 0x7F)},
    **{
        c: f"\\u{c:04x}"
        for c in (
            *range(0x80, 0xA0),
            *range(0x200B, 0x2010),
            *range(0x202A, 0x202F),
            *range(0x2066, 0x206A),
            0xFEFF,
        )
    },
}


def _shown(text: str | pathlib.Path) -> str:
    """Text that can always be printed, and is always **one line**.

    Two properties, and the second was learnt after the first. A file name here is bytes,
    not characters: one that is not UTF-8 arrives from the directory listing carrying
    surrogates, and printing it raised `UnicodeEncodeError` — a traceback and exit 1, the
    code that means *findings*, from a scanner that had a verdict to give (self-audit
    round 15, 2026-09-01). That is the `backslashreplace` below.

    The name then stood for "safe to print", which it was not. A file name on Linux may
    carry a newline, and this scanner's caller reads one line as one finding: a file named
    `wipe\ndelete-means-soft-delete: forged\nx.py` turned one finding into two in the
    report, one SARIF result into three, and put a line no scanner wrote into an agent's
    context. An ANSI escape in a name (`\x1b[2K\x1b[A`) erased the finding printed above
    it (self-audit round 21, 2026-09-03). So a control character, a C1 byte, a bidi
    override and a zero-width format are shown escaped as well, and what is printed is one
    line whatever it was made of.

    This function is **copied into all nine scanners and the doctor on purpose** — each is
    shipped alone into a project that has installed nothing — and the copies are held
    byte-identical by `tests/test_checks_are_standalone.py`.
    """
    return os.fsencode(str(text)).decode("utf-8", "backslashreplace").translate(_ESCAPED)


DEBUG_KEYWORDS = ("debug", "use_debugger")


def _truthy_constant(node: ast.AST) -> bool:
    """A literal the interpreter would call true — `True`, `1`, `"yes"`; nothing computed."""
    return isinstance(node, ast.Constant) and bool(node.value) and node.value is not Ellipsis


def _run_call_debug(node: ast.Call) -> tuple[int, str] | None:
    """`<x>.run(debug=1)`, `.run(use_debugger=True)` or `.run(**{"debug": True})`."""
    if not (isinstance(node.func, ast.Attribute) and node.func.attr == "run"):
        return None
    for keyword in node.keywords:
        if keyword.arg in DEBUG_KEYWORDS and _truthy_constant(keyword.value):
            return node.lineno, f".run({keyword.arg}={ast.unparse(keyword.value)})"
        if keyword.arg is None and isinstance(keyword.value, ast.Dict):
            for key, value in zip(keyword.value.keys, keyword.value.values, strict=True):
                if (
                    isinstance(key, ast.Constant)
                    and key.value in DEBUG_KEYWORDS
                    and _truthy_constant(value)
                ):
                    return node.lineno, f".run(**{{{key.value!r}: {ast.unparse(value)}}})"
    return None


def _assignment_debug(node: ast.Assign) -> tuple[int, str] | None:
    """`<x>.debug = True` or `<x>.config["DEBUG"] = True` — the switch flipped before the run."""
    if not _truthy_constant(node.value):
        return None
    for target in node.targets:
        if isinstance(target, ast.Attribute) and target.attr == "debug":
            return node.lineno, f".debug = {ast.unparse(node.value)}"
        if (
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Attribute)
            and target.value.attr == "config"
            and isinstance(target.slice, ast.Constant)
            and target.slice.value == "DEBUG"
        ):
            return node.lineno, f'.config["DEBUG"] = {ast.unparse(node.value)}'
    return None


def _shape(node: ast.AST) -> tuple[int, str] | None:
    if isinstance(node, ast.Call):
        return _run_call_debug(node)
    if isinstance(node, ast.Assign):
        return _assignment_debug(node)
    return None


def _debug_findings(tree: ast.AST) -> list[tuple[int, str]]:
    """Every line that opens the debugger with a real constant — and how it spells it."""
    return sorted(found for node in ast.walk(tree) if (found := _shape(node)))


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


# **A ceiling on what one file may be.** Nothing here declared one, and the memory this
# scanner uses is a multiple of the largest file it is handed: measured on one 16 MB Python
# file, `ast.parse` took 7.4s and **1,457 MB** — ×90 — with `ast.walk` over its three
# million nodes on top (self-audit round 19, 2026-09-02). A standard runner has 7 GB, so one
# generated file of about 100 MB ends the job by being killed, which CI reports as *the gate
# failed* — blaming the project for a file the tool could not hold. A file above the ceiling
# is named and gets no verdict, on the route this scanner already has for a file it cannot
# parse; it is read up to the ceiling and no further.
MAX_FILE_CHARS = 8 * 1024 * 1024


def _source(path: pathlib.Path) -> str:
    """The file's text, or `ValueError` when it is larger than this scanner reads whole."""
    with path.open(encoding="utf-8") as handle:
        text = handle.read(MAX_FILE_CHARS + 1)
    if len(text) > MAX_FILE_CHARS:
        message = f"larger than the {MAX_FILE_CHARS // 1024 // 1024} MiB this scanner reads whole"
        raise ValueError(message)
    return text


def _config_text(path: pathlib.Path) -> str:
    """`scaffold.json`'s text, or the third answer. Every scanner routes the files it
    judges around undecodable bytes; the configuration beside them was still read bare
    and died of a traceback (self-audit round 3, 2026-09-01)."""
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as problem:
        print(f"cannot read the tree: {_shown(path)}: {problem}", file=sys.stderr)
        raise SystemExit(2) from problem


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
        config = json.loads(_config_text(path))
    except json.JSONDecodeError as problem:
        print(
            f"cannot read the tree: {_shown(path)}: not JSON — "
            f"{problem.msg}, line {problem.lineno}",
            file=sys.stderr,
        )
        raise SystemExit(2) from problem
    if not isinstance(config, dict):
        print(
            f"cannot read the tree: {_shown(path)}: not an object — a configuration "
            f"names keys, and this one holds {json.dumps(config)[:40]}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return config


def _entrypoints(root: pathlib.Path) -> tuple[list[pathlib.Path] | None, int]:
    """Which files to read, or why there are none to read — with the exit code for that."""
    config_path = root / "scaffold.json"
    # A project that has not configured the bundle is not a misuse — the paths
    # below fall back to their defaults, and a default that is not there reports
    # NA. A path the project *named* and does not have is the opposite case: a
    # broken configuration, reported as a finding — an outside audit on
    # 2026-08-29 planted a `scaffold.json` pointing at a Dockerfile that did not
    # exist beside a dirty one that did, and the answer was "nothing to check".
    config = _config(config_path)
    names, wrong = _configured_list(
        config, "entrypoints", ["run.py", "wsgi.py", "app.py", "main.py"]
    )
    if names is None:
        print(f"no-debug-entrypoint: {wrong}")
        return None, 1
    outside = [n for n in names if not _inside(root, root / n)]
    if outside:
        print("no-debug-entrypoint: " + OUTSIDE.format(key="entrypoints", path=outside))
        return None, 1
    present = [root / n for n in names if (root / n).is_file()]
    if not present:
        # The list is candidates, so one missing name is fine; none present when
        # the project wrote the list itself is a broken configuration.
        if "entrypoints" in config:
            print("no-debug-entrypoint: " + MISCONFIGURED.format(key="entrypoints", path=names))
            return None, 1
        print("NA: none of the declared entrypoints exist — nothing to check yet")
        return None, 0
    return present, 0


def main(root: pathlib.Path) -> int:
    if not root.is_dir():
        # NA means "this project has nothing of that kind"; a root that is not
        # there has no project to say it about, and answering the second with
        # the first is a green over nothing (self-audit round 2, 2026-08-31).
        print(f"cannot read the tree: {_shown(root)} is not a directory", file=sys.stderr)
        return 2
    present, code = _entrypoints(root)
    if present is None:
        return code

    findings: list[str] = []
    for path in present:
        try:
            tree = ast.parse(_source(path), filename=str(path))
        except (SyntaxError, ValueError, OSError) as error:
            # A file Python cannot parse is not a verdict either way — said plainly,
            # exit 2, the way every other unreadable input is refused (self-audit,
            # 2026-08-31: a traceback and exit 1, which reads as "findings").
            # `OSError` joined them in round 19 (2026-09-02): the two AST readers are the
            # only scanners that call `read_text` without the `_text` guard round 5 gave
            # the others, and a symlink pointing nowhere — which the walk lists, because
            # the name is there — was a raw `FileNotFoundError` and exit 1 out of a
            # scanner that had judged nothing.
            print(
                f"no-debug-entrypoint: cannot read {path.relative_to(root)} — {error}",
                file=sys.stderr,
            )
            return 2
        findings += [
            f"{path.relative_to(root)}:{line} {shape}" for line, shape in _debug_findings(tree)
        ]
    for finding in findings:
        print(f"no-debug-entrypoint: {_shown(finding)}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: scan_entrypoint_debug.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
