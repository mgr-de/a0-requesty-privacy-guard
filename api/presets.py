from helpers.api import ApiHandler
from agent import AgentContext

class Presets(ApiHandler):
    async def process(self,input,request):
        context=AgentContext.get(str(input.get('context_id') or ''))
        if context is None or context.agent0 is None:return {'ok':False,'error':'Chat not found.'}
        from usr.plugins.requesty.helpers.call_context import owner
        from usr.plugins.requesty.helpers import scope
        identity=owner(context.agent0)
        setup=scope.read(identity,'setup.json',{})
        if not setup.get('active') or not scope.enabled(identity):return {'ok':True,'protected':False,'presets':[]}
        from plugins._model_config.helpers import model_config as mc
        from usr.plugins.requesty.helpers.preset_status import evaluate
        from helpers import projects
        base=mc.get_config(context.agent0)
        local=None
        try:
            from usr.plugins.local_privacy_guard.helpers.model_guard import owner_and_config
            from usr.plugins.local_privacy_guard.helpers.agent_scope import embedding
            config=owner_and_config(context.agent0)[1]
            if config:local=embedding(config)
        except ImportError:pass
        presets=mc.get_combined_presets(projects.get_context_project_name(context) or None)
        from usr.plugins.requesty.helpers.instance import manager
        from usr.plugins.requesty.helpers.call_context import root_agent
        policy_owner=scope.from_agent(root_agent(context.agent0)) if manager() is not None else identity
        return {'ok':True,'protected':True,'presets':[evaluate(preset,base,identity,local,policy_owner) for preset in presets],
                'basis':'Effective model configuration and current Requesty catalog; evaluated again before every call.'}
