import unittest
from unittest.mock import patch, AsyncMock
from dataclasses import asdict
from usr.plugins.requesty.helpers import validation as v
from usr.plugins.requesty.helpers.policy import Policy, PolicyError
import models

ID = "synthetic/test"
META = {"id": ID, "api": "chat", "geolocation": "eu", "data_retention": False,
        "data_used_for_training": False}


class ValidationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from usr.plugins.requesty.helpers import catalog
        self.wrapper = AsyncMock()
        self.wrapper.unified_call.return_value = ('{"tool_name":"response","tool_args":{"text":"requesty_test_ok"}}', "")
        for target, name, value in ((v, "settings", Policy()), (v, "state", "unchanged"),
                (v.scope, "key", "synthetic-key"),
                (catalog, "fetch", {ID: META})):
            mocked = patch.object(target, name, return_value=value)
            mocked.start(); self.addCleanup(mocked.stop)
        from usr.plugins.requesty.helpers import wrapper
        mocked = patch.object(wrapper, "GuardedRequestyWrapper", return_value=self.wrapper)
        mocked.start(); self.addCleanup(mocked.stop)
        v._tickets.clear()

    async def test_ticket_consumed_once_and_same_model_called_once(self):
        ticket = await v.validate(ID, ID, asdict(Policy()), ("", "agent0"))
        self.assertEqual(self.wrapper.unified_call.await_count, 1)
        v.consume(ticket, ID, ID, ("", "agent0"))
        with self.assertRaises(PolicyError): v.consume(ticket, ID, ID, ("", "agent0"))

    async def test_expired_ticket_and_changed_state_rejected(self):
        ticket = await v.validate(ID, ID, asdict(Policy()), ("", "agent0"))
        with patch.object(v.time, "monotonic", return_value=v._tickets[ticket][0] + 601):
            with self.assertRaises(PolicyError): v.consume(ticket, ID, ID, ("", "agent0"))
        ticket = await v.validate(ID, ID, asdict(Policy()), ("", "agent0"))
        with patch.object(v, "state", return_value="changed"):
            with self.assertRaises(PolicyError): v.consume(ticket, ID, ID, ("", "agent0"))

    async def test_failed_output_never_issues_ticket(self):
        for response in ("invalid", "{}", "[]", '{"tool_name":"response","tool_args":{"text":"wrong"}}'):
            self.wrapper.unified_call.return_value = (response, "")
            with self.assertRaises(PolicyError): await v.validate(ID, ID, asdict(Policy()), ("", "agent0"))
        self.assertFalse(v._tickets)

    async def test_transport_errors_are_sanitized(self):
        self.wrapper.unified_call.side_effect = RuntimeError("synthetic-secret")
        with self.assertRaises(PolicyError) as error: await v.validate(ID, ID, asdict(Policy()), ("", "agent0"))
        self.assertNotIn("synthetic-secret", str(error.exception))

    async def test_changed_settings_and_unapproved_models_never_dispatch(self):
        with self.assertRaises(PolicyError): await v.validate(ID, ID, {}, ("", "agent0"))
        with self.assertRaises(PolicyError): await v.validate("missing", ID, asdict(Policy()), ("", "agent0"))
        self.wrapper.unified_call.assert_not_called()
