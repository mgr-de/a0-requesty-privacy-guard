"""Task-local owner for native tool model calls (not a global active agent)."""
from contextvars import ContextVar

tool_agent = ContextVar("requesty_tool_agent", default=None)


def root_agent(agent):
    from agent import AgentContext
    from usr.plugins.requesty.helpers.policy import PolicyError
    from plugins._agent_editor.helpers.editor import EditorAgent
    if isinstance(agent,EditorAgent):return agent
    current=getattr(agent.context,'agent0',None) or agent
    # Native profile editors use a lightweight context without chat identity.
    # Configuration reads need profile ownership, not parent-chat traversal.
    if not getattr(current.context,'id',None):return current
    seen=set()
    while current.context.id not in seen:
        seen.add(current.context.id)
        getter=getattr(current.context,'get_output_data',None)
        parent_id=getter('parent_context_id') if getter else None
        if not parent_id:return current
        parent=AgentContext.get(parent_id)
        if parent is None or parent.agent0 is None:
            raise PolicyError('The parent privacy context is unavailable. Restore the parent chat before continuing this subordinate.')
        current=parent.agent0
    raise PolicyError('The subordinate privacy context has a cyclic parent chain.')


def owner(agent):
    from usr.plugins.requesty.helpers import scope
    root = root_agent(agent)
    candidate = scope.from_agent(root)
    from usr.plugins.requesty.helpers.instance import manager
    instance=manager()
    if instance is not None:return instance.requesty_owner(root)
    setup = scope.read(candidate, "setup.json")
    if setup and setup.get("active") and scope.enabled(candidate):
        return candidate
    return scope.from_agent(agent)
