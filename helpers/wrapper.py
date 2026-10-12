"""Protect LangChain invoke/stream paths returned by Agent model builders."""
from models import LiteLLMChatWrapper
from pydantic import PrivateAttr
from usr.plugins.requesty.helpers.runtime_guard import guarded_kwargs, guard_function


class GuardedRequestyWrapper(LiteLLMChatWrapper):
    _requesty_scope: tuple | None = PrivateAttr(default=None)
    _requesty_slot: str | None = PrivateAttr(default=None)
    _requesty_test: bool = PrivateAttr(default=False)
    _requesty_policy_bound: bool = PrivateAttr(default=False)

    async def unified_call(self, *args, **kwargs):
        data = {"args": (self,), "kwargs": kwargs}
        guard_function(data)
        return await super().unified_call(*args, **data["kwargs"])

    async def unified_turn(self, *args, **kwargs):
        data = {"args": (self,), "kwargs": kwargs}
        guard_function(data)
        return await super().unified_turn(*args, **data["kwargs"])
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


class GuardedLocalWrapper(LiteLLMChatWrapper):
    _requesty_scope: tuple | None = PrivateAttr(default=None)
    _requesty_policy_bound: bool = PrivateAttr(default=True)

    def checked(self, kwargs):
        data = {"args":(self,),"kwargs":kwargs}
        guard_function(data)
        return data["kwargs"]

    async def unified_call(self, *args, **kwargs):
        return await super().unified_call(*args, **self.checked(kwargs))

    async def unified_turn(self, *args, **kwargs):
        return await super().unified_turn(*args, **self.checked(kwargs))

    def _call(self, messages, stop=None, run_manager=None, **kwargs):
        return super()._call(messages,stop=stop,run_manager=run_manager,**self.checked(kwargs))

    def _stream(self,messages,stop=None,run_manager=None,**kwargs):
        yield from super()._stream(messages,stop=stop,run_manager=run_manager,**self.checked(kwargs))

    async def _astream(self,messages,stop=None,run_manager=None,**kwargs):
        async for chunk in super()._astream(messages,stop=stop,run_manager=run_manager,**self.checked(kwargs)):
            yield chunk
