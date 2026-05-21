from unittest.mock import MagicMock, patch

from dbt.artifacts.resources import HookWhen
from dbt.artifacts.schemas.results import RunStatus
from dbt.task.run import ModelRunner, RunHookResult


def make_runner():
    runner = ModelRunner.__new__(ModelRunner)
    runner.adapter = MagicMock()
    return runner


def make_node(hooks):
    node = MagicMock()
    node.config.post_hook = hooks
    return node


def test_failure_hook_runs_on_error():
    runner = make_runner()
    node = make_node([{"sql": "select 'fail'", "when": "failure", "transaction": False}])
    with patch("dbt.task.run.get_execution_status", return_value=(RunStatus.Success, "OK")):
        with patch("dbt.task.run.get_rendered", return_value="select 'fail'"):
            results = runner._run_user_post_hooks(node, {}, RunStatus.Error)
    assert len(results) == 1
    assert results[0].status == RunStatus.Success


def test_failure_hook_skipped_on_success():
    runner = make_runner()
    node = make_node([{"sql": "select 'fail'", "when": "failure", "transaction": False}])
    with patch("dbt.task.run.get_execution_status", return_value=(RunStatus.Success, "OK")):
        results = runner._run_user_post_hooks(node, {}, RunStatus.Success)
    assert len(results) == 0


def test_always_hook_runs_on_both():
    runner = make_runner()
    node = make_node([{"sql": "select 'always'", "when": "always", "transaction": False}])
    with patch("dbt.task.run.get_execution_status", return_value=(RunStatus.Success, "OK")):
        with patch("dbt.task.run.get_rendered", return_value="select 'always'"):
            success_results = runner._run_user_post_hooks(node, {}, RunStatus.Success)
            error_results = runner._run_user_post_hooks(node, {}, RunStatus.Error)
    assert len(success_results) == 1
    assert len(error_results) == 1


def test_merge_hook_results_partial_success():
    runner = make_runner()
    node = make_node([])
    from dbt.artifacts.schemas.run import RunResult

    model_result = RunResult(
        node=node,
        status=RunStatus.Success,
        timing=[],
        thread_id="test",
        execution_time=0.0,
        message="OK",
        adapter_response={},
        failures=None,
    )
    hook_results = [RunHookResult(status=RunStatus.Error, message="boom", sql="select fail")]
    merged = runner._merge_hook_results(model_result, hook_results)
    assert merged.status == RunStatus.PartialSuccess


def test_run_user_post_hooks_commits_on_success():
    runner = make_runner()
    node = make_node([{"sql": "select 1", "when": "always", "transaction": False}])
    with patch("dbt.task.run.get_execution_status", return_value=(RunStatus.Success, "OK")):
        with patch("dbt.task.run.get_rendered", return_value="select 1"):
            runner._run_user_post_hooks(node, {}, RunStatus.Success)
    runner.adapter.commit_if_has_connection.assert_called_once()


def test_run_post_hooks_after_model_failure_does_not_release_connection():
    runner = make_runner()
    runner._failure_post_hooks_ran = False
    runner.node = MagicMock()
    model = make_node([{"sql": "select 1", "when": "failure", "transaction": False}])
    with patch.object(runner, "_run_user_post_hooks", return_value=[]) as mock_hooks:
        runner._run_post_hooks_after_model_failure(model, {})
    mock_hooks.assert_called_once()
    runner.adapter.connection_named.assert_not_called()


def test_hook_when_reads_from_hook_object():
    runner = make_runner()
    from dbt.artifacts.resources import Hook

    node = MagicMock()
    node.config.post_hook = [
        Hook.from_dict({"sql": "select 'fail'", "when": "failure", "transaction": False})
    ]
    with patch("dbt.task.run.get_execution_status", return_value=(RunStatus.Success, "OK")):
        with patch("dbt.task.run.get_rendered", return_value="select 'fail'"):
            results = runner._run_user_post_hooks(node, {}, RunStatus.Error)
    assert len(results) == 1
