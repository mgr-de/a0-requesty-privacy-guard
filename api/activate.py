from helpers.api import ApiHandler
from usr.plugins.requesty.helpers import scope
from usr.plugins.requesty.helpers.configuration import activate
from usr.plugins.requesty.helpers.policy import PolicyError

class Activate(ApiHandler):
    async def process(self, input, request):
        try:
            with self.thread_lock:
                result = activate(scope.from_input(input), input.get("active"))
            return {"ok": True, **result}
        except PolicyError as error:
            return {"ok": False, "error": str(error)}
