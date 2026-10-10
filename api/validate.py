from helpers.api import ApiHandler
from usr.plugins.requesty.helpers.validation import validate
from usr.plugins.requesty.helpers.policy import PolicyError


class Validate(ApiHandler):
    async def process(self, input, request):
        try:
            ticket = await validate(input.get("main"), input.get("utility"), input.get("config"))
            return {"ok": True, "ticket": ticket}
        except PolicyError as error:
            return {"ok": False, "error": str(error)}
