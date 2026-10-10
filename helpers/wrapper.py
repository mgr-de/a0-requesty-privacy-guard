"""Protect LangChain invoke/stream paths returned by Agent model builders."""
from models import LiteLLMChatWrapper
from usr.plugins.requesty.helpers.runtime_guard import guarded_kwargs


class GuardedRequestyWrapper(LiteLLMChatWrapper):
    def _call(self, messages, stop=None, run_manager=None, **kwargs):
        checked = guarded_kwargs(self, kwargs)
        return super()._call(messages, stop=stop, run_manager=run_manager, **checked)

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        checked = guarded_kwargs(self, kwargs)
        yield from super()._stream(messages, stop=stop, run_manager=run_manager, **checked)

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        checked = guarded_kwargs(self, kwargs)
        async for chunk in super()._astream(messages, stop=stop, run_manager=run_manager, **checked):
            yield chunk
