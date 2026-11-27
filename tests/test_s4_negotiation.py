"""PR-S4-2: per-parameter negotiation and scheme B acceptance tests."""

from __future__ import annotations

import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.s4_contracts import (  # noqa: E402
    CalibrationProject, MicroParameter, ModelCondition, ParamClass, ParamState,
)
from core.s4_negotiation import SEVEN_STEPS, NegotiationEngine  # noqa: E402


def setup():
    cond = ModelCondition(contact_model="LINEAR_PARALLEL_BOND", pfc_version="9.0")
    project = CalibrationProject("prj", "negotiation", cond)
    p = MicroParameter("p1", "fric", ParamClass.EXPERIMENT_ESTIMATED, "", 0.5,
                       contact_model="LINEAR_PARALLEL_BOND")
    q = MicroParameter("p2", "pb_ten", ParamClass.INVERSE, "MPa", 2.0,
                       contact_model="LINEAR_PARALLEL_BOND")
    project.parameters["p1"] = p
    project.parameters["p2"] = q
    return project, NegotiationEngine(project), p, q


def complete_seven_steps(engine, pid):
    engine.start(pid)
    for step in SEVEN_STEPS:
        engine.advance(pid, step, "step content for " + step)


class TestS4Negotiation(unittest.TestCase):
    def test_seven_steps_must_be_in_order(self):
        project, engine, p, q = setup()
        engine.start("p1")
        with self.assertRaises(ValueError):
            engine.advance("p1", "candidate_discussion", "too early")
        for step in SEVEN_STEPS:
            engine.advance("p1", step, "ok")
        self.assertEqual(len(engine.progress["p1"]), 7)

    def test_card_submit_is_not_confirm_nor_authorize(self):
        project, engine, p, q = setup()
        card = engine.create_card("p1", "是否有独立实验约束摩擦参数?",
                                  ["物理含义", "耦合风险"], ["有", "部分", "无"])
        card.submit("目前没有相关证据")
        self.assertTrue(card.submitted_opinion)
        self.assertFalse(card.confirmed)
        self.assertFalse(card.authorized)
        self.assertNotEqual(p.state, ParamState.USER_CONFIRMED)
        with self.assertRaises(ValueError):
            card.authorize("执行")
        card.confirm("确认该判断")
        card.authorize("授权执行")
        self.assertTrue(card.authorized)

    def test_decision_requires_full_seven_steps(self):
        project, engine, p, q = setup()
        with self.assertRaises(ValueError):
            engine.decide("p1", "topic", "rec", ["a"], [])
        complete_seven_steps(engine, "p1")
        decision = engine.decide("p1", "摩擦参数方案", "保持当前值", ["0.5"], ["evidence-1"])
        self.assertEqual(decision.approval_state, "PENDING")
        self.assertFalse(bool(decision.user_response))

    def test_confirm_state_needs_approved_decision(self):
        project, engine, p, q = setup()
        complete_seven_steps(engine, "p1")
        decision = engine.decide("p1", "topic", "rec", ["a"], [])
        with self.assertRaises(ValueError):
            engine.confirm_state("p1", decision.decision_id, "用户回答")
        decision.approve("用户同意该方案")
        engine.confirm_state("p1", decision.decision_id, "用户同意")
        self.assertEqual(p.state, ParamState.USER_CONFIRMED)
        self.assertEqual(decision.approval_state, "CONFIRMED")

    def test_scheme_b_group_needs_independent_archives(self):
        project, engine, p, q = setup()
        with self.assertRaises(ValueError):
            engine.create_group("弹性组", ["p1", "p2"], "耦合")
        complete_seven_steps(engine, "p1")
        d1 = engine.decide("p1", "t", "r", ["a"], [])
        d1.approve("ok")
        engine.confirm_state("p1", d1.decision_id, "ok")
        with self.assertRaises(ValueError):
            engine.create_group("弹性组", ["p1", "p2"], "p2 无独立档案")
        complete_seven_steps(engine, "p2")
        d2 = engine.decide("p2", "t2", "r2", ["b"], [])
        d2.approve("ok")
        engine.confirm_state("p2", d2.decision_id, "ok")
        group = engine.create_group("弹性组", ["p1", "p2"], "都影响 E")
        self.assertEqual(len(group.parameter_ids), 2)
        self.assertEqual(len(project.parameters), 2)  # independent archives remain

    def test_joint_decision_requires_all_coupling_answers(self):
        project, engine, p, q = setup()
        for pid in ("p1", "p2"):
            complete_seven_steps(engine, pid)
            d = engine.decide(pid, "t", "r", ["a"], [])
            d.approve("ok")
            engine.confirm_state(pid, d.decision_id, "ok")
        group = engine.create_group("组", ["p1", "p2"], "耦合")
        with self.assertRaises(ValueError):
            engine.joint_decision(group.group_id, "联合调参")
        for question in ("direction", "compensation", "distinguishable"):
            engine.set_coupling_answer(group.group_id, "p1", "p2", question, True)
        engine.joint_decision(group.group_id, "联合调参")
        self.assertEqual(group.joint_decision, "联合调参")


if __name__ == "__main__":
    unittest.main()
