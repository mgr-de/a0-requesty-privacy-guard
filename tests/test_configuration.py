import tempfile
import unittest
from pathlib import Path
from dataclasses import asdict
from unittest.mock import patch
import models
from helpers import files, cache
from plugins._model_config.helpers import model_config as mc
from usr.plugins.requesty.helpers import configuration as config
from usr.plugins.requesty.helpers.policy import Policy, PolicyError

MODEL = {"id": "bedrock/synthetic@eu-central-1", "api": "chat", "geolocation": "eu-central-1",
         "data_retention": False, "data_retention_days": 0, "data_used_for_training": False,
         "context_window": 10000}


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="requesty-config-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "presets.yaml"
        self.original_abs = files.get_abs_path
        def abs_path(*parts):
            if parts and parts[0] == "usr/plugins/requesty/recovery.json":
                return str(self.root / "recovery.json")
            return self.original_abs(*parts)
        for target, name, kw in ((mc, "_get_presets_path", {"return_value": str(self.path)}),
                                 (files, "get_abs_path", {"side_effect": abs_path}),
                                 (config, "settings", {"return_value": Policy()}),
                                 (config, "fetch", {"return_value": {MODEL["id"]: MODEL}}),
                                 (models, "get_api_key", {"return_value": "synthetic-key"})):
            mock = patch.object(target, name, **kw); mock.start(); self.addCleanup(mock.stop)
        cache.clear(mc.PRESETS_CACHE_AREA)
        self.addCleanup(cache.clear, mc.PRESETS_CACHE_AREA)
        self.before = mc.get_presets()
        self.effective = mc.get_effective_config()

    def create(self):
        return config.create("Requesty Synthetic", MODEL["id"], MODEL["id"], asdict(Policy()))

    def test_create_and_undo_without_activation(self):
        result = self.create()
        self.assertFalse(result["activated"])
        self.assertTrue(result["embedding_preserved"])
        self.assertEqual(mc.get_effective_config(), self.effective)
        after = mc.get_presets()
        self.assertEqual(len(after), len(self.before) + 1)
        self.assertEqual(after[:-1], mc.validate_presets(self.before))
        restored = config.recover()
        self.assertEqual(restored, mc.validate_presets(self.before))
        self.assertNotIn("synthetic-key", self.path.read_text())
        self.assertNotIn("synthetic-key", (self.root / "recovery.json").read_text())

    def test_failed_validation_does_not_write(self):
        for policy, name in (({}, "Fresh"), (asdict(Policy()), "Default")):
            with self.assertRaises(PolicyError):
                config.create(name, MODEL["id"], MODEL["id"], policy)
        self.assertFalse(self.path.exists())
        with patch.object(config, "fetch", return_value={}):
            with self.assertRaises(PolicyError): self.create()
        self.assertFalse(self.path.exists())

    def test_duplicate_and_newer_edits_are_preserved(self):
        self.create()
        with self.assertRaises(PolicyError): self.create()
        after = mc.get_presets()
        after[-1]["chat"]["temperature"] = 0.25
        mc.save_presets(after)
        content = self.path.read_bytes()
        with self.assertRaisesRegex(PolicyError, "changed after creation"):
            config.recover()
        self.assertEqual(self.path.read_bytes(), content)

    def test_interrupted_after_write_is_recoverable(self):
        real_write = config.atomic_write
        count = 0
        def interrupted(path, text):
            nonlocal count
            count += 1
            if count == 3:
                raise OSError("simulated interrupted journal finalization")
            return real_write(path, text)
        with patch.object(config, "atomic_write", side_effect=interrupted):
            with self.assertRaises(OSError): self.create()
        self.assertEqual(config.recover(), mc.validate_presets(self.before))

    def test_atomic_failure_preserves_previous_file(self):
        target = self.root / "test.txt"
        target.write_text("before")
        with patch.object(config.os, "replace", side_effect=OSError("simulated failure")):
            with self.assertRaises(OSError): config.atomic_write(target, "after")
        self.assertEqual(target.read_text(), "before")
        self.assertFalse(list(self.root.glob(".requesty-*")))

    def test_corrupted_presets_are_not_overwritten(self):
        self.path.write_text("[malformed: YAML")
        content = self.path.read_bytes()
        with self.assertRaises(PolicyError):
            self.create()
        self.assertEqual(self.path.read_bytes(), content)
