from unittest.mock import patch
from plugins._agent_editor.helpers.editor import EditorAgent, build_editor_state
from usr.plugins.requesty.helpers.call_context import root_agent
from usr.plugins.requesty.helpers.chat_override import reconcile

def test_native_editor_without_chat_identity_reads_configuration():
    editor=EditorAgent('agent0')
    assert not hasattr(editor.context,'id')
    assert root_agent(editor) is editor
    reconcile(editor,('', 'agent0'),False)
    state=build_editor_state('agent0')
    assert state['profile']['id']=='agent0'
    assert state['model_presets']

def test_editor_of_another_profile_does_not_inherit_the_open_chat_owner():
    from agent import Agent,AgentConfig
    chat=Agent(0,AgentConfig(profile='agent0',mcp_servers=''))
    editor=EditorAgent('developer',chat.context)
    assert root_agent(editor) is editor
