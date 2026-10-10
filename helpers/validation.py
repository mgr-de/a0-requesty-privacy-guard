"""Short synthetic test calls before creating a preset. No Memory or user prompts."""
import asyncio
import hashlib
import secrets
import time
import threading
from dataclasses import asdict
from usr.plugins.requesty.helpers.policy import PolicyError
from usr.plugins.requesty.helpers.configuration import digest
from usr.plugins.requesty.helpers.runtime_guard import settings

_tickets = {}
_lock = threading.RLock()
PROMPT = 'Reply with this JSON only: {"tool_name":"response","tool_args":{"text":"requesty_test_ok"}}'


def state(main, utility):
    import models
    from plugins._model_config.helpers import model_config as mc
    return digest({"main": main, "utility": utility, "policy": asdict(settings()),
                   "key": hashlib.sha256(models.get_api_key_raw("requesty_guarded").encode()).hexdigest(),
                   "presets": mc.get_presets(), "effective": mc.get_effective_config()})


async def validate(main, utility, expected_policy):
    import models
    from usr.plugins.requesty.helpers.catalog import fetch
    policy = settings()
    if expected_policy != asdict(policy):
        raise PolicyError("Save the current privacy settings before testing the models.")
    if not isinstance(main, str) or not isinstance(utility, str):
        raise PolicyError("Choose Main and Utility catalog models.")
    before = state(main, utility)
    key = models.get_api_key("requesty_guarded")
    catalog = await asyncio.to_thread(fetch, policy.endpoint, key, refresh=True)
    for identifier in dict.fromkeys((main, utility)):
        policy.check(catalog.get(identifier))
        wrapper = models.get_chat_model("requesty_guarded", identifier,
            model_config=models.ModelConfig(type=models.ModelType.CHAT, provider="requesty_guarded", name=identifier),
            api_base=policy.endpoint, max_tokens=256, timeout=30, a0_retry_attempts=0)
        try:
            response, _ = await wrapper.unified_call(user_message=PROMPT)
            import json
            parsed = json.loads(response.strip())
            if parsed.get("tool_name") != "response" or parsed.get("tool_args", {}).get("text") != "requesty_test_ok":
                raise ValueError()
        except PolicyError:
            raise
        except Exception:
            raise PolicyError("Synthetic model test failed or returned an incompatible Agent Zero response. No preset was created.") from None
    if before != state(main, utility):
        raise PolicyError("Configuration changed during model tests; run them again.")
    ticket = secrets.token_urlsafe(24)
    with _lock:
        now = time.monotonic()
        for existing in list(_tickets):
            if now - _tickets[existing][0] > 600:
                del _tickets[existing]
        if len(_tickets) >= 32:
            _tickets.pop(next(iter(_tickets)))
        _tickets[ticket] = (now, before)
    return ticket


def consume(ticket, main, utility):
    if not isinstance(ticket, str):
        raise PolicyError("Run the synthetic Main/Utility tests before creating the preset.")
    with _lock:
        saved = _tickets.pop(ticket, None)
    if not saved or time.monotonic() - saved[0] > 600 or saved[1] != state(main, utility):
        raise PolicyError("Model test expired or settings changed; run the tests again.")
