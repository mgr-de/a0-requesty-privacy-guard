"""Authenticated catalog fetches; no anonymous fallback or persisted credentials."""
import copy
import hashlib
import threading
import time
from usr.plugins.requesty.helpers.policy import ENDPOINTS, PolicyError, parse_catalog

TTL_SECONDS = 60
_cache = {}
_lock = threading.RLock()


def clear():
    with _lock:
        _cache.clear()


def fetch(endpoint, key, *, refresh=False, transport=None):
    import httpx
    if endpoint not in ENDPOINTS.values():
        raise PolicyError("Only documented Requesty endpoints are allowed.")
    if not isinstance(key, str) or not key.strip() or key in ("None", "NA"):
        raise PolicyError("Save a Requesty API key in Agent Zero API Keys first.")
    identity = (endpoint, hashlib.sha256(key.encode()).hexdigest())
    with _lock:
        cached = _cache.get(identity)
        if not refresh and cached and time.monotonic() - cached[0] < TTL_SECONDS:
            return copy.deepcopy(cached[1])
        # A failed forced refresh must invalidate the previously usable snapshot.
        _cache.pop(identity, None)
        try:
            with httpx.Client(timeout=10, follow_redirects=False, transport=transport) as client:
                response = client.get(endpoint + "/models", headers={"Authorization": "Bearer " + key})
                if response.status_code != 200:
                    raise PolicyError(f"Requesty catalog unavailable (HTTP {response.status_code}).")
                if len(response.content) > 8 * 1024 * 1024:
                    raise PolicyError("Requesty catalog exceeds the supported size.")
                payload = response.json()
            models = parse_catalog(payload)
            for identifier, entry in models.items():
                if "/" not in identifier:
                    entry["_requesty_catalog_kind"] = "unverified_policy"
            # This public catalog is supplementary, never a fallback for a
            # failed authenticated catalog. Do not infer aliases from suffixes.
            with httpx.Client(timeout=10, follow_redirects=False, transport=transport) as client:
                managed_response = client.get(endpoint + "/models/managed")
                if managed_response.status_code == 200 and len(managed_response.content) <= 8 * 1024 * 1024:
                    managed = parse_catalog(managed_response.json())
                    for identifier, entry in managed.items():
                        if "/" in identifier or entry.get("owned_by") != "system":
                            continue
                        # Organization policies take precedence in Requesty.
                        # Never apply public metadata to such an override.
                        if identifier in models:
                            continue
                        if "policy/" + identifier in models:
                            models[identifier] = dict(models["policy/" + identifier], id=identifier,
                                                      _requesty_catalog_kind="unverified_policy")
                        else:
                            models[identifier] = dict(entry, _requesty_catalog_kind="managed")
        except PolicyError:
            raise
        except Exception:
            raise PolicyError("Requesty catalog could not be read. Check the connection and key.") from None
        _cache[identity] = (time.monotonic(), models)
        # Bound memory when credentials change often.
        if len(_cache) > 16:
            oldest = min(_cache, key=lambda item: _cache[item][0])
            _cache.pop(oldest, None)
        return copy.deepcopy(models)
