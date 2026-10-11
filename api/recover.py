from helpers.api import ApiHandler
from usr.plugins.requesty.helpers.configuration import recover
from usr.plugins.requesty.helpers import scope
from usr.plugins.requesty.helpers.policy import PolicyError


class Recover(ApiHandler):
    async def process(self, input, request):
        try:
            with self.thread_lock:
                recover(scope.from_input(input))
            return {"ok": True, "recovered": True}
        except PolicyError as error:
            return {"ok": False, "error": str(error)}
