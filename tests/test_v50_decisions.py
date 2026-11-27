"""5.0 PR-2: decision states, authorization binding and dual-channel dedup."""

from __future__ import annotations

import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.v50_context import DecisionStatus, InteractionStatus, ResearchTask, StageID  # noqa: E402
from core.v50_decisions import AUQ, NATIVE_CHAT, DecisionManager, InteractionRouter  # noqa: E402


def setup(auq_available=True):
    task = ResearchTask("task-auth", "授权验收")
    decisions = DecisionManager(task)
    return task, decisions, InteractionRouter(task, decisions, auq_available=auq_available)


class TestV50Decisions(unittest.TestCase):
    def test_agent_proposal_never_auto_confirms(self):
        task, decisions, _ = setup()
        d = decisions.propose("围压", "选5MPa", "实验目标")
        self.assertEqual(d.status, DecisionStatus.PROPOSED)
        self.assertFalse(d.user_response["confirmed"])

    def test_answer_is_not_confirmation(self):
        task, decisions, router = setup()
        event, new, _ = router.open("围压", "选哪个围压?", stage=StageID.S4)
        self.assertTrue(new)
        answer = router.answer(event.interaction_id, "5MPa")
        self.assertFalse(answer["decision_confirmed"])
        self.assertFalse(answer["execution_authorized"])
        with self.assertRaises(ValueError):
            router.confirm_from_answer(event.interaction_id)
        decisions.confirm(event.decision_id, "用户明确选择5MPa")
        self.assertEqual(task.decisions[event.decision_id].status, DecisionStatus.CONFIRMED)

    def test_authorization_binds_operation_target_and_versions(self):
        task, decisions, _ = setup()
        d = decisions.propose("启动仿真", "运行正式三轴", "用户已讨论方案",
                              affected_assets=["model_v1"])
        with self.assertRaises(ValueError):
            decisions.authorize(d.decision_id, "start_formal_simulation", "model_v1",
                                "run", "model_v1", "par_v1", "mx1")
        decisions.confirm(d.decision_id, "确认启动正式仿真")
        auth = decisions.authorize(
            d.decision_id, "start_formal_simulation", "model_v1", "run",
            "model_v1", "par_v1", "mx1")
        ok, issues = decisions.validate_authorization(
            auth.authorization_id, "start_formal_simulation", "model_v1", "run",
            "model_v1", "par_v1", "mx1")
        self.assertTrue(ok, issues)
        ok, issues = decisions.validate_authorization(
            auth.authorization_id, "run_batch", "model_v1", "run",
            "model_v1", "par_v1", "mx1")
        self.assertFalse(ok)
        self.assertTrue(any("operation" in i for i in issues))

    def test_context_change_invalidates_authorization(self):
        task, decisions, _ = setup()
        d = decisions.propose("重跑", "参数修改后重跑", "对照需要")
        decisions.confirm(d.decision_id, "确认重跑")
        auth = decisions.authorize(d.decision_id, "start_formal_simulation", "m1", "run",
                                   "m1", "p1", "mx1")
        task.bump_version("用户改变了研究边界")
        ok, issues = decisions.validate_authorization(
            auth.authorization_id, "start_formal_simulation", "m1", "run",
            "m1", "p1", "mx1")
        self.assertFalse(ok)
        self.assertTrue(any("上下文版本" in i for i in issues))

    def test_changed_asset_revokes_related_authorization(self):
        task, decisions, _ = setup()
        d = decisions.propose("关键参数", "修改 pb_ten", "标定结果",
                              affected_assets=["pb_ten"])
        decisions.confirm(d.decision_id, "确认修改")
        auth = decisions.authorize(d.decision_id, "change_key_parameter_and_rerun",
                                   "pb_ten", "run", "m1", "p1", "mx1")
        invalidated = decisions.invalidate_affected(["pb_ten"], "标定误差超限")
        self.assertIn(d.decision_id, invalidated)
        self.assertTrue(decisions.authorizations[auth.authorization_id].revoked)

    def test_dedup_across_channels(self):
        task, decisions, router = setup()
        first, new, _ = router.open("围压", "围压取多少?", channel=NATIVE_CHAT)
        self.assertTrue(new)
        again, new, reason = router.open("围压", "围压取多少?", channel=AUQ)
        self.assertFalse(new)
        self.assertEqual(again.interaction_id, first.interaction_id)
        self.assertIn("重复投递", reason)

    def test_cancel_and_timeout_are_not_rejection(self):
        task, decisions, router = setup()
        event, _, _ = router.open("维度", "选2D还是3D?")
        router.cancel(event.interaction_id, "用户离开")
        self.assertEqual(event.status, InteractionStatus.CANCELLED)
        self.assertIn("不等于拒绝", event.note)
        self.assertEqual(task.decisions[event.decision_id].status, DecisionStatus.PROPOSED)
        event2, _, _ = router.open("加载方式", "位移还是力控制?")
        router.timeout(event2.interaction_id)
        self.assertEqual(event2.status, InteractionStatus.TIMED_OUT)
        self.assertIn("不等于", event2.note)

    def test_auq_fallback_and_channel_switch(self):
        task, decisions, router = setup(auq_available=False)
        event, _, reason = router.open("围压", "围压取多少?", channel=AUQ)
        self.assertEqual(event.channel, NATIVE_CHAT)
        self.assertIn("回退", event.note)
        router.auq_available = True
        switched = router.switch_channel(event.interaction_id, AUQ)
        self.assertEqual(switched.channel, AUQ)
        self.assertEqual(event.status, InteractionStatus.SUPERSEDED)
        self.assertEqual(switched.decision_id, event.decision_id)


if __name__ == "__main__":
    unittest.main()
