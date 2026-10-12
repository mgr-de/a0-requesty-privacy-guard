"""Native adapters for parent policies when a child's plugin hooks are hidden.

No service or shared model configuration. Independent chats are no-ops.
"""
import hashlib,json
from pathlib import Path

PLUGIN='requesty'

def inherited(agent):
    if agent is None:return False
    from helpers import plugins
    from usr.plugins.requesty.helpers import scope
    from usr.plugins.requesty.helpers.call_context import root_agent
    root=root_agent(agent)
    if root is agent or PLUGIN in plugins.get_enabled_plugins(agent):return False
    owner=scope.from_agent(root);setup=scope.read(owner,'setup.json')
    return bool(setup and setup.get('active') and scope.enabled(owner))

def sources():
    header='from helpers.extension import Extension\n\nclass InheritedRequesty(Extension):\n'
    def body(code,async_=False):
        return header+('    async def execute(self, data=None, **kwargs):\n' if async_ else '    def execute(self, data=None, **kwargs):\n')+''.join('        '+line+'\n' for line in code.splitlines())
    files={}
    for slot,getter in [('chat','get_chat_model'),('utility','get_utility_model')]:
        files[f'_functions/agent/Agent/{getter}/end/_91_requesty_inherited_model.py']=body(
            f"try:\n    from usr.plugins.requesty.helpers.inherited_bridge import inherited\n    from usr.plugins.requesty.helpers.runtime_guard import wrap_agent_result\nexcept ImportError:return\nif inherited(self.agent):wrap_agent_result(data,self.agent,'{slot}')")
    files['_functions/helpers/plugins/get_plugin_config/end/_91_requesty_inherited_config.py']=body(
        "try:\n    from usr.plugins.requesty.helpers.inherited_bridge import inherited\n    from usr.plugins.requesty.extensions.python._functions.helpers.plugins.get_plugin_config.end._90_requesty_memory_safety import RequestyMemorySafety\nexcept ImportError:return\nif inherited(self.agent):RequestyMemorySafety(self.agent).execute(data)")
    files['tool_execute_before/_02_requesty_inherited_owner.py']=body(
        "try:\n    from usr.plugins.requesty.helpers.inherited_bridge import inherited\n    from usr.plugins.requesty.helpers.call_context import tool_agent\nexcept ImportError:return\nif inherited(self.agent):tool_agent.set(self.agent)")
    clear="try:\n    from usr.plugins.requesty.helpers.call_context import tool_agent\nexcept ImportError:return\nif tool_agent.get() is self.agent:tool_agent.set(None)"
    for point in ['tool_execute_after','monologue_end']:
        files[point+'/_02_requesty_inherited_clear.py']=body(clear)
    for method in ['unified_call','unified_turn']:
        files[f'_functions/models/LiteLLMChatWrapper/{method}/start/_91_requesty_scoped_tool.py']=body(
            "try:\n    from usr.plugins.requesty.helpers.runtime_guard import guard_function\n    from usr.plugins.requesty.helpers.call_context import tool_agent\nexcept ImportError:return\nfrom helpers import plugins\nif tool_agent.get() is not None and 'requesty' not in plugins.get_enabled_plugins(None):guard_function(data)")
    return files

def manage(plugin_root,remove=False):
    root=Path(plugin_root).resolve();user=root.parent.parent
    target_root=user/'extensions'/'python';manifest=user/'privacy-guard-adapters'/(PLUGIN+'.json')
    legacy=root/'inherited-bridge.json'
    source_manifest=manifest if manifest.exists() else legacy
    if source_manifest.is_symlink() or not manifest.resolve().is_relative_to(user):
        raise ValueError('Native adapter ownership must stay in the user directory without symbolic links.')
    previous=json.loads(source_manifest.read_text()) if source_manifest.exists() else {}
    if not target_root.resolve().is_relative_to(user):raise ValueError('Native adapters must stay below the user directory.')
    owned=sources();planned=[]
    if not isinstance(previous,dict) or not set(previous).issubset(owned) or any(
        not isinstance(value,str) or len(value)!=64 or any(ch not in '0123456789abcdef' for ch in value)
        for value in previous.values()):
        raise ValueError('Native adapter ownership is invalid. Preserve and recover the ownership journal before updating.')
    digest=lambda value:hashlib.sha256(value.encode()).hexdigest()
    for relative,source in owned.items():
        target=(target_root/relative).resolve()
        if not target.is_relative_to(target_root.resolve()):raise ValueError('Invalid native adapter path.')
        current=target.read_text(encoding='utf-8') if target.exists() else None
        if remove:
            if current is not None and previous.get(relative)==digest(current):planned.append((target,None))
        else:
            if current is not None and current!=source and previous.get(relative)!=digest(current):
                raise ValueError('A native adapter path contains another extension. Preserve it and choose a clean installation path.')
            planned.append((target,source))
    for target,source in planned:
        if source is None:target.unlink()
        else:
            target.parent.mkdir(parents=True,exist_ok=True);target.write_text(source,encoding='utf-8')
    if not remove:
        manifest.parent.mkdir(parents=True,exist_ok=True)
        manifest.write_text(json.dumps({path:digest(source) for path,source in owned.items()}),encoding='utf-8')
    elif manifest.exists():manifest.unlink()
    if legacy.exists():legacy.unlink()
    return {'native_adapters_removed' if remove else 'native_adapters_installed':len(planned)}
