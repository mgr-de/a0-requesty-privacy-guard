"""Create a separate preset; never activate it or change embeddings."""
import hashlib
import json
import os
import tempfile
import threading
from copy import deepcopy
from pathlib import Path
from usr.plugins.requesty.helpers.policy import PolicyError
from usr.plugins.requesty.helpers.runtime_guard import settings
from usr.plugins.requesty.helpers.catalog import fetch

_lock = threading.RLock()


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".requesty-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def strict_presets():
    from plugins._model_config.helpers import model_config as mc
    try:
        return mc._load_global_presets(raise_on_error=True)
    except Exception:
        raise PolicyError("Existing presets cannot be read safely. Restore the preset file before making changes.") from None


def build_candidate(name, original, main, utility, policy, catalog):
    from plugins._model_config.helpers import model_config as mc
    if not isinstance(name, str) or not name.strip() or name.strip().casefold() == "default" or len(name) > 80:
        raise PolicyError("Choose a new preset name other than Default (maximum 80 characters).")
    candidate = mc.config_to_preset(deepcopy(original), name.strip())
    for slot, identifier in (("chat", main), ("utility", utility)):
        if not isinstance(identifier, str):
            raise PolicyError("Choose a catalog model for Main and Utility.")
        metadata = catalog.get(identifier)
        policy.check(metadata)
        config = deepcopy(candidate.get(slot, {}))
        config.update(provider="requesty_guarded", name=identifier, api_base=policy.endpoint,
                      kwargs={}, vision=metadata.get("supports_vision") is True)
        context = metadata.get("context_window")
        if type(context) is not int or context <= 0:
            raise PolicyError("The model catalog must confirm a valid context window.")
        config["ctx_length"] = min(int(config.get("ctx_length") or context), context)
        candidate[slot] = config
    # Do not silently retain a cloud vision sidecar outside Requesty privacy controls.
    candidate["vision"] = {}
    before = mc.config_to_preset(original, "before").get("embedding", {})
    if candidate.get("embedding", {}) != before:
        raise PolicyError("Embedding settings changed; preset creation has been stopped.")
    return candidate


def create(name, main, utility, expected_policy):
    import models
    from dataclasses import asdict
    from helpers import files, cache, yaml as yaml_helper
    from plugins._model_config.helpers import model_config as mc
    with _lock:
        policy = settings()
        if expected_policy != asdict(policy):
            raise PolicyError("Save the current privacy settings, then refresh and validate the model catalog again.")
        presets = strict_presets()
        if not isinstance(name, str) or any(str(p.get("name", "")).casefold() == name.strip().casefold() for p in presets):
            raise PolicyError("That preset name already exists or is invalid.")
        key = models.get_api_key("requesty_guarded")
        catalog = fetch(policy.endpoint, key, refresh=True)
        original = mc.get_effective_config()
        candidate = build_candidate(name, original, main, utility, policy, catalog)
        # Re-read after network I/O to avoid saving a stale collection.
        if presets != strict_presets() or original != mc.get_effective_config() or policy != settings():
            raise PolicyError("Model configuration changed during validation; retry.")
        before = mc.validate_presets(presets)
        after = mc.validate_presets([*presets, candidate])
        path = mc._get_presets_path()
        journal_path = files.get_abs_path("usr/plugins/requesty/recovery.json")
        journal = {"before": before, "after_digest": digest(after), "preset": candidate["name"], "state": "prepared"}
        atomic_write(journal_path, json.dumps(journal))
        atomic_write(path, yaml_helper.dumps(after))
        cache.clear(mc.PRESETS_CACHE_AREA)
        journal["state"] = "applied"
        atomic_write(journal_path, json.dumps(journal))
        return {"preset": candidate["name"], "embedding_preserved": True,
                "activated": False, "vision_sidecar_disabled": True}


def recover():
    from helpers import files, cache, yaml as yaml_helper
    from plugins._model_config.helpers import model_config as mc
    with _lock:
        path = files.get_abs_path("usr/plugins/requesty/recovery.json")
        if not os.path.exists(path):
            raise PolicyError("No Requesty preset creation is available to undo.")
        journal = json.loads(Path(path).read_text(encoding="utf-8"))
        before = mc.validate_presets(journal["before"])
        current = mc.validate_presets(strict_presets())
        if digest(current) == digest(before):
            journal["state"] = "recovered"
            atomic_write(path, json.dumps(journal))
            return {"recovered": True}
        if digest(current) != journal["after_digest"]:
            raise PolicyError("Presets changed after creation. Select your previous preset; automatic restore would overwrite newer edits.")
        # Use the framework API so references to the removed preset are repaired.
        # Recovery is explicit and does not dispatch any model requests.
        from plugins._model_config.api.model_presets import ModelPresets
        return before


def recovery_finished():
    from helpers import files
    path = files.get_abs_path("usr/plugins/requesty/recovery.json")
    journal = json.loads(Path(path).read_text(encoding="utf-8"))
    journal["state"] = "recovered"
    atomic_write(path, json.dumps(journal))
