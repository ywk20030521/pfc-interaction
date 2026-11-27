"""PR-S4-1: macro-micro relation engine acceptance tests."""

from __future__ import annotations

import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.s4_contracts import (  # noqa: E402
    CalibrationProject, EvidenceGrade, FitPhase, FiveLayerRelation,
    ModelCondition, ParamClass, RelationStatus,
)
from core.s4_relation import RelationEngine  # noqa: E402


def setup(model="LINEAR_PARALLEL_BOND"):
    cond = ModelCondition(contact_model=model, pfc_version="9.0", dimension="3D",
                          material_class="sandstone", porosity=0.15,
                          gradation="uniform", preparation="pluviation",
                          boundary="walls", loading="triaxial")
    project = CalibrationProject("prj-1", "标定", cond)
    return project, RelationEngine(project)


def layers():
    return FiveLayerRelation("弹性模量 E", "力链传递与整体刚度", "接触/黏结刚度",
                             "当前孔隙率与级配", "当前项目单因素试算")


class TestS4Relation(unittest.TestCase):
    def test_register_parameter_binds_condition_fingerprint(self):
        project, engine = setup()
        p = engine.register_parameter("emod", ParamClass.INVERSE,
                                      "LINEAR_PARALLEL_BOND", "GPa", 10.0, [5.0, 20.0])
        self.assertEqual(p.condition_ref, project.condition.fingerprint)

    def test_register_target_role_fit_or_validation(self):
        project, engine = setup()
        fit = engine.register_target("E", 10.0, "GPa", 0.1, role=FitPhase.FIT)
        val = engine.register_target("BTS", 5.0, "MPa", 0.1,
                                     role=FitPhase.INDEPENDENT_VALIDATION)
        self.assertEqual(fit.role, FitPhase.FIT)
        self.assertEqual(val.role, FitPhase.INDEPENDENT_VALIDATION)

    def test_static_mapping_table_is_rejected(self):
        project, engine = setup()
        p = engine.register_parameter("emod", ParamClass.INVERSE, "LINEAR_PARALLEL_BOND")
        t = engine.register_target("E", 10.0, "GPa", 0.1)
        with self.assertRaises(ValueError):
            engine.reject_static_mapping(p.parameter_id, t.target_id)

    def test_relation_status_follows_evidence_grade(self):
        project, engine = setup()
        p = engine.register_parameter("emod", ParamClass.INVERSE, "LINEAR_PARALLEL_BOND")
        t = engine.register_target("E", 10.0, "GPa", 0.1)
        rel = engine.add_relation(p.parameter_id, t.target_id, layers(),
                                  "positive", evidence_grade=EvidenceGrade.E2)
        self.assertEqual(rel.status, RelationStatus.LITERATURE_SUPPORTED)
        self.assertEqual(rel.condition_ref, project.condition.fingerprint)

    def test_literature_cannot_upgrade_to_project_validation(self):
        project, engine = setup()
        p = engine.register_parameter("emod", ParamClass.INVERSE, "LINEAR_PARALLEL_BOND")
        t = engine.register_target("E", 10.0, "GPa", 0.1)
        rel = engine.add_relation(p.parameter_id, t.target_id, layers(),
                                  evidence_grade=EvidenceGrade.E2)
        with self.assertRaises(ValueError):
            rel.upgrade_status(RelationStatus.PROJECT_SCREENING, EvidenceGrade.E2,
                               ["run-1"])

    def test_local_sensitivity_is_named_local(self):
        project, engine = setup()
        p = engine.register_parameter("emod", ParamClass.INVERSE, "LINEAR_PARALLEL_BOND")
        t = engine.register_target("E", 10.0, "GPa", 0.1)
        rel = engine.add_relation(p.parameter_id, t.target_id, layers())
        result = engine.local_sensitivity(rel.relation_id, 10.0, 11.0, 10.0, 11.0)
        self.assertAlmostEqual(result["s_ij"], 1.0)
        self.assertIn("局部", result["note"])
        with self.assertRaises(ValueError):
            engine.local_sensitivity(rel.relation_id, 10.0, 11.0, 0.0, 1.0)

    def test_query_relations_filters_by_status(self):
        project, engine = setup()
        p = engine.register_parameter("emod", ParamClass.INVERSE, "LINEAR_PARALLEL_BOND")
        t = engine.register_target("E", 10.0, "GPa", 0.1)
        engine.add_relation(p.parameter_id, t.target_id, layers(),
                            evidence_grade=EvidenceGrade.E2)
        engine.add_relation(p.parameter_id, t.target_id, layers(),
                            evidence_grade=EvidenceGrade.E5)
        self.assertEqual(len(engine.query_relations()), 2)
        self.assertEqual(len(engine.query_relations(
            min_status=RelationStatus.MULTI_CASE_VALIDATED)), 1)

    def test_relation_model_is_isolated(self):
        lpb, engine_lpb = setup("LINEAR_PARALLEL_BOND")
        _, engine_lin = setup("LINEAR")
        p = engine_lpb.register_parameter("emod", ParamClass.INVERSE, "LINEAR_PARALLEL_BOND")
        t = engine_lpb.register_target("E", 10.0, "GPa", 0.1)
        rel = engine_lpb.add_relation(p.parameter_id, t.target_id, layers(),
                                      evidence_grade=EvidenceGrade.E5)
        self.assertEqual(rel.contact_model, "LINEAR_PARALLEL_BOND")
        self.assertEqual(len(engine_lin.project.relations), 0)


if __name__ == "__main__":
    unittest.main()
