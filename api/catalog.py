import asyncio
from dataclasses import asdict
from helpers.api import ApiHandler
import models
from usr.plugins.requesty.helpers.policy import Policy, PolicyError
from usr.plugins.requesty.helpers.catalog import fetch


class Catalog(ApiHandler):
    async def process(self, input, request):
        try:
            from usr.plugins.requesty.helpers.runtime_guard import settings
            policy = Policy.parse(input["config"]) if "config" in input else settings()
            key = models.get_api_key("requesty_guarded")
            catalog = await asyncio.to_thread(fetch, policy.endpoint, key, refresh=True)
            public = []
            fields = ("id", "api", "data_retention", "data_retention_days", "data_used_for_training",
                      "geolocation", "context_window", "max_output_tokens", "supports_vision", "supports_tool_calling")
            for entry in catalog.values():
                item = {field: entry.get(field) for field in fields}
                item["reasons"] = policy.reasons(entry)
                item["allowed"] = not item["reasons"]
                public.append(item)
            return {"ok": True, "models": public, "policy": asdict(policy),
                    "requesty_zdr": "unverified", "source": "Requesty authenticated model catalog"}
        except PolicyError as error:
            return {"ok": False, "error": str(error)}
