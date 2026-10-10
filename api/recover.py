from helpers.api import ApiHandler
from usr.plugins.requesty.helpers.configuration import recover, recovery_finished
from usr.plugins.requesty.helpers.policy import PolicyError


class Recover(ApiHandler):
    async def process(self, input, request):
        try:
            result = recover()
            if isinstance(result, list):
                from plugins._model_config.api.model_presets import ModelPresets
                response = await ModelPresets(self.app, self.thread_lock).process({"action": "save", "presets": result}, request)
                if not isinstance(response, dict) or not response.get("ok"):
                    raise PolicyError("Preset recovery could not be completed.")
                recovery_finished()
            return {"ok": True, "recovered": True}
        except PolicyError as error:
            return {"ok": False, "error": str(error)}
