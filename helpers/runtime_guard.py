"""Guard Agent Zero calls without modifying framework classes or transports."""
from copy import deepcopy
from usr.plugins.requesty.helpers.policy import Policy, PolicyError, ENDPOINTS
from usr.plugins.requesty.helpers import catalog


def settings():
    from helpers import plugins
    return Policy.parse(plugins.get_plugin_config("requesty", project_name="", agent_profile="") or {})


def is_requesty(wrapper):
    conf = getattr(wrapper, "a0_model_conf", None)
    if str(getattr(conf, "provider", "")).lower() == "requesty_guarded":
        return True
    return (getattr(wrapper, "kwargs", {}) or {}).get("api_base", "").rstrip("/") in ENDPOINTS.values()


def guarded_kwargs(wrapper, overrides):
    import models
    from helpers import plugins
    if plugins.get_toggle_state("requesty") != "enabled":
        raise PolicyError("Requesty is disabled. Select your previous preset in Model Settings.")
    policy = settings()
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
    raw = models.get_api_key_raw("requesty_guarded")
    keys = [item.strip() for item in raw.split(",") if item.strip() and item.strip() not in ("None", "NA")]
    key = effective.get("api_key") or (keys[0] if len(keys) == 1 else None)
    if not isinstance(key, str) or key not in keys:
        raise PolicyError("Requesty requires a current key from Agent Zero API Keys.")
    identifier = wrapper.model_name
    if not isinstance(identifier, str) or not identifier.startswith("openai/"):
        raise PolicyError("Requesty must use the OpenAI-compatible transport.")
    identifier = identifier[len("openai/"):]
    available = catalog.fetch(policy.endpoint, key)
    policy.check(available.get(identifier))
    if settings() != policy or models.get_api_key_raw("requesty_guarded") != raw:
        raise PolicyError("Requesty configuration changed during validation; retry the request.")
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


def wrap_agent_result(data):
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
