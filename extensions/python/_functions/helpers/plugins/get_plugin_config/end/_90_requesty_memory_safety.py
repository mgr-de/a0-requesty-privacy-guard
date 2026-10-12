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
        from usr.plugins.requesty.helpers.call_context import owner as inherited_owner
        owner = inherited_owner(agent)
        setup = scope.read(owner, "setup.json")
        active = bool(setup and setup.get("active") and scope.enabled(owner))
        if name == "_model_config":
            # Restore only legacy suspended selections when protection ends.
            # Active native choices remain selected and are checked at calls.
            from usr.plugins.requesty.helpers.chat_override import reconcile
            reconcile(agent, owner, active)
        if not active:
            return
        # Native consolidation catches model failures and can report SKIP as success.
        # V1 uses the guarded extraction + append-only branch instead. Never mutate
        # the cached or saved Memory configuration shared with other agents.
        safe = deepcopy(data["result"])
        if name == "_model_config":
            # Preserve an explicit sidecar. Its actual call is policy-checked.
            data["result"] = safe
            return
        safe["memory_memorize_consolidation"] = False
        safe["memory_memorize_replace_threshold"] = 0
        safe["project_memory_isolation"] = False
        safe["agent_memory_subdir"] = scope.memory_subdir(owner)
        data["result"] = safe
