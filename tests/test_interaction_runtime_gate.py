"""End-to-end interaction gate acceptance (diagnosis report section 7 P1).

These tests exercise the runtime boundary, not just protocol data: insufficient
parameters must stop with an unanswered interaction; an answer must not grant
confirmation or authority; only an explicit execution card may authorize;
version changes invalidate an authorization; channel delivery is de-duplicated.
"""

from __future__ import annotations

import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.host_interaction import (  # noqa: E402
    L0, L1, AskOutcome, HostInteractionAdapter, attach_host_ask,
    probe_host_capability,
)
from core.question import CardType  # noqa: E402
from core.stop_protocol import (  # noqa: E402
    BLOCKED, READY, WAITING_FOR_USER, FormalRunAuthorization,
    gate_formal_execution, minimum_native_chat_requirements,
    require_user_decision,
)
from core.v50_context import InteractionStatus, ResearchTask  # noqa: E402
from core.v50_decisions import DecisionManager, InteractionRouter  # noqa: E402
from modules.question_cards import execution_card  # noqa: E402
from modules.v50_interaction import InteractionCoordinator  # noqa: E402

CONTEXT = {
    "experiment_purpose": "真实岩样标定",
    "boundary_type": "圆柱柔性膜",
    "specimen_size": "直径 50 mm / 高 100 mm",
    "confining_pressure": "10 MPa",
    "loading_endpoint": "峰值后 1% 应变",
    "parameter_source": "室内试验反演",
}


def setup():
    task = ResearchTask("task-gate", "交互闸门验收")
    decisions = DecisionManager(task)
    router = InteractionRouter(task, decisions)
    return task, decisions, router, InteractionCoordinator(task, decisions, router)


def exec_card(qid="exec"):
    return execution_card(
        qid, "是否确认执行正式三轴 Run?",
        "操作：启动正式三轴压缩仿真。",
        "start_formal_simulation", "pfc3d_console", "生成正式科研数据",
    )


class RuntimeGateTests(unittest.TestCase):
    def test_1_missing_parameters_stop_without_execution(self):
        task, decisions, router, _ = setup()
        result = require_user_decision(task, decisions, {"experiment_purpose": "教学演示"})
        self.assertEqual(result.status, WAITING_FOR_USER)
        self.assertEqual(result.allowed_next_action, "none")
        self.assertTrue(result.pending_decision_id)
        self.assertEqual(task.decisions[result.pending_decision_id].status.value, "PROPOSED")
        self.assertFalse(task.decisions[result.pending_decision_id].user_response["confirmed"])

    def test_2_pending_interaction_is_recorded_not_delivered(self):
        task, decisions, router, _ = setup()
        capability = probe_host_capability()
        self.assertEqual(capability.level, L0)
        adapter = HostInteractionAdapter(task, decisions, router, capability)
        outcome = adapter.ask(
            {"question": "使用哪种边界?", "understanding": "三轴压缩建模"},
            topic="边界选择", context_version="v1")
        self.assertIsInstance(outcome, AskOutcome)
        self.assertEqual(outcome.status, "PENDING_NATIVE_CHAT")
        self.assertFalse(outcome.delivered)
        self.assertIn("当前理解", outcome.native_chat_request)
        pending = [e for e in task.interactions.values()
                   if e.status == InteractionStatus.PENDING]
        self.assertEqual(len(pending), 1)

    def test_3_answer_does_not_confirm_or_authorize(self):
        task, decisions, router, coordinator = setup()
        card = exec_card()
        prepared = coordinator.prepare(card)
        submitted = coordinator.submit(prepared.interaction_id, "确认执行")
        self.assertFalse(submitted["decision_confirmed"])
        self.assertFalse(submitted["execution_authorized"])
        self.assertFalse(submitted["execution_performed"])
        self.assertEqual(task.decisions[prepared.decision_id].status.value, "PROPOSED")

    def test_4_explicit_execution_card_grants_authorization(self):
        task, decisions, router, coordinator = setup()
        prepared = coordinator.prepare(exec_card())
        self.assertEqual(prepared.card_type, CardType.EXECUTION.value)
        coordinator.submit(prepared.interaction_id, "确认执行")
        auth = coordinator.authorize_execution(
            prepared.interaction_id, operation="start_formal_simulation",
            target="pfc3d_console", model_version="model-v1",
            parameter_version="param-v1", matrix_version="matrix-v1")
        gate = gate_formal_execution(decisions, FormalRunAuthorization(
            authorization_id=auth.authorization_id,
            research_task_id=task.research_task_id,
            decision_id=prepared.decision_id,
            model_version="model-v1", parameter_version="param-v1",
            matrix_version="matrix-v1", scope="execute:exec"))
        self.assertEqual(gate.status, READY)
        self.assertEqual(gate.authorization_metadata["--authorization-id"],
                         auth.authorization_id)

    def test_5_no_authorization_cannot_pass_execution_gate(self):
        task, decisions, router, _ = setup()
        gate = gate_formal_execution(decisions, FormalRunAuthorization(
            authorization_id="auth-missing", research_task_id=task.research_task_id,
            decision_id="dec-none", model_version="v1",
            parameter_version="v1", matrix_version="v1"))
        self.assertEqual(gate.status, BLOCKED)
        self.assertIn("授权记录不存在", gate.issues)

    def test_6_version_change_invalidates_authorization(self):
        task, decisions, router, coordinator = setup()
        prepared = coordinator.prepare(exec_card())
        coordinator.submit(prepared.interaction_id, "确认执行")
        auth = coordinator.authorize_execution(
            prepared.interaction_id, operation="start_formal_simulation",
            target="pfc3d_console", model_version="model-v1",
            parameter_version="param-v1", matrix_version="matrix-v1")
        task.bump_version("model:edited")
        gate = gate_formal_execution(decisions, FormalRunAuthorization(
            authorization_id=auth.authorization_id,
            research_task_id=task.research_task_id,
            decision_id=prepared.decision_id,
            model_version="model-v1", parameter_version="param-v1",
            matrix_version="matrix-v1", scope="execute:exec"))
        self.assertEqual(gate.status, BLOCKED)
        self.assertIn("上下文版本变化", " ".join(gate.issues))

    def test_7_same_topic_context_not_delivered_twice(self):
        task, decisions, router, _ = setup()
        capability = probe_host_capability(
            structured_ask=lambda payload: {"answer": "柔性膜"},
            auq_available=True, card_ui_available=True,
        )
        from core.host_interaction import L2
        self.assertEqual(capability.level, L2)
        adapter = HostInteractionAdapter(task, decisions, router, capability)
        attach_host_ask(adapter, lambda payload: {"answer": "柔性膜"})
        first = adapter.ask({"question": "边界?"}, topic="边界", context_version="v1")
        second = adapter.ask({"question": "边界?"}, topic="边界", context_version="v1")
        changed = adapter.ask({"question": "边界?"}, topic="边界", context_version="v2")
        self.assertEqual(first.status, "ANSWERED")
        self.assertEqual(second.status, "BLOCKED_DUPLICATE")
        self.assertEqual(changed.status, "ANSWERED")
        self.assertEqual(len(task.interactions), 2)

    def test_native_chat_minimum_turn_is_required(self):
        good = {
            "understanding": "三轴压缩，参数未定",
            "alternatives": [{"label": "方形刚壁"}, {"label": "圆柱柔性膜"}],
            "unresolved_parameters": ["围压", "加载终点"],
            "questions": ["目的是什么?", "用哪种边界?"],
            "stopped": True,
        }
        self.assertEqual(minimum_native_chat_requirements(good), [])
        poor = dict(good, alternatives=[{"label": "单一方案"}], stopped=False)
        self.assertEqual(len(minimum_native_chat_requirements(poor)), 2)


if __name__ == "__main__":
    unittest.main()
