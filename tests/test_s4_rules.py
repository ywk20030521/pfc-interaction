"""PR-S4-3: rule and experience library acceptance tests."""

from __future__ import annotations

import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.s4_contracts import (  # noqa: E402
    CalibrationProject, EvidenceGrade, ModelCondition,
)
from core.s4_rules import PBM_MAPPING, RULES, RuleLibrary  # noqa: E402


def cond(model="LINEAR_PARALLEL_BOND", dim="3D", material="sandstone"):
    return ModelCondition(contact_model=model, pfc_version="9.0", dimension=dim,
                          material_class=material, porosity=0.15,
                          gradation="uniform", loading="triaxial")


class TestS4Rules(unittest.TestCase):
    def test_twelve_rules_present(self):
        self.assertEqual(len(RULES), 12)
        ids = [r["id"] for r in RULES]
        self.assertEqual(ids, list(range(1, 13)))
        for r in RULES:
            self.assertTrue(r["title"] and r["mandate"])

    def test_pbm_mapping_is_model_isolated(self):
        lib = RuleLibrary(CalibrationProject("p", "t", cond()))
        self.assertEqual(len(lib.pbm_mapping("LINEAR_PARALLEL_BOND")), len(PBM_MAPPING))
        for model in ("LINEAR", "FLAT_JOINT", "HERTZ"):
            with self.assertRaises(ValueError):
                lib.pbm_mapping(model)

    def test_experience_grade_and_scope(self):
        project = CalibrationProject("p", "t", cond())
        lib = RuleLibrary(project)
        rec = lib.add_experience("E 主要受刚度控制", EvidenceGrade.E3, cond(),
                                 "当前砂岩三轴", success_cases=["run-1"])
        found = lib.query_experience(cond(), min_grade=EvidenceGrade.E3)
        self.assertIn(rec, found)
        self.assertNotIn(rec, lib.query_experience(cond(), min_grade=EvidenceGrade.E5))

    def test_e5_does_not_migrate_across_model_material_dimension(self):
        project = CalibrationProject("p", "t", cond())
        lib = RuleLibrary(project)
        rec = lib.add_experience("pb_ten 与围压耦合", EvidenceGrade.E5, cond(),
                                 "当前砂岩三轴")
        self.assertTrue(lib.e5_scope_guard(rec.record_id, cond()))
        self.assertFalse(lib.e5_scope_guard(rec.record_id, cond(model="FLAT_JOINT")))
        self.assertFalse(lib.e5_scope_guard(rec.record_id, cond(dim="2D")))
        self.assertFalse(lib.e5_scope_guard(rec.record_id, cond(material="granite")))
        self.assertFalse(lib.query_experience(cond(dim="2D")))

    def test_experience_can_be_negated_with_counterexample(self):
        project = CalibrationProject("p", "t", cond())
        lib = RuleLibrary(project)
        rec = lib.add_experience("提高摩擦必增残余强度", EvidenceGrade.E4, cond(), "局部")
        with self.assertRaises(ValueError):
            lib.negate_experience(rec.record_id, "")
        lib.negate_experience(rec.record_id, "峰后滑移机制改变，残余强度反降")
        self.assertFalse(rec.active)
        self.assertEqual(len(rec.counterexamples), 1)
        self.assertEqual(lib.query_experience(cond()), [])

    def test_rule_class_priority_declared(self):
        from core.s4_rules import RULE_CLASS_PRIORITY
        self.assertGreater(RULE_CLASS_PRIORITY["project_validated"],
                           RULE_CLASS_PRIORITY["general"])


if __name__ == "__main__":
    unittest.main()
