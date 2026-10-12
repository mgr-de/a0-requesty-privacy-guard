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
                    atomic_write(scope.path(owner,'account.json'),'{}')
            elif input.get("action", "get") != "get":
                raise PolicyError("Unknown key action.")
            value = scope.read(owner, "credentials.json", {}).get("key", "")
            if not value:
                try:value=scope.key(owner)
                except PolicyError:pass
            setup = scope.read(owner, "setup.json", {})
            models = setup.get("models", {})
            from usr.plugins.requesty.helpers.instance import manager
            instance=manager()
            return {"ok": True, "has_key": bool(value), "setup": setup.get("models", {}).get("name", ""),
                    "instance_protection":instance is not None,
                    "main": models.get("chat", {}).get("name", ""),
                    "utility": models.get("utility", {}).get("name", ""),
                    "active": setup.get("active", False) and scope.enabled(owner),
                    "requirements_saved": scope.read(owner, "config.json") is not None}
        except PolicyError as error:
            return {"ok": False, "error": str(error)}
