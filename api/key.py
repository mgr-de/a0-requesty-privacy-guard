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
            native=(instance is not None and instance.read('setup.json',{}).get('native_presets')) or setup.get('native_presets')
            if native:
                from plugins._model_config.helpers import model_config as mc
                config=mc.get_config(project_name=owner[0] or None,agent_profile=owner[1])
                models={'chat':config.get('chat_model',{}),'utility':config.get('utility_model',{})}
            label=mc.get_configured_preset_name(project_name=owner[0] or None,agent_profile=owner[1]) if native else setup.get('models',{}).get('name','')
            return {"ok": True, "has_key": bool(value), "setup": label,
                    "instance_protection":instance is not None,
                    "native_presets":bool(native),
                    "main": models.get("chat", {}).get("name", ""),
                    "utility": models.get("utility", {}).get("name", ""),
                    "active": (setup.get("active", False) or native) and scope.enabled(owner),
                    "requirements_saved": scope.read(owner, "config.json") is not None}
        except PolicyError as error:
            return {"ok": False, "error": str(error)}
