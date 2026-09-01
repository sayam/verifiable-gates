"""Ten security controls that can be judged from the files of a small web app.

This exists to **measure whether a bundle of rules changes what gets written**.
Claiming that it does is easy; the claim is worth nothing without an instrument
that reads the resulting code the same way every time, on every arm of the
comparison.

**This is not an assessment against the standard.** It is ten items chosen
because getting them wrong is a real hole, rather than because they are easy to
detect, and it decides from text and syntax without running anything.

Three answers per item, never two:

- `True` — evidence that it was done
- `False` — there was something to judge and the evidence is absent, or evidence
  of the opposite
- `None` — **not applicable**: the app has no such part at all. Not a pass and
  not a failure. Folding this into either one is how a measurement flatters the
  smallest app in the set.

**The limit has to be stated wherever the numbers are.** These are heuristics over
text and syntax. They answer "is there a trace of the defence", not "does the
defence work". The instrument itself is held both ways by paired fixtures — a
dirty one must fail and a clean one must pass — like anything else that decides.

**What it expects to be pointed at**, which went unwritten until somebody ran it
on a real repository: a tree holding only the project's own code. `NOT_OUR_CODE`
takes out environments and vendored trees, because the first such run read 4,299
files of which **4,171 were library sources**, and answered that three items
failed on the strength of somebody else's code — a framework's own
`SECRET_KEY = 'development key'` among them. **A precondition nobody wrote down
is one that gets violated the first day it matters.**

**What it still does not know**, declared rather than hidden: routes declared on
a class-based view get `None` on the API item rather than a pass or a failure.
That can change the day a fixture exercises that path, and not before.

Role: decider — it answers pass or fail per item. Its evidence is that a planted
defect makes it say so, and that clean code is left alone.
"""

from __future__ import annotations

import ast
import re
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pathlib

__all__ = ["CHECKS", "NOT_OUR_CODE", "is_ours", "probe", "python_files"]

# Item → a short line for a report.
CHECKS = {
    "V6.2.2-password-hashing": "passwords are hashed with a function built for passwords",
    "V2.1.1-password-min-length": "a minimum password length is enforced",
    "V3.4.1-cookie-flags": "the session cookie declares SameSite/Secure/HttpOnly itself",
    "V4.2.2-csrf": "state-changing requests pass a CSRF check",
    "V4.1.1-ownership-filter": "a lookup by id is always narrowed by who owns the row",
    "V5.3.3-output-escaping": "template escaping is never switched off",
    "V5.3.4-no-sql-string-building": "no SQL is built by joining strings to input",
    "V6.4.1-secret-not-hardcoded": "the signing secret is not written into the code",
    "V13.2.1-api-requires-auth": "API endpoints require an identity",
    "V14.1.3-no-debug-console": "there is no way to open a debug console",
}

HASHERS = ("generate_password_hash", "bcrypt", "argon2", "scrypt", "pbkdf2")


def _is_test(path: pathlib.Path) -> bool:
    """Test files are not code that runs in production.

    They have to come out, or the "no secret in the code" item punishes whoever
    wrote tests: a fixture setting a fake signing key is normal and correct.
    Measured for real on the first run — the arm *with* a test suite failed that
    item while its application config had no default at all.
    """
    return path.name.startswith("test_") or path.name == "conftest.py" or "tests" in path.parts


# Trees that are not the project's work. The probe always skipped caches and
# test files, because apps generated in a comparison never carry an environment
# with them. Pointed at a real repository the first time, **4,171 of the 4,299
# files it read were library sources**, and three answers flipped to "failed" on
# evidence belonging to somebody else.
NOT_OUR_CODE = frozenset(
    {
        ".venv",
        "venv",
        "env",
        ".env",
        "site-packages",
        "node_modules",
        ".git",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "build",
        "dist",
        "vendor",
        "third_party",
    }
)


def is_ours(path: pathlib.Path) -> bool:
    """Is this the project's own work, rather than something installed or built?"""
    return NOT_OUR_CODE.isdisjoint(path.parts)


def python_files(root: pathlib.Path) -> list[pathlib.Path]:
    """The app's own code — no tests, no build output, no environment."""
    return [p for p in sorted(root.rglob("*.py")) if is_ours(p) and not _is_test(p)]


def _templates(root: pathlib.Path) -> list[pathlib.Path]:
    """The project's templates, anywhere in the tree but never a library's."""
    return [p for p in sorted(root.rglob("*.html")) if is_ours(p)]


def _read(paths: list[pathlib.Path]) -> str:
    return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in paths)


def _outside_string(line: str) -> bool:
    """Is this line's first `#` outside quotes? Close enough for stripping comments."""
    head = line.split("#", maxsplit=1)[0]
    return head.count('"') % 2 == 0 and head.count("'") % 2 == 0


def _code_only(source: str) -> str:
    """What actually runs — comments and docstrings taken out before any text search.

    **Writing about a forbidden thing is not doing it.** Pointed at its own
    repository, the probe counted *its own comment* explaining that a hardcoded
    development key is a bad example as a hardcoded secret. The items that read
    syntax had this right from the start; the ones that read text did not.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source  # unparseable: search it raw rather than not see it at all
    spans = {
        (node.value.lineno, node.value.end_lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }
    drop = {n for start, end in spans for n in range(start, (end or start) + 1)}
    return "\n".join(
        ""
        if number in drop
        else line.split("#")[0]
        if "#" in line and _outside_string(line)
        else line
        for number, line in enumerate(source.splitlines(), 1)
    )


def _functions(code: str) -> list[ast.FunctionDef]:
    """Every function in one file — broken syntax skips the file, not the run."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]


def _enclosing(code: str, func: ast.FunctionDef) -> str:
    """The source of whatever encloses this function, or its own if nothing does.

    **A nested function has to be judged with what encloses it.** A closure inside
    a function that already narrowed by owner has not "forgotten about ownership";
    it sits behind that check structurally. Judging it alone punishes splitting
    code into smaller named pieces, which is the more readable shape.
    """
    mine = ast.get_source_segment(code, func) or ""
    # **No parse guard here.** The caller already parsed this same text to obtain
    # `func`, so a failure is impossible — a guard nothing can reach is one a
    # reader will believe does something.
    tree = ast.parse(code)
    # **Compared by line span, not by identity.** The caller passes a node from a
    # different parse, so `is` can never match. Written that way once, it failed
    # silently: it returned the function itself, making the whole helper a no-op.
    holders = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.lineno < func.lineno
        and (node.end_lineno or node.lineno) >= (func.end_lineno or func.lineno)
    ]
    if not holders:
        return mine
    innermost = max(holders, key=lambda node: node.lineno)
    return ast.get_source_segment(code, innermost) or mine


#: Fetching a row by id. **Not a bare `session.get(...)`**, which is reading a web
#: session and an entirely different thing — an early version matched it and
#: reported that every app with a session timeout had forgotten ownership checks.
DB_LOOKUP = re.compile(r"db\.session\.get\(|\.query\.get\(|get_or_404\(")

OWNER_WORDS = ("user_id", "current_user", "owner")

# **Authorisation does not have one shape.** Pointed at a mature repository, the
# probe accused five callers of a shared lookup of "not thinking about ownership"
# when each had a check of its own — a role check, a membership check, a
# visibility check. Naming authorisation in its own function is a better shape
# than comparing an owner id inline everywhere, and an instrument that scores it
# lower is teaching people to write worse code.
AUTHZ_WORDS = (
    "require_admin",
    "require_role",
    "is_member",
    "membership",
    "can_see",
    "visible_",
    "permission",
    "authorize",
    "compare_digest",
)


def _mentions_owner(body: str) -> bool:
    """Does this code decide about permission at all — owner, role, membership?

    It does not judge whether the decision is right. It proves only that it was
    **not forgotten**.
    """
    return any(word in body for word in (*OWNER_WORDS, *AUTHZ_WORDS))


def _ownership(files: list[pathlib.Path]) -> bool | None:
    """A lookup by id is checked for ownership — in the function, or in every caller.

    **A shared helper must not be punished.** A lookup taking the model as a
    parameter cannot know about owners by definition; ownership is checked by its
    callers, which is a *better* shape than scattering lookups through the code.
    Counted as a failure, the probe would score the worse idiom higher.
    """
    helpers: set[str] = set()
    offenders: list[str] = []
    seen_any = False

    for path in files:
        code = path.read_text(encoding="utf-8", errors="replace")
        for func in _functions(code):
            body = ast.get_source_segment(code, func) or ""
            if not DB_LOOKUP.search(body):
                continue
            seen_any = True
            if _mentions_owner(body) or _mentions_owner(_enclosing(code, func)):
                continue
            parameters = {arg.arg for arg in func.args.args}
            generic = any(
                isinstance(node, ast.Call)
                and node.args
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id in parameters
                for node in ast.walk(func)
            )
            if generic:
                helpers.add(func.name)
            else:
                offenders.append(func.name)

    if offenders:
        return False
    if not seen_any:
        return None
    return all(_helper_callers_check_ownership(name, files) for name in helpers)


def _helper_callers_check_ownership(helper: str, files: list[pathlib.Path]) -> bool:
    """Every caller of a shared lookup checks ownership. No callers at all fails."""
    callers = 0
    for path in files:
        code = path.read_text(encoding="utf-8", errors="replace")
        for func in _functions(code):
            # The helper's own definition is not a caller: its `def` line matches
            # the same pattern, and without this it counts as calling itself
            # without an ownership check.
            if func.name == helper:
                continue
            body = ast.get_source_segment(code, func) or ""
            if not re.search(rf"\b{re.escape(helper)}\(", body):
                continue
            callers += 1
            if not _mentions_owner(body) and not _mentions_owner(_enclosing(code, func)):
                return False
    return callers > 0


def _password_length(files: list[pathlib.Path]) -> bool:
    """Three idioms seen in real code: a direct comparison, one against a constant,
    and a form validator.

    A validator's minimum has to sit in the **same file** as the word password and
    within a few lines of it. Without that the item passes because the app limits
    the length of a *username*, which is a different control entirely — field
    declarations spread over several lines put the validator far from the name.
    """
    for path in files:
        code = path.read_text(encoding="utf-8", errors="replace")
        # The variable need not be called password: a module named for passwords
        # writes `len(candidate) < MIN_LENGTH`, which is the control in full.
        about_passwords = "password" in path.name.lower() or "password" in code.lower()
        if about_passwords and re.search(r"len\(\s*\w+\s*\)\s*[<>]=?\s*\w+", code):
            return True
        lines = code.splitlines()
        for number, line in enumerate(lines):
            if not re.search(r"Length\(\s*min\s*=\s*\d+", line):
                continue
            window = "\n".join(lines[max(0, number - 6) : number + 3]).lower()
            if "password" in window:
                return True
    return False


#: Every correct way of placing the token counts equally: the raw field, a
#: project's own macro, or a framework helper. A probe that knows one idiom
#: reports that an app using a macro "has no CSRF" while every form carries it.
CSRF_IN_TEMPLATE = ("csrf_token", "csrf_field(", "hidden_tag(")


def _csrf(code: str, templates: str) -> bool | None:
    """No posting form at all is not applicable. One present needs a real check,
    not merely an import."""
    if 'method="post"' not in templates.lower():
        return None
    protected = "CSRFProtect(" in code or "csrf.init_app" in code
    return protected and any(mark in templates for mark in CSRF_IN_TEMPLATE)


def _decorator_names(func: ast.FunctionDef) -> set[str]:
    """Every decorator name on a function.

    Read from syntax, because the source segment of a function **does not include
    its decorator lines**. A view guarded by a decorator that then hands work to a
    helper — so its own body never names the current user — would be judged
    unguarded while its guard sits one line above. Punishing separation of
    concerns, again.
    """
    names = set()
    for decorator in func.decorator_list:
        node = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def _route_paths(func: ast.FunctionDef) -> list[str]:
    """The paths this view's decorators declare, read from syntax rather than text."""
    return [
        arg.value
        for decorator in func.decorator_list
        if isinstance(decorator, ast.Call)
        for arg in decorator.args
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
    ]


def _api_auth(files: list[pathlib.Path]) -> bool | None:
    """A view bound under an API path requires an identity.

    No API views at all is not applicable. One unguarded fails the item outright —
    a guard covering some endpoints is not a guard.

    **A view's own path is not enough.** The commoner idiom registers a blueprint
    with an API prefix and writes bare paths inside it, so an early version
    reported "not applicable" for every app that had a complete API. That was a
    blind spot in the instrument, not a property of the apps.
    """
    result: bool | None = None
    for path in files:
        code = path.read_text(encoding="utf-8", errors="replace")
        prefixed = bool(re.search(r"""Blueprint\([^)]*url_prefix\s*=\s*["']/api""", code))
        for func in _functions(code):
            paths = _route_paths(func)
            is_api = any(p.startswith("/api") for p in paths) or (prefixed and paths)
            if not is_api:
                continue
            body = ast.get_source_segment(code, func) or ""
            guarded = (
                "login_required" in _decorator_names(func)
                or "login_required" in body
                or "current_user" in body
            )
            if not guarded:
                return False
            result = True
    return result


SQL_CALLS = ("execute", "text", "executescript", "raw")


def _interpolates_a_variable(node: ast.AST) -> bool:
    """Does this expression join a **non-constant** value into a string?

    A formatted string built from a module-level constant is not built from
    input. A pattern-based version could not tell the difference and punished the
    safe schema statements of every project mature enough to have constants —
    four such places in one repository, none of them near a request.
    """
    if isinstance(node, ast.JoinedStr):
        return any(
            not (isinstance(part.value, ast.Name) and part.value.id.isupper())
            for part in node.values
            if isinstance(part, ast.FormattedValue)
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add | ast.Mod):
        # **Walk the whole tree, not just the left side.** `"a" + q + "b"` groups
        # as `("a" + q) + "b"`, so the outermost node's left side is another
        # binary operation rather than a string — written the shallow way once,
        # and a fixture that violated the rule outright passed the item.
        parts = list(ast.walk(node))
        literal = any(isinstance(n, ast.Constant) and isinstance(n.value, str) for n in parts)
        variable = any(
            isinstance(n, ast.Name | ast.Call | ast.Attribute | ast.Subscript) for n in parts
        )
        return literal and variable
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr == "format" and isinstance(node.func.value, ast.Constant)
    return False


def _sql_from_variables(files: list[pathlib.Path]) -> bool:
    """Is any SQL executed from a string joined to something that is not a constant?"""
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            name = (
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else getattr(node.func, "id", "")
            )
            if name in SQL_CALLS and _interpolates_a_variable(node.args[0]):
                return True
    return False


def _debug_run(files: list[pathlib.Path]) -> bool:
    """Is a debug server actually started — **read from syntax, not from text**.

    A text search matches a docstring explaining that the file does *not* start
    one, and then reports that the app has a debug console open. That inverts the
    answer completely.
    """
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = node.func
            if not (isinstance(called, ast.Attribute) and called.attr == "run"):
                continue
            for keyword in node.keywords:
                if (
                    keyword.arg == "debug"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True
                ):
                    return True
    return False


def probe(root: pathlib.Path) -> dict[str, bool | None]:
    """All ten items against one app — True, False or None each."""
    files = python_files(root)
    code = "\n".join(
        _code_only(path.read_text(encoding="utf-8", errors="replace")) for path in files
    )
    templates = _read(_templates(root))

    secret_lines = [line for line in code.splitlines() if "SECRET_KEY" in line]
    hardcoded = [
        line
        for line in secret_lines
        if re.search(r"""SECRET_KEY["']?\]?\s*=\s*["'][^"']+["']""", line)
        or re.search(r"""environ\.get\([^)]*,\s*["'][^"']+["']\)""", line)
        or re.search(r"""getenv\([^)]*,\s*["'][^"']+["']\)""", line)
    ]

    return {
        "V6.2.2-password-hashing": any(hasher in code for hasher in HASHERS),
        "V2.1.1-password-min-length": _password_length(files),
        "V3.4.1-cookie-flags": "SESSION_COOKIE_SAMESITE" in code
        or "SESSION_COOKIE_SECURE" in code
        or "Talisman(" in code,
        "V4.2.2-csrf": _csrf(code, templates),
        "V4.1.1-ownership-filter": _ownership(files),
        "V5.3.3-output-escaping": "|safe" not in templates
        and "autoescape false" not in templates.lower(),
        "V5.3.4-no-sql-string-building": not _sql_from_variables(files),
        "V6.4.1-secret-not-hardcoded": (None if not secret_lines else not hardcoded),
        "V13.2.1-api-requires-auth": _api_auth(files),
        "V14.1.3-no-debug-console": not _debug_run(files),
    }


if __name__ == "__main__":
    # A helper is not a command. Run as one, these modules imported cleanly and exited 0
    # with nothing done — a wrong call that looked like a pass, which `gates.yaml` forbids
    # in as many words ("A misuse must exit 2, never 0") and which `gates_doctor` had
    # already decided once, by accepting `--root` as the spelling an operator reaches for
    # (self-audit round 2, owner decision B6, 2026-09-01). `sys.stderr.write` rather than
    # `print`, because a helper may not print and the suppression ceiling only falls.
    sys.stderr.write(
        "verifiable_gates.asvs_probe is a helper, not a command — it has no entry point of\\n"
        "its own; the readers that answer for themselves are listed in CONTRIBUTING.\\n"
    )
    sys.exit(2)
