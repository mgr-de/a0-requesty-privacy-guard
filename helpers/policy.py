"""Pure, fail-closed policy evaluation. No framework imports or side effects."""
from dataclasses import dataclass, asdict

ENDPOINTS = {
    "global": "https://router.requesty.ai/v1",
    "eu": "https://router.eu.requesty.ai/v1",
    "us": "https://router.us.requesty.ai/v1",
    "ap": "https://router.ap.requesty.ai/v1",
}
# Deliberate allowlist, not guesses from model names. Extend only from verified data.
LOCATIONS = {
    "eu": {"eu", "eu-central-1", "eu-west-1", "eu-west-3",
           "eu-north-1", "eu-south-1", "eu-south-2", "francecentral", "swedencentral"},
    "us": {"us", "us-east-1", "us-east-2", "us-west-1", "us-west-2", "eastus", "eastus2", "westus", "westus2"},
    "ap": {"ap", "ap-southeast-1", "ap-southeast-2", "ap-northeast-1", "ap-northeast-2", "ap-south-1"},
}


class PolicyError(ValueError):
    """Safe, user-facing error without request payloads or credentials."""


@dataclass(frozen=True)
class Policy:
    region: str = "eu"
    strict_region: bool = True
    no_retention: bool = True
    no_training: bool = True
    require_requesty_zdr: bool = False

    @classmethod
    def parse(cls, raw):
        if not isinstance(raw, dict):
            raise PolicyError("Requesty settings must be an object.")
        expected = set(cls.__dataclass_fields__)
        if set(raw) - expected:
            raise PolicyError("Unknown Requesty setting. Credentials belong in API Keys.")
        values = asdict(cls()) | raw
        if values["region"] not in ENDPOINTS:
            raise PolicyError("Choose Global, EU, US or AP.")
        for field in expected - {"region"}:
            if type(values[field]) is not bool:
                raise PolicyError(f"{field} must be a boolean.")
        if values["strict_region"] and values["region"] == "global":
            raise PolicyError("Strict model residency requires EU, US or AP.")
        return cls(**values)

    @property
    def endpoint(self):
        return ENDPOINTS[self.region]

    def reasons(self, model):
        if not isinstance(model, dict):
            return ["Model metadata is unavailable."]
        reasons = []
        identifier = model.get("id")
        if not isinstance(identifier, str) or not identifier or identifier.startswith("policy/"):
            reasons.append("A concrete catalog model is required; routing policies are not verified.")
        if model.get("api") != "chat":
            reasons.append("A documented chat model is required.")
        if self.no_retention:
            if model.get("data_retention") is not False:
                reasons.append("Provider zero retention is not confirmed.")
            days = model.get("data_retention_days")
            if days is not None and (type(days) not in (int, float) or days != 0):
                reasons.append("Provider retention metadata is contradictory or invalid.")
        if self.no_training and model.get("data_used_for_training") is not False:
            reasons.append("Exclusion of provider training is not confirmed.")
        if self.strict_region:
            location = model.get("geolocation")
            if not isinstance(location, str) or location.lower() not in LOCATIONS[self.region]:
                reasons.append("Model processing in the selected region is not confirmed.")
        if self.require_requesty_zdr:
            reasons.append("Requesty organization ZDR cannot currently be verified through the documented API.")
        return reasons

    def check(self, model):
        reasons = self.reasons(model)
        if reasons:
            raise PolicyError(" ".join(reasons))


def parse_catalog(payload):
    if not isinstance(payload, dict) or payload.get("object") != "list" or not isinstance(payload.get("data"), list):
        raise PolicyError("Requesty returned an invalid model catalog.")
    result = {}
    for model in payload["data"]:
        if not isinstance(model, dict) or not isinstance(model.get("id"), str) or not model["id"]:
            raise PolicyError("Requesty returned an invalid model entry.")
        if model["id"] in result:
            raise PolicyError("Requesty returned duplicate model identities.")
        result[model["id"]] = dict(model)
    return result
