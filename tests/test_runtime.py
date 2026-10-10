import unittest
from unittest.mock import patch
from types import SimpleNamespace
import models
from helpers import plugins
from usr.plugins.requesty.helpers import runtime_guard as guard
from usr.plugins.requesty.helpers.policy import Policy, PolicyError, ENDPOINTS

MODEL = {"id": "bedrock/test@eu-central-1", "api": "chat", "geolocation": "eu-central-1",
         "data_retention": False, "data_retention_days": 0, "data_used_for_training": False,
         "context_window": 10000, "supports_vision": False}


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.wrapper = models.get_chat_model("openai", MODEL["id"],
            model_config=models.ModelConfig(type=models.ModelType.CHAT, provider="requesty_guarded", name=MODEL["id"]),
            api_base=ENDPOINTS["eu"], api_key="synthetic-key")
        for target, name, value in ((guard, "settings", Policy()), (plugins, "get_toggle_state", "enabled"),
                                    (models, "get_api_key_raw", "synthetic-key"),
                                    (guard.catalog, "fetch", {MODEL["id"]: MODEL})):
            mock = patch.object(target, name, return_value=value)
            mock.start(); self.addCleanup(mock.stop)

    def test_region_owned_and_model_unchanged(self):
        original = dict(self.wrapper.kwargs)
        result = guard.guarded_kwargs(self.wrapper, {"api_base": ENDPOINTS["us"]})
        self.assertEqual(result["api_base"], ENDPOINTS["eu"])
        self.assertEqual(self.wrapper.kwargs, original)

    def test_transport_bypasses_blocked(self):
        for name in ("base_url", "model", "custom_llm_provider", "extra_body", "extra_headers", "http_client", "fallbacks"):
            with self.subTest(name=name), self.assertRaises(PolicyError):
                guard.guarded_kwargs(self.wrapper, {name: "bad"})
        for overrides in ({"api_key": "foreign-key"}, {"api_base": "https://other.test"}, {"a0_api_mode": "responses"}):
            with self.assertRaises(PolicyError):
                guard.guarded_kwargs(self.wrapper, overrides)

    def test_missing_model_and_disabled(self):
        with patch.object(guard.catalog, "fetch", return_value={}):
            with self.assertRaises(PolicyError):
                guard.guarded_kwargs(self.wrapper, {})
        with patch.object(plugins, "get_toggle_state", return_value="disabled"):
            with self.assertRaises(PolicyError):
                guard.guarded_kwargs(self.wrapper, {})

    def test_other_provider_unaffected(self):
        other = SimpleNamespace(a0_model_conf=SimpleNamespace(provider="anthropic"), kwargs={})
        data = {"args": (other,), "kwargs": {"hello": "world"}}
        guard.guard_function(data)
        self.assertEqual(data["kwargs"], {"hello": "world"})

    def test_wrapper_and_langchain_paths(self):
        from usr.plugins.requesty.helpers.wrapper import GuardedRequestyWrapper
        data = {"result": self.wrapper}
        guard.wrap_agent_result(data)
        wrapped = data["result"]
        self.assertIsInstance(wrapped, GuardedRequestyWrapper)
        self.assertEqual(wrapped.model_name, self.wrapper.model_name)
        with patch.object(guard.catalog, "fetch", return_value={}):
            with self.assertRaises(PolicyError): wrapped.invoke("synthetic")
            with self.assertRaises(PolicyError): list(wrapped.stream("synthetic"))

    def test_candidate_preserves_embeddings(self):
        from usr.plugins.requesty.helpers.configuration import build_candidate
        original = {"chat_model": {"provider": "openai", "name": "old", "kwargs": {"extra_body": {"old": True}}},
                    "utility_model": {"provider": "openai", "name": "old"},
                    "embedding_model": {"provider": "huggingface", "name": "local", "kwargs": {"dimension": 384}},
                    "vision_model": {"provider": "other", "name": "old-vision"}}
        candidate = build_candidate("Private", original, MODEL["id"], MODEL["id"], Policy(), {MODEL["id"]: MODEL})
        self.assertEqual(candidate["embedding"], original["embedding_model"])
        self.assertEqual(candidate["vision"], {})
        self.assertEqual(candidate["chat"]["kwargs"], {})
        self.assertEqual(original["chat_model"]["name"], "old")
