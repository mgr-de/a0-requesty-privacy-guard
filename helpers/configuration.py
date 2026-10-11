"""Profile model setups; shared presets are never written."""
import hashlib
import json
import os
import tempfile
import threading
from copy import deepcopy
from pathlib import Path
from dataclasses import asdict
from usr.plugins.requesty.helpers.policy import PolicyError
from usr.plugins.requesty.helpers.runtime_guard import settings
from usr.plugins.requesty.helpers.catalog import fetch
from usr.plugins.requesty.helpers import scope

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

def build_candidate(name, original, main, utility, policy, catalog):
    from plugins._model_config.helpers import model_config as mc
    if not isinstance(name, str) or not name.strip() or len(name) > 80:
        raise PolicyError("Choose a setup name (maximum 80 characters).")
    candidate = mc.config_to_preset(deepcopy(original), name.strip())
    for slot, identifier in (("chat", main), ("utility", utility)):
        if not isinstance(identifier, str):
            raise PolicyError("Choose a catalog model for Main and Utility.")
        metadata = catalog.get(identifier)
        policy.check(metadata)
        context = metadata.get("context_window")
        if type(context) is not int or context <= 0:
            raise PolicyError("The catalog must confirm a valid context window.")
        candidate[slot] = {"provider": "requesty_guarded", "name": identifier,
            "api_base": policy.endpoint, "kwargs": {}, "vision": metadata.get("supports_vision") is True,
            "ctx_length": context}
    candidate["vision"] = {}
    return candidate

def create(name, main, utility, expected_policy, owner):
    from plugins._model_config.helpers import model_config as mc
    with _lock:
        policy = settings(owner)
        if expected_policy != asdict(policy):
            raise PolicyError("Save the profile privacy settings, then test again.")
        key = scope.key(owner)
        catalog = fetch(policy.endpoint, key, refresh=True)
        original = mc.get_config(project_name=owner[0], agent_profile=owner[1])
        candidate = build_candidate(name, original, main, utility, policy, catalog)
        if policy != settings(owner) or key != scope.key(owner):
            raise PolicyError("Profile settings changed during validation; retry.")
        candidate.pop("embedding", None)
        atomic_write(scope.path(owner, "setup.json"), json.dumps({"active": False, "models": candidate}))
        return {"preset": candidate["name"], "embedding_preserved": True,
                "activated": False, "vision_sidecar_disabled": True}

def activate(owner, active):
    if type(active) is not bool:
        raise PolicyError("Activation must be a boolean.")
    with _lock:
        setup = scope.read(owner, "setup.json")
        if not isinstance(setup, dict) or not isinstance(setup.get("models"), dict):
            raise PolicyError("Create a model setup for this profile first.")
        if active:
            policy = settings(owner)
            key = scope.key(owner)
            catalog = fetch(policy.endpoint, key, refresh=True)
            for slot in ("chat", "utility"):
                policy.check(catalog.get(setup["models"][slot]["name"]))
            if policy != settings(owner) or key != scope.key(owner) or setup != scope.read(owner, "setup.json"):
                raise PolicyError("Profile configuration changed during activation; retry.")
        setup["active"] = active
        atomic_write(scope.path(owner, "setup.json"), json.dumps(setup))
        return {"activated": active}

def recover(owner):
    return activate(owner, False)
