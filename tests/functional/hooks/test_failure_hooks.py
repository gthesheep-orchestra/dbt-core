import pytest

from dbt.tests.util import run_dbt

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


class TestFailureHookRunsOnFailure:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "failing_model.sql": FAILING_MODEL,
            "passing_model.sql": PASSING_MODEL,
        }

    def test_failure_hook_runs_on_failure(self, project):
        project.run_sql(
            "create table if not exists hook_log (event varchar, ts timestamp)",
            fetch=None,
        )
        project.run_sql("delete from hook_log", fetch=None)

        results = run_dbt(["run", "--select", "failing_model"], expect_pass=False)
        assert results[0].status == "error"

        rows = project.run_sql("select event from hook_log order by ts", fetch="all")
        events = [r[0] for r in rows]
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
        project.run_sql(
            "create table if not exists hook_log (event varchar, ts timestamp)",
            fetch=None,
        )
        project.run_sql("delete from hook_log", fetch=None)

        results = run_dbt(["run", "--select", "passing_model"])
        assert results[0].status == "success"

        rows = project.run_sql("select event from hook_log order by ts", fetch="all")
        events = [r[0] for r in rows]
        assert "success_hook" in events
        assert "always_hook" in events
        assert "failure_hook" not in events
