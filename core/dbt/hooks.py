import json
from typing import Any, Dict, Union

from dbt_common.dataclass_schema import StrEnum


class ModelHookType(StrEnum):
    PreHook = "pre-hook"
    PostHook = "post-hook"


def get_hook_dict(source: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """From a source string-or-dict, get a dictionary that can be passed to
    Hook.from_dict
    """
    if isinstance(source, dict):
        result = dict(source)
        result.setdefault("when", "success")
        return result
    try:
        result = json.loads(source)
        if isinstance(result, dict):
            result.setdefault("when", "success")
            return result
    except ValueError:
        pass
    return {"sql": source, "transaction": True, "when": "success"}
