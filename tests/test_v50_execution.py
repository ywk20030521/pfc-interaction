"""5.0 PR-9: module_result conversion, Core-bound gateway and real bridge evidence."""

from __future__ import annotations

import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from adapters.itasca_mcp import BridgeUnavailable, ItascaMcpAdapter  # noqa: E402
from core.contract import Envelope, Evidence, EvidenceSource, ModuleID  # noqa: E402
from core.v50_context import EvidenceKind, ResearchTask  # noqa: E402
from core.v50_decisions import DecisionManager  # noqa: E402
from modules.v50_execution import (  # noqa: E402
    V50ExecutionGateway, module_result_from_envelope, parse_metric,
)


def auth_setup():
    task = ResearchTask("t-exec", "执行载体验收")
    decisions = DecisionManager(task)
    d = decisions.propose("启动仿真", "执行验证脚本", "协议验收", affected_assets=["m1"])
    decisions.confirm(d.decision_id, "用户确认")
    auth = decisions.authorize(d.decision_id, "start_formal_simulation", "m1", "run_model",
                               "m1", "p1", "mx1")
    return task, decisions, auth


def bridge_online() -> bool:
    try:
        ItascaMcpAdapter().health()
        return True
    except BridgeUnavailable:
        return False


class TestV50ModuleResult(unittest.TestCase):
    def test_envelope_converts_to_5_0_module_result(self):
        env = Envelope(
            module_id=ModuleID.M3, module_version="4.0.0",
            research_task_id="t", module_task_id="mt",
            status={"module_state": "COMPLETED"},
            output={"structured": {"next_recommendation": "进入 M4"}},
            evidence=[Evidence(EvidenceSource.PFC_EXECUTED, "r1", tool_task_id="pfc-1")],
            limitations=["历史限制"],
        )
        result = module_result_from_envelope(env, "S3", ["model_design"])
        self.assertEqual(result.validate(), [])
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.evidence[0]["kind"], EvidenceKind.TOOL_EVIDENCE.value)
        self.assertEqual(result.next_recommendation, "进入 M4")
        self.assertEqual(result.affected_assets, ["model_design"])
        self.assertIn("历史限制", result.limitations)


class TestV50GatewayOffline(unittest.TestCase):
    def test_authorization_mismatch_blocks_before_tool_call(self):
        task, decisions, auth = auth_setup()
        gateway = V50ExecutionGateway(task, decisions, ItascaMcpAdapter("http://localhost:9999", 2))
        out = gateway.execute_code("print(1)", auth.authorization_id,
                                   "run_batch", "m1", "m1", "p1", "mx1")
        self.assertEqual(out["status"], "BLOCKED")
        self.assertIsNone(out["tool_task_id"])
        self.assertFalse(out["execution_verified"])

    def test_bridge_unavailable_returns_blocked_without_fabricating_id(self):
        task, decisions, auth = auth_setup()
        gateway = V50ExecutionGateway(task, decisions, ItascaMcpAdapter("http://localhost:9999", 2))
        out = gateway.execute_code("print(1)", auth.authorization_id,
                                   "start_formal_simulation", "m1", "m1", "p1", "mx1")
        self.assertEqual(out["status"], "BLOCKED")
        self.assertIn("bridge", out["reason"])
        self.assertIsNone(out["tool_task_id"])
        self.assertEqual(task.evidence, [])

    def test_parse_metric(self):
        self.assertEqual(parse_metric("log\nBALL_COUNT=10\n", "BALL_COUNT"), 10.0)
        self.assertIsNone(parse_metric("no metric", "BALL_COUNT"))


@unittest.skipUnless(bridge_online(), "bridge offline: real execution skipped")
class TestV50GatewayRealBridge(unittest.TestCase):
    def test_real_execution_records_tool_evidence(self):
        task, decisions, auth = auth_setup()
        gateway = V50ExecutionGateway(task, decisions)
        probe = ItascaMcpAdapter().execute_code(
            "import itasca\nitasca.command('model new')\n"
            "itasca.command('model domain extent -2 2 -2 2 -2 2')\n"
            "print('DIM3D_OK')\n")
        probe_out = (probe.output_artifacts[0].get("output", "")
                     if probe.output_artifacts else "")
        is_3d = "DIM3D_OK" in probe_out
        extent = "-2 2 -2 2 -2 2" if is_3d else "-2 2 -2 2"
        position = "(%f,0,0)" if is_3d else "(%f,0)"
        code = (
            "import itasca\n"
            "itasca.command('model new')\n"
            "itasca.command('model domain extent %s')\n" % extent +
            "for i in range(1,11):\n"
            "    itasca.command('ball create id=%%d position=%s radius=0.05' %% (i, i*0.1))\n" % position +
            "print('BALL_COUNT=%d' % itasca.ball.count())\n"
        )
        out = gateway.execute_code(
            code, auth.authorization_id, "start_formal_simulation", "m1",
            "m1", "p1", "mx1", description="V50 真实桥接验收")
        self.assertEqual(out["status"], "EXECUTED", out)
        self.assertTrue(out["tool_task_id"].startswith("pfc-"))
        self.assertTrue(out["execution_verified"])
        self.assertEqual(parse_metric(out["output"], "BALL_COUNT"), 10.0)
        self.assertEqual(len(task.evidence), 1)
        self.assertEqual(task.evidence[0].kind, EvidenceKind.TOOL_EVIDENCE)
        self.assertEqual(task.evidence[0].tool_task_id, out["tool_task_id"])
        print("\n[V50-BRIDGE] tool_task_id=%s metric=BALL_COUNT=10" % out["tool_task_id"])

    def test_stale_authorization_is_rejected_after_context_change(self):
        task, decisions, auth = auth_setup()
        gateway = V50ExecutionGateway(task, decisions)
        task.bump_version("研究边界变化")
        out = gateway.execute_code("print(1)", auth.authorization_id,
                                   "start_formal_simulation", "m1", "m1", "p1", "mx1")
        self.assertEqual(out["status"], "BLOCKED")
        self.assertIsNone(out["tool_task_id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
