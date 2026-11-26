"""IF0 interface-level acceptance tests - first batch (M1/M2/M3).

Run: python -m unittest discover -s tests -v
These tests check CONTRACT compliance, not module feature completeness.
"""

import os
import sys
import tempfile
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "modules"))

from core import (  # noqa: E402
    ArtifactStore,
    CONTRACT_VERSION,
    CoreDispatcher,
    DecisionKey,
    DispatchRequest,
    Envelope,
    Evidence,
    EvidenceSource,
    ExecutionResult,
    ModuleID,
    ModuleState,
    TaskState,
    state_mapping_check,
)
from m1_planning import ResearchRequirements  # noqa: E402
from m2_design import ExperimentDesign, ParameterDef, build_matrix  # noqa: E402
from m3_modeling import ModelDesign, generate_pfc_script, validate_script  # noqa: E402


class IF0Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core = CoreDispatcher(ArtifactStore(self.tmp.name))


class TestStateLayers(IF0Base):
    def test_mapping_presented_approved_executed(self):
        self.assertTrue(all(state_mapping_check().values()))

    def test_approved_is_not_executed(self):
        self.core.states.dispatch("t")
        self.core.states.present("t")
        self.core.states.resolve("t", "APPROVED")
        snap = self.core.states.snapshot("t")
        self.assertEqual(snap["interaction_state"].value, "APPROVED")
        self.assertEqual(snap["task_state"].value, "READY")
        self.assertEqual(snap["module_state"].value, ModuleState.RUNNING)

    def test_c07_execution_without_tool_task_id_is_rejected(self):
        self.core.states.dispatch("t")
        errors = self.core.states.finish_execution("t", ExecutionResult("", TaskState.COMPLETED))
        self.assertTrue(errors)
        self.assertEqual(self.core.states.snapshot("t")["module_state"], ModuleState.FAILED)

    def test_c05_rejected_cannot_be_represented(self):
        self.core.states.dispatch("t")
        self.core.states.present("t")
        self.core.states.resolve("t", "REJECTED")
        self.assertEqual(self.core.states.snapshot("t")["module_state"], ModuleState.BLOCKED)


class TestContract(IF0Base):
    def test_c01_wrong_contract_version_rejected(self):
        env = Envelope(
            module_id=ModuleID.M1,
            module_version="0.1.0",
            research_task_id="R",
            module_task_id="T",
            contract_version="IF0-0.9.0",
            status={"module_state": "COMPLETED"},
            output={"structured": {}},
        )
        errors = env.validate()
        self.assertTrue(any("contract_version" in e for e in errors))

    def test_c02_unresolvable_input_ref_rejected(self):
        from core import ArtifactRef

        req = DispatchRequest(
            "R",
            ModuleID.M3,
            input_refs=[ArtifactRef("missing", "x", "v1", "deadbeef")],
        )
        _env, errors = self.core.dispatch(req)
        self.assertTrue(any("unresolvable" in e for e in errors))

    def test_evidence_enum_is_closed(self):
        ev = Evidence("not_a_source", "ref")
        self.assertTrue(ev.validate())

    def test_module_cannot_claim_verified_by_execution(self):
        env = Envelope(
            module_id=ModuleID.M3,
            module_version="0.1.0",
            research_task_id="R",
            module_task_id="T",
            status={"module_state": "COMPLETED"},
            output={"structured": {}, "artifacts": [], "verified_by_execution": True},
        )
        self.core._module_tasks["T"] = DispatchRequest("R", ModuleID.M3)
        errors = self.core.accept_result(env)
        self.assertTrue(any("verified_by_execution" in e for e in errors))


class TestDedupAndAuthorization(IF0Base):
    def test_c05_duplicate_answered_not_represented(self):
        key = DecisionKey("E1", "M1", "确认研究计划", "cv1")
        item1, present1, _ = self.core.decisions.request(key, "q", ["a"], "t")
        self.assertTrue(present1)
        self.core.decisions.present(item1.decision_id)
        self.core.decisions.resolve(item1.decision_id, "APPROVED")
        item2, present2, _ = self.core.decisions.request(key, "q", ["a"], "t")
        self.assertFalse(present2)
        self.assertEqual(item2.decision_id, item1.decision_id)

    def test_c06_context_change_invalidates_approval(self):
        key = DecisionKey("E1", "M2", "确认参数", "cv1")
        item, _, _ = self.core.decisions.request(
            key, "q", ["a"], "t", authorization_scope="run_model"
        )
        auth = self.core.decisions.resolve(item.decision_id, "APPROVED", "cv1")
        ok, _ = self.core.decisions.valid_authorization(auth.authorization_id, "cv1", "run_model")
        self.assertTrue(ok)
        ok, reason = self.core.decisions.valid_authorization(auth.authorization_id, "cv2", "run_model")
        self.assertFalse(ok)
        self.assertIn("context", reason)

    def test_authorization_scope_is_enforced(self):
        key = DecisionKey("E1", "M3", "执行模型", "cv1")
        item, _, _ = self.core.decisions.request(
            key, "q", ["a"], "t", authorization_scope="run_model"
        )
        auth = self.core.decisions.resolve(item.decision_id, "APPROVED", "cv1")
        ok, _ = self.core.decisions.valid_authorization(auth.authorization_id, "cv1", "other_op")
        self.assertFalse(ok)

    def test_superseded_link_is_kept(self):
        key = DecisionKey("E1", "M1", "确认研究计划", "cv1")
        item, _, _ = self.core.decisions.request(key, "q", ["a"], "t")
        new = self.core.decisions.supersede(item.decision_id)
        self.assertEqual(self.core.decisions.snapshot(item.decision_id)["superseded_by"], new.decision_id)


class TestC03C04C13C14(IF0Base):
    def test_c03_parameters_trace_to_m2(self):
        from m3_modeling import build_model_parameters

        m2 = {
            "parameter_schema": [
                {"name": "颗粒半径", "unit": "mm", "values": [0.3], "confirmed": True}
            ]
        }
        params = build_model_parameters(m2, {"颗粒半径": 0.3})
        radius = [p for p in params if p.name == "颗粒半径"][0]
        self.assertIn("M2", radius.source)
        self.assertTrue(radius.confirmed)

    def test_c04_script_generation_is_not_verification(self):
        design = ModelDesign("2D", "C01")
        design.model_parameters = []
        design.scripts.append(generate_pfc_script(design, {}))
        design.validation = validate_script(design)
        self.assertFalse(design.validation["verified_by_execution"])

    def test_c13_inference_cannot_be_confirmed(self):
        ev = Evidence(EvidenceSource.AGENT_INFERRED, "x")
        self.assertEqual(ev.validate(), [])
        self.assertIn(EvidenceSource.AGENT_INFERRED, EvidenceSource.non_conclusive())

    def test_c14_raw_artifacts_not_overwritten(self):
        ref1 = self.core.store.write("raw", "data.csv", "a,b\n1,2", raw=True)
        ref2 = self.core.store.write("raw", "data.csv", "a,b\n3,4", raw=True)
        self.assertNotEqual(ref1.version, ref2.version)
        self.assertEqual(self.core.store.get(ref1), "a,b\n1,2")
        self.assertIn("raw", self.core.store.raw_ids())


class TestM1M2M3Contract(IF0Base):
    def test_m1_stays_waiting_for_user(self):
        req = ResearchRequirements(
            research_objective="研究粒径影响",
            independent_vars=["粒径"],
            dependent_vars=["峰值强度"],
            fact_vs_suggestion=[{"claim": "目标由用户给出", "origin": "user_provided"}],
        )
        self.assertEqual(req.validate(), [])
        self.assertIn("research_scope", req.missing_for_confirmation())

    def test_m2_matrix_has_no_duplicate_cases(self):
        design = ExperimentDesign(
            "单轴压缩",
            parameter_schema=[
                ParameterDef("粒径", "mm", [0.2, 0.3], 0.2, "M1", True),
            ],
            measurement_plan=[
                {"metric": m}
                for m in ["轴向应力", "轴向应变", "峰值强度", "弹性模量"]
            ],
            trace_to_vars=[{"m1_var": "粒径", "parameter": "粒径"}],
        )
        build_matrix(design)
        self.assertEqual(len(design.cases), 2)
        self.assertEqual(design.validate(), [])

    def test_m3_validation_lists_unconfirmed_parameters(self):
        design = ModelDesign("2D", "C01")
        design.validation = validate_script(design)
        self.assertEqual(design.validation["structure"]["status"], "FAIL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
