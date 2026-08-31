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
import re
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
    from types import ModuleType


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


PINNED_ACTION = "jobs:\n  a:\n    steps:\n      - uses: actions/checkout@" + "a" * 40 + " # v4\n"
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


@pytest.mark.parametrize("where", ["Dockerfile.prod", "docker/Dockerfile", "deploy/Dockerfile.web"])
def test_an_unnamed_dockerfile_away_from_the_root_is_not_nothing(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], where: str
) -> None:
    """No scaffold.json, no root Dockerfile, one somewhere else: that is a finding, not NA."""
    root = build(tmp_path, {where: "FROM python:3.13-slim\n"})
    assert scan_dockerfile_digest.main(root) == 1
    out = capsys.readouterr().out
    assert where in out
    assert "name it under `dockerfiles`" in out


def test_a_dockerfile_under_a_hidden_directory_is_somebody_elses(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`.venv/…/Dockerfile` is a copy of something else — still NA."""
    root = build(tmp_path, {".venv/lib/x/Dockerfile": "FROM python:3.13-slim\n"})
    assert scan_dockerfile_digest.main(root) == 0
    assert capsys.readouterr().out.startswith("NA:")


def test_a_project_that_named_its_dockerfiles_has_decided(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With `dockerfiles` written down, a `Dockerfile.prod` beside it is the project's own."""
    files = {
        "Dockerfile": "FROM python@sha256:" + "b" * 64 + "\n",
        "Dockerfile.prod": "FROM python:3.13-slim\n",
    }
    root = build(tmp_path, files, {"dockerfiles": ["Dockerfile"]})
    assert scan_dockerfile_digest.main(root) == 0
    assert "Dockerfile.prod" not in capsys.readouterr().out


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
        ("pip install --no-deps --no-build-isolation -e .", 0),
        ("pip install --no-deps --no-build-isolation ./tools", 0),
        ("pip install --no-deps --no-build-isolation -e .[dev]", 0),
        ("pip install --no-deps --no-build-isolation --index-url https://mirror.example -e .", 0),
        ("pip install --no-deps --no-build-isolation -e . && pytest -q", 0),
        # Without `--no-build-isolation` pip fetches the build backend from the
        # index, unhashed — the same fetch `python -m build` makes (2026-08-30).
        ("pip install --no-deps -e .", 1),
        # The audit's line: both halves present, and a package fetched anyway.
        ("pip install --no-deps --no-build-isolation requests .", 1),
        ("pip install --no-deps --no-build-isolation . requests", 1),
        ("pip install --no-deps --no-build-isolation -r requirements.txt .", 1),
        ("pip install --no-deps --no-build-isolation -e . ; pip install requests", 1),
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
    ("command", "exit_code"),
    [
        # pip's global options sit before the subcommand; the release job's own
        # line was the first of these and passed for five releases (2026-08-30).
        ("pip --python sbom-env/bin/python install dist/*.whl", 1),
        ("pip --python sbom-env/bin/python install --require-hashes -r pins/x.txt", 0),
        ("pip --python sbom-env/bin/python install --no-deps --no-build-isolation ./dist/*.whl", 0),
        ("pip -q --no-cache-dir install ruff", 1),
        ("pip --python=.venv/bin/python install ruff", 1),
        ("python -m pip install ruff", 1),
        # A build backend is a tool CI installs for itself — with no `pip` on the line.
        ("python -m build tagged --outdir dist", 1),
        ("python3 -m build .", 1),
        ("pyproject-build .", 1),
        ("python -m build --no-isolation tagged --outdir dist", 0),
        # pipx resolves from the index like pip does.
        ("pipx install ruff", 1),
        ("pipx run ruff check .", 1),
        # Not an install at all.
        ("python -m build_docs", 0),
        ("echo pip-audit install", 0),
        ("cp installer/pip install.log", 0),
        # Review of 2026-08-30: interpreter spellings with a minor version, the
        # subcommand found after an option value that contains `install`, and
        # build's documented short flag.
        ("pip3.13 install ruff", 1),
        ("python3.13 -m build .", 1),
        ("pip --python /opt/installer/bin/python install --no-deps --no-build-isolation .", 0),
        ("python -m build -n tagged --outdir dist", 0),
        ("pip " + "--x=y " * 40 + "download ruff", 0),
    ],
    ids=lambda value: value if isinstance(value, str) else str(value),
)
def test_every_shape_that_reaches_an_index_is_seen(
    tmp_path: pathlib.Path, command: str, exit_code: int
) -> None:
    """A scanner that reads one spelling of `pip install` excuses every other."""
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


@pytest.mark.parametrize(
    "line",
    [
        "      - uses: actions/checkout@" + "a" * 40 + "\n",
        "      - uses: actions/checkout@" + "a" * 40 + "  # pinned\n",
        "      - uses: >\n          actions/checkout@" + "a" * 40 + "\n",
    ],
)
def test_a_sha_with_no_version_comment_is_a_pin_nobody_can_read(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], line: str
) -> None:
    """The rule is a SHA *with the version in a comment*; a bare SHA is half of it."""
    body = "jobs:\n  a:\n    steps:\n" + line
    assert scan_workflow_pinning.main(build(tmp_path, {".github/workflows/ci.yml": body})) == 1
    assert "pinned with no version comment" in capsys.readouterr().out


@pytest.mark.parametrize("comment", ["# v4", "# v7.0.1", "#v4", "# 4.2.0 — checkout"])
def test_a_sha_with_its_version_in_a_comment_is_the_whole_rule(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], comment: str
) -> None:
    body = "jobs:\n  a:\n    steps:\n      - uses: actions/checkout@" + "a" * 40 + f" {comment}\n"
    assert scan_workflow_pinning.main(build(tmp_path, {".github/workflows/ci.yml": body})) == 0
    assert capsys.readouterr().out == ""


def test_a_folded_uses_comment_may_sit_beside_the_marker(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`uses: > # v4` then the SHA on the next line — one step to the platform,
    wherever the fold put the comment."""
    body = "jobs:\n  a:\n    steps:\n      - uses: > # v4\n          actions/checkout@"
    body += "a" * 40 + "\n"
    assert scan_workflow_pinning.main(build(tmp_path, {".github/workflows/ci.yml": body})) == 0
    assert capsys.readouterr().out == ""


def test_a_docker_digest_needs_no_version_comment(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A digest names the image itself; the version-comment half is the action rule's."""
    body = "jobs:\n  a:\n    steps:\n      - uses: docker://alpine@sha256:" + "0" * 64 + "\n"
    assert scan_workflow_pinning.main(build(tmp_path, {".github/workflows/ci.yml": body})) == 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("quote", ['"', "'"])
def test_a_quoted_uses_value_is_judged_without_its_quotes(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], quote: str
) -> None:
    """`uses: "actions/checkout@<sha>"` is pinned; the closing quote is not part of the ref."""
    sha = "a" * 40
    pinned = f"jobs:\n  a:\n    steps:\n      - uses: {quote}actions/checkout@{sha}{quote} # v4\n"
    floating = f"jobs:\n  a:\n    steps:\n      - uses: {quote}actions/checkout@v4{quote}\n"
    good = build(tmp_path / "p", {".github/workflows/ci.yml": pinned})
    assert scan_workflow_pinning.main(good) == 0
    assert capsys.readouterr().out == ""
    bad = build(tmp_path / "f", {".github/workflows/ci.yml": floating})
    assert scan_workflow_pinning.main(bad) == 1
    assert "actions/checkout@v4" in capsys.readouterr().out


@pytest.mark.parametrize("marker", [">", "|", ">-", "|-"])
def test_a_folded_uses_names_its_action_not_the_fold_marker(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], marker: str
) -> None:
    """`uses: >` then the action on the next line — the finding has to name the action."""
    body = f"jobs:\n  a:\n    steps:\n      - uses: {marker}\n          actions/checkout@v4\n"
    assert scan_workflow_pinning.main(build(tmp_path, {".github/workflows/ci.yml": body})) == 1
    out = capsys.readouterr().out
    assert "actions/checkout@v4" in out
    assert ": >" not in out
    assert ": |" not in out


def test_a_folded_uses_that_is_pinned_is_clean(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    body = "jobs:\n  a:\n    steps:\n      - uses: >\n          actions/checkout@" + "a" * 40
    body += " # v4\n"
    assert scan_workflow_pinning.main(build(tmp_path, {".github/workflows/ci.yml": body})) == 0
    assert "actions-sha-pinned" not in capsys.readouterr().out


def test_a_fold_marker_with_nothing_after_it_is_reported_as_itself(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A dangling `uses: >` at end of file: not a traceback, and still not pinned."""
    body = "jobs:\n  a:\n    steps:\n      - uses: >\n"
    assert scan_workflow_pinning.main(build(tmp_path, {".github/workflows/ci.yml": body})) == 1
    assert ": >" in capsys.readouterr().out


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
            "    - uses: actions/checkout@" + "a" * 40 + " # v4\n",
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


OUTSIDE_ACTION = "ci/actions/setup/action.yml"
OUTSIDE_CALLER = {
    ".github/workflows/ci.yml": "jobs:\n  a:\n    steps:\n      - uses: ./ci/actions/setup\n"
}


@pytest.mark.parametrize("case", COMPOSITE)
def test_a_local_action_outside_dot_github_is_read_too(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], case: Composite
) -> None:
    """GitHub runs `uses: ./ci/actions/setup` like any other — so it is read like any other."""
    root = build(tmp_path, {**OUTSIDE_CALLER, OUTSIDE_ACTION: COMPOSITE_HEAD + case.dirty})
    assert case.module.main(root) == 1, "a local action outside .github/ was not judged"
    assert OUTSIDE_ACTION in capsys.readouterr().out


@pytest.mark.parametrize("case", COMPOSITE)
def test_an_action_calling_an_action_is_followed(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], case: Composite
) -> None:
    """A clean action that calls a dirty one, one level down and spelled `action.yaml`."""
    files = {
        **OUTSIDE_CALLER,
        OUTSIDE_ACTION: COMPOSITE_HEAD + "    - uses: ./ci/actions/inner\n",
        "ci/actions/inner/action.yaml": COMPOSITE_HEAD + case.dirty,
    }
    assert case.module.main(build(tmp_path, files)) == 1
    assert "ci/actions/inner/action.yaml" in capsys.readouterr().out


@pytest.mark.parametrize("marker", [">", "|", ">-"])
@pytest.mark.parametrize("case", COMPOSITE)
def test_a_folded_local_uses_is_followed_like_a_plain_one(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], case: Composite, marker: str
) -> None:
    """`uses: >` then `./ci/actions/setup` on the next line names the same action GitHub runs."""
    caller = f"jobs:\n  a:\n    steps:\n      - uses: {marker}\n          ./ci/actions/setup\n"
    files = {".github/workflows/ci.yml": caller, OUTSIDE_ACTION: COMPOSITE_HEAD + case.dirty}
    assert case.module.main(build(tmp_path, files)) == 1, "a folded local action was not followed"
    assert OUTSIDE_ACTION in capsys.readouterr().out


@pytest.mark.parametrize("case", COMPOSITE)
def test_a_local_action_that_does_not_exist_is_nothing_to_read(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], case: Composite
) -> None:
    """`uses: ./nowhere` with no file behind it: GitHub's problem, not a traceback here."""
    caller = {".github/workflows/ci.yml": "jobs:\n  a:\n    steps:\n      - uses: ./nowhere\n"}
    assert case.module.main(build(tmp_path, caller)) == 0
    assert case.gate not in capsys.readouterr().out


# ------------------------------------------- the bundle's own starting workflow
#
# Installed into an empty directory, the bundle writes `.github/workflows/gates.yml`
# and `gates.yaml`; the two pinning scans then said `pass` on the workflow it had
# just written — nothing of the project's measured (outside audit, 2026-08-30).
# The registry scan is different on purpose: the shipped index is real content
# that has to be true about itself, and `tests/test_box_opens_true.py` holds it
# to *pass*, never NA, so an absent index cannot look like a satisfied one.

TEMPLATE = (bundle.BUNDLE / "ci-template.yml").read_text(encoding="utf-8")
DEFAULT_REGISTRY = (bundle.BUNDLE / "gates.yaml.default").read_text(encoding="utf-8")
STARTING = {".github/workflows/gates.yml": TEMPLATE, "gates.yaml": DEFAULT_REGISTRY}
OWN_SCANNERS = [
    pytest.param(scan_workflow_pinning, id="workflow-pinning"),
    pytest.param(scan_install_pinning, id="install-pinning"),
]


@pytest.mark.parametrize("scanner", OWN_SCANNERS)
def test_the_untouched_starting_workflow_is_nothing_of_yours(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], scanner: ModuleType
) -> None:
    assert scanner.main(build(tmp_path, STARTING)) == 0
    out = capsys.readouterr().out
    assert out.startswith("NA:"), out
    assert "bundle's own" in out


@pytest.mark.parametrize("scanner", OWN_SCANNERS)
def test_a_starting_workflow_with_a_line_added_is_the_projects_and_is_judged(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], scanner: ModuleType
) -> None:
    """One floating action appended: no longer the bundle's, and red for it or not NA."""
    edited = TEMPLATE + "      - uses: evil/act@v1\n      - run: pip install ruff\n"
    files = {**STARTING, ".github/workflows/gates.yml": edited}
    assert scanner.main(build(tmp_path, files)) == 1
    assert not capsys.readouterr().out.startswith("NA:")


@pytest.mark.parametrize("scanner", OWN_SCANNERS)
def test_a_starting_workflow_whose_pin_was_loosened_is_judged(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], scanner: ModuleType
) -> None:
    """The one edit that matters most is not the bundle's any more — and is not NA."""
    loosened = re.sub(r"actions/checkout@[0-9a-f]{40}", "actions/checkout@v7", TEMPLATE)
    files = {**STARTING, ".github/workflows/gates.yml": loosened}
    code = scanner.main(build(tmp_path, files))
    out = capsys.readouterr().out
    assert not out.startswith("NA:"), out
    if scanner is scan_workflow_pinning:
        assert code == 1
        assert "actions/checkout@v7" in out


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


def test_adr_index_reports_two_records_with_one_number(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`0001-a.md` and `0001-b.md`: a dict keyed by number kept one and lost the other silently."""
    files = {
        "docs/adr/0001-a.md": "# a\n",
        "docs/adr/0001-b.md": "# b\n",
        "docs/adr/README.md": "- [0001](0001-a.md)\n- [0001](0001-b.md)\n",
    }
    assert scan_adr_index.main(build(tmp_path, files)) == 1
    assert "number used twice: 0001-a.md, 0001-b.md" in capsys.readouterr().out


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


@pytest.mark.parametrize(
    ("markup", "label"),
    [
        ('<DIV ONCLICK="go()">go</DIV>\n', "inline handler"),
        ('<P STYLE="color:red">x</P>\n', "inline style="),
        ("<STYLE>a {}</STYLE>\n", "inline <style>"),
        ("<style>\na {}\n</style>\n", "inline <style>"),
    ],
)
def test_inline_markup_is_a_finding_in_any_case(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], markup: str, label: str
) -> None:
    """HTML is case-insensitive and the browser blocks `ONCLICK=` exactly as `onclick=`."""
    assert scan_templates_inline.main(build(tmp_path, {"app/templates/x.html": markup})) == 1
    assert label in capsys.readouterr().out


@pytest.mark.parametrize(
    ("markup", "label"),
    [
        ('<button\nonclick="go()">x</button>\n', "inline handler"),
        ('<button\nstyle="color:red">x</button>\n', "inline style="),
        ('<a href="x"/onclick="go()">x</a>\n', "inline handler"),
        ('<script\n  type="module">\nalert(1)\n</script>\n', "inline <script>"),
        ("<div><style\n>a {}</style></div>\n", "inline <style>"),
    ],
)
def test_markup_split_over_lines_is_read_the_way_a_browser_reads_it(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], markup: str, label: str
) -> None:
    """An attribute at column 0 after a wrap, after a `/`, or a tag closing on a later line."""
    assert scan_templates_inline.main(build(tmp_path, {"app/templates/x.html": markup})) == 1
    assert label in capsys.readouterr().out


@pytest.mark.parametrize(
    "markup",
    [
        "<!-- never write onclick= or style= here -->\n<p>x</p>\n",
        "<!-- <script>alert(1)</script> -->\n<p>x</p>\n",
        '<script\n  src="app.js"></script>\n',
        '<script src="app.js"></script>\n',
    ],
)
def test_a_comment_explains_and_a_sourced_script_loads(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], markup: str
) -> None:
    """`<!-- onclick= -->` runs nothing, and `src=` is the allowed shape on any line."""
    assert scan_templates_inline.main(build(tmp_path, {"app/templates/x.html": markup})) == 0
    assert "csp-no-inline" not in capsys.readouterr().out


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


@pytest.mark.parametrize(
    "line",
    [
        "uv tool install ruff",
        "uv add ruff",
        "uvx ruff check .",
        "poetry add ruff",
        "pdm add ruff",
        "pipenv install ruff",
    ],
)
def test_an_installer_with_no_pip_in_the_line_still_resolves_from_the_index(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], line: str
) -> None:
    """The scanner keyed on the word `pip`; these fetch from the index with nothing to hold them."""
    files = {".github/workflows/ci.yml": f"jobs:\n  a:\n    steps:\n      - run: {line}\n"}
    assert scan_install_pinning.main(build(tmp_path, files)) == 1
    assert "resolves from the index with no lock" in capsys.readouterr().out


@pytest.mark.parametrize(
    "line",
    ["uv run --locked pytest", "uv sync --locked", "uv build", "poetry install --sync"],
)
def test_an_install_from_a_lockfile_is_left_alone(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], line: str
) -> None:
    """`uv.lock` and `poetry.lock` carry hashes — the other direction, so the regex is not `uv`."""
    files = {".github/workflows/ci.yml": f"jobs:\n  a:\n    steps:\n      - run: {line}\n"}
    assert scan_install_pinning.main(build(tmp_path, files)) == 0
    assert "ci-tools-hash-pinned" not in capsys.readouterr().out


SCRIPT_CALLERS = [
    "./scripts/setup.sh",
    "bash scripts/setup.sh",
    "sh ./scripts/setup.sh",
    "source scripts/setup.sh",
    ". scripts/setup.sh",
    "make lint && ./scripts/setup.sh --fast",
]


@pytest.mark.parametrize("call", SCRIPT_CALLERS)
def test_an_install_hidden_in_a_shell_script_ci_runs_is_read(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], call: str
) -> None:
    """The workflow shows `./scripts/setup.sh`; the `pip install` is in the script."""
    files = {
        ".github/workflows/ci.yml": f"jobs:\n  a:\n    steps:\n      - run: {call}\n",
        "scripts/setup.sh": "#!/bin/sh\n# pip install ruff <- a comment\npip install ruff\n",
    }
    assert scan_install_pinning.main(build(tmp_path, files)) == 1
    out = capsys.readouterr().out
    assert "scripts/setup.sh: pip install ruff" in out


@pytest.mark.parametrize("call", ["./scripts/setup", "bash scripts/setup", ". scripts/setup"])
def test_a_script_with_no_extension_is_known_by_its_shebang(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], call: str
) -> None:
    """`./scripts/setup` under `#!/usr/bin/env bash` is a shell script by all but its name."""
    files = {
        ".github/workflows/ci.yml": f"jobs:\n  a:\n    steps:\n      - run: {call}\n",
        "scripts/setup": "#!/usr/bin/env bash\npip install ruff\n",
    }
    assert scan_install_pinning.main(build(tmp_path, files)) == 1
    assert "scripts/setup: pip install ruff" in capsys.readouterr().out


def test_a_file_with_no_extension_and_no_shell_shebang_is_not_a_script(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other direction: a Python tool that only *prints* the words is not read as shell."""
    files = {
        ".github/workflows/ci.yml": "jobs:\n  a:\n    steps:\n      - run: ./tools/report\n",
        "tools/report": "#!/usr/bin/env python3\nprint('pip install ruff')\n",
    }
    assert scan_install_pinning.main(build(tmp_path, files)) == 0
    assert "ci-tools-hash-pinned" not in capsys.readouterr().out


def test_a_script_calling_a_script_is_followed(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = {
        ".github/workflows/ci.yml": "jobs:\n  a:\n    steps:\n      - run: ./scripts/setup.sh\n",
        "scripts/setup.sh": "#!/bin/sh\n./scripts/inner.sh\n",
        "scripts/inner.sh": "pip install ruff\n",
    }
    assert scan_install_pinning.main(build(tmp_path, files)) == 1
    assert "scripts/inner.sh: pip install ruff" in capsys.readouterr().out


def test_a_clean_shell_script_is_left_alone(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other direction: a script that pins is not reported for being a script."""
    files = {
        ".github/workflows/ci.yml": "jobs:\n  a:\n    steps:\n      - run: ./scripts/setup.sh\n",
        "scripts/setup.sh": "pip install --require-hashes -r pins/dev/requirements.txt\n",
    }
    assert scan_install_pinning.main(build(tmp_path, files)) == 0
    assert "ci-tools-hash-pinned" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "call", ["./scripts/gone.sh", "bash /usr/local/bin/setup.sh", "sh ../elsewhere/setup.sh"]
)
def test_a_script_that_is_not_ours_to_read_is_nothing(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], call: str
) -> None:
    """Missing, absolute, or climbing out of the checkout: not read, not a traceback."""
    files = {".github/workflows/ci.yml": f"jobs:\n  a:\n    steps:\n      - run: {call}\n"}
    root = build(tmp_path / "project", files)
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere" / "setup.sh").write_text("pip install ruff\n", encoding="utf-8")
    assert scan_install_pinning.main(root) == 0
    assert "ci-tools-hash-pinned" not in capsys.readouterr().out


def test_a_script_named_twice_and_calling_itself_is_read_once(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two steps call it and it calls itself: one reading, one finding, no loop."""
    files = {
        ".github/workflows/ci.yml": (
            "jobs:\n  a:\n    steps:\n"
            "      - run: ./scripts/setup.sh\n      - run: ./scripts/setup.sh\n"
        ),
        "scripts/setup.sh": "./scripts/setup.sh\npip install ruff\n",
    }
    assert scan_install_pinning.main(build(tmp_path, files)) == 1
    assert capsys.readouterr().out.count("scripts/setup.sh: pip install ruff") == 1


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


def test_a_trailing_comment_naming_the_flag_does_not_pin(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`pip install ruff  # TODO --require-hashes` is unpinned — the flag is in the comment."""
    files = {
        ".github/workflows/ci.yml": (
            "jobs:\n  a:\n    steps:\n"
            "      - run: pip install ruff  # TODO: use --require-hashes one day\n"
        )
    }
    assert scan_install_pinning.main(build(tmp_path, files)) == 1
    assert "ci-tools-hash-pinned" in capsys.readouterr().out


@pytest.mark.parametrize(
    "line",
    [
        "echo $(pip install ruff)",
        "echo `pip install ruff`",
        "(pip install ruff)",
        'sh -c "pip install ruff"',
        "bash -c 'pip install ruff'",
    ],
)
def test_an_install_behind_a_command_boundary_is_still_an_install(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], line: str
) -> None:
    """`$( )`, backticks, a subshell and `sh -c` all execute what they carry."""
    files = {".github/workflows/ci.yml": f"jobs:\n  a:\n    steps:\n      - run: {line}\n"}
    assert scan_install_pinning.main(build(tmp_path, files)) == 1
    assert "ci-tools-hash-pinned" in capsys.readouterr().out


@pytest.mark.parametrize("line", ["echo pip install ruff", "printf 'pip install ruff'"])
def test_a_command_that_only_says_the_words_installs_nothing(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], line: str
) -> None:
    """The shell runs `echo`; the words are prose (a chained real install is its own command)."""
    files = {".github/workflows/ci.yml": f"jobs:\n  a:\n    steps:\n      - run: {line}\n"}
    assert scan_install_pinning.main(build(tmp_path, files)) == 0
    assert "ci-tools-hash-pinned" not in capsys.readouterr().out


def test_an_echo_chained_to_a_real_install_still_reports_the_install(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    body = "jobs:\n  a:\n    steps:\n      - run: echo installing && pip install ruff\n"
    assert scan_install_pinning.main(build(tmp_path, {".github/workflows/ci.yml": body})) == 1
    assert "pip install ruff" in capsys.readouterr().out


@pytest.mark.parametrize(
    "step",
    ["      - run : pip install ruff\n", "      - {run: pip install ruff}\n"],
)
def test_a_yaml_shape_the_platform_reads_is_read_here_too(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], step: str
) -> None:
    """A space before the colon and a flow-style step are both valid YAML."""
    files = {".github/workflows/ci.yml": f"jobs:\n  a:\n    steps:\n{step}"}
    assert scan_install_pinning.main(build(tmp_path, files)) == 1
    assert "pip install ruff" in capsys.readouterr().out


@pytest.mark.parametrize(
    "step",
    ["      - uses : actions/checkout@v4\n", "      - {uses: actions/checkout@v4}\n"],
)
def test_a_yaml_shaped_uses_is_judged_too(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], step: str
) -> None:
    files = {".github/workflows/ci.yml": f"jobs:\n  a:\n    steps:\n{step}"}
    assert scan_workflow_pinning.main(build(tmp_path, files)) == 1
    assert "actions/checkout@v4" in capsys.readouterr().out


def test_a_flow_style_pinned_uses_with_its_comment_is_clean(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    body = "jobs:\n  a:\n    steps:\n      - {uses: actions/checkout@" + "a" * 40 + "} # v4\n"
    assert scan_workflow_pinning.main(build(tmp_path, {".github/workflows/ci.yml": body})) == 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "line",
    [
        "MARKER=--require-hashes pip install ruff",
        'pip install ruff "# --require-hashes"',
        "echo --require-hashes && pip install ruff",
    ],
)
def test_require_hashes_counts_only_as_an_argument_of_the_install(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], line: str
) -> None:
    """The flag in an environment value, a quoted argument or another command pins nothing."""
    files = {".github/workflows/ci.yml": f"jobs:\n  a:\n    steps:\n      - run: {line}\n"}
    assert scan_install_pinning.main(build(tmp_path, files)) == 1
    assert "ci-tools-hash-pinned" in capsys.readouterr().out


@pytest.mark.parametrize(
    "step",
    [
        "      - name: explain why pip install ruff is forbidden\n        run: echo ok\n",
        "      - run: echo ok\n        env:\n          NOTE: pip install ruff is banned here\n",
        "      - uses: ./ci/setup\n        with:\n          hint: pip install ruff\n",
    ],
)
def test_only_what_run_executes_is_judged_in_a_workflow(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], step: str
) -> None:
    """A `name:`, an `env:` value or a `with:` input that quotes the command runs nothing."""
    files = {".github/workflows/ci.yml": f"jobs:\n  a:\n    steps:\n{step}"}
    assert scan_install_pinning.main(build(tmp_path, files)) == 0
    assert "ci-tools-hash-pinned" not in capsys.readouterr().out


@pytest.mark.parametrize("marker", ["|", ">", "|-"])
def test_a_run_block_is_read_to_its_end_and_no_further(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], marker: str
) -> None:
    """`run: |` then the lines beneath it are the shell's; the next step's `name:` is not."""
    body = (
        "jobs:\n  a:\n    steps:\n"
        f"      - run: {marker}\n          echo one\n\n          pip install ruff\n"
        "      - name: pip install black is fine to mention\n        run: echo two\n"
    )
    assert scan_install_pinning.main(build(tmp_path, {".github/workflows/ci.yml": body})) == 1
    out = capsys.readouterr().out
    assert "pip install ruff" in out
    assert "black" not in out


def test_a_quoted_run_value_is_the_command_inside_the_quotes(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    body = 'jobs:\n  a:\n    steps:\n      - run: "pip install ruff"\n'
    assert scan_install_pinning.main(build(tmp_path, {".github/workflows/ci.yml": body})) == 1
    assert "pip install ruff" in capsys.readouterr().out


def test_a_hash_inside_quotes_is_not_a_comment(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The install chained after a quoted `#` is still read — the quote is text, not a comment."""
    files = {
        ".github/workflows/ci.yml": (
            'jobs:\n  a:\n    steps:\n      - run: echo "step #1" && pip install ruff\n'
        )
    }
    assert scan_install_pinning.main(build(tmp_path, files)) == 1
    assert "ci-tools-hash-pinned" in capsys.readouterr().out


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
            "jobs:\n  a:\n    steps:\n"
            "      - run: pip install --no-deps --no-build-isolation -e .\n"
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


@pytest.mark.parametrize(
    ("source", "shape"),
    [
        ("app.run(debug=1)\n", ".run(debug=1)"),
        ("app.debug = True\napp.run()\n", ".debug = True"),
        ("app.run(use_debugger=True)\n", ".run(use_debugger=True)"),
        ("app.run(**{'debug': True})\n", ".run(**{'debug': True})"),
        ("app.run(**{'port': 5000, 'debug': True})\n", ".run(**{'debug': True})"),
        ('app.config["DEBUG"] = True\napp.run()\n', '.config["DEBUG"] = True'),
    ],
)
def test_every_spelling_that_opens_the_debugger_is_a_finding(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], source: str, shape: str
) -> None:
    """Flask does `self.debug = bool(debug)` and hands werkzeug `use_debugger=self.debug` —
    five spellings, one console (self-audit, 2026-08-31, each proved live on Flask 3.1.3)."""
    files = {"run.py": "app = object()\n" + source}
    assert scan_entrypoint_debug.main(build(tmp_path, files)) == 1
    assert f"run.py:2 {shape}" in capsys.readouterr().out


@pytest.mark.parametrize(
    "source",
    [
        "app.run(debug=False)\n",
        "app.run(debug=0)\n",
        "app.debug = False\napp.run()\n",
        'app.config["DEBUG"] = os.environ.get("DEBUG")\napp.run()\n',
        "app.run(debug=DEBUG)\n",
        "app.run(**{'port': 5000})\n",
        'app.config["TESTING"] = True\napp.run()\n',
    ],
)
def test_a_switch_left_off_or_computed_at_runtime_is_not_judged(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], source: str
) -> None:
    """A false constant is off; a value read at runtime is unknown, and unknown is not a finding."""
    files = {"run.py": "import os\napp = object()\ncache = object()\n" + source}
    assert scan_entrypoint_debug.main(build(tmp_path, files)) == 0
    assert capsys.readouterr().out == ""


ANCHORED_INSTALL = "x-cmd: &cmd pip install ruff\njobs:\n  a:\n    steps:\n      - run: *cmd\n"
LISTED_INSTALL = "anchors:\n  - &cmd pip install ruff\njobs:\n  a:\n    steps:\n      - run: *cmd\n"
FOLDED_SPLIT = "jobs:\n  a:\n    steps:\n      - run: >\n          pip\n          install ruff\n"
FOLDED_STRIP_SPLIT = (
    "jobs:\n  a:\n    steps:\n      - run: >-\n          pip\n          install ruff\n"
)
PLAIN_SPLIT = "jobs:\n  a:\n    steps:\n      - run: pip\n          install ruff\n"
QUOTED_SPLIT = 'jobs:\n  a:\n    steps:\n      - run: "pip\n          install ruff"\n'
TAGGED_INSTALL = "jobs:\n  a:\n    steps:\n      - run: !!str pip install ruff\n"
PADDED_SPLIT = (
    "jobs:\n  a:\n    steps:\n      - run: >\n\n          pip\n          install ruff\n\n"
)


@pytest.mark.parametrize(
    "body",
    [
        ANCHORED_INSTALL,
        LISTED_INSTALL,
        FOLDED_SPLIT,
        FOLDED_STRIP_SPLIT,
        PLAIN_SPLIT,
        QUOTED_SPLIT,
        TAGGED_INSTALL,
        PADDED_SPLIT,
        'jobs:\n  a:\n    steps:\n      - "run": pip install ruff\n',
        "jobs:\n  a:\n    steps:\n      - 'run': pip install ruff\n",
    ],
    ids=[
        "alias-of-a-scalar-anchor",
        "alias-of-a-listed-anchor",
        "folded-split-over-lines",
        "folded-strip-split-over-lines",
        "plain-scalar-continued",
        "double-quoted-continued",
        "tagged-scalar",
        "folded-with-blank-lines-around",
        "double-quoted-key",
        "single-quoted-key",
    ],
)
def test_a_run_the_platform_reads_as_one_install_is_read_as_one_here(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], body: str
) -> None:
    """An alias is its anchor's value, a quoted key is the key, a tag is dropped, and a
    plain, quoted or folded scalar that continues onto the next line is joined with a
    space before the shell sees it — so `pip` ⏎ `install ruff` is one command (self-audit,
    2026-08-31: every shape here exited 0)."""
    assert scan_install_pinning.main(build(tmp_path, {".github/workflows/ci.yml": body})) == 1
    assert "ci.yml: pip install ruff" in capsys.readouterr().out


def test_a_literal_block_keeps_its_lines_apart(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`|` hands the shell two lines: `pip` alone, then `install ruff` alone — no install."""
    body = "jobs:\n  a:\n    steps:\n      - run: |\n          pip\n          install ruff\n"
    assert scan_install_pinning.main(build(tmp_path, {".github/workflows/ci.yml": body})) == 0
    assert capsys.readouterr().out == ""


def test_an_anchor_on_the_run_line_names_the_command_not_the_anchor(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    body = "jobs:\n  a:\n    steps:\n      - run: &cmd pip install ruff\n      - run: *cmd\n"
    assert scan_install_pinning.main(build(tmp_path, {".github/workflows/ci.yml": body})) == 1
    out = capsys.readouterr().out
    assert out.count("ci.yml: pip install ruff") == 2
    assert "&cmd" not in out


def test_a_local_action_named_through_an_alias_is_followed(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workflow = "x-act: &act ./ci/setup\njobs:\n  a:\n    steps:\n      - uses: *act\n"
    files = {
        ".github/workflows/ci.yml": workflow,
        "ci/setup/action.yml": "runs:\n  steps:\n    - run: pip install ruff\n",
    }
    assert scan_install_pinning.main(build(tmp_path, files)) == 1
    assert "ci/setup/action.yml: pip install ruff" in capsys.readouterr().out


SHA = "a" * 40


@pytest.mark.parametrize(
    "body",
    [
        f"x-co: &co actions/checkout@{SHA} # v4\njobs:\n  a:\n    steps:\n      - uses: *co\n",
        f"jobs:\n  a:\n    steps:\n      - uses: !!str actions/checkout@{SHA} # v4\n",
        (
            "jobs:\n  a:\n    steps:\n      - uses: ./ci/setup\n        with:\n"
            "          uses: actions/checkout@v4\n"
        ),
    ],
    ids=["alias-of-a-pinned-anchor", "tagged-pinned", "input-named-uses"],
)
def test_a_pinned_uses_the_platform_reads_is_clean_here_too(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], body: str
) -> None:
    """The alias carries its anchor's version comment; a tag is dropped; a `uses` under
    `with:` is an input, not a step (self-audit, 2026-08-31: `*co` was the finding)."""
    assert scan_workflow_pinning.main(build(tmp_path, {".github/workflows/ci.yml": body})) == 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "body",
    [
        "x-co: &co actions/checkout@v4\njobs:\n  a:\n    steps:\n      - uses: *co\n",
        'jobs:\n  a:\n    steps:\n      - "uses": actions/checkout@v4\n',
        "jobs:\n  a:\n    steps:\n      - uses: &co actions/checkout@v4\n",
    ],
    ids=["alias-of-a-floating-anchor", "quoted-key", "own-anchor-on-the-line"],
)
def test_a_floating_uses_behind_a_yaml_shape_names_the_action(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], body: str
) -> None:
    assert scan_workflow_pinning.main(build(tmp_path, {".github/workflows/ci.yml": body})) == 1
    out = capsys.readouterr().out
    assert "ci.yml: actions/checkout@v4" in out
    assert "*co" not in out
    assert "&co" not in out


STEP = "jobs:\n  a:\n    steps:\n      - run: {line}\n"


@pytest.mark.parametrize(
    "line",
    [
        'bash -lc "pip install ruff"',
        "sh -ec 'pip install ruff'",
        'echo "pip install ruff" | bash',
        "printf 'pip install ruff' | sh",
        'bash <<< "pip install ruff"',
        'eval "pip install ruff"',
        "echo preparing & pip install ruff",
        "echo \\#1 && pip install ruff",
        "${PIP:-pip} install ruff",
        "python3 -c \"import os; os.system('pip install ruff')\"",
    ],
    ids=[
        "flag-folded-c",
        "flag-folded-ec",
        "echo-piped-to-bash",
        "printf-piped-to-sh",
        "here-string",
        "eval-of-a-string",
        "after-a-lone-ampersand",
        "after-an-escaped-hash",
        "default-word-of-an-expansion",
        "string-handed-to-os-system",
    ],
)
def test_text_a_shell_will_run_is_read_as_the_command_it_becomes(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], line: str
) -> None:
    """`-c` folded into other flags, words piped or here-stringed into a shell, `eval`,
    a lone `&`, an escaped `#`, a `${VAR:-pip}` default and a string inside `os.system`
    all execute the install — and all were green (self-audit, 2026-08-31)."""
    files = {".github/workflows/ci.yml": STEP.format(line=line)}
    assert scan_install_pinning.main(build(tmp_path, files)) == 1
    assert "pip install ruff" in capsys.readouterr().out


@pytest.mark.parametrize(
    "line",
    [
        'echo "pip install ruff" | tee install.log',
        "echo '# pip install ruff'",
        'grep -c "pip install ruff" README.md',
        "echo done # pip install ruff",
        "${PIP:-pip} install --require-hashes -r requirements.txt",
    ],
    ids=["piped-to-a-file", "quoted-hash", "grep-of-the-words", "real-comment", "default-pinned"],
)
def test_words_no_shell_runs_stay_prose(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], line: str
) -> None:
    files = {".github/workflows/ci.yml": STEP.format(line=line)}
    assert scan_install_pinning.main(build(tmp_path, files)) == 0
    assert capsys.readouterr().out == ""


def test_a_hash_inside_a_word_is_not_a_comment(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`$#` and `${#PKGS}` are what the shell reads them as; the install after them runs."""
    files = {
        ".github/workflows/ci.yml": STEP.format(line="./scripts/setup.sh"),
        "scripts/setup.sh": 'if [ $# -gt 0 ]; then pip install "$@"; fi\n'
        "if [ ${#PKGS} -gt 0 ]; then pip install $PKGS; fi\n",
    }
    assert scan_install_pinning.main(build(tmp_path, files)) == 1
    assert capsys.readouterr().out.count("scripts/setup.sh: pip install") == 2


@pytest.mark.parametrize(
    "step",
    [
        '      - run: bash "scripts/setup.sh"\n',
        "      - run: cd scripts && ./setup.sh\n",
        "      - run: ./setup.sh\n        working-directory: scripts\n",
        "      - working-directory: scripts\n        run: ./setup.sh\n",
        (
            "      - name: set up\n        working-directory: scripts\n"
            "        run: |\n          ./setup.sh\n"
        ),
    ],
    ids=["quoted-path", "after-cd", "working-directory-after", "working-directory-before", "block"],
)
def test_a_script_is_followed_from_where_the_shell_stands(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], step: str
) -> None:
    """A quoted path is the path; `cd dir &&` and the step's `working-directory:` move
    the shell before it names the script (self-audit, 2026-08-31: all three unread)."""
    files = {
        ".github/workflows/ci.yml": f"jobs:\n  a:\n    steps:\n{step}",
        "scripts/setup.sh": "pip install ruff\n",
    }
    assert scan_install_pinning.main(build(tmp_path, files)) == 1
    assert "scripts/setup.sh: pip install ruff" in capsys.readouterr().out


def test_another_steps_working_directory_does_not_move_this_one(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`docs/build.sh` is clean and is the one this step runs; `scripts/setup.sh` is not."""
    steps = (
        "      - run: ./setup.sh\n        working-directory: scripts\n"
        "      - run: ./build.sh\n        working-directory: docs\n"
    )
    files = {
        ".github/workflows/ci.yml": f"jobs:\n  a:\n    steps:\n{steps}",
        "scripts/setup.sh": "echo nothing\n",
        "docs/build.sh": "echo nothing\n",
        "setup.sh": "pip install ruff\n",
    }
    assert scan_install_pinning.main(build(tmp_path, files)) == 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    ("files", "line"),
    [
        ({"app/templates/p.html": '<button onclick\n="go()">b</button>\n'}, 1),
        ({"app/templates/p.html": '<button onclick\n=\n"go()">b</button>\n'}, 1),
        ({"app/templates/p.html": '<a href="&#106;avascript:alert(1)">x</a>\n'}, 1),
        ({"app/templates/p.html": '<a href="&#10;java&#115;cript:alert(1)">x</a>\n'}, 1),
        ({"app/templates/p.htm": '<button onclick="go()">b</button>\n'}, 1),
        ({"app/templates/p.jinja2": '<p>\n<button onclick="go()">b</button>\n'}, 2),
        ({"app/templates/x/p.j2": '<button onclick="go()">b</button>\n'}, 1),
    ],
    ids=[
        "name-then-equals-on-the-next-line",
        "name-equals-value-on-three-lines",
        "entity-encoded-scheme",
        "entity-encoded-scheme-with-a-newline-inside",
        "htm-suffix",
        "jinja2-suffix",
        "j2-suffix-nested",
    ],
)
def test_markup_read_the_way_a_browser_reads_it(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], files: dict[str, str], line: int
) -> None:
    """The `=` may follow the name on a later line; entities inside an attribute value
    decode before the scheme is read (a `&#10;` cannot hide it or move a line); a
    template is one by any of its suffixes (self-audit, 2026-08-31: all exited 0)."""
    assert scan_templates_inline.main(build(tmp_path, files)) == 1
    out = capsys.readouterr().out
    assert f":{line} " in out
    assert "inline handler" in out or "javascript: URI" in out


@pytest.mark.parametrize(
    "text",
    [
        '<!-- onclick="x" never closes\n<p>rest</p>\n',
        "<p>Write &lt;script src=x&gt; in text and nothing runs</p>\n",
    ],
    ids=["unclosed-comment", "entities-in-text-stay-text"],
)
def test_what_the_browser_never_runs_is_clean(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], text: str
) -> None:
    """A `<!--` that never closes comments out the rest of the file; entities outside an
    attribute value are the characters they show, not markup (self-audit, 2026-08-31:
    the unclosed comment was a finding)."""
    assert scan_templates_inline.main(build(tmp_path, {"app/templates/p.html": text})) == 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "source",
    [
        "db_session.delete(user)\n",
        "self.session.delete(user)\n",
        "session.delete(user)  # soft delete lives elsewhere\n",
    ],
    ids=["db_session", "self.session", "with-a-trailing-comment"],
)
def test_a_session_by_any_prefix_deleting_is_a_finding(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], source: str
) -> None:
    """`db_session` is SQLAlchemy's own `scoped_session` name and was unseen behind a
    word boundary (self-audit, 2026-08-31)."""
    assert scan_write_discipline.main(build(tmp_path, {"app/models.py": source})) == 1
    assert "app/models.py:1" in capsys.readouterr().out


@pytest.mark.parametrize(
    "source",
    [
        '"""Never call session.delete( here — use soft delete."""\n',
        "# session.delete(user) would remove the row for real\n",
        'note = "session.delete( is forbidden"\n',
        "x = 1  # synchronize_session is a bulk-delete flag\n",
        'sql = f"""\nDELETE via session.delete( is not allowed\n"""\n',
    ],
    ids=["docstring", "comment", "string", "comment-naming-the-flag", "multi-line-string"],
)
def test_the_words_in_prose_are_not_a_delete(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], source: str
) -> None:
    """A docstring, a comment or a string literal explains; it does not delete (self-audit,
    2026-08-31: the docstring was a finding)."""
    assert scan_write_discipline.main(build(tmp_path, {"app/models.py": source})) == 0
    assert capsys.readouterr().out == ""


def test_a_file_python_cannot_tokenize_is_read_as_written(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = 'x = "unclosed\nsession.delete(user)\n'
    assert scan_write_discipline.main(build(tmp_path, {"app/models.py": source})) == 1
    assert "app/models.py:2" in capsys.readouterr().out


SERVICES = {"services_path": "app/services"}


@pytest.mark.parametrize(
    ("source", "named"),
    [
        ("import flask\nx = flask.request.args\n", "flask.request"),
        ("import flask as fl\nfl.session['u'] = 1\n", "fl.session"),
        ("from flask import *\n", "from flask import *"),
        ("from flask.globals import request\n", "from flask.globals import request"),
        ("from werkzeug.wrappers import Request\n", "import werkzeug.wrappers"),
        ("import werkzeug.local\n", "import werkzeug.local"),
        ("from flask_login.utils import current_user\n", "import flask_login"),
    ],
    ids=[
        "module-then-attribute",
        "aliased-module-then-attribute",
        "star-import",
        "from-a-flask-submodule",
        "werkzeug-request-side",
        "werkzeug-local",
        "flask-login-submodule",
    ],
)
def test_every_road_a_request_symbol_takes_into_the_service_layer(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], source: str, named: str
) -> None:
    """`import flask` then `flask.request`, a star import, a flask submodule and werkzeug's
    request side all bring HTTP into the logic (self-audit, 2026-08-31: all exited 0)."""
    files = {"app/services/todos.py": source}
    assert scan_service_layer.main(build(tmp_path, files, SERVICES)) == 1
    assert named in capsys.readouterr().out


@pytest.mark.parametrize(
    "source",
    [
        "import flask\napp = flask.Flask(__name__)\nlog = flask.current_app.logger\n",
        "from werkzeug.security import generate_password_hash\n",
        "from flask.helpers import get_debug_flag\n",
        "request = {}\nx = request.get('a')\n",
    ],
    ids=["application-side-attributes", "werkzeug-security", "flask-helper", "own-name-request"],
)
def test_the_application_side_and_a_name_of_ones_own_stay_clean(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], source: str
) -> None:
    files = {"app/services/todos.py": source}
    assert scan_service_layer.main(build(tmp_path, files, SERVICES)) == 0
    assert capsys.readouterr().out == ""
