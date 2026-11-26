"""强制提问卡片规范 V2 — 最低测试集 8 项（规范 12.4）.

Run: python -m unittest tests.test_v40_card_spec -v

Covers the 8 mandated cases plus the MUST checks from sections 6 and 12:
  1 科研讨论卡  2 参数决策卡  3 参数数值卡  4 暂缓卡
  5 执行确认卡  6 上下文复用  7 决策变更  8 窄屏/长度约束
  + 状态区分 answered/confirmed/authorized/executed/verified
  + 去重键  推荐非默认选中  单卡单决策
"""

from __future__ import annotations

import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core import (  # noqa: E402
    AUTHOR_INPUT_NEEDED, CardStatus, CardType, DEFER_LABEL, Decision,
    Option, Question, QuestionPriority, dedup_key, validate_card, meta_for,
)
from modules.question_cards import (  # noqa: E402
    card_from_question_set, decision_summary, discussion_card,
    execution_card, parameter_card,
)


class TestMandatoryCards(unittest.TestCase):
    """规范 12.4 最低测试集."""

    def test_01_discussion_card(self):
        q = discussion_card(
            "goal", "本轮实验改变哪个变量?", "确定主变量，保证组间可比。",
            [Option("胶结强度", "pb", source="agent_proposal", recommended=True,
                    rationale="便于单因素对比"),
             Option("颗粒摩擦系数", "fric", source="agent_proposal"),
             Option("多个变量，需排序", "multi", source="agent_proposal")],
            known_context=["PFC3D", "单轴压缩"],
        )
        self.assertEqual(q.card_type, CardType.DISCUSSION)
        self.assertTrue(q.allow_free_text)
        self.assertTrue(any(o.get("defer") for o in q.to_decision_question()["options"]))
        self.assertEqual(validate_card(q), [])
        self.assertLessEqual(len(q.options), 4)

    def test_02_parameter_card(self):
        q = parameter_card(
            "dim", "选择模型维度?", "维度决定几何与颗粒生成方式。",
            [Option("PFC3D", "3D", source="user_provided"),
             Option("PFC2D", "2D", source="agent_proposal")],
            stage_id="模型",
        )
        self.assertEqual(q.card_type, CardType.PARAMETER)
        d = q.to_decision_question()
        self.assertEqual(d["header"], "模型·关键决策")
        self.assertEqual(validate_card(q), [])

    def test_03_numeric_card_with_unit_and_source(self):
        q = parameter_card(
            "conf", "围压取哪些水平?", "围压是唯一自变量，其余条件固定。",
            [Option("1,5,10", "1,5,10", unit="MPa", source="user_provided"),
             Option("自定义", "free", unit="MPa", source="agent_proposal")],
            unit="MPa", known_context=["已确认: 三轴压缩", "已确认: PFC3D"],
        )
        d = q.to_decision_question()
        self.assertIn("单位 MPa", d["options"][0]["description"])
        # Source stays in question_meta for audit, not in the visible option.
        meta = meta_for([q])[0]
        self.assertEqual(meta["options"][0]["source"], "user_provided")
        self.assertTrue(q.known_context)
        self.assertEqual(validate_card(q), [])

    def test_04_defer_path(self):
        q = parameter_card(
            "sample", "成样方式选哪种?", "初始重叠影响胶结与平衡。",
            [Option("ball generate", "gen", source="PFC_manual"),
             Option("ball distribute", "dist", source="PFC_manual")],
        )
        d = q.to_decision_question()
        defer = [o for o in d["options"] if o.get("defer")]
        self.assertEqual(len(defer), 1)
        self.assertIn("暂缓影响", defer[0]["description"])
        summary = decision_summary(q, "DEFERRED")
        self.assertTrue(summary["deferred"])
        self.assertEqual(summary["status"], CardStatus.DEFERRED.value)

    def test_05_execution_card_requires_explicit_authorization(self):
        q = execution_card(
            "run", "确认开始求解?", "使用已确认参数启动计算。",
            "启动求解", "当前 PFC3D 模型", "新建结果目录，不覆盖现有文件",
        )
        d = q.to_decision_question()
        self.assertFalse(q.allow_defer)
        self.assertNotIn(DEFER_LABEL, [o["label"] for o in d["options"]])
        self.assertEqual(q.submit_label, "确认执行")
        self.assertEqual(validate_card(q), [])
        summary = decision_summary(q, "CONFIRM_EXECUTE")
        self.assertTrue(summary["requires_execution_approval"])

    def test_06_context_reuse_no_repeat(self):
        # A known item must be marked known_context, never asked again.
        q = parameter_card(
            "dim", "选择模型维度?", "维度决定几何生成。",
            [Option("PFC3D", "3D", source="user_provided"),
             Option("PFC2D", "2D", source="agent_proposal")],
            known_context=["已确认: PFC3D"],
        )
        self.assertIn("已确认: PFC3D", q.known_context)
        self.assertEqual(dedup_key("exp1", "model", "dim"),
                         "exp1::model::dim")
        self.assertEqual(dedup_key("exp1", "model", "dim"),
                         dedup_key("exp1", "model", "dim"))

    def test_07_decision_change_supersedes(self):
        d = Decision("d1", "exp1", "design", "q1", decision="仅改变胶结强度")
        d.confirm()
        self.assertEqual(d.status, CardStatus.CONFIRMED)
        # Upstream change -> downstream marked superseded
        d.status = CardStatus.SUPERSEDED
        with self.assertRaises(ValueError):
            d.confirm()

    def test_08_length_caps_and_visual_constraints(self):
        q = parameter_card(
            "x", "短标题?", "一句话说明，不超过五十汉字。",
            [Option("选项A", "a", source="agent_proposal"),
             Option("选项B", "b", source="agent_proposal")],
        )
        self.assertEqual(validate_card(q), [])
        bad = Question(id="bad", prompt="x", title="这是一个非常非常非常非常非常非常非常长的标题超过二十个汉字上限",
                       description="说明",
                       options=[Option("o1", source="agent_proposal"),
                                Option("o2", source="agent_proposal")])
        self.assertIn("标题超过20汉字", validate_card(bad))


class TestStateMachine(unittest.TestCase):
    def test_state_distinctions(self):
        d = Decision("d2", "e", "exec", "q", requires_execution_approval=True)
        self.assertEqual(d.status, CardStatus.ANSWERED)
        with self.assertRaises(ValueError):
            d.mark_executed()          # not authorized yet
        d.confirm()
        self.assertEqual(d.status, CardStatus.CONFIRMED)
        with self.assertRaises(ValueError):
            d.mark_verified(True)      # not executed yet
        d.authorize()
        self.assertEqual(d.status, CardStatus.AUTHORIZED)
        d.mark_executed()
        self.assertEqual(d.status, CardStatus.EXECUTED)
        d.mark_verified(True)
        self.assertEqual(d.status, CardStatus.VERIFIED)
        self.assertTrue(d.verified)

    def test_confirmed_is_not_authorized(self):
        d = Decision("d3", "e", "exec", "q")
        d.confirm()
        self.assertNotEqual(d.status, CardStatus.AUTHORIZED)
        self.assertNotEqual(d.status, CardStatus.EXECUTED)

    def test_failed_verification(self):
        d = Decision("d4", "e", "exec", "q")
        d.confirm(); d.authorize(); d.mark_executed()
        d.mark_verified(False)
        self.assertEqual(d.status, CardStatus.FAILED)
        self.assertFalse(d.verified)


class TestSpecMUST(unittest.TestCase):
    def test_single_decision_per_card(self):
        # One card carries one core decision: only one question_id per card.
        q = parameter_card("only_one", "选择接触模型?", "决定颗粒间力学作用。",
                           [Option("Linear", "linear", source="agent_proposal"),
                            Option("LinearPBond", "pb", source="agent_proposal")])
        d = q.to_decision_question()
        self.assertEqual(len({o["id"] for o in d["options"]}), 1)

    def test_recommendation_not_default_selected(self):
        q = parameter_card("rec", "成样方式?", "影响初始重叠。",
                           [Option("ball generate", "gen", source="PFC_manual",
                                   recommended=True),
                            Option("ball distribute", "dist", source="PFC_manual")])
        d = q.to_decision_question()
        rec = [o for o in d["options"] if o.get("recommended")]
        self.assertEqual(len(rec), 1)
        self.assertIn("（建议）", rec[0]["label"])
        # recommended is a label, not a pre-checked state
        self.assertNotIn("is_default", rec[0])
        self.assertNotIn("checked", rec[0])

    def test_p4_not_asked(self):
        q = Question(id="p4", prompt="当前颗粒数?", title="当前颗粒数?",
                     description="该信息应自动读取，不应询问。",
                     priority=QuestionPriority.P4,
                     options=[Option("自动读取", source="agent_proposal"),
                              Option("手动输入", source="agent_proposal")])
        self.assertIn("P4 信息不得询问用户，应自动读取", validate_card(q))

    def test_question_set_to_compliant_card(self):
        item = {"id": "legacy", "question": "本轮实验改变哪个变量?\n确定主变量，保证组间可比。",
                "options": [{"label": "胶结强度", "value": "pb", "source": "agent_proposal"},
                            {"label": "摩擦系数", "value": "fric", "source": "agent_proposal"}]}
        q = card_from_question_set(item, "设计")
        self.assertEqual(validate_card(q), [])
        self.assertIn("本轮实验改变哪个变量?", q.panel_prompt())

    def test_author_input_needed_preserved(self):
        q = parameter_card("n", "独立重复次数?", "由你给出具体次数。",
                           [Option(AUTHOR_INPUT_NEEDED, AUTHOR_INPUT_NEEDED,
                                   source="pfc_practice"),
                            Option("3 次（不同随机种子）", "pfc_seed_3",
                                   source="pfc_practice")],
                           author_input_needed=True)
        self.assertTrue(q.author_input_needed)
        self.assertEqual(validate_card(q), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
