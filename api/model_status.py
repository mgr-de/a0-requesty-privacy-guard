"""Native chat gate with profile-owned Requesty status; never return credentials."""
from helpers.api import ApiHandler
from agent import AgentContext
from plugins._model_config.api.model_config_get import ModelConfigGet
from usr.plugins.requesty.helpers import scope
from usr.plugins.requesty.helpers.policy import PolicyError

class ModelStatus(ApiHandler):
    async def process(self, input, request):
        result = await ModelConfigGet(self.app, self.thread_lock).process(input, request)
        context = AgentContext.get(str(input.get("context_id") or ""))
        if context is None or context.agent0 is None or not isinstance(result, dict):
            return result
        owner = scope.from_agent(context.agent0)
        setup = scope.read(owner, "setup.json")
        if not setup or not setup.get("active") or not scope.enabled(owner):
            return result
        try:
            scope.key(owner)
            has_key = True
        except PolicyError:
            has_key = False
        config = dict(result["config"])
        config.update(chat_model=setup["models"]["chat"], utility_model=setup["models"]["utility"], vision_model={})
        result.update(config=config, model_configured=has_key,
            model_configured_label="requesty_guarded / " + setup["models"]["chat"]["name"],
            api_key_status={**result.get("api_key_status", {}), "requesty_guarded":has_key})
        return result
