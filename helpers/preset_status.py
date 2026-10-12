"""Evaluate effective preset slots with the same runtime transport guard."""
from copy import deepcopy

def evaluate(preset,base,owner,local_embedding=None,policy_owner=None):
    from plugins._model_config.helpers import model_config as mc
    from usr.plugins.requesty.helpers.runtime_guard import guarded_kwargs,local_kwargs,is_requesty
    from usr.plugins.requesty.helpers.wrapper import GuardedRequestyWrapper
    from usr.plugins.requesty.helpers.policy import PolicyError
    import models
    reasons=[]
    config=mc.build_config_from_preset(preset,base,strip_api_key=False)
    for slot,section in [('Main','chat_model'),('Utility','utility_model'),('Vision','vision_model')]:
        conf=config.get(section) or {}
        if slot=='Vision' and (not conf or (config.get('chat_model',{}).get('vision') and not conf.get('override_main'))):continue
        try:
            model_config=mc.build_model_config(conf,models.ModelType.CHAT)
            from usr.plugins.requesty.helpers.policy import ENDPOINTS
            native_other=conf.get('provider') in {'other','openai'} and str(model_config.build_kwargs().get('api_base','')).rstrip('/') in ENDPOINTS.values()
            if conf.get('provider')=='requesty_guarded' or native_other:
                from usr.plugins.requesty.helpers import scope
                options=model_config.build_kwargs()
                if options.get('api_key') in (None,'','NA','None'):options['api_key']=scope.key(owner)
                model_config=deepcopy(model_config);model_config.provider='requesty_guarded'
                wrapper=GuardedRequestyWrapper(model=conf.get('name',''),provider='openai',model_config=model_config,**options)
                wrapper._requesty_scope=owner;wrapper._requesty_slot=slot.lower()
                wrapper._requesty_policy_scope=policy_owner
                checked=guarded_kwargs(wrapper,{})
                if slot=='Vision':
                    from usr.plugins.requesty.helpers.catalog import fetch
                    if fetch(checked['api_base'],checked['api_key']).get(conf.get('name'),{}).get('supports_vision') is not True:
                        raise PolicyError('Image support is not confirmed.')
            else:
                wrapper=models.get_chat_model(model_config.provider,model_config.name,model_config=model_config,**model_config.build_kwargs())
                local_kwargs(wrapper,{})
        except PolicyError as error:reasons.append(slot+': '+str(error))
        except Exception:reasons.append(slot+': Model configuration cannot be safely verified.')
    if local_embedding:
        candidate=config.get('embedding_model',{})
        if any(candidate.get(key)!=local_embedding.get(key) for key in ('provider','name')) or candidate.get('kwargs') not in (None,{}):
            reasons.append('Embedding: The preset must use the configured local embedding model without custom transport parameters.')
    return {'name':preset.get('name',''),'allowed':not reasons,'reasons':reasons}
