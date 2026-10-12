"""Native chat gate with profile-owned Requesty status; never return credentials."""
from helpers.api import ApiHandler
from agent import AgentContext
from plugins._model_config.api.model_config_get import ModelConfigGet
from usr.plugins.requesty.helpers import scope
from usr.plugins.requesty.helpers.policy import PolicyError

class ModelStatus(ApiHandler):
    async def process(self, input, request):
        try:
            result = await ModelConfigGet(self.app, self.thread_lock).process(input, request)
        except ValueError as error:
            from plugins._model_config.helpers import model_config as mc
            # Read-only fallback keeps the preset editor reachable for invalid
            # embedding/policy selections; it never repairs a user's selection.
            return {"config":mc.get_effective_config(), "model_configured":False,
                    "model_configured_label":"Preset blocked by privacy requirements", "policy_error":str(error),
                    "api_key_status":{}}
        context = AgentContext.get(str(input.get("context_id") or ""))
        if context is None or context.agent0 is None or not isinstance(result, dict):
            return result
        from usr.plugins.requesty.helpers.call_context import owner as inherited_owner
        owner = inherited_owner(context.agent0)
        setup = scope.read(owner, "setup.json")
        if not setup or not setup.get("active") or not scope.enabled(owner):
            return result
        try:
            scope.key(owner)
            has_key = True
        except PolicyError:
            has_key = False
        config = dict(result["config"])
        selected = context.get_data("chat_model_override") or context.get_data("_browser_model_active")
        if not selected:
            config.update(chat_model=setup["models"]["chat"], utility_model=setup["models"]["utility"])
        local_selection=False
        if selected:
            try:
                from usr.plugins.requesty.helpers.runtime_guard import guarded_kwargs,local_kwargs,is_requesty
                kinds=[]
                for getter in (context.agent0.get_chat_model,context.agent0.get_utility_model):
                    wrapper=getter()
                    while hasattr(wrapper,'_privacy_inner'):wrapper=wrapper._privacy_inner
                    if is_requesty(wrapper):guarded_kwargs(wrapper,{});kinds.append('requesty')
                    else:local_kwargs(wrapper,{});kinds.append('local')
                local_selection=all(kind=='local' for kind in kinds)
            except ValueError as error:
                result.update(config=config,model_configured=False,
                    model_configured_label='Preset blocked by privacy requirements',policy_error=str(error))
                return result
        result.update(config=config, model_configured=has_key or local_selection,
            model_configured_label=config.get("chat_model",{}).get("provider", "") + " / " + config.get("chat_model",{}).get("name", ""),
            api_key_status={**result.get("api_key_status", {}), "requesty_guarded":has_key})
        result['requesty_active']=True
        result['requesty_owner_profile']=owner[1]
        result['effective_models']={slot:{key:config.get(section,{}).get(key,'') for key in ('provider','name')}
            for slot,section in [('main','chat_model'),('utility','utility_model'),('embedding','embedding_model')]}
        return result
