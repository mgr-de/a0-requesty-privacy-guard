"""Profile setup writes, deactivation and failure preserve every other profile."""
import json
import tempfile
import unittest
from pathlib import Path
from dataclasses import asdict
from unittest.mock import patch
from plugins._model_config.helpers import model_config as mc
from usr.plugins.requesty.helpers import configuration as config
from usr.plugins.requesty.helpers.policy import Policy, PolicyError

MODEL = {"id":"bedrock/synthetic@eu-central-1","api":"chat","geolocation":"eu-central-1",
         "data_retention":False,"data_retention_days":0,"data_used_for_training":False,"context_window":10000}
OWNER = ("", "agent0")

class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix="requesty-profile-")
        self.addCleanup(temporary.cleanup); self.root=Path(temporary.name)
        def path(owner,name): return self.root / owner[1] / name
        for target,name,kw in ((config.scope,"path",{"side_effect":path}),
            (config,"settings",{"return_value":Policy()}),
            (config.scope,"key",{"return_value":"synthetic-key"}),
            (config,"fetch",{"return_value":{MODEL["id"]:MODEL}})):
            mocked=patch.object(target,name,**kw); mocked.start(); self.addCleanup(mocked.stop)
        self.shared=self.root/"shared-presets.yaml"; self.shared.write_text("shared sentinel")
        self.other=self.root/"other"/"setup.json"; self.other.parent.mkdir();self.other.write_text('{"sentinel":true}')
        self.before=mc.get_effective_config()

    def create(self):
        return config.create("Profile Private",MODEL["id"],MODEL["id"],asdict(Policy()),OWNER)

    def test_create_activate_deactivate_preserves_others_and_native_config(self):
        result=self.create(); self.assertFalse(result["activated"])
        target=config.scope.path(OWNER,"setup.json")
        saved=json.loads(target.read_text()); self.assertFalse(saved["active"])
        self.assertNotIn("embedding",saved["models"]); self.assertNotIn("synthetic-key",target.read_text())
        config.activate(OWNER,True);self.assertTrue(json.loads(target.read_text())["active"])
        config.recover(OWNER);self.assertFalse(json.loads(target.read_text())["active"])
        self.assertEqual(mc.get_effective_config(),self.before)
        self.assertEqual(self.shared.read_text(),"shared sentinel")
        self.assertEqual(self.other.read_text(),'{"sentinel":true}')

    def test_failed_validation_and_activation_never_write(self):
        with self.assertRaises(PolicyError):config.create("New",MODEL["id"],MODEL["id"],{},OWNER)
        self.assertFalse(config.scope.path(OWNER,"setup.json").exists())
        self.create();before=config.scope.path(OWNER,"setup.json").read_bytes()
        with patch.object(config,"fetch",return_value={}):
            with self.assertRaises(PolicyError):config.activate(OWNER,True)
        self.assertEqual(config.scope.path(OWNER,"setup.json").read_bytes(),before)

    def test_profile_recovery_does_not_deactivate_another_profile(self):
        self.create();config.activate(OWNER,True)
        with self.assertRaises(PolicyError):config.recover(("", "other"))
        self.assertTrue(config.scope.read(OWNER,"setup.json")["active"])

    def test_atomic_failure_preserves_previous_file(self):
        target=self.root/"test.txt";target.write_text("before")
        with patch.object(config.os,"replace",side_effect=OSError("simulated failure")):
            with self.assertRaises(OSError):config.atomic_write(target,"after")
        self.assertEqual(target.read_text(),"before");self.assertFalse(list(self.root.glob(".requesty-*")))
