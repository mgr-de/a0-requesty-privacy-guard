from helpers.extension import Extension
from usr.plugins.requesty.helpers.runtime_guard import wrap_agent_result


class RequestyWrapper(Extension):
    def execute(self, data, **kwargs):
        wrap_agent_result(data)
