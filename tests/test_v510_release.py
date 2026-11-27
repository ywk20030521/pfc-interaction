"""5.1 release tests: continuity, routing, deep modules and physics gates."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.v501_archive import ResearchArchive  # noqa: E402
from core.v501_deep_discussion import DeepDiscussionEngine, DepthLevel  # noqa: E402
from core.v501_issues import IssueType, IssueTree  # noqa: E402
from core.v510_continuity import SessionRestore  # noqa: E402
from core.v510_physics import evaluate_triaxial_case  # noqa: E402
from core.v510_routing import recommend_mode  # noqa: E402
from modules.v510_deep_modules import V510DeepModuleRunner  # noqa: E402


def ready_tree():
    tree = IssueTree("t")
    issue = tree.create("围压耦合", IssueType.SCIENTIFIC_QUESTION)
    engine = DeepDiscussionEngine(tree)
    engine.start(issue.issue_id, DepthLevel.D2)
    for stage, kw in [("problem_definition", {}),
                      ("candidate_solutions", {"alternatives": [{"name": "A"}]}),
                      ("adversarial_review", {"counterexample": "伺服假象"}),
                      ("user_feedback", {"user_feedback": "诊断优先"}),
                      ("revision_synthesis", {"revision": "全矩阵延期"})]:
        engine.record_stage(issue.issue_id, stage, "分析:"+stage, **kw)
    return tree, issue, engine


class TestV510Continuity(unittest.TestCase):
    def test_archive_restores_issue_tree(self):
        tree, issue, engine = ready_tree()
        with tempfile.TemporaryDirectory() as tmp:
            ResearchArchive(Path(tmp)).write_all(
                {"research_task_id": "t", "title": "恢复"}, tree, None, None, None, None,
                engine)
            restore = SessionRestore(Path(tmp))
            state = restore.restore_all()
            self.assertEqual(len(state["issues"].issues), 1)
            self.assertEqual(len(state["open_backlog"]), 1)
            self.assertEqual(restore.summary()["issue_count"], 1)

    def test_restore_requires_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                SessionRestore(Path(tmp)).load()


class TestV510Routing(unittest.TestCase):
    def test_anomaly_routes_to_conference(self):
        tree = IssueTree("t")
        issue = tree.create("伺服异常", IssueType.ANOMALY)
        self.assertEqual(recommend_mode(issue).mode.value, "ANOMALY_CONFERENCE")

    def test_parameter_routes_to_negotiation(self):
        tree = IssueTree("t")
        issue = tree.create("pb_ten", IssueType.PARAMETER)
        self.assertEqual(recommend_mode(issue).mode.value, "PARAMETER_NEGOTIATION")


class TestV510DeepModules(unittest.TestCase):
    def test_module_blocked_when_depth_missing(self):
        tree = IssueTree("t")
        issue = tree.create("实验设计", IssueType.EXPERIMENT_DESIGN)
        engine = DeepDiscussionEngine(tree)
        engine.start(issue.issue_id, DepthLevel.D2)
        runner = V510DeepModuleRunner()
        result = runner.run("M2", issue.issue_id,
                            {"control_strategy": "baseline", "variable_map": "v",
                             "measurement_plan": "m"}, tree, engine)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(result["unresolved_items"])

    def test_module_completes_after_gate(self):
        tree, issue, engine = ready_tree()
        runner = V510DeepModuleRunner()
        result = runner.run(
            "M2", issue.issue_id,
            {"control_strategy": "baseline", "variable_map": "v",
             "measurement_plan": "m", "candidates": ["全因子", "诊断优先"],
             "conclusion": "诊断优先"}, tree, engine)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["module_id"], "M2")
        self.assertIn("unresolved_items", result)


class TestV510Physics(unittest.TestCase):
    def test_confinement_gate_passes_valid_run(self):
        result = evaluate_triaxial_case(1.0004, 1.0, [1.01, 0.99], ["pfc-1"],
                                        samples_after_peak=2)
        self.assertTrue(result["data_valid_for_mechanism_comparison"])
        self.assertTrue(result["peak_strength_claim_allowed"])

    def test_uncontrolled_confinement_blocks(self):
        result = evaluate_triaxial_case(0.014, 1.0, [0.2], ["pfc-1"])
        self.assertEqual(result["status"], "BLOCKED_CONFINEMENT")
        self.assertFalse(result["peak_strength_claim_allowed"])

    def test_missing_tool_id_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_triaxial_case(1.0, 1.0, [1.0], [])


if __name__ == "__main__":
    unittest.main()
