"""A check name is not a job id, and the difference is where two failures hide.

Require a name no job can produce and every pull request waits forever with
nothing red to look at. Fail to require one that exists and it goes red and merges
anyway. Both are invisible unless something works out the names the platform will
actually use, which is what this reader does.

The reference implementation shipped a report claiming `dialect` had failed ten
times and `dialects` had never gone red — the same jobs, one named by its check
and one by its id, with no reader able to see they were the same thing.
"""

from __future__ import annotations

import pytest

from verifiable_gates import check_names

PLAIN = {"on": ["pull_request"], "jobs": {"test": {"runs-on": "ubuntu-latest"}}}
NAMED = {"on": ["pull_request"], "jobs": {"test": {"name": "the test suite"}}}
MATRIX = {
    "on": ["pull_request"],
    "jobs": {
        "dialects": {
            "name": "dialect (${{ matrix.db.name }})",
            "strategy": {"matrix": {"db": [{"name": "mysql-8"}, {"name": "mariadb-11"}]}},
        }
    },
}
SCHEDULED = {"on": {"schedule": [{"cron": "0 0 * * *"}]}, "jobs": {"scorecard": {}}}


# --------------------------------------------------------- one job, one name


def test_a_job_without_a_name_is_known_by_its_id() -> None:
    assert check_names.check_names(PLAIN) == {"test"}


def test_a_job_with_a_name_is_known_by_that_name() -> None:
    """**The failure that hides here**: requiring the id of a job that declares a name.

    Branch protection would wait for `test` while the platform reports
    `the test suite`, and nothing anywhere is red.
    """
    assert check_names.check_names(NAMED) == {"the test suite"}


def test_a_workflow_with_no_jobs_answers_empty_rather_than_raising() -> None:
    assert check_names.check_names({"on": ["push"]}) == set()


# ------------------------------------------------------- one job, many checks


def test_a_matrix_produces_one_check_per_row() -> None:
    """Counting the job once is how a register ends up missing the jobs that run most."""
    assert check_names.check_names(MATRIX) == {"dialect (mysql-8)", "dialect (mariadb-11)"}


def test_a_nested_matrix_reference_is_resolved() -> None:
    """`${{ matrix.db.name }}` reaches into the row, not just at it."""
    assert "dialect (mysql-8)" in check_names.check_names(MATRIX)


def test_a_matrix_whose_values_are_not_in_the_name_still_gives_distinct_checks() -> None:
    """The platform appends the row itself, so two rows are never one check."""
    workflow = {
        "on": ["pull_request"],
        "jobs": {"build": {"strategy": {"matrix": {"python": ["3.12", "3.13"]}}}},
    }

    assert len(check_names.check_names(workflow)) == 2


def test_a_reference_to_the_whole_row_reads_the_key_it_names() -> None:
    """`${{ matrix.db }}` where each row is a mapping — the value under that key.

    The dotted form reaches *into* a row; this form names the row's own key. Both
    appear in real workflows, and a reader handling only the dotted one produces a
    name containing a dict repr, which matches no check the platform will ever
    report.
    """
    workflow = {
        "on": ["pull_request"],
        "jobs": {
            "dialects": {
                "name": "dialect (${{ matrix.db }})",
                "strategy": {"matrix": {"db": [{"db": "mysql-8"}, {"db": "mariadb-11"}]}},
            }
        },
    }

    assert check_names.check_names(workflow) == {"dialect (mysql-8)", "dialect (mariadb-11)"}


def test_a_plain_matrix_value_needs_no_dotted_reference() -> None:
    workflow = {
        "on": ["pull_request"],
        "jobs": {
            "build": {
                "name": "build (${{ matrix.python }})",
                "strategy": {"matrix": {"python": ["3.12", "3.13"]}},
            }
        },
    }

    assert check_names.check_names(workflow) == {"build (3.12)", "build (3.13)"}


# ------------------------------------------------------------ the three sets


def test_only_workflows_a_pull_request_starts_are_counted() -> None:
    """A required name that no pull request can produce is a pull request that never merges."""
    found = check_names.pull_request_checks({"ci.yml": PLAIN, "scorecard.yml": SCHEDULED})

    assert found == {"test"}


def test_everything_the_repository_can_produce_is_wider_on_purpose() -> None:
    """The register of "not required, and here is why" has to be held against this set.

    Held against the pull-request set instead, its entries can never appear in it,
    so nothing ever consults it and the register quietly becomes a text file — the
    exact shape the reference implementation found in its own.
    """
    found = check_names.all_checks({"ci.yml": PLAIN, "scorecard.yml": SCHEDULED})

    assert found == {"test", "scorecard"}


def test_the_count_is_of_runs_not_of_distinct_names() -> None:
    """Two jobs may share a name: two runs, one name — and the advertised number is runs."""
    same_name = {"on": ["push"], "jobs": {"a": {"name": "shared"}, "b": {"name": "shared"}}}

    assert check_names.total_checks({"x.yml": same_name}) == 2
    assert check_names.all_checks({"x.yml": same_name}) == {"shared"}


def test_the_count_includes_every_matrix_row() -> None:
    assert check_names.total_checks({"ci.yml": MATRIX, "s.yml": SCHEDULED}) == 3


def test_the_count_of_an_empty_repository_is_zero() -> None:
    assert check_names.total_checks({}) == 0


# ------------------------------------------------- the shape `on:` arrives in


@pytest.mark.parametrize(
    "on",
    [
        "pull_request",
        ["push", "pull_request"],
        {"pull_request": None, "push": None},
    ],
)
def test_a_pull_request_trigger_is_found_in_every_shape_of_on(on: object) -> None:
    """All three are valid YAML for the same thing, and the middle one is the trap.

    A reader handling only two of them reports "no pull-request workflows", which
    reads exactly like a repository whose checks are all correctly not required.
    """
    found = check_names.pull_request_checks({"ci.yml": {"on": on, "jobs": {"test": {}}}})

    assert found == {"test"}


def test_an_unquoted_on_read_as_a_boolean_is_still_found() -> None:
    """YAML 1.1 turns a bare `on:` into the boolean `True` — which is what a real file has."""
    found = check_names.pull_request_checks(
        {"ci.yml": {True: ["pull_request"], "jobs": {"test": {}}}}
    )

    assert found == {"test"}
