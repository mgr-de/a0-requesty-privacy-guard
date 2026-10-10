from helpers.extension import Extension
from usr.plugins.requesty.helpers.runtime_guard import guard_function


class RequestyGuard(Extension):
    def execute(self, data, **kwargs):
        guard_function(data)
