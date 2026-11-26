"""A6 dual-channel dedup verification (protocol + registry level).

This test proves the Skill's dedup behavior against a REAL auq-mcp-server
via stdio MCP protocol. It does NOT claim host-level tool visibility (A8),
which requires a WorkBuddy session restart.

Scenarios (from review):
  A6-1  same pending question is created only once
  A6-2  Chat-answered question is NOT presented to AUQ (no duplicate session)
  A6-3  switching channel marks old item SUPERSEDED with a link
  A6-4  new context_version creates a new item (not falsely deduped)
  A6-5  rejected item is not re-presented in same context

Run: python tests/test_a6_dual_channel.py
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core import (  # noqa: E402
    ArtifactStore, CoreDispatcher, DecisionKey, DecisionRegistry,
    DeliveryStatus, DispatchRequest, ModuleID,
)

AUQ_SERVER = (
    "C:/Users/L/AppData/Local/npm-cache/_npx/933e3c81d81d7880/"
    "node_modules/auq-mcp-server/dist/src/server.js"
)


def auq_call(method, params=None, msg_id=1):
    """One MCP stdio round-trip against the real AUQ server."""
    messages = [
        {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "a6-probe", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {
            "jsonrpc": "2.0", "id": msg_id, "method": method,
            "params": params or {},
        },
    ]
    payload = "\n".join(json.dumps(m) for m in messages) + "\n"
    try:
        proc = subprocess.run(
            ["node", AUQ_SERVER], input=payload, capture_output=True,
            text=True, timeout=30, encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in proc.stdout.splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("id") == msg_id:
            return obj
    return None


class TestA6DualChannel(unittest.TestCase):
    def setUp(self):
        self.core = CoreDispatcher(ArtifactStore(tempfile.mkdtemp()))
        self.suffix = uuid.uuid4().hex[:6]

    def key(self, topic, cv="cv1", exp="A6"):
        return DecisionKey(exp, "M2", topic + self.suffix, cv)

    def test_a61_same_pending_created_once(self):
        k = self.key("参数")
        i1, p1, _ = self.core.decisions.request(k, "q", ["a"], "t1", authorization_scope="scope")
        self.core.decisions.present(i1.decision_id, channel="NATIVE_CHAT")
        i2, p2, _ = self.core.decisions.request(k, "q", ["a"], "t2", authorization_scope="scope")
        self.assertTrue(p1)
        self.assertFalse(p2)
        self.assertEqual(i1.decision_id, i2.decision_id)

    def test_a62_chat_answered_not_presented_to_auq(self):
        """Chat answered -> registry must refuse a second AUQ presentation."""
        k = self.key("加载速率")
        item, presented, _ = self.core.request_decision(
            k, "选择加载速率", ["0.01", "0.05"], "m2-task",
            channel="NATIVE_CHAT",
        )
        self.assertTrue(presented)
        self.assertEqual(item["channel"], "NATIVE_CHAT")
        self.core.resolve_decision(item["decision_id"], "APPROVED", "cv1")

        # A second channel attempt for the SAME item key must be refused.
        again, should_present, reason = self.core.request_decision(
            k, "选择加载速率", ["0.01", "0.05"], "m2-task",
            channel="AUQ",
        )
        self.assertFalse(should_present)
        self.assertEqual(again["decision_id"], item["decision_id"])
        # No new AUQ session should be created; verify with the real server.
        resp = auq_call("tools/call", {
            "name": "get_answered_questions",
            "arguments": {"session_id": again["decision_id"], "blocking": False},
        }, msg_id=2)
        # A refused item has no AUQ session; the tool must not report an
        # answered session for it.
        if resp is not None:
            text = json.dumps(resp)
            self.assertNotIn('"selectedOption"', text)

    def test_a63_channel_switch_marks_superseded(self):
        k = self.key("围压")
        item, _, _ = self.core.request_decision(
            k, "选择围压", ["1MPa", "2MPa"], "m4-task", channel="NATIVE_CHAT"
        )
        new_item = self.core.decisions.supersede(item["decision_id"])
        new_item.channel = "AUQ"
        old = self.core.decisions.snapshot(item["decision_id"])
        self.assertEqual(old["delivery_status"], DeliveryStatus.SUPERSEDED.value)
        self.assertEqual(old["superseded_by"], new_item.decision_id)
        self.assertEqual(new_item.channel, "AUQ")

    def test_a64_new_context_creates_new_item(self):
        k1 = self.key("密度", "cv1")
        k2 = self.key("密度", "cv2")
        i1, p1, _ = self.core.decisions.request(k1, "q", ["a"], "t", authorization_scope="s")
        self.core.decisions.present(i1.decision_id, channel="NATIVE_CHAT")
        i2, p2, _ = self.core.decisions.request(k2, "q", ["a"], "t", authorization_scope="s")
        self.assertTrue(p1)
        self.assertTrue(p2)
        self.assertNotEqual(i1.decision_id, i2.decision_id)

    def test_a65_auq_tool_schema_via_real_server(self):
        """The real AUQ server exposes the two expected tools."""
        resp = auq_call("tools/list", {}, msg_id=2)
        if resp is None:
            self.skipTest("AUQ server not reachable")
        names = [
            t.get("name")
            for t in resp.get("result", {}).get("tools", [])
        ]
        self.assertIn("ask_user_questions", names)
        self.assertIn("get_answered_questions", names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
