"""gate: ci-tools-hash-pinned — tools CI installs for itself are pinned by hash.

`pip install <name>` takes whatever is newest at the second the job runs, and runs
it with the workflow's permissions. It has to carry `--require-hashes`, normally as
`--require-hashes -r <lockfile>`. The `-r` is not required *here*: pip refuses
`--require-hashes` with nothing to read hashes from, so a scanner repeating that
refusal would add a rule without adding a catch (DECISIONS `pip-uppercase-not-a-gap`,
which is also why the word `pip` is read in lower case only).
On the node side it has to be `npm ci`: `npm install pkg@x` pins that one package
and leaves the rest of the tree floating.
The installers with no `pip` in the line — `uv tool install`, `uv add`, `uvx`,
`poetry add`, `pdm add`, `pipenv install` — resolve against the index too, and
were unread until an outside audit on 2026-08-30 planted two of them.

Installing the checkout itself (`pip install --no-deps --no-build-isolation -e .`)
is not an index install: nothing is fetched, so there is nothing to pin. That
exemption needs all three halves, and there is a test for each of them — see
`_installs_from_an_index`.

A `run:` line that hands off to a shell script in the checkout — by its `.sh` name or by
the shebang on its first line — is followed into the script, because the install it
hides runs with the job's permissions all the same (outside audit, 2026-08-30: `pip
install ruff` in `scripts/setup.sh`, exit 0).

In a workflow or an action only what `run:` executes is judged — a `name:` or an
`env:` that quotes the command is prose the runner never executes (outside audit,
2026-08-30: a step *named* after `pip install ruff` was a finding, and an
environment value carrying `--require-hashes` pinned nothing and passed). And
`--require-hashes` counts only as an argument of the install itself.
Comments are stripped before checking — these files like to explain themselves by
quoting the very command they are telling you not to use. A comment at the end of
a line goes too: `pip install ruff  # TODO --require-hashes` was green because the
word it needs sat in the comment (outside audit, 2026-08-30).

A composite action under `.github/actions/<name>/action.yml` installs with the
calling workflow's permissions, so its `run:` steps are read too — an outside
audit on 2026-08-29 planted an unpinned install there and got a clean exit. So
is every local action a read file names with `uses: ./<path>`, wherever it lives
and however the value is folded.

exit 0 = clean or N/A · 1 = findings · 2 = called wrongly

Role: decider — it answers pass or fail with an exit code, and it ships as a
standalone file; its evidence is a planted violation and a clean tree in
`tests/test_checks_behaviour.py`.
"""

from __future__ import annotations

import pathlib
import re
import shlex
import sys

# `pip` takes global options *before* the subcommand — `pip --python <interpreter>
# install`, `pip -q install` — and this repository's own release job used the
# first shape on an unpinned wheel install for five releases while the scanner
# read only `pip install` side by side (re-audit, 2026-08-30).
# The option shape starts with a letter after the dashes so `--x` parses one way
# only — `-{1,2}[\w-]+` parsed it two ways and a line of twenty `--flags` with no
# `install` took a second, forty took minutes (review, 2026-08-30). `pip3.13`
# and `python3.13` are the interpreter spellings Actions runners ship.
PIP_INSTALL = re.compile(
    r"(?:^|[\s/])pip(?:3(?:\.\d+)?)?(?:\s+--?[A-Za-z][\w-]*(?:=\S+|\s+[^-\s]\S*)?)*\s+install(?=\s|$)"
)
# The Node side is wider than `npm install`: `npx <pkg>` and `npm exec <pkg>` fetch a
# package to run it, `yarn add` and `pnpm add` resolve one against the registry the
# way `npm install <pkg>` does — the title promises both sides and the scanner read
# one command (self-audit, 2026-08-31, each exited 0). `npm ci`, `yarn install
# --frozen-lockfile`/`--immutable` and `pnpm install --frozen-lockfile` install from a
# lock and are left alone.
NPM_INSTALL = re.compile(
    r"(?:^|[\s/])(?:npm\s+(?:install|i|add|exec)|npx|yarn\s+add|pnpm\s+(?:add|dlx))\b"
)
# `pipx install` / `pipx run` resolve the tool from the index like `pip install`.
PIPX_INSTALL = re.compile(r"(?:^|[\s/])pipx\s+(?:install|run)\b")
# So do the installers with no `pip` in the line: `uv tool install`, `uv add`,
# `uvx`, `poetry add`, `pdm add`, `pipenv install` each resolve a name against
# the index with nothing but a tag or a range to hold it — an outside audit on
# 2026-08-30 planted `uv tool install ruff` and `poetry add ruff` and got exit 0
# from a scanner that keyed on the word `pip`. `uv run --locked` and `uv sync
# --locked` install from `uv.lock`, which carries hashes, and are left alone.
# `uv tool run` is `uvx` spelled out, and `uv run --with <pkg>` resolves that package
# against the index before it runs — both unread (self-audit, 2026-08-31, proved
# against uv 0.12.7).
NO_PIP_INSTALL = re.compile(
    r"(?:^|[\s/])(?:uv\s+(?:tool\s+(?:install|run)|add|run\s+(?:\S+\s+)*?--with(?:=|\s))"
    r"|uvx|poetry\s+add|pdm\s+add|pipenv\s+install)\b"
)
# `python -m build` (and `pyproject-build`) creates an isolated environment and
# `pip install`s the build backend from the index, unpinned — a tool CI installs
# for itself, under the job's privileges, with no `pip` on the line at all.
# `--no-isolation` makes the backend come from whatever the job already pinned.
# `pip wheel` builds in an isolated environment exactly as `python -m build` does,
# fetching the backend from the index (self-audit, 2026-08-31: unread).
BUILD = re.compile(
    r"(?:^|[\s/])(?:python(?:3(?:\.\d+)?)?\s+-m\s+build|pyproject-build|pip(?:3(?:\.\d+)?)?\s+wheel)\b"
)
NO_ISOLATION = re.compile(r"(?:^|\s)(?:--no-isolation|--no-build-isolation|-n)(?:\s|$)")
# `pip install --no-deps -e .` installs the checkout itself and resolves nothing
# from an index, so there is no hash to pin and nothing an attacker could swap.
# **Both halves are required.** `--no-deps requests` still reaches the index, and
# `-e .` without `--no-deps` drags the whole dependency tree in unpinned — either
# one alone would turn this rule off for the case it exists to catch. And the
# local target has to be the *only* target: `--no-deps requests .` has both
# halves and still fetches `requests` from the index — an outside audit on
# 2026-08-29 planted exactly that line and the exemption covered it.
# A path is local by its `./`, `/` or `.` — or by being a wheel file wherever it
# sits: `dist/*.whl` without the `./` was "from an index" (self-audit, 2026-08-31).
LOCAL_TARGET = re.compile(r"^(?:\.|\./|/|.*\.whl$)")
# Options whose next token is a value, not a package — `-r`/`-c` are left out on
# purpose: a requirements file names packages, so it is an index install.
TAKES_A_VALUE = frozenset(
    {
        "-i",
        "--index-url",
        "--extra-index-url",
        "-f",
        "--find-links",
        "-t",
        "--target",
        "--prefix",
        "--root",
        "--src",
        "-C",
        "--config-settings",
        "--cache-dir",
        "--python",
    }
)
# One `run:` line can chain several commands — and a command can carry another
# inside `$( )`, backticks, a `( )` subshell or an `sh -c "…"` string; each of
# those executes for real, and a scanner that read only the outer command let
# `$(pip install ruff)` and `sh -c "pip install ruff"` through (outside audit,
# 2026-08-31). Each boundary starts a new command to judge.
# `-c` may be folded into other flags (`bash -lc`, `sh -ec`), a lone `&` ends a
# command as surely as `&&`, and `os.system('pip install ruff')` is a string handed
# to a shell from inside `python -c` — each was a hiding place (self-audit,
# 2026-08-31, all exited 0).
CHAIN = re.compile(
    r"\s*(?:&&|\|\||;|\||&)\s*|\$\(|`|(?<!\S)\("
    r"|(?:(?:ba|z|da|k)?sh|python(?:3(?:\.\d+)?)?)\s+-[A-Za-z]*c\s+[\"']|(?<=\w)\(\s*[\"']"
)
# `then pip install …` is `pip install …` to the shell: a keyword opens the command.
KEYWORD = re.compile(r"^\s*(?:then|do|else|elif|if|while|until|!|\{)\s+")
# A command that only *says* the words — `echo pip install ruff` — installs
# nothing: the shell runs `echo`. It was a finding (outside audit, 2026-08-31).
PROSE = frozenset({"echo", "printf"})
# …unless the words are handed to a shell: `echo "pip install ruff" | bash`,
# `bash <<< "pip install ruff"` and `eval "pip install ruff"` all run them, and
# all three were green (self-audit, 2026-08-31). The text is read as the command
# it becomes. `${PIP:-pip} install ruff` runs `pip` when `PIP` is unset — the
# default is read as the word.
SHELL = r"(?:ba|z|da|k)?sh"
PIPED_TO_SHELL = re.compile(
    rf"""(?:^|(?<=[;&|(]))\s*(?:echo|printf)\s+(?P<q>['"]?)(?P<text>.*?)(?P=q)\s*\|\s*{SHELL}\b[^|;&]*"""
)
HERE_STRING = re.compile(rf"""{SHELL}\s*<<<\s*(?P<q>['"])(?P<text>.*?)(?P=q)""")
EVAL = re.compile(r"""(?:^|(?<=[\s;&|(]))eval\s+(?P<q>['"])(?P<text>.*?)(?P=q)""")
DEFAULT_WORD = re.compile(r"\$\{\w+:?-([^}]*)\}")


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


def _as_the_shell_runs_it(line: str) -> str:
    """Text a shell will execute, written where the shell will read it."""
    line = DEFAULT_WORD.sub(r"\1", line)
    line = PIPED_TO_SHELL.sub(lambda m: m.group("text"), line)
    line = HERE_STRING.sub(lambda m: m.group("text"), line)
    return EVAL.sub(lambda m: m.group("text"), line)


# The bundle's own starting workflow, as `install.py` writes `ci-template.yml`:
# one pinned checkout and one run of the doctor. A tree where every workflow is
# that has nothing of the project's to judge yet, and the answer is NA — so
# "every scan NA" can mean what README says it means. An outside audit on
# 2026-08-30 installed into an empty directory and three scans said `pass` on
# the file the bundle had just written. Any line added or changed makes the
# workflow the project's, and it is judged like any other.
STEP = re.compile(r"^\s*-?\s*(uses|run):\s*(.+?)\s*$", re.MULTILINE)
TEMPLATE_STEPS = (("uses", re.compile(r"^actions/checkout@[0-9a-f]{40}$")), ("run", None))
DOCTOR_RUN = "python3 tools/gates_doctor.py"


def _bundles_own(text: str) -> bool:
    """Is this workflow the untouched starting one — a pinned checkout, then the doctor?"""
    steps = [(kind, value.split(" #")[0].strip()) for kind, value in STEP.findall(text)]
    if len(steps) != len(TEMPLATE_STEPS):
        return False
    (uses_kind, uses), (run_kind, run) = steps
    return (
        uses_kind == "uses"
        and TEMPLATE_STEPS[0][1] is not None
        and TEMPLATE_STEPS[0][1].match(uses) is not None
        and run_kind == "run"
        and run == DOCTOR_RUN
    )


# A local action is whatever `uses: ./<path>` names — GitHub reads
# `<path>/action.yml` wherever it lives, so reading `.github/actions/` alone left
# `uses: ./ci/actions/setup` unread: an outside audit on 2026-08-30 planted one
# there and both pinning scanners exited 0 while CHANGELOG said composite actions
# were read. Every file read is followed, so an action calling an action is read.
# YAML lets the value fold onto the next line — `uses: >` then `./ci/action` —
# and a regex that wanted `./` on the `uses:` line left that action unread
# (outside audit, 2026-08-30: an unpinned install behind it exited 0).
# The key may be quoted (`"uses":`), the value may be an alias (`uses: *co`) of an
# anchor set anywhere in the file, carry a tag (`!!str`) or an anchor of its own,
# and a `uses` under `with:` is an input, not a step — every one of these is
# YAML the platform reads, and every one was misread here (self-audit,
# 2026-08-31: an alias to an unpinned install exited 0; an alias to a pinned
# action was reported as `*co`).
USES = re.compile(r"""^(\s*)-?\s*\{?\s*["']?uses["']?\s*:\s*(.+?)\s*$""")
BLOCK = re.compile(r"^[|>][-+]?$")
ANCHOR = re.compile(r"""^\s*(?:-\s*)?(?:["']?[\w.-]+["']?\s*:\s*)?&([\w-]+)\s+(.+?)\s*$""")
ALIAS = re.compile(r"^\*([\w-]+)$")
TAG = re.compile(r"^!!?[\w:/.-]*\s+")
OWN_ANCHOR = re.compile(r"^&[\w-]+\s+")
WITH = re.compile(r"^(\s*)with\s*:\s*$")


def _anchors(text: str) -> dict[str, str]:
    """Every scalar anchor in the file — `&name value` — by name, quotes and tag stripped."""
    found: dict[str, str] = {}
    for line in text.splitlines():
        match = ANCHOR.match(_without_comment(line))
        if match and not BLOCK.match(match.group(2)):
            found[match.group(1)] = _unquoted(TAG.sub("", match.group(2)).strip())
    return found


def _resolved(value: str, anchors: dict[str, str]) -> str:
    """The value as the platform reads it: tag and own anchor dropped, an alias replaced."""
    value = OWN_ANCHOR.sub("", TAG.sub("", value.strip())).strip()
    alias = ALIAS.match(value)
    return anchors.get(alias.group(1), value) if alias else value


def _under_with(lines: list[str]) -> list[bool]:
    """For each line, whether it sits inside a `with:` block — an input, not a step."""
    inside: list[bool] = []
    with_indent = -1
    for line in lines:
        indent = len(line) - len(line.lstrip())
        if line.strip() and with_indent >= 0 and indent <= with_indent:
            with_indent = -1
        inside.append(with_indent >= 0 and indent > with_indent)
        match = WITH.match(line)
        if match:
            with_indent = len(match.group(1))
    return inside


def _local_uses(text: str) -> list[str]:
    """The paths of every local action the file names, folded, aliased or not."""
    lines = text.splitlines()
    anchors = _anchors(text)
    nested = _under_with(lines)
    found: list[str] = []
    for index, line in enumerate(lines):
        match = USES.match(line)
        if not match or nested[index]:
            continue
        ref = _without_comment(match.group(2)).strip()
        if BLOCK.match(ref):
            rest = [later.strip() for later in lines[index + 1 :] if later.strip()]
            ref = _without_comment(rest[0]).strip() if rest else ref
        ref = _resolved(ref, anchors).split()[0].strip("\"',}") if ref else ref
        if ref.startswith("./"):
            found.append(ref[2:])
    return found


def _followed(root: pathlib.Path, targets: list[pathlib.Path]) -> list[pathlib.Path]:
    """`targets` plus every local action a read file points at, wherever it lives."""
    seen = list(targets)
    queue = list(targets)
    while queue:
        for relative in _local_uses(_text(queue.pop())):
            for name in ("action.yml", "action.yaml"):
                candidate = root / relative / name
                if candidate.is_file() and candidate not in seen:
                    seen.append(candidate)
                    queue.append(candidate)
    return seen


def _targets(command: str) -> list[str]:
    """What one `pip install` would install: its non-option tokens."""
    # Slice after the matched subcommand, not the first substring `install` —
    # `--python /opt/installer/bin/python install` has one before it.
    matched = PIP_INSTALL.search(command)
    tokens = command[matched.end() if matched else 0 :].split()
    found: list[str] = []
    skip = False
    for token in tokens:
        if skip:
            skip = False
        elif token in TAKES_A_VALUE:
            skip = True
        elif not token.startswith("-"):
            found.append(token)
    return found


def _installs_from_an_index(command: str) -> bool:
    # Three halves now: `--no-deps` for the tree, every target local, and
    # `--no-build-isolation` — without it pip builds the checkout in a fresh
    # environment and fetches the build backend from the index, unhashed, which
    # is the same fetch `python -m build` makes (review of 2026-08-30; this
    # repository's own four `pip install --no-deps -e .` lines had it).
    targets = _targets(command)
    if not ("--no-deps" in command and targets and all(LOCAL_TARGET.match(t) for t in targets)):
        return True
    # A wheel is copied, never built — nothing is fetched for it (self-audit,
    # 2026-08-31: `pip install --no-deps ./dist/*.whl` was a finding).
    return not ("--no-build-isolation" in command or all(t.endswith(".whl") for t in targets))


def _without_comment(line: str) -> str:
    """The line up to its first `#` outside quotes — a `#` inside quotes is text, and so
    is one inside a word: `$#`, `${#PKGS}` and `\\#` are what the shell reads them as,
    not comments (self-audit, 2026-08-31: `if [ $# -gt 0 ]; then pip install …` was
    cut to `if [` and passed)."""
    quote = ""
    for index, char in enumerate(line):
        if quote:
            quote = "" if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char == "#" and (index == 0 or line[index - 1].isspace()):
            return line[:index]
    return line


# A `run:` line that hands off to a shell script in the checkout — `./scripts/
# setup.sh`, `bash scripts/setup.sh`, `sh …`, `source …`, `. …` — installs with
# the job's permissions from lines the workflow never shows. An outside audit on
# 2026-08-30 planted `pip install ruff` in a script the workflow called and got
# exit 0. Every script a read file names is read too, scripts calling scripts
# included; a path that climbs out of the checkout or is absolute is not ours.
# A script is one by its `.sh`/`.bash` name, or — `./scripts/setup`, `bash
# scripts/setup` — by a shell shebang on its first line: the name was the only
# test until an outside audit on 2026-08-30 planted an extensionless one.
# The path may be quoted, and it is relative to wherever the shell stands: a `cd dir`
# earlier on the line, or the step's `working-directory:` — `cd scripts && ./setup.sh`
# and the same script under `working-directory: scripts` were both unread
# (self-audit, 2026-08-31).
SCRIPT = re.compile(
    r"(?:^|[\s;&|(])(?:(?:bash|sh|source|\.)\s+[\"']?(?P<run>[\w./-]+)[\"']?"
    r"|[\"']?(?P<own>\./[\w./-]+)[\"']?|[\"']?(?P<named>[\w./-]+\.(?:sh|bash))[\"']?)(?=[\s;&|)]|$)"
)
CD = re.compile(r"^\s*cd\s+[\"']?(?P<dir>[\w./-]+)[\"']?\s*$")
SHEBANG = re.compile(r"^#!.*\b(?:ba|z|da|k)?sh\b")


def _is_shell_script(path: pathlib.Path) -> bool:
    if path.suffix in {".sh", ".bash"}:
        return True
    with path.open("rb") as handle:
        first = handle.readline(200).decode("utf-8", errors="replace")
    return SHEBANG.match(first) is not None


def _scripts_named(root: pathlib.Path, path: pathlib.Path) -> list[pathlib.Path]:
    """The shell scripts in the checkout that one read file hands off to, each resolved
    from where the shell stands when it names it."""
    named: list[pathlib.PurePosixPath] = []
    for line in _commands(path):
        cwd = pathlib.PurePosixPath()
        for part in CHAIN.split(line):
            if moved := CD.match(part):
                cwd = cwd / moved.group("dir")
                continue
            named += [
                cwd / (match.group("run") or match.group("own") or match.group("named"))
                for match in SCRIPT.finditer(part)
            ]
    return [
        root / name
        for name in named
        if not name.is_absolute()
        and ".." not in name.parts
        and (root / name).is_file()
        and _is_shell_script(root / name)
    ]


def _with_scripts(root: pathlib.Path, targets: list[pathlib.Path]) -> list[pathlib.Path]:
    """`targets` plus every shell script they hand off to, however deep."""
    seen = list(targets)
    queue = list(targets)
    while queue:
        for script in _scripts_named(root, queue.pop()):
            if script not in seen:
                seen.append(script)
                queue.append(script)
    return seen


# In a workflow or an action only what `run:` executes is judged — the value on
# the line, or the `|`/`>` block beneath it. Every other line is prose to the
# runner: a `name:` that says "explain why pip install ruff is forbidden" was a
# finding, and an `env:` value was a `--require-hashes` that pip never saw
# (outside audit, 2026-08-30). A script and a Dockerfile are read whole.
# YAML allows a space before the colon (`run :`) and a flow-style step
# (`- {run: pip install ruff}`) — PyYAML and the platform both read them, and
# both shapes were unread here (outside audit, 2026-08-31).
# The key may be quoted, the value may be an alias, a tagged scalar, or a scalar
# that continues onto further lines — plain, quoted or folded (`>`) — which YAML
# joins with spaces before the shell ever sees it, so `pip` on one line and
# `install ruff` on the next is one command. Only a literal block (`|`) keeps its
# newlines. Every one of these shapes was unread or misread here (self-audit,
# 2026-08-31: `run: *cmd`, `"run":` and a folded `pip`⏎`install ruff` all exited 0).
RUN = re.compile(r"""^(\s*-?\s*)["']?run["']?\s*:\s*(.*?)\s*$""")
WORKING_DIRECTORY = re.compile(r"""^(\s*-?\s*)["']?working-directory["']?\s*:\s*(.+?)\s*$""")
ENV_KEY = re.compile(r"""^(\s*-?\s*)["']?env["']?\s*:\s*$""")
ENV_REQUIRE_HASHES = re.compile(
    r"""^\s*["']?PIP_REQUIRE_HASHES["']?\s*:\s*["']?(?:1|true|yes|on)["']?\s*$""", re.IGNORECASE
)
FLOW_RUN = re.compile(r"""\{[^{}]*?\b["']?run["']?\s*:\s*([^,}]*)""")
YAML = {".yml", ".yaml"}


def _unquoted(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _folded(lines: list[str]) -> list[str]:
    """Lines joined the way YAML folds a scalar: with a space; a blank line is a newline."""
    joined: list[str] = []
    piece: list[str] = []
    for line in lines:
        if line.strip():
            # A trailing backslash continues the command in the shell's eyes too.
            piece.append(line.strip().removesuffix("\\").rstrip())
        elif piece:
            joined.append(" ".join(piece))
            piece = []
    if piece:
        joined.append(" ".join(piece))
    return joined


def _working_directory(lines: list[str], at: int, column: int) -> str:
    """The `working-directory:` of the step whose `run:` key sits at `column` on line
    `at` — a sibling key at the same column, inside the same list item."""
    marker = column - 2
    first = at
    while first > 0 and not (
        lines[first].lstrip().startswith("- ")
        and len(lines[first]) - len(lines[first].lstrip()) == marker
    ):
        first -= 1
    last = at + 1
    while last < len(lines) and (
        not lines[last].strip() or len(lines[last]) - len(lines[last].lstrip()) > marker
    ):
        last += 1
    for line in lines[first:last]:
        sibling = WORKING_DIRECTORY.match(line)
        if sibling and len(sibling.group(1)) == column:
            return _unquoted(sibling.group(2))
    return ""


def _step_item(lines: list[str], at: int, column: int) -> list[str]:
    """The lines of the list item whose key sits at `column` on line `at`."""
    marker = column - 2
    first = at
    while first > 0 and not (
        lines[first].lstrip().startswith("- ")
        and len(lines[first]) - len(lines[first].lstrip()) == marker
    ):
        first -= 1
    last = at + 1
    while last < len(lines) and (
        not lines[last].strip() or len(lines[last]) - len(lines[last].lstrip()) > marker
    ):
        last += 1
    return lines[first:last]


def _requires_hashes_by_env(lines: list[str], at: int, column: int) -> bool:
    """The step's own `env:` sets `PIP_REQUIRE_HASHES` on — pip reads it (self-audit,
    2026-08-31: a step with it was a finding)."""
    item = _step_item(lines, at, column)
    for index, line in enumerate(item):
        key = ENV_KEY.match(line)
        if not key or len(key.group(1)) != column:
            continue
        for later in item[index + 1 :]:
            if later.strip() and len(later) - len(later.lstrip()) <= column:
                break
            if ENV_REQUIRE_HASHES.match(later):
                return True
    return False


def _run_lines(text: str) -> list[str]:
    """The lines a workflow or action hands to the shell: each `run:` value or block,
    standing in the step's `working-directory:` when it names one."""
    lines = text.splitlines()
    anchors = _anchors(text)
    found: list[str] = []
    index = 0
    while index < len(lines):
        flow = FLOW_RUN.search(lines[index])
        match = None if flow else RUN.match(lines[index])
        index += 1
        if flow:
            found.append(_resolved(_unquoted(flow.group(1).strip()), anchors))
            continue
        if not match:
            continue
        indent, value = len(match.group(1)), match.group(2)
        stands_in = _working_directory(lines, index - 1, indent)
        prefix = f"cd {stands_in} && " if stands_in else ""
        if _requires_hashes_by_env(lines, index - 1, indent):
            prefix += "PIP_REQUIRE_HASHES=1 "
        # A block's lines, or a plain value's continuation lines: past the key's own column
        # — a sibling `env:` or `name:` of a `- run:` item sits at that column, not past it.
        rest: list[str] = []
        while index < len(lines) and (
            not lines[index].strip() or len(lines[index]) - len(lines[index].lstrip()) > indent
        ):
            rest.append(lines[index])
            index += 1
        if value.startswith("|"):
            found += [prefix + line.lstrip() if prefix else line for line in rest]
        elif BLOCK.match(value):
            found += [prefix + line for line in _folded(rest)]
        else:
            joined = _resolved(_unquoted(" ".join(_folded([value, *rest]))), anchors)
            found.append(prefix + joined)
    return found


def _commands(path: pathlib.Path) -> list[str]:
    text = _text(path)
    joined, buffer = [], ""
    for raw in _run_lines(text) if path.suffix in YAML else text.splitlines():
        if raw.lstrip().startswith("#"):
            continue
        buffer += _without_comment(raw).rstrip()
        if buffer.endswith("\\"):
            buffer = buffer[:-1]
            continue
        joined.append(buffer)
        buffer = ""
    if buffer:
        joined.append(buffer)
    return joined


def _nothing_of_yours(targets: list[pathlib.Path]) -> bool:
    """Every file read is the bundle's untouched starting workflow — said as NA."""
    if not all(_bundles_own(_text(path)) for path in targets):
        return False
    print("NA: only the bundle's own starting workflow, untouched — nothing of yours to check yet")
    return True


def _files_read(root: pathlib.Path) -> list[pathlib.Path]:
    """The files read as written: workflows, composite actions, the root Dockerfile."""
    targets = sorted((root / ".github" / "workflows").glob("*.y*ml"))
    targets += sorted((root / ".github" / "actions").glob("**/action.y*ml"))
    return targets + [p for p in [root / "Dockerfile"] if p.is_file()]


# pip enters hash-checking mode by the flag, by `PIP_REQUIRE_HASHES=1` in the
# environment, or on its own when every requirement in the file carries a
# `--hash=`; `--no-index` fetches nothing from an index at all, and a wheel installed
# with `--no-deps` is a file copied, not a build. Each of these was a finding
# (self-audit, 2026-08-31, proved against pip 26.2.1) — a scanner that repeats what
# pip already enforces sends a project that did the right thing back to rewrite it.
REQUIRE_HASHES_ENV = re.compile(
    r"(?:^|\s)PIP_REQUIRE_HASHES=(?:1|true|yes|on)(?=\s|$)", re.IGNORECASE
)
REQUIREMENT_FILE = re.compile(r"(?:^|\s)(?:-r|--requirement)[\s=]+[\"']?([^\s\"']+)")
HASHED = re.compile(r"--hash[=\s]")


def _requirements_all_hashed(command: str, where: pathlib.Path) -> bool:
    """Every requirement in every `-r` file the command names carries a hash — pip
    then requires hashes on its own. A file that is not there is not hashed."""
    files = REQUIREMENT_FILE.findall(command)
    if not files:
        return False
    for name in files:
        path = where / name
        if not path.is_file():
            return False
        # pip joins a line ending in `\` with the next — the shape `pip-compile`
        # writes, one hash per continuation line.
        text = re.sub(r"\\\s*\n", " ", path.read_text(encoding="utf-8", errors="replace"))
        lines = [line.split("#", 1)[0].strip() for line in text.splitlines()]
        requirements = [line for line in lines if line and not line.startswith("-")]
        if not requirements or not all(HASHED.search(line) for line in requirements):
            return False
    return True


def _pip_requires_hashes(command: str, where: pathlib.Path) -> bool:
    """Hashes are required of the install itself — by its own argument, by
    `PIP_REQUIRE_HASHES=1` on its command, or by a fully hashed requirements file — or
    nothing is fetched from an index (`--no-index`). `MARKER=--require-hashes pip
    install ruff` carried the flag where pip never reads it and passed (outside audit,
    2026-08-30); `"--require-hashes"` in quotes was a finding (self-audit, 2026-08-31)."""
    matched = PIP_INSTALL.search(command)
    after = command[matched.end() :] if matched else ""
    try:
        arguments = set(shlex.split(after))  # `"--require-hashes"` is the flag; `"# x"` is text
    except ValueError:
        arguments = set(after.split())
    if "--require-hashes" in arguments or "--no-index" in arguments:
        return True
    if REQUIRE_HASHES_ENV.search(command[: matched.start()] if matched else ""):
        return True
    return _requirements_all_hashed(after, where)


def _line_findings(where: pathlib.Path, line: str, stands_in: pathlib.Path) -> list[str]:
    """Everything one command does that reaches an index unpinned."""
    found: list[str] = []
    while KEYWORD.match(line):
        line = KEYWORD.sub("", line, count=1)
    words = line.split()
    if words and words[0] in PROSE:
        return found
    if (
        PIP_INSTALL.search(line)
        and not _pip_requires_hashes(line, stands_in)
        and _installs_from_an_index(line)
    ):
        found.append(f"{where}: {line.strip()[:70]}")
    if NPM_INSTALL.search(line):
        found.append(f"{where}: use npm ci instead — {line.strip()[:60]}")
    if PIPX_INSTALL.search(line):
        found.append(f"{where}: pipx resolves from the index — {line.strip()[:55]}")
    if NO_PIP_INSTALL.search(line):
        found.append(f"{where}: resolves from the index with no lock — {line.strip()[:50]}")
    if BUILD.search(line) and not NO_ISOLATION.search(line):
        found.append(
            f"{where}: build fetches its backend unpinned;"
            f" pin it and pass --no-isolation — {line.strip()[:50]}"
        )
    return found


def _judge(root: pathlib.Path) -> int:
    if not root.is_dir():
        # NA means "this project has nothing of that kind"; a root that is not
        # there has no project to say it about, and answering the second with
        # the first is a green over nothing (self-audit round 2, 2026-08-31).
        print(f"cannot read the tree: {root} is not a directory", file=sys.stderr)
        return 2
    targets = _files_read(root)
    if not targets:
        print("NA: no workflows, composite actions or Dockerfile — nothing to check yet")
        return 0
    if _nothing_of_yours(targets):
        return 0

    findings: list[str] = []
    for path in _with_scripts(root, _followed(root, targets)):
        # One `run:` line can chain several commands; each is judged on its own,
        # or the second hides behind the first's exemption.
        for joined in _commands(path):
            stands_in = root
            for line in CHAIN.split(_as_the_shell_runs_it(joined)):
                if moved := CD.match(line):
                    stands_in = stands_in / moved.group("dir")
                    continue
                findings += _line_findings(path.relative_to(root), line, stands_in)

    for finding in findings:
        print(f"ci-tools-hash-pinned: {finding}")
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
        print("usage: scan_install_pinning.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
