"""Framework integration with synthetic transport responses and isolated FAISS stores."""
import asyncio
import hashlib
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock
import models
from helpers import plugins
from langchain_core.embeddings import Embeddings
from usr.plugins.requesty.helpers import runtime_guard as guard
from usr.plugins.requesty.helpers.policy import Policy, PolicyError, ENDPOINTS

IDENTIFIER = "bedrock/synthetic@eu-central-1"
METADATA = {"id": IDENTIFIER, "api": "chat", "geolocation": "eu-central-1", "data_retention": False,
            "data_retention_days": 0, "data_used_for_training": False, "context_window": 10000}


class SyntheticEmbeddings(Embeddings):
    calls = 0
    def embed_documents(self, texts):
        return [self.embed_query(text) for text in texts]
    def embed_query(self, text):
        self.calls += 1
        return [1.0, 0.0, 0.0, 0.0] if "blue" in text.lower() else [0.0, 1.0, 0.0, 0.0]


class FrameworkIntegration(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for target, name, value in ((guard, "settings", Policy()), (plugins, "get_toggle_state", "enabled"),
                                   (models, "get_api_key_raw", "synthetic-key"),
                                   (guard.catalog, "fetch", {IDENTIFIER: METADATA})):
            mock = patch.object(target, name, return_value=value)
            mock.start(); self.addCleanup(mock.stop)
        self.wrapper = models.get_chat_model("requesty_guarded", IDENTIFIER,
            model_config=models.ModelConfig(type=models.ModelType.CHAT, provider="requesty_guarded", name=IDENTIFIER))

    async def test_real_discovered_hooks_block_before_transport(self):
        # Do not mock extension dispatch. This exercises discovery from installed plugin paths.
        with patch.object(guard.catalog, "fetch", return_value={}), patch.object(models.LiteLLMTransport, "acomplete", new_callable=AsyncMock) as send:
            for method in ("unified_call", "unified_turn"):
                with self.assertRaises(PolicyError):
                    await getattr(self.wrapper, method)(user_message="synthetic")
            send.assert_not_called()

    async def test_real_call_and_turn_preserve_messages(self):
        observed = []
        async def complete(transport):
            observed.append((transport.model, transport.kwargs["api_base"], transport.messages))
            return {"response_delta": "synthetic answer", "reasoning_delta": ""}
        with patch.object(models.LiteLLMTransport, "acomplete", complete):
            response, _ = await self.wrapper.unified_call(system_message="synthetic system", user_message="synthetic user")
            self.assertEqual(response, "synthetic answer")
            from langchain_core.messages import HumanMessage
            result = await self.wrapper.unified_turn(messages=[HumanMessage(content="synthetic turn")],
                a0_responses_function_tools=[], responses_local_input_items=[], responses_prompt_replacements={})
            self.assertEqual(result.response, "synthetic answer")
        self.assertEqual(observed[0][1], ENDPOINTS["eu"])
        self.assertEqual(observed[0][2][0]["content"], "synthetic system")
        self.assertEqual(observed[1][2][0]["content"], "synthetic turn")

    async def test_streaming_and_async_langchain_block(self):
        async def stream(transport):
            yield {"response_delta": "one ", "reasoning_delta": ""}
            yield {"response_delta": "two", "reasoning_delta": ""}
        chunks = []
        async def callback(chunk, full):
            chunks.append(chunk)
        with patch.object(models.LiteLLMTransport, "astream", stream):
            response, _ = await self.wrapper.unified_call(user_message="synthetic", response_callback=callback)
        self.assertEqual(response, "one two")
        self.assertEqual(chunks, ["one ", "two"])
        data = {"result": self.wrapper}
        guard.wrap_agent_result(data)
        with patch.object(guard.catalog, "fetch", return_value={}):
            with self.assertRaises(PolicyError):
                await data["result"].ainvoke("synthetic")
            with self.assertRaises(PolicyError):
                async for _ in data["result"].astream("synthetic"):
                    pass

    async def test_faiss_memory_persistence_and_no_reindex(self):
        from plugins._memory.helpers import memory
        with tempfile.TemporaryDirectory(prefix="requesty-memory-") as directory:
            embeddings = SyntheticEmbeddings()
            def db_path(scope):
                return str(Path(directory) / scope)
            configuration = models.ModelConfig(type=models.ModelType.EMBEDDING, provider="synthetic_local", name="fixed")
            with patch.object(memory, "abs_db_dir", db_path), patch.object(models, "get_embedding_model", return_value=embeddings):
                index, created = memory.Memory.initialize(None, configuration, "project-a", in_memory=True)
                self.assertTrue(created)
                store = memory.Memory(index, "project-a")
                identity = await store.insert_text("Synthetic blue preference", {"area": "main"})
                matches = await store.search_similarity_threshold("blue", 3, 0.5)
                self.assertEqual(matches[0].metadata["id"], identity)
                before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(db_path("project-a")).iterdir()}
                calls = embeddings.calls
                reloaded, created = memory.Memory.initialize(None, configuration, "project-a", in_memory=True)
                self.assertFalse(created)
                self.assertEqual(embeddings.calls, calls)
                self.assertEqual(memory.Memory(reloaded, "project-a").get_document_by_id(identity).page_content, "Synthetic blue preference")
                backup = Path(directory) / "backup"
                shutil.copytree(db_path("project-a"), backup)
                await store.insert_text("Synthetic later change", {"area": "main"})
                shutil.rmtree(db_path("project-a"))
                shutil.copytree(backup, db_path("project-a"))
                restored, created = memory.Memory.initialize(None, configuration, "project-a", in_memory=True)
                self.assertFalse(created)
                store = memory.Memory(restored, "project-a")
                self.assertEqual(len(store.db.get_all_docs()), 1)
                self.assertEqual(store.get_document_by_id(identity).page_content, "Synthetic blue preference")
                # A blocked Requesty call cannot write or replace existing Memory data.
                with patch.object(guard.catalog, "fetch", return_value={}):
                    with self.assertRaises(PolicyError):
                        await self.wrapper.unified_call(user_message="synthetic consolidation")
                after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(db_path("project-a")).iterdir()}
                self.assertEqual(before, after)
                other, _ = memory.Memory.initialize(None, configuration, "project-b", in_memory=True)
                self.assertEqual(other.get_all_docs(), {})
                await store.delete_documents_by_ids([identity])
                self.assertEqual(store.db.get_all_docs(), {})
