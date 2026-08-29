"""Each scanner is shown a project that violates it and one that does not.

A scanner that returns 0 for everything is indistinguishable from a clean
project, and that is the failure mode nobody notices: CI stays green and the
report says there is nothing to report. So every scanner gets a **pair** — one
tree that breaks its rule, one that keeps it, differing in exactly the thing the
scanner is about.

The third case matters as much as the first two: **not-applicable must not read
as clean**. Pointed at a project with no Dockerfile, a scanner prints `NA:` and
exits 0, and that has to be visible in the output. Otherwise a whole class of
"we never looked" gets filed under "we looked and it was fine".
"""

from __future__ import annotations

import importlib
import json
from typing import TYPE_CHECKING, Any, NamedTuple

import bundle
import pytest

from verifiable_gates.checks import (
    scan_adr_index,
    scan_dockerfile_digest,
    scan_entrypoint_debug,
    scan_install_pinning,
    scan_service_layer,
    scan_templates_inline,
    scan_workflow_pinning,
    scan_write_discipline,
)

if TYPE_CHECKING:
    import pathlib


class Case(NamedTuple):
    """A scanner plus the smallest pair of trees that tells its two answers apart."""

    module: Any
    dirty: dict[str, str]
    clean: dict[str, str]
    config: dict[str, Any] | None
    gate: str


def build(
    root: pathlib.Path, files: dict[str, str], config: dict[str, Any] | None = None
) -> pathlib.Path:
    """Write a tiny project tree. `config` becomes scaffold.json when given."""
    if config is not None:
        (root / "scaffold.json").write_text(json.dumps(config), encoding="utf-8")
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


PINNED_ACTION = "jobs:\n  a:\n    steps:\n      - uses: actions/checkout@" + "a" * 40 + "\n"
FLOATING_ACTION = "jobs:\n  a:\n    steps:\n      - uses: actions/checkout@v4\n"
CLEAN_ENTRYPOINT = (
    '"""No debug=True here — the words in this string must not trip it."""\n'
    "app = object()\napp.run()\n"
)
FLOATING_INSTALL = "jobs:\n  a:\n    steps:\n      - run: pip install ruff\n"
PINNED_INSTALL = (
    "jobs:\n  a:\n    steps:\n"
    "      # pip install ruff <- a comment must not count\n"
    "      - run: pip install --require-hashes -r pins/dev/requirements.txt\n"
)

CASES = [
    pytest.param(
        Case(
            scan_workflow_pinning,
            {".github/workflows/ci.yml": FLOATING_ACTION},
            {".github/workflows/ci.yml": PINNED_ACTION},
            None,
            "actions-sha-pinned",
        ),
        id="workflow-pinning",
    ),
    pytest.param(
        Case(
            scan_dockerfile_digest,
            {"Dockerfile": "FROM python:3.13-slim\n"},
            {"Dockerfile": "FROM python@sha256:" + "b" * 64 + "\n"},
            {"dockerfiles": ["Dockerfile"]},
            "image-digest-pinned",
        ),
        id="dockerfile-digest",
    ),
    pytest.param(
        Case(
            scan_entrypoint_debug,
            {"run.py": "app = object()\napp.run(debug=True)\n"},
            {"run.py": CLEAN_ENTRYPOINT},
            {"entrypoints": ["run.py"]},
            "no-debug-entrypoint",
        ),
        id="entrypoint-debug",
    ),
    pytest.param(
        Case(
            scan_install_pinning,
            {".github/workflows/ci.yml": FLOATING_INSTALL},
            {".github/workflows/ci.yml": PINNED_INSTALL},
            None,
            "ci-tools-hash-pinned",
        ),
        id="install-pinning",
    ),
    pytest.param(
        Case(
            scan_service_layer,
            {"app/services/todos.py": "from flask import request\n"},
            {"app/services/todos.py": "from flask import current_app\n"},
            {"services_path": "app/services"},
            "logic-knows-no-http",
        ),
        id="service-layer",
    ),
    pytest.param(
        Case(
            scan_templates_inline,
            {"app/templates/x.html": '<button onclick="go()">go</button>\n'},
            {"app/templates/x.html": '<button data-go="1">go</button>\n'},
            {"templates_path": "app/templates"},
            "csp-no-inline",
        ),
        id="templates-inline",
    ),
    pytest.param(
        Case(
            scan_write_discipline,
            {"app/routes.py": "db.session.delete(row)\n"},
            {"app/routes.py": "cache.delete(key)\nrow.deleted_at = now()\n"},
            {"src_path": "app", "purge_paths": ["app/purge.py"]},
            "delete-means-soft-delete",
        ),
        id="write-discipline",
    ),
]


@pytest.mark.parametrize("case", CASES)
def test_a_scanner_finds_the_violation(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], case: Case
) -> None:
    root = build(tmp_path, case.dirty, case.config)
    assert case.module.main(root) == 1, "the violating tree was reported as clean"
    assert case.gate in capsys.readouterr().out, "the finding does not name its gate"


@pytest.mark.parametrize("case", CASES)
def test_a_scanner_stays_quiet_on_a_clean_tree(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], case: Case
) -> None:
    """The other direction — a rule that fires on everything is not a rule."""
    root = build(tmp_path, case.clean, case.config)
    assert case.module.main(root) == 0, "a clean tree was reported as a violation"
    assert case.gate not in capsys.readouterr().out


# Nothing configured, nothing at the default path: N/A. A key the project wrote
# itself is a different case, judged below.
NOT_APPLICABLE = [
    pytest.param(scan_workflow_pinning, id="no-workflows"),
    pytest.param(scan_dockerfile_digest, id="no-dockerfile"),
    pytest.param(scan_entrypoint_debug, id="no-entrypoint"),
    pytest.param(scan_install_pinning, id="nothing-that-installs"),
    pytest.param(scan_service_layer, id="no-service-layer"),
    pytest.param(scan_templates_inline, id="no-templates"),
    pytest.param(scan_write_discipline, id="no-source"),
    pytest.param(scan_adr_index, id="no-adrs"),
]


@pytest.mark.parametrize("module", NOT_APPLICABLE)
def test_nothing_to_check_says_so_out_loud(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    module: Any,  # noqa: ANN401 — the parameter is a module object
) -> None:
    """Silence would file "we never looked" under "we looked and it was fine"."""
    root = build(tmp_path, {}, {"_comment": "nothing named"})
    assert module.main(root) == 0
    assert capsys.readouterr().out.startswith("NA:"), "a not-applicable run must announce itself"


# A path the project named in scaffold.json and does not have. An outside audit
# on 2026-08-29 planted `"dockerfiles": ["docker/Dockerfile"]` beside a dirty
# `Dockerfile` at the root and got `NA: no Dockerfile`, exit 0 — one wrong line
# of configuration had turned "checked and clean" into "nothing to check" with
# the same exit code. A configured path that is missing is a broken
# configuration, and a broken configuration is a finding.
class Misconfigured(NamedTuple):
    """A scanner, a path the project named and does not have, and the tree beside it."""

    module: Any
    config: dict[str, Any]
    files: dict[str, str]
    gate: str


MISCONFIGURED = [
    pytest.param(
        Misconfigured(
            scan_dockerfile_digest,
            {"dockerfiles": ["docker/Dockerfile"]},
            {"Dockerfile": "FROM python:3.13-slim\n"},
            "image-digest-pinned",
        ),
        id="dockerfile-named-elsewhere",
    ),
    pytest.param(
        Misconfigured(
            scan_entrypoint_debug,
            {"entrypoints": ["serve.py"]},
            {"run.py": "app = object()\napp.run(debug=True)\n"},
            "no-debug-entrypoint",
        ),
        id="entrypoint-named-elsewhere",
    ),
    pytest.param(
        Misconfigured(
            scan_service_layer,
            {"services_path": "src/services"},
            {"app/services/todos.py": "from flask import request\n"},
            "logic-knows-no-http",
        ),
        id="services-named-elsewhere",
    ),
    pytest.param(
        Misconfigured(
            scan_templates_inline,
            {"templates_path": "src/templates"},
            {"app/templates/x.html": '<button onclick="go()">go</button>\n'},
            "csp-no-inline",
        ),
        id="templates-named-elsewhere",
    ),
    pytest.param(
        Misconfigured(
            scan_write_discipline,
            {"src_path": "src"},
            {"app/routes.py": "db.session.delete(row)\n"},
            "delete-means-soft-delete",
        ),
        id="source-named-elsewhere",
    ),
    pytest.param(
        Misconfigured(
            scan_adr_index,
            {"adr_path": "docs/decisions"},
            {"docs/adr/0002-b.md": "# 0002\n"},
            "adr-index-complete",
        ),
        id="adrs-named-elsewhere",
    ),
]


@pytest.mark.parametrize("case", MISCONFIGURED)
def test_a_configured_path_that_is_missing_is_a_finding_not_na(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], case: Misconfigured
) -> None:
    """The dirty tree at the default path is beside the point: the config is wrong."""
    root = build(tmp_path, case.files, case.config)
    (key, named), *_ = case.config.items()
    named = named[0] if isinstance(named, list) else named
    assert case.module.main(root) == 1, "a path the project named and does not have was excused"
    out = capsys.readouterr().out
    assert not out.startswith("NA:"), "a broken configuration was reported as nothing to check"
    assert out.startswith(f"{case.gate}: "), "the finding does not name its gate"
    assert key in out, "the finding does not name the configuration key"
    assert named in out, "the finding does not say which path is missing"


def test_a_dockerfile_named_and_present_beside_one_named_and_missing_judges_both(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One missing name is a finding on its own; it does not hide the file that is there."""
    pinned = "FROM python@sha256:" + "b" * 64 + "\n"
    config = {"dockerfiles": ["Dockerfile", "docker/Dockerfile"]}
    root = build(tmp_path, {"Dockerfile": pinned}, config)
    assert scan_dockerfile_digest.main(root) == 1
    out = capsys.readouterr().out
    assert "docker/Dockerfile" in out
    assert out.count("image-digest-pinned:") == 1, "the pinned file that exists is clean"


def test_a_candidate_list_with_some_entrypoints_present_is_not_misconfigured(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`entrypoints` lists candidates, so one absent name is fine while another exists."""
    config = {"entrypoints": ["run.py", "wsgi.py"]}
    root = build(tmp_path, {"run.py": CLEAN_ENTRYPOINT}, config)
    assert scan_entrypoint_debug.main(root) == 0
    assert capsys.readouterr().out == ""


# --------------------------------------------- an exemption covers only its case
#
# Two exemptions read wider than the case they were written for — an outside
# audit on 2026-08-29 planted a line inside each and got a clean exit.


@pytest.mark.parametrize(
    ("command", "exit_code"),
    [
        ("pip install --no-deps -e .", 0),
        ("pip install --no-deps ./tools", 0),
        ("pip install --no-deps -e .[dev]", 0),
        ("pip install --no-deps --index-url https://mirror.example -e .", 0),
        ("pip install --no-deps -e . && pytest -q", 0),
        # The audit's line: both halves present, and a package fetched anyway.
        ("pip install --no-deps requests .", 1),
        ("pip install --no-deps . requests", 1),
        ("pip install --no-deps -r requirements.txt .", 1),
        ("pip install --no-deps -e . ; pip install requests", 1),
        ("pip install --no-deps", 1),
    ],
    ids=lambda value: value if isinstance(value, str) else str(value),
)
def test_the_local_install_exemption_needs_every_target_to_be_local(
    tmp_path: pathlib.Path, command: str, exit_code: int
) -> None:
    """`--no-deps` plus a local target excuses a line only when nothing else is on it."""
    root = build(
        tmp_path, {".github/workflows/ci.yml": f"jobs:\n  a:\n    steps:\n      - run: {command}\n"}
    )
    assert scan_install_pinning.main(root) == exit_code, command


@pytest.mark.parametrize(
    ("ref", "exit_code"),
    [
        ("docker://alpine@sha256:" + "c" * 64, 0),
        ("./.github/actions/setup", 0),
        # The audit's line: a floating image tag behind a prefix that was exempt whole.
        ("docker://alpine:latest", 1),
        ("docker://ghcr.io/org/tool:1.2", 1),
        ("docker://alpine@sha256:" + "c" * 63, 1),
    ],
    ids=lambda value: value if isinstance(value, str) else str(value),
)
def test_a_docker_step_is_held_to_a_digest_not_excused(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], ref: str, exit_code: int
) -> None:
    """`docker://` runs an image with the job's permissions; a tag on it can move."""
    root = build(
        tmp_path, {".github/workflows/ci.yml": f"jobs:\n  a:\n    steps:\n      - uses: {ref}\n"}
    )
    assert scan_workflow_pinning.main(root) == exit_code, ref
    assert (ref in capsys.readouterr().out) is bool(exit_code)


# ------------------------------------------------------------ composite actions
#
# A step moved into `.github/actions/<name>/action.yml` runs with the calling
# workflow's permissions and used to be out of both pinning scanners' sight: an
# outside audit on 2026-08-29 planted a floating `uses:` and an unpinned
# `pip install` there and got exit 0 from each. The workflow that calls the
# action is clean on its own, so a scanner that read only `workflows/` had
# nothing to report.

ACTION = ".github/actions/setup/action.yml"
CALLER = {
    ".github/workflows/ci.yml": "jobs:\n  a:\n    steps:\n      - uses: ./.github/actions/setup\n"
}
COMPOSITE_HEAD = "name: setup\nruns:\n  using: composite\n  steps:\n"


class Composite(NamedTuple):
    """A pinning scanner and the composite-action step that breaks or keeps its rule."""

    module: Any
    dirty: str
    clean: str
    gate: str


COMPOSITE = [
    pytest.param(
        Composite(
            scan_workflow_pinning,
            "    - uses: actions/checkout@v4\n",
            "    - uses: actions/checkout@" + "a" * 40 + "\n",
            "actions-sha-pinned",
        ),
        id="workflow-pinning",
    ),
    pytest.param(
        Composite(
            scan_install_pinning,
            "    - run: pip install ruff\n      shell: bash\n",
            "    - run: pip install --require-hashes -r pins/requirements.txt\n      shell: bash\n",
            "ci-tools-hash-pinned",
        ),
        id="install-pinning",
    ),
]


@pytest.mark.parametrize("case", COMPOSITE)
def test_a_composite_action_is_judged_like_the_workflow_that_calls_it(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], case: Composite
) -> None:
    root = build(tmp_path, {**CALLER, ACTION: COMPOSITE_HEAD + case.dirty})
    assert case.module.main(root) == 1, "a step hidden in a composite action was not judged"
    out = capsys.readouterr().out
    assert out.startswith(f"{case.gate}: "), "the finding does not name its gate"
    assert ACTION in out, "the finding does not say which action file it is in"


@pytest.mark.parametrize("case", COMPOSITE)
def test_a_clean_composite_action_is_left_alone(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], case: Composite
) -> None:
    root = build(tmp_path, {**CALLER, ACTION: COMPOSITE_HEAD + case.clean})
    assert case.module.main(root) == 0, "a pinned composite action was reported"
    assert case.gate not in capsys.readouterr().out


@pytest.mark.parametrize("case", COMPOSITE)
def test_a_composite_action_alone_is_something_to_check(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], case: Composite
) -> None:
    """No `workflows/` directory at all, but an action file: that is not N/A."""
    root = build(tmp_path, {ACTION: COMPOSITE_HEAD + case.dirty})
    assert case.module.main(root) == 1
    assert not capsys.readouterr().out.startswith("NA:")


# ---------------------------------------------------------------- the ADR index
#
# Four findings from one scanner, so each gets its own case rather than sharing
# the pair above: a shared case would prove one of them and imply the rest.

ADR_BODY = "# 0001 — a decision\n"
ADR_CONFIG = {"adr_path": "docs/adr"}


def test_adr_index_reports_a_record_missing_from_the_index(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = {"docs/adr/0001-a.md": ADR_BODY, "docs/adr/README.md": "| index |\n"}
    assert scan_adr_index.main(build(tmp_path, files, ADR_CONFIG)) == 1
    assert "missing from the index" in capsys.readouterr().out


def test_adr_index_reports_an_index_entry_whose_file_is_gone(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = {
        "docs/adr/0001-a.md": ADR_BODY,
        "docs/adr/README.md": "[0001](0001-a.md) [0002](0002-gone.md)\n",
    }
    assert scan_adr_index.main(build(tmp_path, files, ADR_CONFIG)) == 1
    assert "file that is gone" in capsys.readouterr().out


def test_adr_index_reports_a_gap_in_the_numbering(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = {
        "docs/adr/0001-a.md": ADR_BODY,
        "docs/adr/0003-c.md": ADR_BODY,
        "docs/adr/README.md": "[0001](0001-a.md) [0003](0003-c.md)\n",
    }
    assert scan_adr_index.main(build(tmp_path, files, ADR_CONFIG)) == 1
    assert "gap in the numbering" in capsys.readouterr().out


def test_adr_index_reports_records_with_no_index_at_all(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = {"docs/adr/0001-a.md": ADR_BODY}
    assert scan_adr_index.main(build(tmp_path, files, ADR_CONFIG)) == 1
    assert "no README.md index" in capsys.readouterr().out


def test_a_complete_adr_index_is_quiet(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = {
        "docs/adr/0001-a.md": ADR_BODY,
        "docs/adr/0002-b.md": ADR_BODY,
        "docs/adr/README.md": "[0001](0001-a.md) [0002](0002-b.md)\n",
    }
    assert scan_adr_index.main(build(tmp_path, files, ADR_CONFIG)) == 0
    assert "adr-index-complete" not in capsys.readouterr().out


# ---------------------------------------------------------------- the branches the pairs miss
#
# Coverage found these: each is a decision the scanner makes that the pair above
# never exercises, and every one of them is the part a reader would assume works.


def test_a_declared_purge_module_is_allowed_to_delete_for_real(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The exemption is the whole point — without it the rule would ban deleting at all."""
    files = {"app/purge.py": "db.session.delete(row)\n"}
    config = {"src_path": "app", "purge_paths": ["app/purge.py"]}
    assert scan_write_discipline.main(build(tmp_path, files, config)) == 0
    assert "delete-means-soft-delete" not in capsys.readouterr().out


def test_a_commented_out_delete_is_not_a_finding(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = {"app/routes.py": "# db.session.delete(row) — explaining why we do not\n"}
    config = {"src_path": "app", "purge_paths": ["app/purge.py"]}
    assert scan_write_discipline.main(build(tmp_path, files, config)) == 0
    assert "delete-means-soft-delete" not in capsys.readouterr().out


def test_npm_install_is_reported_and_names_the_alternative(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`npm install pkg@x` pins that one package and leaves the tree floating."""
    files = {
        ".github/workflows/ci.yml": "jobs:\n  a:\n    steps:\n      - run: npm install pa11y\n"
    }
    assert scan_install_pinning.main(build(tmp_path, files)) == 1
    assert "use npm ci instead" in capsys.readouterr().out, "the finding has to say what to do"


def test_a_command_split_over_lines_is_judged_whole(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--require-hashes` on the continuation line still counts — otherwise the fix looks broken."""
    files = {
        ".github/workflows/ci.yml": (
            "jobs:\n  a:\n    steps:\n"
            "      - run: pip install \\\n"
            "          --require-hashes -r pins/dev/requirements.txt"
        )
    }
    assert scan_install_pinning.main(build(tmp_path, files)) == 0
    assert "ci-tools-hash-pinned" not in capsys.readouterr().out


def test_a_split_command_that_is_still_unpinned_is_reported(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other direction, so the joining is not just swallowing everything."""
    files = {
        ".github/workflows/ci.yml": (
            "jobs:\n  a:\n    steps:\n      - run: pip install \\\n          ruff mypy"
        )
    }
    assert scan_install_pinning.main(build(tmp_path, files)) == 1
    assert "ci-tools-hash-pinned" in capsys.readouterr().out


def test_importing_the_session_module_is_a_finding(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`import flask_login` reaches the request side without naming a forbidden symbol."""
    files = {"app/services/todos.py": "import flask_login\n"}
    config = {"services_path": "app/services"}
    assert scan_service_layer.main(build(tmp_path, files, config)) == 1
    assert "flask_login" in capsys.readouterr().out


def test_importing_the_session_module_by_from_is_also_a_finding(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = {"app/services/todos.py": "from flask_login import current_user\n"}
    config = {"services_path": "app/services"}
    assert scan_service_layer.main(build(tmp_path, files, config)) == 1
    assert "flask_login" in capsys.readouterr().out


def test_a_command_left_dangling_at_the_end_of_a_file_is_still_judged(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A file ending on a continuation would otherwise drop its last command unseen."""
    files = {
        ".github/workflows/ci.yml": "jobs:\n  a:\n    steps:\n      - run: pip install ruff \\"
    }
    assert scan_install_pinning.main(build(tmp_path, files)) == 1
    assert "ci-tools-hash-pinned" in capsys.readouterr().out


def test_an_ordinary_import_in_the_service_layer_is_left_alone(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The rule is about the request side, not about importing."""
    files = {"app/services/todos.py": "import datetime\nfrom collections import Counter\n"}
    config = {"services_path": "app/services"}
    assert scan_service_layer.main(build(tmp_path, files, config)) == 0
    assert "logic-knows-no-http" not in capsys.readouterr().out


def test_installing_the_checkout_itself_is_not_an_index_install(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Found by pointing this scanner at its own repository — see tests/test_dogfood.py."""
    files = {
        ".github/workflows/ci.yml": (
            "jobs:\n  a:\n    steps:\n      - run: pip install --no-deps -e .\n"
        )
    }
    assert scan_install_pinning.main(build(tmp_path, files)) == 0
    assert "ci-tools-hash-pinned" not in capsys.readouterr().out


def test_no_deps_alone_does_not_excuse_reaching_the_index(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Half the exemption is not the exemption — this still fetches from PyPI."""
    files = {
        ".github/workflows/ci.yml": (
            "jobs:\n  a:\n    steps:\n      - run: pip install --no-deps requests\n"
        )
    }
    assert scan_install_pinning.main(build(tmp_path, files)) == 1
    assert "ci-tools-hash-pinned" in capsys.readouterr().out


def test_a_local_install_that_still_resolves_dependencies_is_reported(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other half — `-e .` without `--no-deps` pulls the whole tree in unpinned."""
    files = {".github/workflows/ci.yml": "jobs:\n  a:\n    steps:\n      - run: pip install -e .\n"}
    assert scan_install_pinning.main(build(tmp_path, files)) == 1
    assert "ci-tools-hash-pinned" in capsys.readouterr().out


# ------------------------------------------------- a project that configured nothing


@pytest.mark.parametrize("name", bundle.scanner_ids(), ids=lambda n: n)
def test_a_scanner_survives_a_project_with_no_scaffold_file(
    name: str, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No `scaffold.json` means "nothing configured", never a traceback.

    Six of the seven scanners that read the file read it unguarded, so pointing
    one at a project that had not configured the bundle raised FileNotFoundError
    out of `main()`. The dogfood check found it by running them here, where there
    is no scaffold file — and a traceback is the worst of the three answers,
    because it is neither a finding, nor N/A, nor a pass, and the exit code that
    reaches a caller is whatever the shell made of the crash.
    """
    module = importlib.import_module(f"verifiable_gates.checks.{name.removesuffix('.py')}")
    assert not (tmp_path / "scaffold.json").exists()

    result = module.main(tmp_path)
    output = capsys.readouterr().out

    assert result == 0, f"an unconfigured project is not a finding:\n{output}"
    assert output.startswith("NA:"), (
        f"with nothing configured there is nothing to check, so the answer is N/A: {output!r}"
    )


# ---------------------------------------------------------------- Dockerfile spellings

DIGEST = "@sha256:" + "0" * 64


@pytest.mark.parametrize(
    ("dockerfile", "named"),
    [
        pytest.param("from ubuntu:22.04\n", "FROM ubuntu:22.04", id="lowercase-from"),
        pytest.param(
            f"FROM ubuntu{DIGEST}\nCOPY --from=ghcr.io/x/y:latest /a /b\n",
            "COPY --from ghcr.io/x/y:latest",
            id="copy-from-an-unpinned-image",
        ),
        pytest.param(
            f"FROM ubuntu{DIGEST}\ncopy --chown=1 --from=ghcr.io/x/y:latest /a /b\n",
            "COPY --from ghcr.io/x/y:latest",
            id="copy-from-behind-another-flag",
        ),
        pytest.param(
            "FROM --platform=linux/amd64 ubuntu:22.04\n",
            "FROM ubuntu:22.04",
            id="platform-flag-is-not-the-image",
        ),
    ],
)
def test_the_dockerfile_scanner_judges_the_image_however_it_is_written(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], dockerfile: str, named: str
) -> None:
    """Dockerfile instructions are case-insensitive and images also arrive via COPY.

    An outside audit on 2026-08-29 planted each of these and watched the scanner
    stay green: a rule that reads only uppercase `FROM` decides the spelling,
    not the image. The finding must also name the image, not a flag in front of it.
    """
    root = build(tmp_path, {"Dockerfile": dockerfile}, {"dockerfiles": ["Dockerfile"]})

    assert scan_dockerfile_digest.main(root) == 1
    assert named in capsys.readouterr().out


@pytest.mark.parametrize(
    "dockerfile",
    [
        pytest.param(
            f"FROM python{DIGEST} AS build\nFROM python{DIGEST}\nCOPY --from=BUILD /a /b\n",
            id="stage-alias-any-case",
        ),
        pytest.param(
            f"FROM python{DIGEST} AS build\nFROM python{DIGEST}\nCOPY --from=0 /a /b\n",
            id="stage-index",
        ),
        pytest.param(
            f"from python{DIGEST}\ncopy --from=ghcr.io/x/z{DIGEST} /a /b\n",
            id="all-pinned-lowercase",
        ),
    ],
)
def test_the_dockerfile_scanner_stays_quiet_when_every_image_is_pinned(
    tmp_path: pathlib.Path, dockerfile: str
) -> None:
    """A stage alias or index is a local name, not an image — refusing it is a false red."""
    root = build(tmp_path, {"Dockerfile": dockerfile}, {"dockerfiles": ["Dockerfile"]})

    assert scan_dockerfile_digest.main(root) == 0
