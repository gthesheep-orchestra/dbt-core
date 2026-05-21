import os

import pytest

from dbt.tests.util import run_dbt


def _adapters_run_hooks_filters_when() -> bool:
    import dbt

    hooks_sql = os.path.join(
        os.path.dirname(dbt.__file__),
        "include",
        "global_project",
        "macros",
        "materializations",
        "hooks.sql",
    )
    if not os.path.isfile(hooks_sql):
        return False
    with open(hooks_sql) as f:
        contents = f.read()
    return (
        "rejectattr('when', 'equalto', 'failure')" in contents
        and "rejectattr('when', 'equalto', 'always')" in contents
    )


pytestmark = pytest.mark.skipif(
    not _adapters_run_hooks_filters_when(),
    reason=(
        "dbt-adapters run_hooks must filter when=failure and when=always. "
        "Install patched dbt-adapters: pip install -e /path/to/dbt-adapters/dbt-adapters"
    ),
)

FAILING_MODEL = """
{{ config(
    materialized='table',
    post_hook=[
        {"sql": "insert into {{ target.schema }}.hook_log values ('success_hook', current_timestamp)", "when": "success", "transaction": false},
        {"sql": "insert into {{ target.schema }}.hook_log values ('failure_hook', current_timestamp)", "when": "failure", "transaction": false},
        {"sql": "insert into {{ target.schema }}.hook_log values ('always_hook', current_timestamp)", "when": "always", "transaction": false},
    ]
) }}
select 1/0 as boom
"""

PASSING_MODEL = """
{{ config(
    materialized='table',
    post_hook=[
        {"sql": "insert into {{ target.schema }}.hook_log values ('success_hook', current_timestamp)", "when": "success", "transaction": false},
        {"sql": "insert into {{ target.schema }}.hook_log values ('failure_hook', current_timestamp)", "when": "failure", "transaction": false},
        {"sql": "insert into {{ target.schema }}.hook_log values ('always_hook', current_timestamp)", "when": "always", "transaction": false},
    ]
) }}
select 1 as id
"""


def _hook_log_table(project) -> str:
    return f"{project.test_schema}.hook_log"


def _setup_hook_log(project) -> None:
    table = _hook_log_table(project)
    project.run_sql(
        f"create table if not exists {table} (event varchar, ts timestamp)",
        fetch=None,
    )
    project.run_sql(f"delete from {table}", fetch=None)


def _hook_log_events(project) -> list:
    table = _hook_log_table(project)
    rows = project.run_sql(f"select event from {table} order by ts", fetch="all")
    return [r[0] for r in rows]


class TestFailureHookRunsOnFailure:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "failing_model.sql": FAILING_MODEL,
            "passing_model.sql": PASSING_MODEL,
        }

    def test_failure_hook_runs_on_failure(self, project):
        _setup_hook_log(project)

        results = run_dbt(["run", "--select", "failing_model"], expect_pass=False)
        assert results[0].status == "error"

        events = _hook_log_events(project)
        assert "failure_hook" in events
        assert "always_hook" in events
        assert "success_hook" not in events


class TestSuccessHookRunsOnSuccess:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "failing_model.sql": FAILING_MODEL,
            "passing_model.sql": PASSING_MODEL,
        }

    def test_success_hook_runs_on_success(self, project):
        _setup_hook_log(project)

        results = run_dbt(["run", "--select", "passing_model"])
        assert results[0].status == "success"

        events = _hook_log_events(project)
        assert "success_hook" in events
        assert "always_hook" in events
        assert "failure_hook" not in events
