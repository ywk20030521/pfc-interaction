"""PR-S4-2: identifiability and coupling acceptance tests."""

from __future__ import annotations

import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.s4_contracts import (  # noqa: E402
    CalibrationProject, EvidenceGrade, FiveLayerRelation, MicroParameter,
    ModelCondition, ParamClass, ParamState, ParameterGroup, ParameterRelation,
    RelationStatus,
)
from core.s4_identifiability import IdentifiabilityEngine  # noqa: E402


def setup():
    cond = ModelCondition(contact_model="LINEAR_PARALLEL_BOND", pfc_version="9.0")
    project = CalibrationProject("prj", "ident", cond)
    a = MicroParameter("a", "emod", ParamClass.INVERSE, "GPa", 10.0, [5, 20],
                       contact_model="LINEAR_PARALLEL_BOND")
    b = MicroParameter("b", "pb_ten", ParamClass.INVERSE, "MPa", 2.0, [1, 5],
                       contact_model="LINEAR_PARALLEL_BOND")
    a.set_state(ParamState.CANDIDATE, "初值")
    b.set_state(ParamState.CANDIDATE, "初值")
    project.parameters["a"] = a
    project.parameters["b"] = b
    layers = FiveLayerRelation("E", "力链", "刚度", "级配", "试算")
    project.relations["r1"] = ParameterRelation(
        "r1", "a", "t1", layers, contact_model="LINEAR_PARALLEL_BOND",
        condition_ref=cond.fingerprint, evidence_grade=EvidenceGrade.E3,
        status=RelationStatus.PROJECT_SCREENING)
    project.relations["r2"] = ParameterRelation(
        "r2", "b", "t1", layers, contact_model="LINEAR_PARALLEL_BOND",
        condition_ref=cond.fingerprint, evidence_grade=EvidenceGrade.E3,
        status=RelationStatus.PROJECT_SCREENING)
    return project, IdentifiabilityEngine(project), a, b


class TestS4Identifiability(unittest.TestCase):
    def test_five_questions_all_must_pass(self):
        project, engine, a, b = setup()
        result = engine.assess("a", ["t1"], {"t1": {"a": 0.8, "b": 0.2}})
        self.assertEqual(result["verdict"], "identifiable")
        self.assertEqual(result["action"], "proceed_to_calibration")

    def test_unidentifiable_refuses_blind_search(self):
        project, engine, a, b = setup()
        result = engine.assess("a", ["missing_target"], {"t1": {"a": 0.0}})
        self.assertEqual(result["verdict"], "NOT_IDENTIFIABLE")
        self.assertIn("DO_NOT_expand_blind_search", result["action"])
        self.assertIn("missing_target", result["missing_observation_targets"])

    def test_high_correlation_detects_compensation(self):
        project, engine, a, b = setup()
        result = engine.assess("a", ["t1"], {"t1": {"a": 0.8, "b": 0.75}},
                               pairwise_correlations={"a|b": 0.95})
        self.assertFalse(result["questions"]["effects_distinguishable"])
        self.assertTrue(result["equivalent_solution_risk"])

    def test_coupling_four_questions(self):
        project, engine, a, b = setup()
        group = ParameterGroup("g1", "弹性组", ["a", "b"], "都影响 E")
        res = engine.coupling_check(group)
        self.assertEqual(len(res["pairs"]), 1)
        self.assertTrue(res["pairs"][0]["q1_same_macro_target"])

    def test_equivalent_solutions_are_reported(self):
        project, engine, a, b = setup()
        res = engine.equivalent_solutions("t1", [
            {"response": 10.0, "params": {"a": 1}},
            {"response": 10.01, "params": {"a": 2}},
            {"response": 20.0, "params": {"a": 3}},
        ])
        self.assertTrue(res["has_equivalent_solutions"])
        self.assertIn("增加独立观测", res["conclusion"])


if __name__ == "__main__":
    unittest.main()
