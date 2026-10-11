from helpers.api import ApiHandler
import json
from usr.plugins.requesty.helpers import scope
from usr.plugins.requesty.helpers.configuration import atomic_write
from usr.plugins.requesty.helpers.policy import PolicyError

class Key(ApiHandler):
    async def process(self, input, request):
        try:
            owner = scope.from_input(input)
            if input.get("action") == "set":
                value = input.get("key")
                if not isinstance(value, str) or not value.strip() or len(value) > 4096 or any(c.isspace() for c in value.strip()):
                    raise PolicyError("Enter a valid API key.")
                with self.thread_lock:
                    atomic_write(scope.path(owner, "credentials.json"), json.dumps({"key": value.strip()}))
            elif input.get("action", "get") != "get":
                raise PolicyError("Unknown key action.")
            value = scope.read(owner, "credentials.json", {}).get("key", "")
            setup = scope.read(owner, "setup.json", {})
            return {"ok": True, "has_key": bool(value), "setup": setup.get("models", {}).get("name", ""),
                    "active": setup.get("active", False) and scope.enabled(owner),
                    "requirements_saved": scope.read(owner, "config.json") is not None}
        except PolicyError as error:
            return {"ok": False, "error": str(error)}
