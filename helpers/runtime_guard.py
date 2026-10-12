"""Guard Agent Zero calls without modifying framework classes or transports."""
from copy import deepcopy
from usr.plugins.requesty.helpers.policy import Policy, PolicyError, ENDPOINTS
from usr.plugins.requesty.helpers import catalog
from usr.plugins.requesty.helpers import scope
from urllib.parse import urlparse

INSTANCE_API_VERSION=2


def is_local_route(wrapper, options):
    """Recognize an explicitly configured host-local native endpoint, without probing it."""
    endpoint=options.get('api_base') or getattr(wrapper.a0_model_conf,'api_base','')
    parsed=urlparse(str(endpoint))
    return parsed.scheme in {'http','https'} and parsed.hostname in {
        'localhost','127.0.0.1','::1','host.docker.internal'
    } and not parsed.username and not parsed.password


def local_kwargs(wrapper, overrides):
    """Retain native local endpoints without adding provider-specific integrations."""
    import models
    options = models._merge_litellm_call_kwargs(wrapper.kwargs, overrides)
    forbidden = {"base_url", "model", "custom_llm_provider", "fallbacks", "model_list", "router",
                 "client", "aclient", "http_client", "extra_body", "extra_headers", "headers", "proxy"}
    if not is_local_route(wrapper,options) or forbidden.intersection(options):
        raise PolicyError("This preset bypasses Requesty. Select the profile's Requesty route or an explicitly configured local endpoint.")
    return options


def settings(owner):
    raw = scope.read(owner, "config.json")
    from usr.plugins.requesty.helpers.instance import manager
    instance=manager()
    if instance is not None:return Policy.parse(instance.effective_policy(raw))
    if raw is None:
        raise PolicyError("Save privacy requirements for this agent profile first.")
    return Policy.parse(raw)


def is_requesty(wrapper):
    conf = getattr(wrapper, "a0_model_conf", None)
    if str(getattr(conf, "provider", "")).lower() == "requesty_guarded":
        return True
    return False


def validate_model_parameters(effective, policy):
    # Do not let unvalidated secondary request bodies or transport choices bypass routing.
    forbidden = {"base_url", "model", "messages", "custom_llm_provider", "api_version",
                 "azure_ad_token", "client", "aclient", "http_client", "deployment_id",
                 "fallbacks", "context_window_fallbacks", "model_list", "router",
                 "extra_body", "extra_headers", "headers", "api_url", "proxy"}
    if forbidden.intersection(effective):
        raise PolicyError("Requesty does not allow custom routing, headers, clients or extra request bodies.")
    allowed = {"api_base", "api_key", "a0_api_mode", "a0_retry_attempts", "a0_retry_delay_seconds",
               "temperature", "top_p", "max_tokens", "max_completion_tokens", "timeout", "seed",
               "stop", "presence_penalty", "frequency_penalty", "logit_bias", "logprobs", "top_logprobs",
               "response_format", "reasoning_effort", "tools", "tool_choice", "parallel_tool_calls",
               "drop_params", "additional_drop_params", "num_retries", "stream_options",
               "a0_explicit_prompt_caching", "a0_responses_function_tools", "a0_responses_tool_choice",
               "responses_local_input_items", "responses_history_context", "responses_prompt_replacements",
               "responses_state", "responses_input_items", "previous_response_id"}
    if set(effective) - allowed:
        raise PolicyError("Unsupported Requesty parameter. Remove custom parameters from the model preset.")
    dropping=effective.get('additional_drop_params',[])
    sampling={'temperature','top_p','seed','stop','presence_penalty','frequency_penalty','logit_bias','logprobs','top_logprobs','reasoning_effort','parallel_tool_calls'}
    if not isinstance(dropping,list) or any(item not in sampling for item in dropping):
        raise PolicyError('Only sampling parameters may be dropped. Model, routing, authentication, message and output-limit parameters must remain intact.')
    if str(effective.get("a0_api_mode", "chat")).lower() != "chat":
        raise PolicyError("This Requesty version supports Chat Completions only.")
    base = effective.get("api_base", "")
    if not isinstance(base, str) or base.rstrip("/") not in ENDPOINTS.values():
        raise PolicyError("Requesty API base must be a documented Requesty endpoint.")
    if base.rstrip('/') != policy.endpoint:
        raise PolicyError('The selected Requesty route conflicts with the owning profile region. Correct the preset endpoint.')
    effective["api_base"] = policy.endpoint
    return effective


def guarded_kwargs(wrapper, overrides):
    import models
    from helpers import plugins
    owner = getattr(wrapper, "_requesty_scope", None)
    if owner is None:
        raise PolicyError("Requesty model has no owning profile. Create a profile model setup.")
    if not scope.enabled(owner):
        raise PolicyError("Requesty is disabled. Select your previous preset in Model Settings.")
    setup = None
    from usr.plugins.requesty.helpers.instance import manager
    native_instance=manager()
    native_mode=native_instance is not None and native_instance.read('setup.json',{}).get('native_presets')
    if not getattr(wrapper, "_requesty_test", False):
        setup = scope.read(owner, "setup.json")
        slot = getattr(wrapper, "_requesty_slot", None)
        if (not setup or not setup.get("active")) and not native_mode:
            raise PolicyError("The owning profile setup changed or is inactive. Rebuild the model before requesting.")
    policy_owner=getattr(wrapper,'_requesty_policy_scope',None) or owner
    policy = settings(policy_owner)
    effective = models._merge_litellm_call_kwargs(wrapper.kwargs, overrides)
    effective = validate_model_parameters(effective, policy)
    raw = scope.key(owner)
    key = effective.get("api_key") or raw
    if key != raw:
        raise PolicyError("Requesty requires the current key of the owning profile.")
    identifier = wrapper.model_name
    if not isinstance(identifier, str) or not identifier.startswith("openai/"):
        raise PolicyError("Requesty must use the OpenAI-compatible transport.")
    identifier = identifier[len("openai/"):]
    available = catalog.fetch(policy.endpoint, key)
    policy.check(available.get(identifier))
    from usr.plugins.requesty.helpers.instance import manager
    instance=manager()
    if instance is not None and instance.read('setup.json',{}).get('native_presets') and not getattr(wrapper,'_requesty_test',False):
        from usr.plugins.local_privacy_guard.helpers.model_guard import filtered_call,tool_agent as filter_agent
        from usr.plugins.requesty.helpers.call_context import tool_agent
        proof=filtered_call.get()
        agent=tool_agent.get() or filter_agent.get() or (proof[1] if proof and proof[0] is wrapper else None)
        if agent is not None:
            from plugins._model_config.helpers import model_config as mc
            role=getattr(wrapper,'_requesty_slot',None)
            section={'chat':'chat_model','utility':'utility_model','vision':'vision_model'}.get(role)
            effective_config=mc.get_effective_config(agent)
            if role!='utility' and agent.context.get_data('_browser_model_active'):
                section='vision_model' if mc.get_vision_model_config(agent) else 'chat_model'
            if section and effective_config.get(section,{}).get('name')!=identifier:
                raise PolicyError('The preset changed. Rebuild this cached model before requesting.')
            if section is None:
                current={effective_config.get(part,{}).get('name') for part in ('chat_model','utility_model')}
                current.add(mc.get_vision_model_config(agent).get('name'))
                if identifier not in current:raise PolicyError('This cached tool model is no longer selected by the native preset. Rebuild it.')
    if settings(policy_owner) != policy or scope.key(owner) != raw or not scope.enabled(owner):
        raise PolicyError("Requesty configuration changed during validation; retry the request.")
    if setup is not None and scope.read(owner, "setup.json") != setup:
        raise PolicyError("The profile setup changed during validation; retry the request.")
    effective["api_key"] = key
    return effective


def guard_function(data):
    wrapper = data["args"][0]
    from usr.plugins.requesty.helpers.call_context import tool_agent, owner as inherited_owner
    active_agent = tool_agent.get()
    if active_agent is None:
        try:
            from usr.plugins.local_privacy_guard.helpers.model_guard import filtered_call
            proof=filtered_call.get()
            if proof and proof[0] is wrapper:active_agent=proof[1]
        except ImportError:pass
    if active_agent is not None and getattr(wrapper, "_requesty_scope", None) is None:
        owner = inherited_owner(active_agent)
        setup = scope.read(owner, "setup.json")
        if setup and setup.get("active") and scope.enabled(owner):
            # Native Vision wrappers can be shared by the framework cache.
            # Validate a per-call copy; never attach one chat's owner to it.
            wrapper = wrapper.model_copy(deep=True)
            endpoint=wrapper.kwargs.get('api_base') or getattr(wrapper.a0_model_conf,'api_base','')
            native_requesty=is_requesty(wrapper) or (
                str(endpoint).rstrip('/') in ENDPOINTS.values() and wrapper.model_name.startswith('openai/'))
            if native_requesty and not wrapper.model_name.startswith('openai/'):
                # Provider discovery may be off; construct the compatible
                # transport explicitly without changing the shared cache.
                from usr.plugins.requesty.helpers.wrapper import GuardedRequestyWrapper
                wrapper=GuardedRequestyWrapper(model=wrapper.a0_model_conf.name,provider='openai',
                    model_config=deepcopy(wrapper.a0_model_conf),**deepcopy(wrapper.kwargs))
            if native_requesty:
                wrapper.a0_model_conf=deepcopy(wrapper.a0_model_conf)
                wrapper.a0_model_conf.provider='requesty_guarded'
            wrapper._requesty_scope = owner
            wrapper._requesty_slot = "vision"
            wrapper._requesty_policy_bound = True
            from usr.plugins.requesty.helpers.instance import manager
            if manager() is not None:
                from usr.plugins.requesty.helpers.call_context import root_agent
                wrapper._requesty_policy_scope=scope.from_agent(root_agent(active_agent))
            data['args']=(wrapper,*data['args'][1:])
    policy_bound = getattr(wrapper, "_requesty_policy_bound", False)
    if policy_bound and not is_requesty(wrapper):
        names = {"system_message", "user_message", "messages", "response_callback", "reasoning_callback",
                 "tokens_callback", "rate_limiter_callback", "explicit_caching"}
        original = data.get("kwargs", {})
        owner = wrapper._requesty_scope
        setup = scope.read(owner, "setup.json")
        if not setup or not setup.get("active") or not scope.enabled(owner):
            raise PolicyError("The owning profile setup changed; rebuild the model.")
        checked = local_kwargs(wrapper, {k:v for k,v in original.items() if k not in names})
        data["kwargs"] = {**checked, **{k:v for k,v in original.items() if k in names}}
        return
    if is_requesty(wrapper):
        # Function arguments are not provider transport kwargs. In particular,
        # messages and callbacks must never be merged into a request-options body.
        original = data.get("kwargs", {})
        names = {"system_message", "user_message", "messages", "response_callback", "reasoning_callback",
                 "tokens_callback", "rate_limiter_callback", "explicit_caching"}
        method_args = {k: v for k, v in original.items() if k in names}
        transport_args = {k: v for k, v in original.items() if k not in names}
        data["kwargs"] = {**guarded_kwargs(wrapper, transport_args), **method_args}
        def has_image(value):
            if isinstance(value,dict):
                return value.get("type") in {"image_url","input_image","image"} or any(has_image(v) for v in value.values())
            if isinstance(value,list):return any(has_image(v) for v in value)
            if hasattr(value,"content"):return has_image(value.content)
            return False
        if has_image(method_args.get("messages", [])) or any(has_image(v) for v in data["args"][1:4]):
            checked=data["kwargs"]
            metadata=catalog.fetch(checked["api_base"],checked["api_key"]).get(wrapper.model_name.removeprefix("openai/"),{})
            if metadata.get("supports_vision") is not True:
                raise PolicyError("This Requesty model does not have verified image support. Select an approved Vision model.")


def wrap_agent_result(data, agent=None, slot=None):
    from usr.plugins.requesty.helpers.call_context import owner as inherited_owner
    owner = inherited_owner(agent) if agent is not None else getattr(data.get("result"), "_requesty_scope", None)
    setup = scope.read(owner, "setup.json") if owner else None
    from usr.plugins.requesty.helpers.instance import manager
    native_instance=manager()
    native_mode=native_instance is not None and native_instance.read('setup.json',{}).get('native_presets')
    if agent is not None and ((setup and setup.get("active")) or native_mode) and scope.enabled(owner):
        from usr.plugins.requesty.helpers.instance import manager
        instance=manager()
        from usr.plugins.requesty.helpers.call_context import root_agent
        policy_owner=scope.from_agent(root_agent(agent)) if instance is not None else owner
        import models
        from usr.plugins.requesty.helpers.wrapper import GuardedRequestyWrapper
        # Native chat/browser presets are actual selections, not hints to ignore.
        selected = data.get("result")
        override = agent.context.get_data("chat_model_override")
        browser_selected = agent.context.get_data("_browser_model_active")
        native_presets=native_mode or bool(setup and setup.get('native_presets'))
        if selected is not None and (override or browser_selected or native_presets):
            endpoint=selected.kwargs.get('api_base') or getattr(selected.a0_model_conf,'api_base','')
            if not is_requesty(selected) and str(endpoint).rstrip('/') in ENDPOINTS.values() and selected.model_name.startswith('openai/'):
                selected=selected.model_copy(deep=True)
                selected.a0_model_conf=deepcopy(selected.a0_model_conf)
                selected.a0_model_conf.provider='requesty_guarded'
            if not is_requesty(selected) and is_local_route(selected,selected.kwargs):
                if native_mode:raise PolicyError('Privacy Agent requires Requesty for Main, Utility and Vision.')
                from usr.plugins.requesty.helpers.wrapper import GuardedLocalWrapper
                prefix, name = selected.model_name.split("/",1)
                local = GuardedLocalWrapper(model=name,provider=prefix,model_config=deepcopy(selected.a0_model_conf), **deepcopy(selected.kwargs))
                local._requesty_scope = owner
                local._requesty_policy_bound = True
                local._requesty_policy_scope=policy_owner
                local_kwargs(local,{})
                data["result"] = local
                return
            if not is_requesty(selected):
                raise PolicyError("This preset bypasses Requesty. Select a Requesty or local model preset.")
            conf = {"provider":"requesty_guarded", "name":selected.model_name.removeprefix("openai/"),
                    "kwargs":deepcopy(selected.kwargs), "vision":bool(selected.a0_model_conf.vision)}
        else:
            conf = setup["models"][slot]
        configuration = deepcopy(conf)
        options = configuration.pop("kwargs", {})
        options = models.ModelConfig(type=models.ModelType.CHAT, **configuration).build_kwargs() | options
        key = scope.key(owner)
        if options.get("api_key") not in (None,"","None","NA",key):
            raise PolicyError("The preset uses a credential from another scope.")
        if options.get("api_base") and str(options["api_base"]).rstrip("/") != settings(owner).endpoint:
            raise PolicyError("The preset route conflicts with this profile's Requesty region.")
        options.update(api_base=settings(owner).endpoint,api_key=key)
        wrapper = GuardedRequestyWrapper(model=conf["name"], provider="openai",
            model_config=models.ModelConfig(type=models.ModelType.CHAT, **deepcopy(conf)), **options)
        wrapper._requesty_scope = owner
        wrapper._requesty_slot = slot
        wrapper._requesty_policy_bound = True
        wrapper._requesty_policy_scope=policy_owner
        data["result"] = wrapper
        return
    wrapper = data.get("result")
    if not is_requesty(wrapper):
        return
    from usr.plugins.requesty.helpers.wrapper import GuardedRequestyWrapper
    if isinstance(wrapper, GuardedRequestyWrapper):
        return
    # Reconstruct only the returned instance; other providers and framework classes stay intact.
    provider, identifier = wrapper.model_name.split("/", 1)
    data["result"] = GuardedRequestyWrapper(
        model=identifier, provider=provider,
        model_config=deepcopy(wrapper.a0_model_conf), **deepcopy(wrapper.kwargs),
    )
    data["result"]._requesty_scope = owner
    data["result"]._requesty_slot = getattr(wrapper, "_requesty_slot", None)
    data["result"]._requesty_test = getattr(wrapper, "_requesty_test", False)
