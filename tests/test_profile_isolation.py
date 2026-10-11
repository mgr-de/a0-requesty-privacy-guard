"""Real framework dispatch for two profiles, with temporary storage and synthetic calls."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from dataclasses import asdict
from copy import deepcopy
import models
from agent import Agent, AgentConfig
from helpers import plugins, cache
from plugins._model_config.helpers import model_config as mc
from plugins._memory.helpers import memory
from usr.plugins.requesty.helpers import scope, configuration, runtime_guard as guard, validation
from usr.plugins.requesty.helpers.policy import Policy, PolicyError
from test_integration import IDENTIFIER, METADATA

class ProfileIsolationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="privacy-profiles-");self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.real_path=scope.path
        def profile_path(owner,name):
            scope.scope(*owner)
            return self.root/owner[0]/owner[1]/"requesty"/name
        mocked=patch.object(scope,"path",side_effect=profile_path);mocked.start();self.addCleanup(mocked.stop)
        self.a=("","agent0");self.b=("","developer")
        for owner,region,key in ((self.a,"eu","synthetic-alpha"),(self.b,"us","synthetic-beta")):
            for name,value in (("config.json",asdict(Policy(region=region))), ("credentials.json",{"key":key})):
                path=scope.path(owner,name);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
        self.alpha=Agent(0,AgentConfig(profile="agent0",mcp_servers=""))
        self.beta=Agent(0,AgentConfig(profile="developer",mcp_servers=""))
        self.native_beta=deepcopy(mc.get_effective_config(self.beta))
        self.shared_path=Path(mc._get_presets_path())
        self.shared=self.shared_path.read_bytes() if self.shared_path.exists() else None

    def write_setup(self,owner):
        scope.path(owner,"setup.json").write_text(json.dumps({"active":True,"models":{"name":"Synthetic",
            "chat":{"provider":"requesty_guarded","name":IDENTIFIER,"api_base":Policy().endpoint},
            "utility":{"provider":"requesty_guarded","name":IDENTIFIER,"api_base":Policy().endpoint}}}))

    async def test_two_profiles_policy_key_and_models_are_independent(self):
        self.write_setup(self.a)
        before=scope.path(self.b,"config.json").read_bytes()
        alpha=self.alpha.get_chat_model();beta=self.beta.get_chat_model()
        self.assertEqual(alpha._requesty_scope,self.a)
        self.assertIsNone(getattr(beta,"_requesty_scope",None))
        self.assertEqual(mc.get_effective_config(self.beta),self.native_beta)
        with patch.object(guard.catalog,"fetch",return_value={IDENTIFIER:METADATA}) as fetch:
            checked=guard.guarded_kwargs(alpha,{})
            self.assertEqual(checked["api_key"],"synthetic-alpha")
            self.assertEqual(checked["api_base"],Policy().endpoint)
            fetch.assert_called_with(Policy().endpoint,"synthetic-alpha")
        scope.path(self.b,"config.json").write_text(json.dumps(asdict(Policy(region="ap"))))
        self.assertEqual(guard.settings(self.a),Policy())
        with patch.object(configuration,"fetch",return_value={IDENTIFIER:METADATA}):
            configuration.recover(self.a)
        with patch.object(models.LiteLLMTransport,"acomplete",new_callable=AsyncMock) as send:
            with self.assertRaises(PolicyError):await alpha.unified_call(user_message="synthetic")
            send.assert_not_called()
        self.assertEqual(self.shared_path.read_bytes() if self.shared_path.exists() else None,self.shared)
        self.assertEqual(scope.key(self.b),"synthetic-beta")

    async def test_memory_override_changes_only_active_profile(self):
        self.write_setup(self.a)
        original=deepcopy(plugins.get_plugin_config("_memory",self.beta))
        protected=plugins.get_plugin_config("_memory",self.alpha)
        self.assertFalse(protected["memory_memorize_consolidation"])
        self.assertEqual(protected["agent_memory_subdir"],scope.memory_subdir(self.a))
        self.assertEqual(plugins.get_plugin_config("_memory",self.beta),original)
        self.assertNotEqual(memory.get_agent_memory_subdir(self.alpha),memory.get_agent_memory_subdir(self.beta))

    async def test_ticket_cannot_cross_profile_even_with_same_models_and_state(self):
        validation._tickets.clear()
        import time
        validation._tickets["synthetic-ticket"]=(time.monotonic(),"same",self.a)
        with patch.object(validation,"state",return_value="same"):
            with self.assertRaises(PolicyError):validation.consume("synthetic-ticket",IDENTIFIER,IDENTIFIER,self.b)

    async def test_no_global_or_project_only_scope_and_no_global_key_fallback(self):
        for project,profile in (("",""),("project",""),("","../agent0")):
            with self.assertRaises(PolicyError):scope.scope(project,profile)
        with self.assertRaises(PolicyError):scope.key(("","researcher"))
        with self.assertRaises(PolicyError):guard.settings(("","researcher"))

    async def test_project_scope_does_not_reuse_profile_key_from_another_project(self):
        with self.assertRaises(PolicyError):scope.key(("another-project","agent0"))

    async def test_chat_gate_uses_profile_key_without_returning_it_and_other_profile_is_native(self):
        from usr.plugins.requesty.api.model_status import ModelStatus
        from plugins._model_config.api.model_config_get import ModelConfigGet
        import threading
        self.write_setup(self.a)
        lock=threading.RLock()
        protected=await ModelStatus(None,lock).process({"context_id":self.alpha.context.id},None)
        self.assertTrue(protected["model_configured"])
        self.assertEqual(protected["config"]["chat_model"]["provider"],"requesty_guarded")
        self.assertNotIn("synthetic-alpha",json.dumps(protected))
        other=await ModelStatus(None,lock).process({"context_id":self.beta.context.id},None)
        native=await ModelConfigGet(None,lock).process({"context_id":self.beta.context.id},None)
        self.assertEqual(other,native)

    async def test_setup_changed_during_catalog_fetch_blocks_old_wrapper(self):
        self.write_setup(self.a);wrapper=self.alpha.get_chat_model()
        def changed(*args,**kwargs):
            scope.path(self.a,"setup.json").write_text(json.dumps({"active":False,"models":{}}))
            return {IDENTIFIER:METADATA}
        with patch.object(guard.catalog,"fetch",side_effect=changed):
            with self.assertRaisesRegex(PolicyError,"changed during validation"):
                guard.guarded_kwargs(wrapper,{})

    async def test_existing_wrapper_blocks_when_plugin_extension_dispatch_is_removed(self):
        self.write_setup(self.a);wrapper=self.alpha.get_chat_model()
        from helpers import extension
        with patch.object(extension,"_get_extension_classes",return_value=[]), patch.object(scope,"enabled",return_value=False), patch.object(models.LiteLLMTransport,"acomplete",new_callable=AsyncMock) as send:
            for name in ("unified_call","unified_turn"):
                with self.assertRaises(PolicyError):await getattr(wrapper,name)(user_message="synthetic")
            send.assert_not_called()

    async def test_profile_storage_path_cannot_escape_user_tree(self):
        from helpers import plugins
        with patch.object(plugins,"determine_plugin_asset_path",return_value="/tmp/outside-profile/credentials.json"):
            with self.assertRaises(PolicyError):self.real_path(self.a,"setup.json")
        self.assertIn("secrets/requesty/",str(self.real_path(self.a,"credentials.json")))
        self.assertNotEqual(self.real_path(self.a,"credentials.json"),self.real_path(self.b,"credentials.json"))

    async def test_native_settings_api_does_not_display_inherited_global_policy(self):
        from helpers.modules import import_module
        Plugins = import_module("api/plugins.py").Plugins
        import threading
        api=Plugins(None,threading.RLock())
        scoped=api._get_config({"plugin_name":"requesty","agent_profile":"developer"})
        self.assertEqual(scoped["data"]["region"],"us")
        unconfigured=api._get_config({"plugin_name":"requesty","agent_profile":"researcher"})
        self.assertEqual(unconfigured["data"],asdict(Policy()))
        self.assertEqual(unconfigured["loaded_path"],"")
        global_defaults=api._get_config({"plugin_name":"requesty"})
        self.assertEqual(global_defaults["data"],asdict(Policy()))

    async def test_key_status_and_save_are_profile_owned_and_never_reveal_keys(self):
        from usr.plugins.requesty.api.key import Key
        import threading
        api=Key(None,threading.RLock())
        status=await api.process({"agent_profile":"agent0"},None)
        self.assertTrue(status["has_key"]);self.assertTrue(status["requirements_saved"])
        self.assertNotIn("synthetic-alpha",json.dumps(status))
        other_before=scope.path(self.b,"credentials.json").read_bytes()
        result=await api.process({"action":"set","agent_profile":"agent0","key":"synthetic-new"},None)
        self.assertTrue(result["ok"]);self.assertEqual(scope.key(self.a),"synthetic-new")
        self.assertEqual(scope.path(self.b,"credentials.json").read_bytes(),other_before)
        rejected=await api.process({"action":"set","key":"synthetic-global"},None)
        self.assertFalse(rejected["ok"])
