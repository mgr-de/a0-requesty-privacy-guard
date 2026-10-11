"""Real Agent methods and Memory extensions, with synthetic transport/data only."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from copy import deepcopy
import models
from agent import Agent, AgentConfig, LoopData, UserMessage
from helpers import plugins
from plugins._model_config.helpers import model_config as mc
from plugins._memory.helpers import memory
from usr.plugins.requesty.helpers import runtime_guard as guard
from usr.plugins.requesty.helpers.policy import Policy, PolicyError
from test_integration import SyntheticEmbeddings, IDENTIFIER, METADATA


class AgentMemoryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        original = mc.get_effective_config()
        configuration = deepcopy(original)
        for slot in ("chat_model", "utility_model"):
            configuration[slot] = {"provider":"requesty_guarded", "name":IDENTIFIER,
                "api_base":Policy().endpoint, "ctx_length":10000, "kwargs":{"max_tokens":256, "a0_retry_attempts":0}}
        setup = {"active":True,"models":{"name":"Synthetic",
            "chat":{"provider":"requesty_guarded","name":IDENTIFIER,"api_base":Policy().endpoint},
            "utility":{"provider":"requesty_guarded","name":IDENTIFIER,"api_base":Policy().endpoint}}}
        for target, name, value in ((mc, "get_effective_config", configuration), (guard,"settings",Policy()),
                (guard.scope,"key","synthetic-key"), (guard.scope,"enabled",True),
                (guard.scope,"read",setup), (guard.catalog,"fetch",{IDENTIFIER:METADATA})):
            mocked = patch.object(target,name,return_value=value); mocked.start(); self.addCleanup(mocked.stop)
        self.agent = Agent(0, AgentConfig(mcp_servers="", profile="agent0"))
        self.agent.loop_data = LoopData()
        temporary = tempfile.TemporaryDirectory(prefix="requesty-agent-memory-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        embedding = models.ModelConfig(type=models.ModelType.EMBEDDING, provider="synthetic_local", name="fixed")
        with patch.object(memory,"abs_db_dir",lambda scope:str(self.directory / scope)), patch.object(models,"get_embedding_model",return_value=SyntheticEmbeddings()):
            db, _ = memory.Memory.initialize(None,embedding,"test",in_memory=True)
        self.store = memory.Memory(db,"test")
        # Keep this isolated destination while extension save operations execute.
        mocked = patch.object(memory,"abs_db_dir",lambda scope:str(self.directory / scope)); mocked.start(); self.addCleanup(mocked.stop)
        mocked = patch.object(memory.Memory,"get",new=AsyncMock(return_value=self.store)); mocked.start(); self.addCleanup(mocked.stop)
        original_config = plugins.get_plugin_config
        self.original_plugin_config = original_config
        settings = deepcopy(original_config("_memory",self.agent))
        settings.update(memory_memorize_consolidation=False, memory_memorize_replace_threshold=0,
                        memory_recall_query_prep=True, memory_recall_post_filter=True)
        def plugin_config(name,*args,**kwargs):
            return settings if name == "_memory" else original_config(name,*args,**kwargs)
        mocked = patch.object(plugins,"get_plugin_config",side_effect=plugin_config); mocked.start(); self.addCleanup(mocked.stop)

    async def test_real_agent_model_hooks_and_utility_block(self):
        from usr.plugins.requesty.helpers.wrapper import GuardedRequestyWrapper
        self.assertIsInstance(self.agent.get_chat_model(),GuardedRequestyWrapper)
        self.assertIsInstance(self.agent.get_utility_model(),GuardedRequestyWrapper)
        with patch.object(guard.catalog,"fetch",return_value={}), patch.object(models.LiteLLMTransport,"acomplete",new_callable=AsyncMock) as send:
            with self.assertRaises(PolicyError):
                await self.agent.call_utility_model("synthetic", "synthetic",background=True)
            send.assert_not_called()

    async def test_auto_recall_and_fragments_and_solutions(self):
        from plugins._memory.extensions.python.message_loop_prompts_after._50_recall_memories import RecallMemories
        from plugins._memory.extensions.python.monologue_end._50_memorize_fragments import MemorizeMemories
        from plugins._memory.extensions.python.monologue_end._51_memorize_solutions import MemorizeSolutions
        identity = await self.store.insert_text("Synthetic blue preference",{"area":"main"})
        log_item = self.agent.context.log.log(type="util",heading="Synthetic test")
        async def complete(transport):
            return {"response_delta":"blue preference", "reasoning_delta":""}
        recall = RecallMemories(agent=self.agent)
        # Query prep is a real guarded utility call. Filter returns index 0.
        with patch.object(models.LiteLLMTransport,"acomplete",new=AsyncMock(side_effect=[
                {"response_delta":"blue preference","reasoning_delta":""},
                {"response_delta":"[0]","reasoning_delta":""}])):
            result = await recall.search_memories(log_item,LoopData())
        self.assertIn("Synthetic blue preference",result["memories"])
        self.agent.hist_add_user_message(UserMessage("For all future projects, use Python 3.12 and pytest."))
        output = '["For all future projects, the user requires Python 3.12 and pytest for automated tests."]'
        with patch.object(models.LiteLLMTransport,"acomplete",new=AsyncMock(return_value={"response_delta":output,"reasoning_delta":""})):
            await MemorizeMemories(agent=self.agent).memorize(LoopData(),log_item)
            await MemorizeSolutions(agent=self.agent).memorize(LoopData(),log_item)
        areas = {doc.metadata.get("area") for doc in self.store.db.get_all_docs().values()}
        self.assertIn("fragments",areas)
        self.assertIn("solutions",areas)
        self.assertEqual(self.store.get_document_by_id(identity).page_content,"Synthetic blue preference")

    async def test_policy_failure_in_auto_memory_preserves_existing_documents(self):
        from plugins._memory.extensions.python.message_loop_prompts_after._50_recall_memories import RecallMemories
        from plugins._memory.extensions.python.monologue_end._50_memorize_fragments import MemorizeMemories
        from plugins._memory.extensions.python.monologue_end._51_memorize_solutions import MemorizeSolutions
        await self.store.insert_text("Synthetic blue preference",{"area":"main"})
        before = {key: doc.page_content for key,doc in self.store.db.get_all_docs().items()}
        item = self.agent.context.log.log(type="util",heading="Synthetic test")
        with patch.object(guard.catalog,"fetch",return_value={}), patch.object(models.LiteLLMTransport,"acomplete",new_callable=AsyncMock) as send:
            result = await RecallMemories(agent=self.agent).search_memories(item,LoopData())
            await MemorizeMemories(agent=self.agent).memorize(LoopData(),item)
            await MemorizeSolutions(agent=self.agent).memorize(LoopData(),item)
            send.assert_not_called()
        self.assertEqual(result,{})
        self.assertEqual(before,{key: doc.page_content for key,doc in self.store.db.get_all_docs().items()})

    async def test_native_memory_safety_override_does_not_mutate_saved_settings(self):
        # The shared loader is decorated and actually discovers the installed hook.
        before = deepcopy(self.original_plugin_config("_memory", agent=None))
        actual = self.original_plugin_config("_memory",self.agent)
        self.assertFalse(actual["memory_memorize_consolidation"])
        self.assertEqual(actual["memory_memorize_replace_threshold"],0)
        self.assertEqual(self.original_plugin_config("_memory",agent=None),before)
        with patch.object(guard.scope,"read",return_value=None):
            self.assertEqual(self.original_plugin_config("_memory",self.agent),before)

    async def test_direct_consolidator_failure_keeps_old_memory_and_documents_upstream_behavior(self):
        from plugins._memory.helpers.memory_consolidation import MemoryConsolidator
        identity = await self.store.insert_text("Synthetic blue preference",{"area":"main"})
        consolidator = MemoryConsolidator(self.agent)
        old = self.store.get_document_by_id(identity)
        with patch.object(consolidator,"_find_similar_memories",new=AsyncMock(return_value=[old])), patch.object(guard.catalog,"fetch",return_value={}), patch.object(models.LiteLLMTransport,"acomplete",new_callable=AsyncMock) as send:
            result = await consolidator.process_new_memory("Synthetic blue preference addition","main",{"area":"main"})
            send.assert_not_called()
        # Agent Zero inserts the original new text when analysis fails (SKIP).
        # It does not replace/delete an old document with an empty failed answer.
        self.assertTrue(result["success"])
        self.assertEqual(self.store.get_document_by_id(identity).page_content,"Synthetic blue preference")
        self.assertEqual(len(self.store.db.get_all_docs()),2)
