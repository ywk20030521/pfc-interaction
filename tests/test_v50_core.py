"""5.0 PR-1/PR-3/PR-4: context, discussion and workflow acceptance tests."""

from __future__ import annotations

import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.v50_context import (  # noqa: E402
    DecisionStatus, EvidenceItem, EvidenceKind, ParameterRecord,
    ParameterStatus, ResearchTask, STAGE_ARTIFACTS, STAGE_COMPLETION,
    StageID, StageStatus,
)
from core.v50_decisions import DecisionManager  # noqa: E402
from core.v50_discussion import DiscussionManager, ProposalOption, make_proposal  # noqa: E402
from core.v50_workflow import WorkflowOrchestrator  # noqa: E402


def setup():
    task = ResearchTask("task-v50", "5.0 验收任务")
    decisions = DecisionManager(task)
    return task, decisions, DiscussionManager(task), WorkflowOrchestrator(task, decisions)


class TestV50Context(unittest.TestCase):
    def test_stage_and_module_status_are_separate(self):
        task, _, _, _ = setup()
        self.assertEqual(task.stage_status[StageID.S1.value], StageStatus.DISCUSSING.value)
        self.assertNotIn("status", task.snapshot()["research_task"])
        self.assertTrue(all(stage.value in task.stage_status for stage in StageID))

    def test_evidence_classification_and_validation(self):
        task, _, _, _ = setup()
        bad = EvidenceItem(EvidenceKind.TOOL_EVIDENCE, "data.csv")
        self.assertIn("tool_task_id", "; ".join(bad.validate()))
        with self.assertRaises(ValueError):
            task.add_evidence(bad)
        item = EvidenceItem(EvidenceKind.TOOL_EVIDENCE, "data.csv", tool_task_id="pfc-123")
        task.add_evidence(item)
        self.assertEqual(task.evidence[0].kind, EvidenceKind.TOOL_EVIDENCE)
        self.assertIn(EvidenceKind.AGENT_PROPOSAL, EvidenceKind.non_conclusive())

    def test_parameter_cannot_be_marked_calibrated_without_evidence(self):
        p = ParameterRecord("p1", "pb_ten")
        p.target_metrics = {"peak": {"target": 10, "tolerance": 0.1}}
        p.error_metrics = {"peak": 0.02}
        p.acceptance_criteria = {"peak": 0.1}
        with self.assertRaises(ValueError):
            p.mark_calibrated([], True, "无证据")
        p.mark_calibrated([EvidenceItem(EvidenceKind.COMPUTED_RESULT, "e1",
                                        input_refs=["data.csv"])], True, "达标")
        self.assertEqual(p.calibration_status, ParameterStatus.CALIBRATED)
        p.confirm("用户确认采用该参数")
        self.assertEqual(p.confirmation_status, "CONFIRMED")

    def test_context_version_changes_with_substantive_updates(self):
        task, _, _, _ = setup()
        before = task.context_version
        task.add_evidence(EvidenceItem(EvidenceKind.USER_INPUT, "user-intent"))
        self.assertNotEqual(task.context_version, before)
        self.assertTrue(task.provenance[-1]["reason"].startswith("evidence:"))


class TestV50Discussion(unittest.TestCase):
    def test_question_only_turn_is_rejected(self):
        _, _, discussion, _ = setup()
        with self.assertRaises(ValueError):
            discussion.add_turn("围压来源", question="请确认围压?")
        turn = discussion.add_turn("围压来源", analysis="文献给出1-10MPa",
                                   next_step="请用户确认目标围压")
        self.assertEqual(turn["analysis"], "文献给出1-10MPa")

    def test_recommendation_requires_evidence(self):
        opt = ProposalOption("线性接触", "颗粒线性接触", "初步成样",
                             pros=["简单"], cons=["无胶结"], recommended=True)
        with self.assertRaises(ValueError):
            make_proposal("观测", "依据", [opt, ProposalOption(
                "平行胶结", "含胶结", "强度分析", ["可表达强度"], ["参数多"])], [], [])
        opt.evidence_refs = ["PFC_manual"]
        proposal = make_proposal("观测", "依据", [opt, ProposalOption(
            "平行胶结", "含胶结", "强度分析", ["可表达强度"], ["参数多"])], [], [])
        self.assertEqual(proposal["source"], "agent_proposal")

    def test_user_viewpoint_requires_understanding_before_response(self):
        _, _, discussion, _ = setup()
        with self.assertRaises(ValueError):
            discussion.respond_to_user("改用2D", "", "2D更快", [])
        discussion.respond_to_user("改用2D", "用户希望降低计算量", "2D更快但代表性下降",
                                   ["结论维度受限"])
        self.assertIn("用户观点", discussion.turns[-1]["topic"])

    def test_stage_advance_uses_conditions_not_question_counts(self):
        task, _, discussion, _ = setup()
        conditions = {c: True for c in STAGE_COMPLETION[StageID.S1]}
        result = discussion.can_advance(conditions)
        self.assertTrue(result["allowed"])
        task.discussion["unresolved"] = ["研究边界不清"]
        result = discussion.can_advance(conditions)
        self.assertFalse(result["allowed"])
        result = discussion.can_advance({}, user_requested_provisional=True)
        self.assertTrue(result["provisional"])


class TestV50Workflow(unittest.TestCase):
    def test_stage_and_module_are_not_one_to_one(self):
        _, _, _, workflow = setup()
        plan = workflow.plan_modules(StageID.S4)
        module_ids = {p["module_id"] for p in plan}
        self.assertGreater(len(module_ids), 1)
        self.assertTrue(all(p["stage_id"] == StageID.S4.value for p in plan))

    def test_direct_stage_skip_is_blocked(self):
        _, _, _, workflow = setup()
        with self.assertRaises(ValueError):
            workflow.enter(StageID.S4)

    def test_submit_review_requires_stage_artifacts(self):
        _, _, _, workflow = setup()
        with self.assertRaises(ValueError):
            workflow.submit_for_review({"research_brief": "x"})
        result = workflow.submit_for_review(
            {name: "ref:%s" % name for name in STAGE_ARTIFACTS[StageID.S1]})
        self.assertEqual(result["status"], StageStatus.READY_FOR_REVIEW.value)

    def test_rollback_requires_evidence_and_invalidates_decisions(self):
        task, decisions, _, workflow = setup()
        decision = decisions.propose(
            "围压方案", "采用5MPa", "标定目标来自实验",
            affected_assets=["calibration_plan"])
        decisions.confirm(decision.decision_id, "用户确认")
        task.current_stage = StageID.S5
        task.set_stage_status(StageID.S5, StageStatus.IN_PROGRESS, "test")
        with self.assertRaises(ValueError):
            workflow.rollback(StageID.S4, "无证据", [], ["calibration_plan"])
        trans = workflow.rollback(
            StageID.S4, "加载中围压失控",
            [EvidenceItem(EvidenceKind.TOOL_EVIDENCE, "log.csv", tool_task_id="pfc-1")],
            ["calibration_plan"])
        self.assertEqual(task.current_stage, StageID.S4)
        self.assertEqual(task.stage_status[StageID.S4.value], StageStatus.REOPENED.value)
        self.assertEqual(task.decisions[decision.decision_id].status,
                         DecisionStatus.INVALIDATED)
        self.assertIn("calibration_plan", trans.artifacts_to_redo)

    def test_rollback_cannot_use_only_agent_proposal(self):
        task, _, _, workflow = setup()
        task.current_stage = StageID.S3
        with self.assertRaises(ValueError):
            workflow.rollback(
                StageID.S2, "感觉不对",
                [EvidenceItem(EvidenceKind.AGENT_PROPOSAL, "idea")], [])


if __name__ == "__main__":
    unittest.main()
