"""PFC Interaction 5.0.1 protocol tests: issues, depth, evidence, archive, cards."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.question import Option  # noqa: E402
from core.v50_context import ResearchTask  # noqa: E402
from core.v50_decisions import DecisionManager, InteractionRouter  # noqa: E402
from core.v501_archive import ResearchArchive  # noqa: E402
from core.v501_change import ChangeManager  # noqa: E402
from core.v501_deep_discussion import (  # noqa: E402
    DeepDiscussionEngine, DepthLevel, DiscussionMode,
)
from core.v501_evidence import (  # noqa: E402
    EvidenceClass, EvidenceManager, HypothesisManager, Maturity,
)
from core.v501_issues import (  # noqa: E402
    IssuePriority, IssueStatus, IssueTree, IssueType,
)
from modules.v50_interaction import InteractionCoordinator  # noqa: E402
from modules.v501_cards import (  # noqa: E402
    CardKind, V501CardCoordinator, new_card, validate_v501_card,
)


def deep_engine(issue_id, depth=DepthLevel.D3):
    tree = IssueTree("t")
    issue = tree.create("围压耦合", IssueType.SCIENTIFIC_QUESTION,
                        priority=IssuePriority.P0)
    engine = DeepDiscussionEngine(tree)
    engine.start(issue.issue_id, depth, DiscussionMode.DISCOVERY)
    stages = [
        ("problem_definition", {}),
        ("candidate_solutions", {"alternatives": [{"name": "全因子"}]}),
        ("adversarial_review", {"counterexample": "伺服假象"}),
        ("user_feedback", {"user_feedback": "诊断优先"}),
        ("revision_synthesis", {"revision": "全矩阵延期"}),
    ]
    if depth == DepthLevel.D3:
        stages.append(("validation_plan", {"validation_plan": "独立围压验证"}))
    for stage, kwargs in stages:
        engine.record_stage(issue.issue_id, stage, "分析:" + stage, **kwargs)
    return tree, issue, engine


class TestV501Issues(unittest.TestCase):
    def test_issue_tree_keeps_history_on_reopen(self):
        tree = IssueTree("t")
        parent = tree.create("母议题", IssueType.SCIENTIFIC_QUESTION)
        child = tree.create("子议题", IssueType.MODEL_SELECTION,
                            parent_id=parent.issue_id)
        tree.depend_on(child.issue_id, parent.issue_id)
        tree.reopen(parent.issue_id, "新证据", ["ev-1"])
        self.assertEqual(parent.status, IssueStatus.REOPENED)
        self.assertEqual(parent.version, 2)
        self.assertEqual(child.status, IssueStatus.REOPENED)
        self.assertEqual(len(parent.history), 2)

    def test_validated_issue_requires_evidence(self):
        tree = IssueTree("t")
        issue = tree.create("待验证", IssueType.HYPOTHESIS)
        with self.assertRaises(ValueError):
            issue.set_status(IssueStatus.VALIDATED, "无证据")
        issue.set_status(IssueStatus.VALIDATED, "有证据", ["ev-1"])
        self.assertEqual(issue.status, IssueStatus.VALIDATED)

    def test_backlog_orders_p0_before_p1(self):
        tree = IssueTree("t")
        tree.create("低优先", IssueType.NEXT_STUDY, IssuePriority.P2)
        tree.create("高优先", IssueType.ANOMALY, IssuePriority.P0)
        self.assertEqual(tree.backlog()[0].priority, IssuePriority.P0)


class TestV501DeepDiscussion(unittest.TestCase):
    def test_d3_first_round_cannot_become_card(self):
        tree = IssueTree("t")
        issue = tree.create("核心假设", IssueType.HYPOTHESIS)
        engine = DeepDiscussionEngine(tree)
        engine.start(issue.issue_id, DepthLevel.D3)
        with self.assertRaises(ValueError):
            engine.can_card(issue.issue_id)

    def test_adversarial_review_needs_counterexample(self):
        tree, issue, engine = deep_engine(issue_id=None, depth=DepthLevel.D2)
        with self.assertRaises(ValueError):
            engine.record_stage(issue.issue_id, "adversarial_review", "仅重复观点")

    def test_d3_gate_ready_after_all_substantive_stages(self):
        tree, issue, engine = deep_engine(None)
        gate = engine.gate(issue.issue_id)
        self.assertTrue(gate["ready"], gate["missing"])
        self.assertIn("validation_plan", gate["stages"])
        self.assertGreaterEqual(gate["revision_count"], 1)

    def test_user_correction_updates_plan(self):
        tree, issue, engine = deep_engine(None, DepthLevel.D2)
        correction = engine.apply_user_correction(
            issue.issue_id, "直接全因子", "诊断优先", "伺服未验证")
        self.assertEqual(correction["corrected"], "诊断优先")
        self.assertTrue(any("诊断优先" in r.get("revision", "")
                            for r in engine.cycles[issue.issue_id].revisions))


class TestV501Evidence(unittest.TestCase):
    def test_user_experience_cannot_support_validation(self):
        ev = EvidenceManager()
        entry = ev.add(EvidenceClass.USER_EXPERIENCE, "user:lab",
                       description="实验室经验")
        with self.assertRaises(ValueError):
            ev.assert_conclusive([entry.evidence_id])

    def test_hypothesis_not_validated_without_conclusive_evidence(self):
        ev = EvidenceManager()
        hm = HypothesisManager(ev)
        hyp = hm.register("围压抑制脆性", competing=["伺服假象"])
        result = hm.assess(hyp.hypothesis_id)
        self.assertEqual(result["maturity"], Maturity.UNRESOLVED.value)
        tool = ev.add(EvidenceClass.TOOL_OBSERVATION, "pfc-1", tool_task_id="pfc-1")
        result = hm.assess(hyp.hypothesis_id) if False else hm.set_maturity(
            hyp.hypothesis_id, Maturity.EMPIRICALLY_SUPPORTED,
            [tool.evidence_id], reason="工具证据")
        self.assertEqual(result.maturity, Maturity.EMPIRICALLY_SUPPORTED)


class TestV501ChangeAndArchive(unittest.TestCase):
    def test_change_reopens_issue_and_invalidates_decision(self):
        task = ResearchTask("t", "变更")
        decisions = DecisionManager(task)
        tree = IssueTree("t")
        issue = tree.create("伺服", IssueType.NUMERICAL_RISK,
                            evidence_needs=["C3"])
        d = decisions.propose("伺服可用", "启用伺服", "暂无证据",
                              affected_assets=["C3"])
        decisions.confirm(d.decision_id, "用户确认")
        ev = EvidenceManager()
        eid = ev.add(EvidenceClass.TOOL_OBSERVATION, "pfc-1", tool_task_id="pfc-1").evidence_id
        change = ChangeManager(tree, decisions, ev).analyze(
            "围压未建立", ["C3"], [eid], [issue.issue_id])
        self.assertEqual(issue.status, IssueStatus.REOPENED)
        self.assertIn(d.decision_id, change.invalidated_decisions)

    def test_archive_generates_expected_files(self):
        tree = IssueTree("t")
        tree.create("议题", IssueType.SCIENTIFIC_QUESTION)
        with tempfile.TemporaryDirectory() as tmp:
            archive = ResearchArchive(Path(tmp))
            files = archive.write_all(
                {"research_task_id": "t", "title": "验收"},
                tree, None, None, None, None, None)
            names = {Path(f).name for f in files}
            self.assertIn("ISSUE_TREE.md", names)
            self.assertIn("EVIDENCE_INDEX.md", names)
            self.assertIn("CHANGELOG.md", names)
            self.assertTrue((Path(tmp) / "archive_index.json").exists())


class TestV501Cards(unittest.TestCase):
    def setUp(self):
        self.task = ResearchTask("t", "卡片")
        self.decisions = DecisionManager(self.task)
        self.coordinator = InteractionCoordinator(
            self.task, self.decisions, InteractionRouter(self.task, self.decisions))

    def test_card_blocked_before_deep_discussion(self):
        tree = IssueTree("t")
        issue = tree.create("设计", IssueType.EXPERIMENT_DESIGN)
        engine = DeepDiscussionEngine(tree)
        engine.start(issue.issue_id, DepthLevel.D2)
        v501 = V501CardCoordinator(self.coordinator, tree, engine)
        card = new_card(CardKind.PLAN_CONFIRMATION, issue.issue_id, "t",
                        "确认诊断方案", "先跑诊断工况。",
                        options=[Option("确认", "ok"), Option("返回", "back")],
                        applicability="围压可控前", rejected_alternatives=["全因子"],
                        unresolved_risks=["伺服失败"], impact="影响工况数")
        with self.assertRaises(ValueError):
            v501.prepare(card)

    def test_execution_card_requires_version_binding(self):
        card = new_card(CardKind.EXECUTION_AUTHORIZATION, "iss-1", "t",
                        "启动正式仿真", "对三工况执行正式仿真。",
                        options=[Option("确认执行", "CONFIRM_EXECUTE"),
                                 Option("取消", "CANCEL")],
                        action="启动三工况", target="model_v1", risks=["覆盖结果"],
                        authorization_scope="run_model")
        errors = validate_v501_card(card)
        self.assertTrue(any("绑定" in e for e in errors))

    def test_parameter_card_requires_unit_and_source(self):
        card = new_card(CardKind.PARAMETER_REGISTRATION, "iss-1", "t",
                        "胶结抗拉取值", "pb_ten 的取值与来源。",
                        options=[Option("1 MPa", "1"), Option("2 MPa", "2")],
                        parameter_name="pb_ten", symbol="pb_ten", unit="MPa",
                        current_value=1.0, suggested_range="1-2 MPa", basis="经验初值")
        self.assertTrue(any("来源" in e for e in validate_v501_card(card)))


if __name__ == "__main__":
    unittest.main()
