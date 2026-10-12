import unittest
from unittest.mock import patch
import httpx
from usr.plugins.requesty.helpers import catalog
from usr.plugins.requesty.helpers.policy import ENDPOINTS, PolicyError


class CatalogTests(unittest.TestCase):
    def setUp(self):
        catalog.clear()

    def test_cache_identity_and_copy(self):
        requests = []
        def respond(request):
            requests.append((str(request.url), request.headers.get("authorization")))
            return httpx.Response(200, json={"object": "list", "data": [{"id": "test", "api": "chat"}]})
        transport = httpx.MockTransport(respond)
        result = catalog.fetch(ENDPOINTS["eu"], "synthetic-key", transport=transport)
        result["test"]["id"] = "mutated"
        self.assertEqual(catalog.fetch(ENDPOINTS["eu"], "synthetic-key", transport=transport)["test"]["id"], "test")
        catalog.fetch(ENDPOINTS["us"], "synthetic-key", transport=transport)
        catalog.fetch(ENDPOINTS["eu"], "other-key", transport=transport)
        self.assertEqual(len(requests), 6)

    def test_errors_have_no_fallback_or_secret(self):
        for status in (302, 401, 403, 429, 500):
            requests = []
            def respond(request):
                requests.append(request)
                return httpx.Response(status, text="synthetic-key private-body", headers={"location": "https://other.test"})
            with self.assertRaises(PolicyError) as caught:
                catalog.fetch(ENDPOINTS["eu"], "synthetic-key", refresh=True, transport=httpx.MockTransport(respond))
            self.assertNotIn("synthetic-key", str(caught.exception))
            self.assertEqual(len(requests), 1)

    def test_timeout_and_invalid_json(self):
        def timeout(request):
            raise httpx.ReadTimeout("synthetic-key")
        for transport in (httpx.MockTransport(timeout), httpx.MockTransport(lambda r: httpx.Response(200, text="invalid"))):
            with self.assertRaises(PolicyError) as caught:
                catalog.fetch(ENDPOINTS["eu"], "synthetic-key", transport=transport)
            self.assertNotIn("synthetic-key", str(caught.exception))

    def test_expiry(self):
        count = []
        transport = httpx.MockTransport(lambda r: count.append(1) or httpx.Response(200, json={"object": "list", "data": []}))
        with patch.object(catalog.time, "monotonic", return_value=0):
            catalog.fetch(ENDPOINTS["eu"], "synthetic-key", transport=transport)
        with patch.object(catalog.time, "monotonic", return_value=61):
            catalog.fetch(ENDPOINTS["eu"], "synthetic-key", transport=transport)
        self.assertEqual(len(count), 4)

    def test_managed_names_keep_metadata_and_custom_override_is_blocked(self):
        from usr.plugins.requesty.helpers.policy import Policy
        safe = {"api":"chat", "data_retention":False, "data_retention_days":0,
                "data_used_for_training":False, "geolocation":"eu"}
        def respond(request):
            if request.url.path.endswith('/managed'):
                self.assertNotIn('authorization', request.headers)
                entries = [dict(safe,id=name,owned_by='system') for name in ('short','override','unknown')]
                entries[-1]['geolocation']='global'
            else:
                self.assertEqual(request.headers['authorization'],'Bearer synthetic-key')
                entries = [dict(safe,id='vendor/short'),dict(safe,id='policy/override')]
            return httpx.Response(200,json={"object":"list","data":entries})
        result=catalog.fetch(ENDPOINTS['eu'],'synthetic-key',transport=httpx.MockTransport(respond))
        Policy().check(result['short']);Policy().check(result['vendor/short'])
        for name in ('override','unknown','policy/override'):
            with self.assertRaises(PolicyError):Policy().check(result[name])

    def test_public_metadata_cannot_replace_an_authenticated_alias(self):
        from usr.plugins.requesty.helpers.policy import Policy
        safe={"id":"short","api":"chat","owned_by":"system","data_retention":False,
              "data_used_for_training":False,"geolocation":"eu"}
        result=catalog.fetch(ENDPOINTS['eu'],'synthetic-key',transport=httpx.MockTransport(
            lambda request:httpx.Response(200,json={"object":"list","data":[safe]})))
        with self.assertRaises(PolicyError):Policy().check(result['short'])

    def test_no_unapproved_endpoint(self):
        for endpoint in ("https://other.test", "http://router.eu.requesty.ai/v1", ENDPOINTS["eu"] + "?x=1"):
            with self.assertRaises(PolicyError):
                catalog.fetch(endpoint, "synthetic-key")

    def test_failed_refresh_invalidates_cache(self):
        good = httpx.MockTransport(lambda r: httpx.Response(200, json={"object": "list", "data": []}))
        bad = httpx.MockTransport(lambda r: httpx.Response(403))
        catalog.fetch(ENDPOINTS["eu"], "synthetic-key", transport=good)
        with self.assertRaises(PolicyError):
            catalog.fetch(ENDPOINTS["eu"], "synthetic-key", refresh=True, transport=bad)
        with self.assertRaises(PolicyError):
            catalog.fetch(ENDPOINTS["eu"], "synthetic-key", transport=bad)
