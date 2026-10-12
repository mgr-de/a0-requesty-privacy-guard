"""Task-local owner for native tool model calls (not a global active agent)."""
from contextvars import ContextVar

tool_agent = ContextVar("requesty_tool_agent", default=None)


def root_agent(agent):
    from agent import AgentContext
    from usr.plugins.requesty.helpers.policy import PolicyError
    current=getattr(agent.context,'agent0',None) or agent
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
    setup = scope.read(candidate, "setup.json")
    if setup and setup.get("active") and scope.enabled(candidate):
        return candidate
    return scope.from_agent(agent)
