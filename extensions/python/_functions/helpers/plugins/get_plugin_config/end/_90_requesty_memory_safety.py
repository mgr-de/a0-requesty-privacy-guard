from copy import deepcopy
from helpers.extension import Extension


class RequestyMemorySafety(Extension):
    def execute(self, data, **kwargs):
        args = data.get("args", ())
        inputs = data.get("kwargs", {})
        name = args[0] if args else inputs.get("plugin_name")
        agent = args[1] if len(args) > 1 else inputs.get("agent")
        if name not in ("_memory", "_model_config") or agent is None or not isinstance(data.get("result"), dict):
            return
        from usr.plugins.requesty.helpers import scope
        owner = scope.from_agent(agent)
        setup = scope.read(owner, "setup.json")
        if not setup or not setup.get("active") or not scope.enabled(owner):
            return
        # Native consolidation catches model failures and can report SKIP as success.
        # V1 uses the guarded extraction + append-only branch instead. Never mutate
        # the cached or saved Memory configuration shared with other agents.
        safe = deepcopy(data["result"])
        if name == "_model_config":
            override = agent.context.get_data("chat_model_override")
            if isinstance(override, dict) and override:
                # A named override can restore a Vision sidecar after this hook.
                from usr.plugins.requesty.helpers.policy import PolicyError
                raise PolicyError("Clear the chat model override while the profile Requesty setup is active.")
            safe["vision_model"] = {}
            data["result"] = safe
            return
        safe["memory_memorize_consolidation"] = False
        safe["memory_memorize_replace_threshold"] = 0
        safe["project_memory_isolation"] = False
        safe["agent_memory_subdir"] = scope.memory_subdir(owner)
        data["result"] = safe
