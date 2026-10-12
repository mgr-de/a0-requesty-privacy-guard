from helpers.api import ApiHandler
from usr.plugins.requesty.helpers.configuration import create
from usr.plugins.requesty.helpers.policy import PolicyError
from usr.plugins.requesty.helpers.validation import consume
from usr.plugins.requesty.helpers import scope


class Apply(ApiHandler):
    async def process(self, input, request):
        try:
            with self.thread_lock:
                owner = scope.from_input(input)
                consume(input.get("ticket"), input.get("main"), input.get("utility"), owner)
                result = create(input.get("name"), input.get("main"), input.get("utility"), input.get("config"), owner)
            return {"ok": True, **result}
        except PolicyError as error:
            return {"ok": False, "error": str(error)}
