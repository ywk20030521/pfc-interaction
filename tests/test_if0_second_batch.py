"""IF0 interface-level acceptance tests - second batch (M4/M5/M6) + C08-C16.

Run: python tests/test_if0_second_batch.py
"""

import os
import sys
import tempfile
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core import (  # noqa: E402
    ArtifactStore, CoreDispatcher, DecisionKey, DispatchRequest,
    Evidence, EvidenceSource, ModuleID, ModuleState, TaskState,
)
from modules import m1_planning, m2_design, m3_modeling, m4_simulation, m5_diagnosis, m6_analysis  # noqa: E402


class IF0Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core = CoreDispatcher(ArtifactStore(self.tmp.name))
        for mid, runner in (
            (ModuleID.M1, m1_planning.run), (ModuleID.M2, m2_design.run),
            (ModuleID.M3, m3_modeling.run), (ModuleID.M4, m4_simulation.run),
            (ModuleID.M5, m5_diagnosis.run), (ModuleID.M6, m6_analysis.run),
        ):
            self.core.register_module(mid, runner)


class TestSecondBatchContract(unittest.TestCase):
    def test_m4_status_comes_from_created_not_inference(self):
        core = CoreDispatcher(ArtifactStore(tempfile.mkdtemp()))
        core.register_module(ModuleID.M4, m4_simulation.run)
        env, errs = core.dispatch(DispatchRequest("R", ModuleID.M4, payload={"case_id": "C01"}))
        self.assertEqual(errs, [])
        self.assertEqual(env.output["structured"]["task_state"], "CREATED")
        self.assertFalse(env.output["verified_by_execution"])

    def test_m5_inference_cannot_be_confirmed(self):
        finding = m5_diagnosis.Finding(
            layer="physical", description="可能是边界问题", basis="观察",
            evidence_refs=["agent_guess"], confidence="confirmed",
        )
        self.assertTrue(finding.validate())

    def test_m5_accepts_tool_backed_confirmed(self):
        finding = m5_diagnosis.Finding(
            layer="numerical", description="任务失败", basis="M4 工具状态",
            evidence_refs=["pfc-1234"], confidence="confirmed",
        )
        self.assertEqual(finding.validate(), [])

    def test_c12_quality_gate_blocks(self):
        gate = m6_analysis.quality_gate(0, 0, [])
        self.assertEqual(gate["status"], "FAIL")
        self.assertIn("no raw data files", gate["reasons"])

    def test_m6_blocks_conclusion_on_fail(self):
        core = CoreDispatcher(ArtifactStore(tempfile.mkdtemp()))
        core.register_module(ModuleID.M6, m6_analysis.run)
        env, errs = core.dispatch(DispatchRequest("R", ModuleID.M6, payload={}))
        self.assertEqual(errs, [])
        self.assertEqual(env.status["module_state"], ModuleState.BLOCKED.value)
        self.assertEqual(env.output["structured"]["quality_gate"]["status"], "FAIL")


class TestC08C16(IF0Base):
    def test_c08_checkpoint_uses_core_only(self):
        core = self.core
        env, _ = core.dispatch(DispatchRequest("R", ModuleID.M4, payload={
            "case_id": "C01",
            "checkpoints": [{"id": "CP1", "stage": "compaction"}],
        }))
        self.assertEqual(env.output["structured"]["checkpoints"][0]["action"], "core_decision_required")
        before = len(core.decision_items())
        core.request_decision(
            DecisionKey("R", "M4", "检查点继续", "cv1"), "继续？", ["继续", "停止"],
            env.module_task_id,
        )
        self.assertEqual(len(core.decision_items()), before + 1)

    def test_c09_same_item_not_presented_twice(self):
        core = self.core
        key = DecisionKey("R", "M4", "检查点继续", "cv1")
        _, p1, _ = core.decisions.request(key, "q", ["a"], "t1")
        _, p2, _ = core.decisions.request(key, "q", ["a"], "t2")
        self.assertTrue(p1)
        self.assertFalse(p2)

    def test_c10_iteration_keeps_parent(self):
        core = self.core
        _, _ = core.dispatch(DispatchRequest("R", ModuleID.M1, payload={
            "research_requirements": {
                "research_objective": "o", "independent_vars": ["v"], "dependent_vars": ["d"],
                "fact_vs_suggestion": [{"claim": "c", "origin": "user_provided"}],
            }
        }))
        parent = [k for k in core._module_tasks if k.startswith("M1")][0]
        result = core.iterate(
            ModuleID.M5, ModuleID.M3, "model", ["pfc-1"], "cv1", False, parent
        )
        self.assertEqual(result["parent_task_id"], parent)
        self.assertFalse(result["requires_new_user_approval"])

    def test_c11_assumption_change_needs_approval(self):
        core = self.core
        _, _ = core.dispatch(DispatchRequest("R", ModuleID.M1, payload={
            "research_requirements": {
                "research_objective": "o", "independent_vars": ["v"], "dependent_vars": ["d"],
                "fact_vs_suggestion": [{"claim": "c", "origin": "user_provided"}],
            }
        }))
        parent = [k for k in core._module_tasks if k.startswith("M1")][0]
        result = core.iterate(
            ModuleID.M6, ModuleID.M1, "result", ["pfc-2"], "cv2", True, parent
        )
        self.assertTrue(result["requires_new_user_approval"])

    def test_c13_evidence_type_constraint(self):
        ev = Evidence(EvidenceSource.AGENT_INFERRED, "x")
        self.assertEqual(ev.validate(), [])
        self.assertIn(EvidenceSource.AGENT_INFERRED, EvidenceSource.non_conclusive())

    def test_c14_raw_not_overwritten(self):
        store = self.core.store
        r1 = store.write("raw", "d.csv", "a", raw=True)
        r2 = store.write("raw", "d.csv", "b", raw=True)
        self.assertNotEqual(r1.version, r2.version)
        self.assertEqual(store.get(r1), "a")

    def test_c15_chain_completeness(self):
        from core import evidence_chain
        complete = evidence_chain("d", "a", "t", "e", "f")
        self.assertTrue(complete["complete"])
        incomplete = evidence_chain("d", "a", None, "e", "f")
        self.assertFalse(incomplete["complete"])
        self.assertEqual(incomplete["missing"], ["tool_task_id"])

    def test_c16_full_six_module_chain(self):
        core = self.core
        research = {
            "research_objective": "o", "independent_vars": ["v"], "dependent_vars": ["d"],
            "fact_vs_suggestion": [{"claim": "c", "origin": "user_provided"}],
        }
        e1, e1err = core.dispatch(DispatchRequest("R", ModuleID.M1, payload={"research_requirements": research}))
        self.assertEqual(e1err, [])
        e2, e2err = core.dispatch(DispatchRequest("R", ModuleID.M2, payload={
            "experiment_design": {
                "experiment_type": "单轴压缩",
                "parameter_schema": [{"name": "v", "unit": "mm", "values": [1, 2], "default": 1, "source": "M1", "confirmed": True}],
                "measurement_plan": [{"metric": m, "definition": "d"} for m in ["轴向应力", "轴向应变", "峰值强度", "弹性模量"]],
                "trace_to_vars": [{"m1_var": "v", "parameter": "v"}],
            }
        }))
        self.assertEqual(e2err, [])
        e3, e3err = core.dispatch(DispatchRequest("R", ModuleID.M3, payload={
            "model_config": {"dimension": "2D"}, "case": e2.output["structured"]["cases"][0]
        }))
        self.assertEqual(e3err, [])
        e4, e4err = core.dispatch(DispatchRequest("R", ModuleID.M4, payload={"case_id": "C00"}))
        self.assertEqual(e4err, [])
        e5, e5err = core.dispatch(DispatchRequest("R", ModuleID.M5))
        self.assertEqual(e5err, [])
        e6, e6err = core.dispatch(DispatchRequest("R", ModuleID.M6, payload={
            "raw_manifest": [{"id": "x"}], "processed_data": [{"id": "y"}],
            "measurement_plan": [{"metric": "峰值强度", "definition": "最大值"}],
            "results": [{"statement": "s", "evidence_ref": "raw-x", "confidence": "confirmed"}],
        }))
        self.assertEqual(e6err, [])
        self.assertEqual(
            [e1.status["module_state"], e2.status["module_state"], e3.status["module_state"],
             e6.status["module_state"]],
            ["WAITING_FOR_USER", "WAITING_FOR_USER", "COMPLETED", "COMPLETED"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
