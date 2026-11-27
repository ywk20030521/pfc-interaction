"""5.0 PR-6: card presentation, dedup, feedback and execution authorization."""

from __future__ import annotations

import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.question import Option, validate_card  # noqa: E402
from core.v50_context import ResearchTask  # noqa: E402
from core.v50_decisions import DecisionManager, InteractionRouter  # noqa: E402
from modules.question_cards import discussion_card, execution_card, parameter_card  # noqa: E402
from modules.v50_interaction import InteractionCoordinator  # noqa: E402


def setup():
    task = ResearchTask("task-card", "卡片验收")
    decisions = DecisionManager(task)
    router = InteractionRouter(task, decisions)
    return task, decisions, router, InteractionCoordinator(task, decisions, router)


def param_card(qid="pb", title="胶结抗拉强度取值?"):
    return parameter_card(
        qid, title, "该参数影响峰值强度与破坏模式。",
        [Option("2 MPa", "2", unit="MPa", source="agent_proposal"),
         Option("3 MPa", "3", unit="MPa", source="agent_proposal")],
        unit="MPa", stage_id="参数标定",
    )


class TestV50Interaction(unittest.TestCase):
    def test_default_single_card_and_max_three(self):
        task, decisions, router, coordinator = setup()
        cards = [param_card("q%d" % i, "参数%d取值?" % i) for i in range(4)]
        self.assertTrue(coordinator.validate_batch(cards))
        self.assertEqual(coordinator.validate_batch(cards[:2]), ["多张卡片必须声明共同事项，否则应逐张展示"])
        self.assertEqual(coordinator.validate_batch(cards[:2], "参数组"), [])

    def test_prepare_renders_panel_and_reuses_dedup_instance(self):
        task, decisions, router, coordinator = setup()
        card = param_card()
        prepared = coordinator.prepare(card)
        self.assertTrue(prepared.new_interaction)
        self.assertIn("关键决策", prepared.panel_header)
        self.assertIn("胶结抗拉强度", prepared.panel_prompt)
        self.assertEqual(prepared.card_type, "PARAMETER")
        self.assertTrue(prepared.question_meta["options"])
        again = coordinator.prepare(param_card("pb2"))
        self.assertFalse(again.new_interaction)
        self.assertEqual(again.interaction_id, prepared.interaction_id)

    def test_submit_never_confirms_or_executes(self):
        task, decisions, router, coordinator = setup()
        prepared = coordinator.prepare(param_card())
        result = coordinator.submit(prepared.interaction_id, "2")
        self.assertFalse(result["decision_confirmed"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["execution_performed"])
        self.assertTrue(result["requires_agent_feedback"])
        self.assertEqual(task.decisions[prepared.decision_id].status.value, "PROPOSED")

    def test_parameter_card_cannot_grant_execution_authority(self):
        task, decisions, router, coordinator = setup()
        prepared = coordinator.prepare(param_card())
        coordinator.submit(prepared.interaction_id, "2")
        with self.assertRaises(ValueError):
            coordinator.authorize_execution(
                prepared.interaction_id, "start_formal_simulation", "model_v1",
                "m1", "p1", "mx1")

    def test_execution_card_explicit_authorization_only(self):
        task, decisions, router, coordinator = setup()
        card = execution_card("exec1", "启动正式仿真?", "将运行三轴压缩三工况。",
                              "启动正式仿真", "model_v1", "覆盖已有结果")
        self.assertEqual(validate_card(card), [])
        self.assertFalse(card.allow_defer)
        prepared = coordinator.prepare(card)
        with self.assertRaises(ValueError):
            coordinator.authorize_execution(
                prepared.interaction_id, "start_formal_simulation", "model_v1",
                "m1", "p1", "mx1")
        coordinator.submit(prepared.interaction_id, "CONFIRM_EXECUTE")
        auth = coordinator.authorize_execution(
            prepared.interaction_id, "start_formal_simulation", "model_v1",
            "m1", "p1", "mx1")
        ok, issues = decisions.validate_authorization(
            auth.authorization_id, "start_formal_simulation", "model_v1", "run",
            "m1", "p1", "mx1")
        self.assertFalse(ok)
        self.assertTrue(any("scope" in i for i in issues))
        ok, issues = decisions.validate_authorization(
            auth.authorization_id, "start_formal_simulation", "model_v1",
            "execute:exec1", "m1", "p1", "mx1")
        self.assertTrue(ok, issues)

    def test_cards_never_bypass_core(self):
        task, decisions, router, coordinator = setup()
        card = discussion_card("d1", "研究目标是否聚焦?", "目标过多会影响实验设计。",
                               [Option("聚焦峰值强度", "focus", source="agent_proposal"),
                                Option("保留全部目标", "all", source="agent_proposal")])
        prepared = coordinator.prepare(card)
        coordinator.submit(prepared.interaction_id, "focus")
        self.assertEqual(task.decisions[prepared.decision_id].status.value, "PROPOSED")
        self.assertEqual(list(decisions.authorizations), [])


if __name__ == "__main__":
    unittest.main()
