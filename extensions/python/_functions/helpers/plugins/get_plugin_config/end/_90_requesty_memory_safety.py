from copy import deepcopy
from helpers.extension import Extension


class RequestyMemorySafety(Extension):
    def execute(self, data, **kwargs):
        args = data.get("args", ())
        inputs = data.get("kwargs", {})
        name = args[0] if args else inputs.get("plugin_name")
        agent = args[1] if len(args) > 1 else inputs.get("agent")
        if name != "_memory" or agent is None or not isinstance(data.get("result"), dict):
            return
        from plugins._model_config.helpers.model_config import get_utility_model_config
        config = get_utility_model_config(agent)
        if config.get("provider") != "requesty_guarded":
            return
        # Native consolidation catches model failures and can report SKIP as success.
        # V1 uses the guarded extraction + append-only branch instead. Never mutate
        # the cached or saved Memory configuration shared with other agents.
        safe = deepcopy(data["result"])
        safe["memory_memorize_consolidation"] = False
        safe["memory_memorize_replace_threshold"] = 0
        data["result"] = safe
