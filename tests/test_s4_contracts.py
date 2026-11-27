"""PR-S4-1: S4 data contracts acceptance tests."""

from __future__ import annotations

import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.s4_contracts import (  # noqa: E402
    CalibrationPlan, CalibrationProject, CalibrationRun, CalibrationValidation,
    DataStatus, EvidenceGrade, FitPhase, FiveLayerRelation, MacroTarget,
    MicroParameter, ModelCondition, ParamClass, ParamState, ParameterRelation,
    RelationStatus, _fingerprint,
)


def condition(model="LINEAR_PARALLEL_BOND", dim="3D", material="sandstone", porosity=0.15):
    return ModelCondition(contact_model=model, pfc_version="9.0", dimension=dim,
                          material_class=material, porosity=porosity,
                          gradation="uniform", preparation="pluviation",
                          boundary="walls", loading="triaxial")


def five_layers():
    return FiveLayerRelation(
        macro_goal="弹性模量 E",
        micro_mechanism="接触力链与整体刚度",
        micro_parameter="接触/黏结刚度",
        structure_condition="当前级配与孔隙率",
        evidence="当前项目单因素试算",
    )


class TestS4Contracts(unittest.TestCase):
    def test_condition_fingerprint_changes_with_structure(self):
        c1, c2 = condition(), condition(porosity=0.22)
        c3 = condition()
        self.assertNotEqual(c1.fingerprint, c2.fingerprint)
        self.assertEqual(c1.fingerprint, c3.fingerprint)
        self.assertTrue(c1.same_as(c3))
        self.assertFalse(c1.same_as(c2))

    def test_five_layers_must_be_complete(self):
        incomplete = FiveLayerRelation("E", "力链", "刚度", "", "试算")
        self.assertTrue(incomplete.validate())
        self.assertFalse(five_layers().validate())

    def test_parameter_class_and_state_transition(self):
        p = MicroParameter("p1", "pb_ten", ParamClass.INVERSE, "MPa", 2.0,
                           [1.0, 5.0],
                           contact_model="LINEAR_PARALLEL_BOND",
                           physical_meaning="parallel bond",
                           condition_ref=condition().fingerprint)
        self.assertEqual(p.param_class, ParamClass.INVERSE)
        with self.assertRaises(ValueError):
            p.set_state(ParamState.CANDIDATE, "")
        p.set_state(ParamState.USER_CONFIRMED, "用户确认初值")
        self.assertEqual(p.state, ParamState.USER_CONFIRMED)
        self.assertEqual(len(p.change_log), 1)

    def test_relation_requires_model_and_condition(self):
        with self.assertRaises(ValueError):
            ParameterRelation("r1", "p1", "t1", five_layers(), contact_model="")
        with self.assertRaises(ValueError):
            ParameterRelation("r1", "p1", "t1", five_layers(),
                              contact_model="LINEAR_PARALLEL_BOND", condition_ref="")

    def test_relation_upgrade_needs_project_evidence(self):
        rel = ParameterRelation("r1", "p1", "t1", five_layers(),
                                contact_model="LINEAR_PARALLEL_BOND",
                                condition_ref=condition().fingerprint,
                                evidence_grade=EvidenceGrade.E2,
                                status=RelationStatus.LITERATURE_SUPPORTED)
        with self.assertRaises(ValueError):
            rel.upgrade_status(RelationStatus.PROJECT_SCREENING, EvidenceGrade.E2, [])
        with self.assertRaises(ValueError):
            rel.upgrade_status(RelationStatus.PROJECT_SCREENING, EvidenceGrade.E2, ["run-1"])
        rel.upgrade_status(RelationStatus.PROJECT_SCREENING, EvidenceGrade.E3, ["run-1"])
        self.assertEqual(rel.status, RelationStatus.PROJECT_SCREENING)
        with self.assertRaises(ValueError):
            rel.upgrade_status(RelationStatus.MULTI_CASE_VALIDATED, EvidenceGrade.E4, ["r1", "r2"])
        rel.upgrade_status(RelationStatus.MULTI_CASE_VALIDATED, EvidenceGrade.E5, ["r1", "r2", "r3"])
        rel.negate("新工况反例")
        self.assertEqual(rel.status, RelationStatus.NEGATED)

    def test_calibration_run_rejects_fake_tool_ids(self):
        for fake in ("", "recorded-abc", "synthetic-run", "mock-1", "demo"):
            with self.assertRaises(ValueError):
                CalibrationRun("run", "p1:v1", "cf-1", fake, "data.csv")
        run = CalibrationRun("run", "p1:v1", "cf-1", "pfc-abc123", "data.csv",
                             phase=FitPhase.INDEPENDENT_VALIDATION)
        self.assertEqual(run.phase, FitPhase.INDEPENDENT_VALIDATION)

    def test_calibration_plan_requires_c8(self):
        with self.assertRaises(ValueError):
            CalibrationPlan("plan", stages=["C1", "C2"])
        with self.assertRaises(ValueError):
            CalibrationPlan("plan", stages=["C1", "C9", "C8"])
        plan = CalibrationPlan("plan", stages=["C1", "C3", "C8"])
        self.assertIn("C8", plan.stages)

    def test_independent_validation_object(self):
        with self.assertRaises(ValueError):
            CalibrationValidation("v1", held_out_conditions=[])
        with self.assertRaises(ValueError):
            CalibrationValidation("v1", held_out_conditions=["ucs"], passed=True)
        v = CalibrationValidation("v1", held_out_conditions=["brazil"],
                                  outcomes={"bts": 5.2}, passed=True)
        self.assertTrue(v.passed)

    def test_validation_status_cannot_be_assigned_to_prediction(self):
        target = MacroTarget("t1", "E", 10.0, "GPa", 0.1, data_status=DataStatus.predicted)
        self.assertIn(target.data_status, {DataStatus.predicted, DataStatus.inferred,
                                           DataStatus.expert_prior})
        self.assertNotEqual(target.data_status, DataStatus.validated)

    def test_project_snapshot_is_traceable(self):
        project = CalibrationProject("prj-1", "砂岩三轴标定", condition())
        project.record("C1", "确定目标")
        project.record("C2", "建立参数体系")
        snap = project.to_dict()
        self.assertEqual(len(snap["history"]), 2)
        self.assertIn("fingerprint", snap["condition"])


if __name__ == "__main__":
    unittest.main()
