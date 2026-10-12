from helpers.extension import Extension
from usr.plugins.requesty.helpers.call_context import tool_agent

class PrivacyCallOwner(Extension):
    def execute(self, **kwargs):
        tool_agent.set(None)
