"""The instrument gets measured first — both ways, per item, never per suite.

**A tool built to prove something can lie in the direction its builder wants.**
A probe that answers "passed" for every app reports that the rules made no
difference — a wrong conclusion with nothing anywhere to contradict it.

So a **pair of apps** is planted in a temporary directory: one violating all ten
items, one satisfying all ten, and **every item has to tell them apart**. An item
answering the same for both is an item measuring nothing.
"""

import json
import pathlib

import pytest

from verifiable_gates.asvs_probe import CHECKS, NOT_OUR_CODE, probe, python_files

INSECURE_APP = {
    "run.py": "from app import create_app\n\napp = create_app()\napp.run(debug=True)\n",
    "app/__init__.py": (
        "from flask import Flask\n\n\n"
        "def create_app():\n"
        "    app = Flask(__name__)\n"
        '    app.config["SECRET_KEY"] = "dev-secret"\n'
        "    return app\n"
    ),
    "app/views.py": (
        "from flask import Blueprint, request\n\n"
        "from . import db\n"
        "from .models import Note, User\n\n"
        'main = Blueprint("main", __name__)\n\n\n'
        '@main.route("/register", methods=["POST"])\n'
        "def register():\n"
        '    user = User(password=request.form["password"])\n'
        "    db.session.add(user)\n"
        '    return ""\n\n\n'
        '@main.route("/notes/<int:note_id>")\n'
        "def show(note_id):\n"
        "    note = db.session.get(Note, note_id)\n"
        "    return note.body\n\n\n"
        '@main.route("/api/notes")\n'
        "def api_notes():\n"
        '    q = request.args.get("q", "")\n'
        '    rows = db.session.execute("SELECT * FROM note WHERE body LIKE \'%" + q + "%\'")\n'
        '    return {"notes": [dict(r) for r in rows]}\n'
    ),
    "app/templates/index.html": (
        '<form method="post"><button>delete</button></form>\n{{ body|safe }}\n'
    ),
}

SECURE_APP = {
    "run.py": "from app import create_app\n\napp = create_app()\n",
    "app/__init__.py": (
        "import os\n\n"
        "from flask import Flask\n"
        "from flask_wtf import CSRFProtect\n\n\n"
        "def create_app():\n"
        "    app = Flask(__name__)\n"
        '    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]\n'
        '    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"\n'
        "    CSRFProtect(app)\n"
        "    return app\n"
    ),
    "app/views.py": (
        "from flask import Blueprint, request\n"
        "from flask_login import current_user, login_required\n"
        "from werkzeug.security import generate_password_hash\n\n"
        "from . import db\n"
        "from .models import Note, User\n\n"
        'main = Blueprint("main", __name__)\n\n\n'
        '@main.route("/register", methods=["POST"])\n'
        "def register():\n"
        '    password = request.form["password"]\n'
        "    if len(password) < 8:\n"
        '        return "too short", 400\n'
        "    db.session.add(User(password_hash=generate_password_hash(password)))\n"
        '    return ""\n\n\n'
        '@main.route("/notes/<int:note_id>")\n'
        "@login_required\n"
        "def show(note_id):\n"
        "    note = db.session.get(Note, note_id)\n"
        "    if note is None or note.user_id != current_user.id:\n"
        '        return "not found", 404\n'
        "    return note.body\n\n\n"
        '@main.route("/api/notes")\n'
        "@login_required\n"
        "def api_notes():\n"
        '    q = request.args.get("q", "")\n'
        "    rows = db.session.query(Note).filter(\n"
        "        Note.user_id == current_user.id, Note.body.ilike(f'%{q}%')\n"
        "    )\n"
        '    return {"notes": [r.body for r in rows]}\n'
    ),
    "app/templates/index.html": (
        '<form method="post">\n'
        '  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">\n'
        "  <button>delete</button>\n</form>\n{{ body }}\n"
    ),
}


# A second idiom: the same protections written differently — a blueprint carrying
# the API prefix, a password length via a constant, and a form validator. An early
# probe answered "not applicable" or "failed" to all three while the app was complete.
SECURE_APP_OTHER_IDIOM = {
    "run.py": "from app import create_app\n\napp = create_app()\n",
    "app/__init__.py": SECURE_APP["app/__init__.py"],
    "app/forms.py": (
        "from flask_wtf import FlaskForm\n"
        "from wtforms import PasswordField\n"
        "from wtforms.validators import Length\n\n\n"
        "class RegisterForm(FlaskForm):\n"
        '    password = PasswordField("password", validators=[Length(min=8, max=128)])\n'
    ),
    "app/auth.py": (
        "from flask import Blueprint\n"
        "from werkzeug.security import generate_password_hash\n\n"
        "from .forms import RegisterForm\n\n"
        'auth = Blueprint("auth", __name__)\n'
        "MIN_PASSWORD_LENGTH = 8\n\n\n"
        '@auth.route("/register", methods=["POST"])\n'
        "def register():\n"
        "    form = RegisterForm()\n"
        "    if not form.validate_on_submit():\n"
        '        return "rejected", 400\n'
        "    return generate_password_hash(form.password.data)\n"
    ),
    "app/api.py": (
        "from flask import Blueprint\n"
        "from flask_login import current_user, login_required\n\n"
        "from .models import Note\n\n"
        'api = Blueprint("api", __name__, url_prefix="/api")\n\n\n'
        '@api.route("/notes")\n'
        "@login_required\n"
        "def notes():\n"
        "    rows = Note.query.filter_by(user_id=current_user.id).all()\n"
        '    return {"notes": [r.body for r in rows]}\n'
    ),
    "app/templates/index.html": SECURE_APP["app/templates/index.html"],
}


# A third idiom: a service layer — a shared lookup with ownership checked by its
# callers, a password policy in its own module using a constant, and a session
# timeout reading the web session (a different thing from fetching a row).
SECURE_APP_SERVICE_LAYER = {
    "run.py": "from app import create_app\n\napp = create_app()\n",
    "app/__init__.py": SECURE_APP["app/__init__.py"],
    "app/session_security.py": (
        "from flask import session\n\n"
        'STARTED_AT = "started_at"\n\n\n'
        "def expired():\n"
        "    raw = session.get(STARTED_AT)\n"
        "    return raw is None\n"
    ),
    "app/services/lookup.py": (
        "from ..extensions import db\n\n\n"
        "def by_id(model, raw_id):\n"
        "    try:\n"
        "        row_id = int(raw_id)\n"
        "    except (TypeError, ValueError):\n"
        "        return None\n"
        "    return db.session.get(model, row_id)\n"
    ),
    "app/services/passwords.py": (
        "MIN_LENGTH = 8\n\n\n"
        "def validate(candidate):\n"
        '    """The one place the password policy lives."""\n'
        "    if len(candidate) < MIN_LENGTH:\n"
        '        raise ValueError("too short")\n'
    ),
    "app/services/notes.py": (
        "from ..models import Note\n"
        "from .lookup import by_id\n\n\n"
        "def get_note(user_id, note_id):\n"
        "    note = by_id(Note, note_id)\n"
        "    if note is None or note.user_id != user_id:\n"
        '        raise LookupError("not found")\n'
        "    return note\n"
    ),
    "app/api.py": (
        "from flask import Blueprint\n"
        "from flask_login import current_user, login_required\n"
        "from werkzeug.security import generate_password_hash\n\n"
        "from .services.notes import get_note\n\n"
        'api = Blueprint("api", __name__, url_prefix="/api")\n\n\n'
        '@api.route("/notes/<int:note_id>")\n'
        "@login_required\n"
        "def one(note_id):\n"
        "    note = get_note(current_user.id, note_id)\n"
        '    return {"body": note.body, "hash": generate_password_hash(\'x\')}\n'
    ),
    "app/templates/index.html": SECURE_APP["app/templates/index.html"],
    # The target project's own tests — a secret in a fixture is not a hardcoded secret
    "tests/conftest.py": 'SECRET_KEY = "x" * 48\n',
}


def _plant(root: pathlib.Path, files: dict[str, str]) -> pathlib.Path:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


@pytest.fixture
def insecure(tmp_path: pathlib.Path) -> pathlib.Path:
    return _plant(tmp_path / "insecure", INSECURE_APP)


@pytest.fixture
def secure(tmp_path: pathlib.Path) -> pathlib.Path:
    return _plant(tmp_path / "secure", SECURE_APP)


def test_the_secure_app_passes_every_check(secure: pathlib.Path) -> None:
    """The complete app must fail nothing, or the probe punishes both arms alike."""
    result = probe(secure)
    failed = sorted(name for name, value in result.items() if value is False)
    assert not failed, f"the complete app failed: {failed}"


def test_the_insecure_app_fails_every_check(insecure: pathlib.Path) -> None:
    """The violating app must fail everything — an item still passing checks nothing."""
    result = probe(insecure)
    passed = sorted(name for name, value in result.items() if value is not False)
    assert not passed, f"the violating app passed: {passed}"


def test_every_declared_check_is_answered(secure: pathlib.Path, insecure: pathlib.Path) -> None:
    """The declared items and the answered items are one set, on both arms."""
    for app in (secure, insecure):
        assert set(probe(app)) == set(CHECKS)


def test_the_same_protections_written_differently_still_pass(tmp_path: pathlib.Path) -> None:
    """The same protection written differently has to give the same answer.

    Tied to one idiom, the probe measures "written like our example?" instead of
    "protected?" — which leans toward whichever arm read our own rules. Caught
    for real on the first control-arm run: a blueprint prefix counted as "no API"
    and a validator minimum counted as "no length rule".
    """
    app = _plant(tmp_path / "other", SECURE_APP_OTHER_IDIOM)
    result = probe(app)
    failed = sorted(name for name, value in result.items() if value is False)
    assert not failed, f"the second idiom failed: {failed}"
    assert result["V13.2.1-api-requires-auth"] is True, "a blueprint prefix has to count as an API"
    assert result["V2.1.1-password-min-length"] is True


def test_a_service_layer_shape_is_not_punished(tmp_path: pathlib.Path) -> None:
    """A shared lookup, ownership checked by callers, and the project's own tests
    must not cause a failure.

    All three made an early probe judge the better-structured arm as the worse
    one: reading the web session counted as fetching a row, a shared lookup
    counted as forgetting ownership though every caller checked it, and a signing
    key in a fixture counted as a hardcoded secret. **An instrument that scores
    the worse idiom higher is answering a different question from the one the
    report names.**
    """
    app = _plant(tmp_path / "service-layer", SECURE_APP_SERVICE_LAYER)
    result = probe(app)
    failed = sorted(name for name, value in result.items() if value is False)
    assert not failed, f"the service-layer shape failed: {failed}"
    assert result["V4.1.1-ownership-filter"] is True
    assert result["V2.1.1-password-min-length"] is True
    assert result["V6.4.1-secret-not-hardcoded"] is True


def test_writing_about_a_forbidden_thing_is_not_doing_it(tmp_path: pathlib.Path) -> None:
    """A docstring saying the file has no debug server must not count as having one.

    The same trap the bundle's own scanners read syntax to avoid, and the same one
    an agent hit when a template comment quoted the forbidden thing to explain it.
    A text search **inverts the answer completely**.
    """
    files = dict(SECURE_APP_SERVICE_LAYER)
    files["run.py"] = (
        '"""entrypoint — no ``debug=True`` here, and debug cannot come from env"""\n\n'
        "from app import create_app\n\napp = create_app()\n"
    )
    app = _plant(tmp_path / "docstring", files)
    assert probe(app)["V14.1.3-no-debug-console"] is True


def test_a_csrf_macro_counts_like_a_raw_token(tmp_path: pathlib.Path) -> None:
    """A macro placing the token is placing the token, not an absence of CSRF."""
    files = dict(SECURE_APP_SERVICE_LAYER)
    files["app/templates/index.html"] = (
        '<form method="post">\n  {{ csrf_field() }}\n  <button>delete</button>\n</form>\n'
    )
    app = _plant(tmp_path / "macro", files)
    assert probe(app)["V4.2.2-csrf"] is True


def test_a_guard_on_the_decorator_line_counts(tmp_path: pathlib.Path) -> None:
    """A guard on the decorator line counts, even when the body never names a user.

    A function's source segment does not include its decorator lines, so a view
    handing work to a helper is judged unguarded while its guard sits one line
    above. Caught for real: 2 of 5 apps in one arm were counted as having an
    unauthenticated API when every endpoint was guarded.
    """
    files = dict(SECURE_APP_SERVICE_LAYER)
    files["app/api.py"] = (
        "from flask import Blueprint\n"
        "from flask_login import login_required\n\n"
        "from .services.notes import list_for\n\n"
        'api = Blueprint("api", __name__, url_prefix="/api")\n\n\n'
        '@api.get("/notes")\n'
        "@login_required\n"
        "def listing():\n"
        '    return {"notes": list_for()}\n'
    )
    app = _plant(tmp_path / "decorated", files)
    assert probe(app)["V13.2.1-api-requires-auth"] is True


def test_an_api_view_with_no_guard_at_all_still_fails(tmp_path: pathlib.Path) -> None:
    """Allowing for decorators is not allowing for everything — no guard still fails."""
    files = dict(SECURE_APP_SERVICE_LAYER)
    files["app/api.py"] = (
        "from flask import Blueprint\n\n"
        "from .services.notes import list_for\n\n"
        'api = Blueprint("api", __name__, url_prefix="/api")\n\n\n'
        '@api.get("/notes")\n'
        "def listing():\n"
        '    return {"notes": list_for()}\n'
    )
    app = _plant(tmp_path / "unguarded", files)
    assert probe(app)["V13.2.1-api-requires-auth"] is False


def test_a_lookup_helper_with_no_owner_check_anywhere_still_fails(tmp_path: pathlib.Path) -> None:
    """Allowing for a shared lookup is not a blanket pass — an unchecking caller fails."""
    files = dict(SECURE_APP_SERVICE_LAYER)
    files["app/services/notes.py"] = (
        "from ..models import Note\nfrom .lookup import by_id\n\n\n"
        "def get_note(note_id):\n    return by_id(Note, note_id)\n"
    )
    files["app/api.py"] = files["app/api.py"].replace(
        "get_note(current_user.id, note_id)", "get_note(note_id)"
    )
    app = _plant(tmp_path / "leaky-helper", files)
    assert probe(app)["V4.1.1-ownership-filter"] is False


def test_a_length_rule_on_something_else_does_not_count(tmp_path: pathlib.Path) -> None:
    """A length rule on a *username* is not a password length rule."""
    files = dict(SECURE_APP_OTHER_IDIOM)
    files["app/forms.py"] = (
        "from flask_wtf import FlaskForm\n"
        "from wtforms import StringField\n"
        "from wtforms.validators import Length\n\n\n"
        "class RegisterForm(FlaskForm):\n"
        '    username = StringField("username", validators=[Length(min=3, max=64)])\n'
    )
    files["app/auth.py"] = files["app/auth.py"].replace("MIN_PASSWORD_LENGTH = 8\n", "")
    app = _plant(tmp_path / "username-only", files)
    assert probe(app)["V2.1.1-password-min-length"] is False


def test_csrf_needs_both_the_guard_and_the_token(tmp_path: pathlib.Path) -> None:
    """The guard installed but no token in the form is still a failure.

    Written separately because the main pair cannot catch it: the violating app
    never installs the guard at all, so dropping the "token in the template"
    condition would not make it pass. A check that only separates the two extremes
    lets everything in between through.
    """
    half = _plant(tmp_path / "half", {**SECURE_APP})
    (half / "app" / "templates" / "index.html").write_text(
        '<form method="post"><button>delete</button></form>\n', encoding="utf-8"
    )
    assert probe(half)["V4.2.2-csrf"] is False


# ------------------------------- the report has to match the measurement it came from

COMPARISON = pathlib.Path(__file__).resolve().parent.parent / "docs" / "comparison"
REPORT = COMPARISON / "results-2026-08-14.md"
RAW = COMPARISON / "results-2026-08-14.json"
TABLE_START = "<!-- results table begins — tests/test_asvs_probe.py reads it against the JSON -->"
TABLE_END = "<!-- results table ends -->"


def _report_rows() -> dict[tuple[str, str], tuple[int, int, int]]:
    """(arm, app) → (lines, gate findings, scanner) as the report's table states them."""
    text = REPORT.read_text(encoding="utf-8")
    block = text.split(TABLE_START, 1)[1].split(TABLE_END, 1)[0]
    rows = {}
    for line in block.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 6 and cells[0] in ("ctrl", "review", "skill"):
            rows[(cells[0], cells[1])] = (int(cells[2]), int(cells[3]), int(cells[5]))
    return rows


def test_the_report_matches_the_raw_measurement() -> None:
    """The numbers in the report come from the measurement file, not from memory."""
    raw = {(r["side"], r["app"]): r for r in json.loads(RAW.read_text(encoding="utf-8"))}
    report = _report_rows()
    assert set(report) == set(raw), "the report and the raw data list different apps"
    for key, (lines, findings, semgrep) in report.items():
        row = raw[key]
        assert (lines, findings, row["semgrep"]) == (row["py_lines"], row["gate_findings"], semgrep)


def test_the_report_records_the_conditions_it_was_measured_under() -> None:
    """A result with no model, date or spec recorded cannot be compared with the next one."""
    text = REPORT.read_text(encoding="utf-8")
    for required in ("claude-opus-5", "2026-08-14", "spec-notes-app.md", "N |"):
        assert required in text, f"the report does not record: {required}"


def test_an_empty_directory_answers_not_applicable(tmp_path: pathlib.Path) -> None:
    """Nothing to judge is `None`, not a pass — an app that died half-built is not good."""
    result = probe(tmp_path)
    assert result["V4.1.1-ownership-filter"] is None
    assert result["V4.2.2-csrf"] is None
    assert result["V13.2.1-api-requires-auth"] is None
    assert result["V6.4.1-secret-not-hardcoded"] is None


# ------------------- the tree the probe expects, and what must never be read
#
# Pointed at a real repository the first time, **4,171 of the 4,299 files it read
# were library sources**, and three answers flipped to "failed" on evidence such as
# a framework's own development key and a database library's formatted statement.
#
# Apps generated in a comparison never carry an environment with them, so this
# precondition went unwritten — and **a coincidence is not a mechanism**.

VENDORED = {
    ".venv/lib/python3.13/site-packages/flask/sansio/app.py": (
        "class Flask:\n"
        "    def make_config(self):\n"
        "        SECRET_KEY = 'development key'\n"
        "        return SECRET_KEY\n"
    ),
    ".venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py": (
        "def go(conn, name):\n    return conn.execute(f'SELECT * FROM {name}')\n"
    ),
    "node_modules/pkg/tool.py": 'SECRET_KEY = "leaked-from-a-dependency"\n',
}


def test_a_virtualenv_in_the_tree_changes_no_answer(tmp_path: pathlib.Path) -> None:
    """Library code must not count as the project's work, on any item."""
    before = probe(_plant(tmp_path / "clean", SECURE_APP))
    after = probe(_plant(tmp_path / "vendored", {**SECURE_APP, **VENDORED}))

    assert after == before, (
        f"answers moved because of code the app did not write: {before} → {after}"
    )


def test_the_probe_reads_only_the_projects_own_files(tmp_path: pathlib.Path) -> None:
    """The direct direction — no file read may sit under an environment directory."""
    root = _plant(tmp_path / "vendored", {**SECURE_APP, **VENDORED})

    read = python_files(root)

    assert read, "nothing was read at all — a check green for want of input"
    assert all(NOT_OUR_CODE.isdisjoint(p.parts) for p in read), sorted(str(p) for p in read)


def test_writing_about_a_hardcoded_secret_in_a_comment_is_not_having_one(
    tmp_path: pathlib.Path,
) -> None:
    """A comment *about* a secret is not a secret.

    Found on itself: the probe's own comment explaining that a hardcoded
    development key is a bad example was counted as evidence that the repository
    had hardcoded a secret.
    """
    app = dict(SECURE_APP)
    app["app/notes.py"] = (
        '"""never write SECRET_KEY = \'dev\' inline — read it from the environment"""\n\n'
        "# the wrong way: SECRET_KEY = 'hardcoded'\n"
        "TITLE = 'notes'\n"
    )

    assert probe(_plant(tmp_path / "prose", app))["V6.4.1-secret-not-hardcoded"] is not False


# ------------------ a *better* shape must not be punished — the fifth, sixth and seventh
#
# All three below come from a real repository, not from imagination: the
# instrument reported that a project with a full manual assessment failed three
# items, and each one turned out to be an idiom it did not know — a better one.

ROLE_GUARDED = {
    "app/__init__.py": "SECRET_KEY = __import__('os').environ['SECRET_KEY']\n",
    "app/lookup.py": (
        "from . import db\n\n\n"
        "def by_id(model, raw_id):\n"
        "    return db.session.get(model, raw_id)\n"
    ),
    "app/admin.py": (
        "from .lookup import by_id\nfrom .models import Team\n"
        "from .roles import require_admin\n\n\n"
        "def get_team(actor, team_id):\n"
        "    require_admin(actor)\n"
        "    return by_id(Team, team_id)\n"
    ),
}

NESTED_SCOPE = {
    "app/__init__.py": "SECRET_KEY = __import__('os').environ['SECRET_KEY']\n",
    "app/lookup.py": (
        "from . import db\n\n\n"
        "def by_id(model, raw_id):\n"
        "    return db.session.get(model, raw_id)\n"
    ),
    "app/risk.py": (
        "from .lookup import by_id\nfrom .models import Todo\n\n\n"
        "def at_risk(owner):\n"
        "    mine = Todo.query.filter_by(user_id=owner.id).all()\n\n"
        "    def walk(todo_id):\n"
        "        todo = by_id(Todo, todo_id)\n"
        "        return todo is not None\n\n"
        "    return [t for t in mine if walk(t.id)]\n"
    ),
}


def test_a_role_check_counts_as_thinking_about_authorization(tmp_path: pathlib.Path) -> None:
    """A role check is a check, not a forgotten owner.

    Naming authorisation in its own function is a better shape than comparing an
    owner id inline everywhere. An instrument scoring it lower teaches people to
    write worse code.
    """
    result = probe(_plant(tmp_path / "roles", ROLE_GUARDED))

    assert result["V4.1.1-ownership-filter"] is not False, result


def test_a_closure_inherits_the_guard_of_the_scope_that_holds_it(tmp_path: pathlib.Path) -> None:
    """A nested function sits behind its parent's guard structurally — judge them together."""
    result = probe(_plant(tmp_path / "nested", NESTED_SCOPE))

    assert result["V4.1.1-ownership-filter"] is not False, result


def test_sql_built_from_a_constant_is_not_sql_built_from_input(tmp_path: pathlib.Path) -> None:
    """A string joined to a module constant is not a string joined to a request.

    The opposite direction lives in the violating-app test, which builds a
    statement out of a variable — if this item loosened enough to let that pass,
    that test goes red.
    """
    app = dict(SECURE_APP)
    app["app/tuning.py"] = (
        'ISOLATION_LEVEL = "READ COMMITTED"\n\n\n'
        "def tune(cursor):\n"
        '    cursor.execute(f"SET SESSION TRANSACTION ISOLATION LEVEL {ISOLATION_LEVEL}")\n'
    )

    assert probe(_plant(tmp_path / "constant-sql", app))["V5.3.4-no-sql-string-building"] is True


# ------------------------------------------- a file the probe cannot parse


def test_a_file_that_does_not_parse_does_not_stop_the_run(tmp_path: pathlib.Path) -> None:
    """**Broken syntax skips the file, never the measurement.**

    A generated app that failed halfway leaves one unparseable file behind. Raising
    there would lose every answer about every other file, and reporting nothing is
    how an app that died half-built ends up looking clean.
    """
    root = _plant(tmp_path / "app", {**SECURE_APP, "app/broken.py": "def (:\n"})

    answers = probe(root)

    assert set(answers) == set(CHECKS)
    assert answers["V14.1.3-no-debug-console"] is True


def test_an_unparseable_file_is_still_searched_as_text(tmp_path: pathlib.Path) -> None:
    """Comments cannot be stripped from what will not parse, so it is read raw.

    Not seeing it at all would be the worse failure: a hardcoded secret in a file
    with a syntax error is still a hardcoded secret.
    """
    root = _plant(
        tmp_path / "app",
        {
            "run.py": "from app import create_app\n",
            "app/__init__.py": 'SECRET_KEY = "dev-secret"\ndef (:\n',
        },
    )

    assert probe(root)["V6.4.1-secret-not-hardcoded"] is False


def test_a_formatted_statement_built_by_a_method_call_is_caught(tmp_path: pathlib.Path) -> None:
    """`"...".format(value)` is the third way to build a statement out of input."""
    root = _plant(
        tmp_path / "app",
        {
            "run.py": "from app import create_app\n",
            "app/__init__.py": (
                "from . import db\n\n\n"
                "def search(term):\n"
                '    return db.session.execute("SELECT * FROM t WHERE a = {}".format(term))\n'
            ),
        },
    )

    assert probe(root)["V5.3.4-no-sql-string-building"] is False


def test_a_decorator_that_is_an_attribute_is_read_too(tmp_path: pathlib.Path) -> None:
    """`@bp.route(...)` and `@login_required` sit on the same view — both are names."""
    root = _plant(
        tmp_path / "app",
        {
            "run.py": "from app import create_app\n",
            "app/__init__.py": (
                "from flask import Blueprint\n"
                "from flask_login import login_required\n\n"
                'api = Blueprint("api", __name__, url_prefix="/api")\n\n\n'
                '@api.route("/notes")\n'
                "@login_required\n"
                "def notes():\n"
                "    return {}\n"
            ),
        },
    )

    assert probe(root)["V13.2.1-api-requires-auth"] is True


def test_a_server_started_without_the_debug_flag_is_not_a_debug_console(
    tmp_path: pathlib.Path,
) -> None:
    """`run(host=...)` and `run(debug=False)` are both fine — only a true flag is not."""
    root = _plant(
        tmp_path / "app",
        {
            "run.py": (
                "from app import create_app\n\n"
                "app = create_app()\n"
                'app.run(host="127.0.0.1", port=5000, debug=False)\n'
            ),
            "app/__init__.py": "def create_app():\n    return None\n",
        },
    )

    assert probe(root)["V14.1.3-no-debug-console"] is True


def test_a_statement_executed_from_a_variable_is_not_string_building(
    tmp_path: pathlib.Path,
) -> None:
    """A statement handed over whole is not a statement built out of input.

    The item asks whether SQL is *joined together*, not whether SQL is executed.
    Reporting every `execute(...)` would fail every application that uses a
    database at all, which is no measurement.
    """
    root = _plant(
        tmp_path / "app",
        {
            "run.py": "from app import create_app\n",
            "app/__init__.py": (
                "from . import db\n\n\n"
                "def counted(statement):\n"
                "    return db.session.execute(statement)\n"
            ),
        },
    )

    assert probe(root)["V5.3.4-no-sql-string-building"] is True


def test_a_decorator_the_probe_cannot_read_is_not_credited_as_a_guard(
    tmp_path: pathlib.Path,
) -> None:
    """A decorator taken out of a registry names nothing the syntax can read.

    Python allows any expression there, so the loop must survive one — and must
    not award the view a guard it cannot see. Failing the item is the honest
    answer: the instrument reports what it can prove, and this it cannot.
    """
    root = _plant(
        tmp_path / "app",
        {
            "run.py": "from app import create_app\n",
            "app/__init__.py": (
                "from flask import Blueprint\n"
                "from flask_login import login_required\n\n"
                'api = Blueprint("api", __name__, url_prefix="/api")\n'
                'guards = {"api": login_required}\n\n\n'
                '@api.route("/notes")\n'
                '@guards["api"]\n'
                "def notes():\n"
                "    return {}\n"
            ),
        },
    )

    assert probe(root)["V13.2.1-api-requires-auth"] is False
