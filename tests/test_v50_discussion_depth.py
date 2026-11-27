"""5.0: discussion depth gate before structuring a topic into a card."""

from __future__ import annotations

import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.question import Option  # noqa: E402
from core.v50_context import EvidenceItem, EvidenceKind, ResearchTask  # noqa: E402
from core.v50_decisions import DecisionManager, InteractionRouter  # noqa: E402
from core.v50_discussion import DiscussionManager  # noqa: E402
from modules.question_cards import discussion_card  # noqa: E402
from modules.v50_interaction import InteractionCoordinator  # noqa: E402


def setup():
    task = ResearchTask("t-depth", "讨论深度验收")
    decisions = DecisionManager(task)
    discussion = DiscussionManager(task)
    router = InteractionRouter(task, decisions)
    coordinator = InteractionCoordinator(task, decisions, router)
    return task, discussion, coordinator


def deep_turn(discussion: DiscussionManager, topic: str) -> None:
    discussion.add_turn(
        topic, understanding="用户希望比较围压与胶结对强度的影响",
        analysis="双因素问题需区分主效应与交互项",
        evidence=[EvidenceItem(EvidenceKind.USER_INPUT, "user:intent")],
        assumptions=["pb_ten 尚未标定"],
        alternatives=[
            {"name": "全因子", "pros": "可估交互", "cons": "成本高"},
            {"name": "正交缩减", "pros": "省成本", "cons": "交互估计弱"},
        ],
        impact=["工况数增加", "标定负担上升"],
        next_step="确认工况结构",
    )


class TestV50DiscussionDepth(unittest.TestCase):
    def test_empty_discussion_is_not_ready(self):
        task, discussion, _ = setup()
        gate = discussion.gate_for_card("围压与胶结耦合")
        self.assertFalse(gate["ready"])
        self.assertIn("understanding", " ".join(gate["missing"]))
        self.assertIn("alternatives", " ".join(gate["missing"]))

    def test_shallow_turn_still_missing_dimensions(self):
        task, discussion, _ = setup()
        discussion.add_turn("围压与胶结耦合", analysis="需要双因素设计",
                            next_step="确认工况")
        gate = discussion.gate_for_card("围压与胶结耦合")
        self.assertFalse(gate["ready"])
        self.assertTrue(any("understanding" in m for m in gate["missing"]))

    def test_deep_turn_passes_default_profile(self):
        task, discussion, _ = setup()
        deep_turn(discussion, "围压与胶结耦合")
        gate = discussion.gate_for_card("围压与胶结耦合")
        self.assertTrue(gate["ready"], gate["missing"])
        self.assertEqual(gate["supplied"]["alternatives"], 2)

    def test_high_stakes_requires_two_alternatives(self):
        task, discussion, _ = setup()
        discussion.add_turn(
            "胶结强度参数化", understanding="需把概念转为参数",
            analysis="pb_ten 与 UCS 反标定成本不同",
            evidence=[EvidenceItem(EvidenceKind.USER_INPUT, "user:intent")],
            alternatives=[{"name": "pb_ten", "pros": "直接", "cons": "需标定"}],
            impact=["影响标定工作量"], next_step="确认参数化")
        gate = discussion.gate_for_card("胶结强度参数化", "high_stakes")
        self.assertFalse(gate["ready"])
        self.assertTrue(any("alternatives" in m for m in gate["missing"]))

    def test_require_depth_raises_with_detail(self):
        task, discussion, _ = setup()
        with self.assertRaises(ValueError) as ctx:
            discussion.require_depth("科研目标")
        self.assertIn("讨论深度不足", str(ctx.exception))

    def test_card_preparation_is_blocked_until_discussion_is_deep(self):
        task, discussion, coordinator = setup()
        card = discussion_card(
            "matrix", "工况矩阵如何设置?", "确定双因素工况结构。",
            [Option("全因子", "full", source="agent_proposal"),
             Option("正交缩减", "orth", source="agent_proposal")],
            known_context=["三轴压缩"],
        )
        with self.assertRaises(ValueError):
            coordinator.prepare(card, discussion=discussion,
                                topic="围压与胶结耦合")
        deep_turn(discussion, "围压与胶结耦合")
        prepared = coordinator.prepare(card, discussion=discussion,
                                       topic="围压与胶结耦合")
        self.assertTrue(prepared.depth_gate["ready"])
        self.assertEqual(prepared.depth_gate["related_turns"], 1)

    def test_legacy_prepare_without_discussion_records_unchecked_gate(self):
        task, discussion, coordinator = setup()
        card = discussion_card(
            "goal", "研究目标是什么?", "明确本轮核心问题。",
            [Option("围压效应", "conf", source="agent_proposal"),
             Option("胶结效应", "bond", source="agent_proposal")],
            known_context=["三轴压缩"],
        )
        prepared = coordinator.prepare(card)
        self.assertFalse(prepared.depth_gate["checked"])
        self.assertIn("未接入", prepared.depth_gate["note"])


if __name__ == "__main__":
    unittest.main()
