from helpers.api import ApiHandler
from usr.plugins.requesty.helpers.configuration import create
from usr.plugins.requesty.helpers.policy import PolicyError
from usr.plugins.requesty.helpers.validation import consume


class Apply(ApiHandler):
    async def process(self, input, request):
        try:
            with self.thread_lock:
                consume(input.get("ticket"), input.get("main"), input.get("utility"))
                result = create(input.get("name"), input.get("main"), input.get("utility"), input.get("config"))
            return {"ok": True, **result}
        except PolicyError as error:
            return {"ok": False, "error": str(error)}
