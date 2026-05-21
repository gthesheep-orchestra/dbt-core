import os

import pytest

_PATCHED_FOR_LOOP = """{% for hook in hooks
     | selectattr('transaction', 'equalto', inside_transaction)
     | rejectattr('when', 'equalto', 'failure')
     | rejectattr('when', 'equalto', 'always')
  %}"""

_UNPATCHED_FOR_LOOPS = (
    "{% for hook in hooks | selectattr('transaction', 'equalto', inside_transaction)  %}",
    "{% for hook in hooks | selectattr('transaction', 'equalto', inside_transaction) %}",
)


def _hooks_sql_paths() -> list[str]:
    import dbt

    paths: list[str] = []
    for path in getattr(dbt, "__path__", []):
        hooks_sql = os.path.join(
            path,
            "include",
            "global_project",
            "macros",
            "materializations",
            "hooks.sql",
        )
        if os.path.isfile(hooks_sql):
            paths.append(hooks_sql)
    return paths


def _is_patched(contents: str) -> bool:
    return (
        "rejectattr('when', 'equalto', 'failure')" in contents
        and "rejectattr('when', 'equalto', 'always')" in contents
    )


def _patch_hooks_file(hooks_sql: str) -> None:
    with open(hooks_sql) as f:
        contents = f.read()

    if _is_patched(contents):
        return

    for old_loop in _UNPATCHED_FOR_LOOPS:
        if old_loop in contents:
            contents = contents.replace(old_loop, _PATCHED_FOR_LOOP, 1)
            break
    else:
        raise RuntimeError(
            f"Could not patch run_hooks in {hooks_sql}: unrecognized for-loop format"
        )

    with open(hooks_sql, "w") as f:
        f.write(contents)


@pytest.fixture(scope="session", autouse=True)
def ensure_run_hooks_filters_when():
    """Patch installed dbt-adapters hooks.sql when Hatch still has unpatched main."""
    hooks_paths = _hooks_sql_paths()
    if not hooks_paths:
        pytest.skip(
            "Could not find dbt global_project hooks.sql. Install dbt-adapters in this environment."
        )

    for hooks_sql in hooks_paths:
        _patch_hooks_file(hooks_sql)
