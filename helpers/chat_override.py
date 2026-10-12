"""Suspend chat selections only for the profile that owns an active setup."""
from copy import deepcopy
import hashlib
import json

def backup_key(owner):
    return "requesty_chat_override_" + hashlib.sha256(json.dumps(owner).encode()).hexdigest()

def reconcile(agent, owner, active):
    context = agent.context
    key = backup_key(owner)
    current = context.get_data("chat_model_override")
    saved = context.get_data(key)
    # Current versions validate selections instead of silently suspending them.
    # Restore a selection suspended by 0.3.x when no newer selection exists.
    if not active and isinstance(saved, dict) and saved:
        # A newer native selection takes precedence over the suspended choice.
        if not current:
            context.set_data("chat_model_override", deepcopy(saved))
        context.set_data(key, None)

def restore_profile_chats(owner):
    from agent import AgentContext
    from usr.plugins.requesty.helpers import scope
    for context in AgentContext.all():
        agent = context.agent0
        if agent is not None and scope.from_agent(agent) == owner:
            reconcile(agent, owner, False)
