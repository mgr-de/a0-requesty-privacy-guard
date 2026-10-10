import unittest
from usr.plugins.requesty.helpers.policy import Policy, PolicyError, parse_catalog


def model(**changes):
    return {"id": "bedrock/test@eu-central-1", "api": "chat", "data_retention": False,
            "data_retention_days": 0, "data_used_for_training": False,
            "geolocation": "eu-central-1"} | changes


class PolicyTests(unittest.TestCase):
    def test_valid(self):
        Policy().check(model())

    def test_unknown_or_false_type_never_passes(self):
        for field in ("data_retention", "data_used_for_training"):
            for value in (True, None, "false", 0, [], {}):
                with self.subTest(field=field, value=value), self.assertRaises(PolicyError):
                    Policy().check(model(**{field: value}))

    def test_region_not_inferred_from_name(self):
        for location in (None, "global", "unknown", "eu-west-2", "us-east-1", "EUROPE"):
            with self.subTest(location=location), self.assertRaises(PolicyError):
                Policy().check(model(geolocation=location))

    def test_contradictory_days(self):
        for days in (1, -1, True, "0", float("nan")):
            with self.subTest(days=days), self.assertRaises(PolicyError):
                Policy().check(model(data_retention_days=days))

    def test_org_zdr_is_not_provider_retention(self):
        with self.assertRaisesRegex(PolicyError, "organization ZDR"):
            Policy(require_requesty_zdr=True).check(model())

    def test_policy_and_wrong_modality(self):
        for changes in ({"id": "policy/test"}, {"api": "embedding"}, {"api": None}):
            with self.assertRaises(PolicyError):
                Policy().check(model(**changes))

    def test_explicit_relaxation(self):
        Policy(region="global", strict_region=False, no_retention=False, no_training=False).check(model(data_retention=True, data_used_for_training=True, geolocation="global"))

    def test_settings_rejected(self):
        for raw in (None, [], {"api_key": "secret"}, {"region": "elsewhere"}, {"strict_region": "true"}, {"region": "global"}):
            with self.assertRaises(PolicyError):
                Policy.parse(raw)

    def test_bad_catalog(self):
        for payload in ({}, {"object": "list", "data": [None]}, {"object": "list", "data": [model(), model()]}):
            with self.assertRaises(PolicyError):
                parse_catalog(payload)


if __name__ == "__main__":
    unittest.main()
