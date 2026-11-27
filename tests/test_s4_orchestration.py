"""PR-S4-4: S4 subsystem orchestration and freeze acceptance tests."""

from __future__ import annotations

import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.s4_contracts import (  # noqa: E402
    CalibrationProject, EvidenceGrade, FitPhase, ModelCondition, ParamClass,
    ParamState,
)
from modules.s4_calibration import C1_C8, S4CalibrationSubsystem  # noqa: E402


def setup():
    cond = ModelCondition(contact_model="LINEAR_PARALLEL_BOND", pfc_version="9.0",
                          material_class="sandstone", porosity=0.15,
                          gradation="uniform", loading="triaxial")
    project = CalibrationProject("prj", "S4 验收", cond)
    s4 = S4CalibrationSubsystem(project)
    return project, s4


def build_through_c6(s4):
    t = s4.c1_define_goal("E", 10.0, "GPa", 0.1, role=FitPhase.FIT)
    p = s4.c2_register_parameter("emod", ParamClass.INVERSE, "GPa", 10.0, [5, 20], "接触刚度")
    s4.c3_add_relation(p.parameter_id, t.target_id, "弹性模量", "力链刚度",
                       "接触/黏结刚度", "当前孔隙率", "项目试算",
                       "positive", EvidenceGrade.E3)
    plan = s4.c4_plan(validation_cases=["brazil"])
    s4.c5_approve_plan(plan.plan_id, "用户同意方案")
    run = s4.c6_add_run(p.parameter_id, "pfc-real-1", "data.csv", {"E": 9.7})
    return p, t, run


class TestS4Orchestration(unittest.TestCase):
    def test_c_stages_are_ordered(self):
        project, s4 = setup()
        with self.assertRaises(ValueError):
            s4.c2_register_parameter("emod", ParamClass.INVERSE)
        build_through_c6(s4)
        self.assertEqual(C1_C8[:6], s4.completed[:6])
        self.assertEqual(project.status, "C6")

    def test_c6_run_requires_real_tool_task_id(self):
        project, s4 = setup()
        t = s4.c1_define_goal("E", 10.0, "GPa", 0.1)
        p = s4.c2_register_parameter("emod", ParamClass.INVERSE, "GPa", 10.0)
        s4.c3_add_relation(p.parameter_id, t.target_id, "E", "力链", "刚度",
                           "孔隙率", "试算", grade=EvidenceGrade.E3)
        plan = s4.c4_plan()
        s4.c5_approve_plan(plan.plan_id, "同意")
        with self.assertRaises(ValueError):
            s4.c6_add_run(p.parameter_id, "synthetic-run", "d.csv", {"E": 9.0})

    def test_fit_status_is_not_calibration_or_validation(self):
        project, s4 = setup()
        status = s4.c8_fit_status("p1", {"E": 0.02}, {"E": 0.05})
        self.assertTrue(status["fit_good"])
        self.assertFalse(status["calibration_complete"])
        self.assertFalse(status["independent_validation_passed"])

    def test_freeze_requires_independent_validation(self):
        project, s4 = setup()
        p, t, run = build_through_c6(s4)
        # Complete C7 via identifiability check.
        s4.c7_assess_identifiability(p.parameter_id, [t.target_id],
                                     {t.target_id: {p.parameter_id: 0.8}})
        with self.assertRaises(ValueError):
            s4.freeze(p.parameter_id, "no-validation", "用户确认")
        val = s4.c8_validate(held_out_conditions=["brazil-peak"],
                             outcomes={"bts": 0.04}, criteria={"bts": 0.1},
                             mechanism_check="张拉破坏为主")
        self.assertTrue(val.passed)

    def test_freeze_succeeds_only_with_confirmed_param_and_validation(self):
        project, s4 = setup()
        p, t, run = build_through_c6(s4)
        s4.c7_assess_identifiability(p.parameter_id, [t.target_id],
                                     {t.target_id: {p.parameter_id: 0.8}})
        val = s4.c8_validate(["brazil-peak"], {"bts": 0.04}, {"bts": 0.1}, "张拉破坏")
        p.set_state(ParamState.USER_CONFIRMED, "用户确认")
        with self.assertRaises(ValueError):
            s4.freeze(p.parameter_id, val.validation_id, "")
        snap = s4.freeze(p.parameter_id, val.validation_id, "科研判断同意冻结")
        self.assertEqual(p.state, ParamState.VALIDATED)
        self.assertEqual(snap["validation"]["validation_id"], val.validation_id)
        self.assertEqual(project.status, "frozen")
        self.assertIn("relations", snap)

    def test_freeze_rejects_unconfirmed_parameter(self):
        project, s4 = setup()
        p, t, run = build_through_c6(s4)
        s4.c7_assess_identifiability(p.parameter_id, [t.target_id],
                                     {t.target_id: {p.parameter_id: 0.8}})
        val = s4.c8_validate(["brazil-peak"], {"bts": 0.04}, {"bts": 0.1}, "张拉破坏")
        with self.assertRaises(ValueError):
            s4.freeze(p.parameter_id, val.validation_id, "用户确认")

    def test_next_best_wired_into_subsystem(self):
        project, s4 = setup()
        result = s4.c7_next_experiment([
            {"action": "single_perturbation", "information_gain": 0.2,
             "cost": 3, "scientific_value": 0.1},
            {"action": "new_observation", "information_gain": 1.0,
             "cost": 2, "scientific_value": 0.9},
        ], compensation_detected=True)
        self.assertEqual(result["chosen"]["action"], "new_observation")

    def test_snapshot_traceable(self):
        project, s4 = setup()
        build_through_c6(s4)
        snap = s4.snapshot()
        self.assertIn("completed_c_stages", snap)
        self.assertIn("project", snap)
        self.assertTrue(snap["project"]["history"])


if __name__ == "__main__":
    unittest.main()
