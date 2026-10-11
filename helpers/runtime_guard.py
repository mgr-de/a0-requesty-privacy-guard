"""Guard Agent Zero calls without modifying framework classes or transports."""
from copy import deepcopy
from usr.plugins.requesty.helpers.policy import Policy, PolicyError, ENDPOINTS
from usr.plugins.requesty.helpers import catalog
from usr.plugins.requesty.helpers import scope


def settings(owner):
    raw = scope.read(owner, "config.json")
    if raw is None:
        raise PolicyError("Save privacy requirements for this agent profile first.")
    return Policy.parse(raw)


def is_requesty(wrapper):
    conf = getattr(wrapper, "a0_model_conf", None)
    if str(getattr(conf, "provider", "")).lower() == "requesty_guarded":
        return True
    return False


def guarded_kwargs(wrapper, overrides):
    import models
    from helpers import plugins
    owner = getattr(wrapper, "_requesty_scope", None)
    if owner is None:
        raise PolicyError("Requesty model has no owning profile. Create a profile model setup.")
    if not scope.enabled(owner):
        raise PolicyError("Requesty is disabled. Select your previous preset in Model Settings.")
    setup = None
    if not getattr(wrapper, "_requesty_test", False):
        setup = scope.read(owner, "setup.json")
        slot = getattr(wrapper, "_requesty_slot", None)
        identifier = wrapper.model_name.removeprefix("openai/")
        if not setup or not setup.get("active") or setup.get("models", {}).get(slot, {}).get("name") != identifier:
            raise PolicyError("The owning profile setup changed or is inactive. Rebuild the model before requesting.")
    policy = settings(owner)
    effective = models._merge_litellm_call_kwargs(wrapper.kwargs, overrides)
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
    if str(effective.get("a0_api_mode", "chat")).lower() != "chat":
        raise PolicyError("This Requesty version supports Chat Completions only.")
    base = effective.get("api_base", "")
    if not isinstance(base, str) or base.rstrip("/") not in ENDPOINTS.values():
        raise PolicyError("Requesty API base must be a documented Requesty endpoint.")
    # Region is plugin-owned; user slot defaults do not select the effective router.
    effective["api_base"] = policy.endpoint
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
    if settings(owner) != policy or scope.key(owner) != raw or not scope.enabled(owner):
        raise PolicyError("Requesty configuration changed during validation; retry the request.")
    if setup is not None and scope.read(owner, "setup.json") != setup:
        raise PolicyError("The profile setup changed during validation; retry the request.")
    effective["api_key"] = key
    return effective


def guard_function(data):
    wrapper = data["args"][0]
    if is_requesty(wrapper):
        # Function arguments are not provider transport kwargs. In particular,
        # messages and callbacks must never be merged into a request-options body.
        original = data.get("kwargs", {})
        names = {"system_message", "user_message", "messages", "response_callback", "reasoning_callback",
                 "tokens_callback", "rate_limiter_callback", "explicit_caching"}
        method_args = {k: v for k, v in original.items() if k in names}
        transport_args = {k: v for k, v in original.items() if k not in names}
        data["kwargs"] = {**guarded_kwargs(wrapper, transport_args), **method_args}


def wrap_agent_result(data, agent=None, slot=None):
    owner = scope.from_agent(agent) if agent is not None else getattr(data.get("result"), "_requesty_scope", None)
    setup = scope.read(owner, "setup.json") if owner else None
    if agent is not None and setup and setup.get("active") and scope.enabled(owner):
        import models
        from usr.plugins.requesty.helpers.wrapper import GuardedRequestyWrapper
        conf = setup["models"][slot]
        wrapper = GuardedRequestyWrapper(model=conf["name"], provider="openai",
            model_config=models.ModelConfig(type=models.ModelType.CHAT, **deepcopy(conf)),
            api_base=settings(owner).endpoint, api_key=scope.key(owner))
        wrapper._requesty_scope = owner
        wrapper._requesty_slot = slot
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
