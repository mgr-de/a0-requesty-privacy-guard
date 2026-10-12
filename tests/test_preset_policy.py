"""Presets, local transports, sidecars and subordinate profile boundaries."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
import models
from usr.plugins.requesty.helpers import runtime_guard as guard, scope
from usr.plugins.requesty.helpers.call_context import tool_agent, owner
from usr.plugins.requesty.helpers.policy import Policy,PolicyError

MODEL={"id":"synthetic/eu","api":"chat","geolocation":"eu","data_retention":False,"data_used_for_training":False}


@pytest.fixture
def protected(monkeypatch):
    monkeypatch.setattr(guard.local_models,'confirm',lambda *a,**kw:True)
    setup={"active":True,"models":{"chat":{"provider":"requesty_guarded","name":MODEL["id"]},
                                     "utility":{"provider":"requesty_guarded","name":MODEL["id"]}}}
    monkeypatch.setattr(scope,"read",lambda identity,name,default=None:setup if name=="setup.json" else {})
    monkeypatch.setattr(scope,"enabled",lambda identity:True)
    monkeypatch.setattr(scope,"key",lambda identity:"synthetic-profile-key")
    monkeypatch.setattr(guard,"settings",lambda identity:Policy())
    monkeypatch.setattr(guard.catalog,"fetch",lambda *a,**k:{MODEL["id"]:MODEL,"synthetic/second":{**MODEL,"id":"synthetic/second"}})
    return setup


def make(provider="requesty_guarded",name="synthetic/second",**kwargs):
    from usr.plugins.requesty.helpers.wrapper import GuardedRequestyWrapper
    wrapper=GuardedRequestyWrapper(model=name,provider="openai",model_config=models.ModelConfig(type=models.ModelType.CHAT,provider=provider,name=name),
                                  api_base=Policy().endpoint,api_key="synthetic-profile-key",**kwargs)
    wrapper._requesty_scope=("","A")
    return wrapper


def test_different_approved_model_keeps_its_selection(protected):
    wrapper=make()
    assert guard.guarded_kwargs(wrapper,{})["api_base"]==Policy().endpoint
    assert wrapper.model_name=="openai/synthetic/second"


def test_direct_provider_and_transport_override_rejected(protected):
    with pytest.raises(PolicyError):guard.guarded_kwargs(make(),{"base_url":"https://unapproved.example"})
    wrapper=make(provider="openrouter")
    wrapper._requesty_policy_bound=True
    with pytest.raises(PolicyError,match="bypasses Requesty"):
        guard.guard_function({"args":(wrapper,),"kwargs":{}})


def test_local_endpoint_labels_cannot_hide_remote_hosts(protected):
    wrapper=models.LiteLLMChatWrapper(model="gemma3:4b",provider="ollama_chat",
        model_config=models.ModelConfig(type=models.ModelType.CHAT,provider="ollama_chat",name="gemma3:4b"),
        api_base="http://host.docker.internal:11434")
    assert guard.local_kwargs(wrapper,{})["api_base"].startswith("http://host")
    with pytest.raises(PolicyError):guard.local_kwargs(wrapper,{"api_base":"https://remote.example"})


def test_tool_vision_without_owner_is_guarded(protected):
    context=SimpleNamespace(agent0=None,id='synthetic-root')
    agent=SimpleNamespace(context=context,config=SimpleNamespace(profile="A"));context.agent0=agent
    from unittest.mock import patch
    marker=tool_agent.set(agent)
    try:
        with patch.object(scope,"from_agent",return_value=("","A")):
            data={"args":(make(),),"kwargs":{"messages":[]}}
            data["args"][0]._requesty_scope=None
            guard.guard_function(data)
            assert data["args"][0]._requesty_scope is None
            assert data['kwargs']['api_key']=='synthetic-profile-key'
    finally:tool_agent.reset(marker)


def test_subordinate_cannot_escape_by_profile_name(protected,monkeypatch):
    context=SimpleNamespace(agent0=None,id='synthetic-root')
    parent=SimpleNamespace(context=context,config=SimpleNamespace(profile="A"));context.agent0=parent
    child=SimpleNamespace(context=context,config=SimpleNamespace(profile="B"))
    monkeypatch.setattr(scope,"from_agent",lambda a:("",a.config.profile))
    assert owner(child)==("","A")
    independent_context=SimpleNamespace(agent0=None,id='synthetic-independent')
    independent=SimpleNamespace(context=independent_context,config=SimpleNamespace(profile="B"));independent_context.agent0=independent
    assert owner(independent)==("","B")


def test_vision_requires_catalog_support(protected,monkeypatch):
    data={'args':(make(),),'kwargs':{'messages':[{'role':'user','content':[
        {'type':'image_url','image_url':{'url':'data:image/png;base64,AA=='}}]}]}}
    with pytest.raises(PolicyError,match='image support'):guard.guard_function(data)
    monkeypatch.setattr(guard.catalog,'fetch',lambda *a,**k:{'synthetic/second':{**MODEL,'supports_vision':True}})
    guard.guard_function(data)


def test_cached_unowned_vision_wrapper_stays_unowned_between_profiles(protected,monkeypatch):
    wrapper=make();wrapper._requesty_scope=None
    seen=[]
    monkeypatch.setattr(scope,'from_agent',lambda a:('',a.config.profile))
    monkeypatch.setattr(guard,'guarded_kwargs',lambda w,k:seen.append(w._requesty_scope) or {})
    for profile in ('A','B'):
        from agent import Agent,AgentConfig
        agent=Agent(0,AgentConfig(profile=profile,mcp_servers=''))
        marker=tool_agent.set(agent)
        try:guard.guard_function({'args':(wrapper,), 'kwargs':{}})
        finally:tool_agent.reset(marker)
    assert seen==[('','A'),('','B')]
    assert wrapper._requesty_scope is None


def test_native_separate_subordinate_context_inherits_root_policy(protected,monkeypatch):
    from agent import Agent,AgentConfig
    parent=Agent(0,AgentConfig(profile='A',mcp_servers=''))
    child=Agent(1,AgentConfig(profile='B',mcp_servers=''))
    child.context.set_output_data('parent_context_id',parent.context.id)
    monkeypatch.setattr(scope,'from_agent',lambda a:('',a.config.profile))
    assert child.context is not parent.context
    assert owner(child)==('','A')
    independent=Agent(0,AgentConfig(profile='B',mcp_servers=''))
    assert owner(independent)==('','B')
    child.context.set_output_data('parent_context_id','missing-parent')
    with pytest.raises(PolicyError,match='parent privacy context'):owner(child)
