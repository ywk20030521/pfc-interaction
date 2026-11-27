"""5.0 PR-5: cross-module calibration loop acceptance tests."""

from __future__ import annotations

import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.v50_context import EvidenceItem, EvidenceKind, ParameterStatus, ResearchTask  # noqa: E402
from core.v50_decisions import DecisionManager  # noqa: E402
from modules.v50_calibration import ParameterCalibrationLoop  # noqa: E402


def setup(max_iterations=8):
    task = ResearchTask("task-cal", "标定验收")
    decisions = DecisionManager(task)
    return task, decisions, ParameterCalibrationLoop(task, decisions, max_iterations)


def target_evidence():
    return EvidenceItem(EvidenceKind.USER_INPUT, "target:peak:10MPa",
                        description="用户给定峰值目标")


class TestV50Calibration(unittest.TestCase):
    def test_define_target_requires_real_source(self):
        task, decisions, loop = setup()
        param = loop.register_parameter("pb_ten", 2.0, "MPa", "胶结抗拉强度")
        with self.assertRaises(ValueError):
            loop.define_target(param.parameter_id, "peak", 10, "MPa", 0.1,
                               EvidenceItem(EvidenceKind.AGENT_PROPOSAL, "guess"))
        loop.define_target(param.parameter_id, "peak", 10, "MPa", 0.1, target_evidence())
        self.assertIn("peak", param.target_metrics)

    def test_matrix_requires_baseline(self):
        task, decisions, loop = setup()
        param = loop.register_parameter("pb_ten", 2.0, "MPa")
        with self.assertRaises(ValueError):
            loop.design_matrix(param.parameter_id, [{"case_id": "C1", "role": "test"}])
        matrix = loop.design_matrix(param.parameter_id, [
            {"case_id": "C1", "role": "baseline", "value": 2.0},
            {"case_id": "C2", "role": "test", "value": 3.0},
        ])
        self.assertEqual(matrix["matrix_version"], "mx1")

    def test_fake_tool_task_id_is_rejected(self):
        task, decisions, loop = setup()
        param = loop.register_parameter("pb_ten", 2.0, "MPa")
        for fake in ("", "recorded-abc123", "synthetic-run"):
            with self.assertRaises(ValueError):
                loop.add_run(param.parameter_id, "C1", fake, "data.csv", {"peak": 9.0}, "m1")

    def test_error_requires_target_diagnosis_and_computation_input(self):
        task, decisions, loop = setup()
        param = loop.register_parameter("pb_ten", 2.0, "MPa")
        case = loop.add_run(param.parameter_id, "C1", "pfc-123", "data.csv",
                            {"peak": 9.0}, "m1")
        with self.assertRaises(ValueError):
            loop.compute_error("C1")
        loop.diagnose_trust("C1", True, "数据完整", ["data.csv"])
        with self.assertRaises(ValueError):
            loop.compute_error("C1")
        loop.define_target(param.parameter_id, "peak", 10, "MPa", 0.1, target_evidence())
        errors = loop.compute_error("C1")
        self.assertAlmostEqual(errors["peak"], 0.1)

    def test_untrusted_data_cannot_enter_error_analysis(self):
        task, decisions, loop = setup()
        param = loop.register_parameter("pb_ten", 2.0, "MPa")
        loop.define_target(param.parameter_id, "peak", 10, "MPa", 0.1, target_evidence())
        loop.add_run(param.parameter_id, "C1", "pfc-1", "d.csv", {"peak": 9.0}, "m1")
        loop.diagnose_trust("C1", False, "围压未达标", ["log.csv"])
        with self.assertRaises(ValueError):
            loop.compute_error("C1")

    def test_confirm_calibrated_requires_acceptance(self):
        task, decisions, loop = setup()
        param = loop.register_parameter("pb_ten", 2.0, "MPa")
        loop.define_target(param.parameter_id, "peak", 10, "MPa", 0.05, target_evidence())
        loop.add_run(param.parameter_id, "C1", "pfc-1", "d.csv", {"peak": 8.0}, "m1")
        loop.diagnose_trust("C1", True, "可信", ["d.csv"])
        loop.compute_error("C1")
        result = loop.evaluate(param.parameter_id)
        self.assertEqual(result["status"], "NEEDS_ITERATION")
        self.assertFalse(result["acceptance_met"])
        with self.assertRaises(ValueError):
            loop.confirm_calibrated(param.parameter_id, "用户确认")
        self.assertNotEqual(param.calibration_status, ParameterStatus.CALIBRATED)

    def test_full_loop_passes_with_evidence_user_confirmation_and_history(self):
        task, decisions, loop = setup()
        param = loop.register_parameter("pb_ten", 2.0, "MPa", "胶结抗拉")
        loop.define_target(param.parameter_id, "peak", 10, "MPa", 0.1, target_evidence())
        for cid, peak in (("C1", 9.2), ("C2", 9.5)):
            loop.add_run(param.parameter_id, cid, "pfc-" + cid,
                         cid + ".csv", {"peak": peak}, "m1")
            loop.diagnose_trust(cid, True, "工具证据完整", [cid + ".csv"])
            loop.compute_error(cid)
        sensitivity = loop.sensitivity(param.parameter_id)
        self.assertTrue(sensitivity["non_uniqueness_warning"])
        result = loop.evaluate(param.parameter_id)
        self.assertTrue(result["acceptance_met"], result["reasons"])
        loop.confirm_calibrated(param.parameter_id, "用户确认这组参数")
        self.assertEqual(param.calibration_status, ParameterStatus.CONFIRMED)
        self.assertTrue(param.change_history)
        self.assertIn("CALIBRATED", [h.get("event") for h in param.change_history])

    def test_adjustment_needs_user_confirmation_and_iteration_cap(self):
        task, decisions, loop = setup(max_iterations=1)
        param = loop.register_parameter("pb_ten", 2.0, "MPa")
        loop.define_target(param.parameter_id, "peak", 10, "MPa", 0.1, target_evidence())
        proposal = loop.propose_adjustment(param.parameter_id, 3.0, "误差超限",
                                           ["error:C1"])
        with self.assertRaises(ValueError):
            loop.apply_parameter(param.parameter_id, 3.0, "误差超限",
                                 proposal.decision_id, "m2")
        decisions.confirm(proposal.decision_id, "用户同意调整")
        loop.apply_parameter(param.parameter_id, 3.0, "误差超限",
                             proposal.decision_id, "m2")
        self.assertEqual(loop.iterations[param.parameter_id], 1)
        second = loop.propose_adjustment(param.parameter_id, 4.0, "仍需调整", ["error:C2"])
        decisions.confirm(second.decision_id, "用户再次同意")
        with self.assertRaises(ValueError):
            loop.apply_parameter(param.parameter_id, 4.0, "仍需调整",
                                 second.decision_id, "m3")

    def test_snapshot_contains_traceable_history(self):
        task, decisions, loop = setup()
        param = loop.register_parameter("pb_ten", 2.0, "MPa")
        loop.define_target(param.parameter_id, "peak", 10, "MPa", 0.1, target_evidence())
        loop.add_run(param.parameter_id, "C1", "pfc-1", "d.csv", {"peak": 9.5}, "m1")
        snap = loop.snapshot()
        self.assertEqual(snap["cases"][0]["tool_task_id"], "pfc-1")
        self.assertIn(param.parameter_id, snap["evaluation"])


if __name__ == "__main__":
    unittest.main()
