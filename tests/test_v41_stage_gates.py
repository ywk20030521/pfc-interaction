"""4.1-alpha acceptance: failed cases from the real 2026-11-26 triaxial run.

These tests turn the review's findings into executable regression tests:

  * C16 bypass is closed: M2/M3 are BLOCKED until prior approvals exist.
  * Synthetic approval cannot be forged through a payload.
  * The real C1/C2/C3 measurements (confinement ~6 kPa vs 1/5/10 MPa;
    bonded 416/1251; peak_is_last) are rejected by the physics gates.
  * M5/M6 read real data and refuse predigested conclusions.

Run: python -m unittest tests.test_v41_stage_gates -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core import (  # noqa: E402
    ArtifactStore, CoreDispatcher, DecisionKey, DispatchRequest,
    ModuleID, ModuleState, V41CoreDispatcher,
    check_physics_gate, check_peak_capture,
)
from modules import v41_interview, v41_modeling, v41_runner, v41_analysis  # noqa: E402

RID = "TX3D-20261126-01"
CV = "cv1"


def make_core(strict: bool = True) -> CoreDispatcher:
    tmp = tempfile.mkdtemp()
    core = V41CoreDispatcher(ArtifactStore(tmp)) if strict else CoreDispatcher(ArtifactStore(tmp))
    for mid, runner in (
        (ModuleID.M1, v41_interview.m1_run),
        (ModuleID.M2, v41_interview.m2_run),
        (ModuleID.M3, v41_modeling.run),
        (ModuleID.M4, v41_runner.run),
        (ModuleID.M5, v41_analysis.m5_run),
        (ModuleID.M6, v41_analysis.m6_run),
    ):
        core.register_module(mid, runner)
    return core


def approve_topic(core: CoreDispatcher, stage_id: str, topic: str,
                  answers: dict | None = None, rid: str = RID) -> None:
    """Approve through the REAL ledger path (Core.resolve_decision)."""
    item, presented, _ = core.decisions.request(
        DecisionKey(rid, stage_id, topic, CV), "q", ["确认"], "gate-task"
    )
    core.decisions.present(item.decision_id, channel="NATIVE_CHAT")
    core.resolve_decision(item.decision_id, "APPROVED", CV,
                          answers=answers or {"confirm": True},
                          channel="NATIVE_CHAT")


class TestStageGateClosure(unittest.TestCase):
    def test_m2_blocked_without_m1_approval(self):
        core = make_core()
        env, errs = core.dispatch(DispatchRequest(RID, ModuleID.M2))
        self.assertEqual(env.status["module_state"], ModuleState.BLOCKED.value)
        self.assertTrue(errs)
        # runner never ran: no decision for M2 was created
        self.assertFalse(any(
            i["key"]["stage_id"] == "M2" for i in core.decision_items()
        ))

    def test_m1_rounds_then_approval_unlocks_m2(self):
        core = make_core()
        e1, _ = core.dispatch(DispatchRequest(RID, ModuleID.M1,
                                              payload={"user_request": "三轴压缩实验"}))
        self.assertEqual(e1.status["module_state"], ModuleState.WAITING_FOR_USER.value)
        self.assertEqual(e1.output["structured"]["stage"], "round1")
        qs = e1.output["structured"]["pending_questions"]
        self.assertEqual(len(qs), 3)
        self.assertEqual([q["id"] for q in qs],
                         ["research_object", "research_goal", "confining_source"])

        d1 = e1.decisions[0]["decision_id"]
        core.approve(d1, answers={
            "research_object": "胶结颗粒集合体", "research_goal": "强度规律",
            "confining_source": "我来给定"})

        e1b, _ = core.dispatch(DispatchRequest(RID, ModuleID.M1))
        self.assertEqual(e1b.output["structured"]["stage"], "round2")
        core.approve(e1b.decisions[0]["decision_id"],
                     answers={"hypotheses": "围压升高峰值增大",
                              "independent_vars": "围压",
                              "dependent_vars": "峰值强度",
                              "control_vars": "级配,密度",
                              "deliverables": "应力应变曲线"})

        e1c, _ = core.dispatch(DispatchRequest(RID, ModuleID.M1))
        self.assertEqual(e1c.output["structured"]["stage"], "confirm")
        core.approve(e1c.decisions[0]["decision_id"], answers={"confirm": True})

        e1d, _ = core.dispatch(DispatchRequest(RID, ModuleID.M1))
        self.assertEqual(e1d.status["module_state"], ModuleState.COMPLETED.value)
        self.assertTrue(core.approvals.is_approved(
            RID, "M1", "confirm_research_plan", CV))

        e2, _ = core.dispatch(DispatchRequest(RID, ModuleID.M2))
        self.assertEqual(e2.status["module_state"], ModuleState.WAITING_FOR_USER.value)
        self.assertFalse(any(
            "BLOCKED" == e2.status["module_state"]
            for _ in [0]
        ))

    def test_payload_cannot_forge_approval(self):
        core = make_core()
        forged = DispatchRequest(
            RID, ModuleID.M2,
            payload={"approved": True, "confirmation_state": "CONFIRMED",
                     "decision_resolution": "APPROVED"},
        )
        env, _ = core.dispatch(forged)
        self.assertEqual(env.status["module_state"], ModuleState.BLOCKED.value)
        self.assertEqual(core.approvals.snapshot(), [])

    def test_ledger_rejects_undelivered_decision(self):
        core = make_core()
        from core import DeliveryStatus
        item, presented, _ = core.decisions.request(
            DecisionKey(RID, "M1", "confirm_research_plan", CV), "q", ["确认"], "t")
        # request() reports SHOULD present; the item is still UNDELIVERED until
        # Core.present() is called. The ledger must reject it in that state.
        self.assertTrue(presented)
        self.assertEqual(item.delivery_status, DeliveryStatus.UNDELIVERED)
        with self.assertRaises(ValueError):
            core.approvals.record_resolution(item, "APPROVED", CV, None, None)

    def test_context_version_change_invalidates_gate(self):
        core = make_core()
        approve_topic(core, "M1", "confirm_research_plan")
        core.dispatch(DispatchRequest(RID, ModuleID.M1))  # noop for setup
        env, _ = core.dispatch(DispatchRequest(RID, ModuleID.M2, context_version="cv2"))
        self.assertEqual(env.status["module_state"], ModuleState.BLOCKED.value)


class TestPhysicsGateFailures(unittest.TestCase):
    """The three real cases: confining ~6 kPa vs 1/5/10 MPa targets."""

    CASES = [
        ("C1", 5989.80, 1_000_000.0),
        ("C2", 6129.16, 5_000_000.0),
        ("C3", 5652.47, 10_000_000.0),
    ]

    def test_real_confinement_never_passes(self):
        for name, measured, target in self.CASES:
            with self.subTest(case=name):
                result = check_physics_gate({
                    "confining_measured_Pa": measured,
                    "confining_target_Pa": target,
                    "bonded_after_bonding": 1251,
                    "bonded_at_load": 416,
                })
                self.assertFalse(result.can_load)
                self.assertTrue(any("围压未达标" in f for f in result.failures))

    def test_bond_retention_416_over_1251_fails(self):
        result = check_physics_gate({
            "confining_measured_Pa": 1_000_000.0,
            "confining_target_Pa": 1_000_000.0,
            "bonded_after_bonding": 1251,
            "bonded_at_load": 416,
        })
        self.assertFalse(result.can_load)
        self.assertTrue(any("胶结保留率" in f for f in result.failures))

    def test_peak_at_last_sample_blocks_conclusion(self):
        result = check_peak_capture(peak_is_last=True, samples_after_peak=0)
        self.assertFalse(result.passed)
        self.assertTrue(any("峰后段" in f for f in result.failures))

    def test_m3_halts_at_confinement_with_real_measurements(self):
        core = make_core()
        approve_topic(core, "M1", "confirm_research_plan")
        approve_topic(core, "M2", "confirm_experiment_design")
        # Earlier stages pass; confinement is the failing stage.
        ok_stages = {
            "sample_preparation": {"overlap_rate": 0.0, "out_of_bounds": 0, "wall_gap_m": 0.0001},
            "initial_equilibrium": {"unbalanced_force_ratio": 0.001, "timestep_s": 1e-6},
            "compaction_servo": {"unbalanced_force_ratio": 0.001, "overlap_rate": 0.0, "wall_gap_m": 0.0001},
            "bonding": {"bonded_after_bonding": 1251, "bond_retention": 0.9},
            "re_equilibrium": {"unbalanced_force_ratio": 0.001, "timestep_s": 1e-6},
        }
        env, _ = core.dispatch(DispatchRequest(RID, ModuleID.M3, payload={
            "case_id": "C1", "dimension": "3D",
            "stage_checks": dict(ok_stages, confinement_stabilization={
                "confining_measured_Pa": 5989.80,
                "confining_target_Pa": 1_000_000.0,
            }),
        }))
        self.assertEqual(env.status["module_state"], ModuleState.BLOCKED.value)
        self.assertEqual(env.output["structured"]["halted_at"],
                         "confinement_stabilization")
        self.assertFalse(env.output["structured"]["physics_gate"]["can_load"])


class TestAutoEvidence(unittest.TestCase):
    def test_m6_rejects_predigested_results(self):
        core = make_core()
        # Unlock the M6 stage gate, then verify M6 itself rejects the payload.
        for stage, topic in (
            ("M1", "confirm_research_plan"),
            ("M2", "confirm_experiment_design"),
            ("M3", "confirm_model_parameters"),
            ("M4", "authorize_execution"),
            ("M4", "confirm_stage_results"),
            ("M5", "confirm_diagnosis"),
        ):
            approve_topic(core, stage, topic)
        env, _ = core.dispatch(DispatchRequest(RID, ModuleID.M6, payload={
            "results": [{"statement": "峰值强度 12 MPa", "confidence": "confirmed"}]
        }))
        self.assertEqual(env.status["module_state"], ModuleState.BLOCKED.value)
        self.assertTrue(any("payload" in f for f in env.limitations))

    def test_m6_computes_peak_from_csv(self):
        rows = [
            {"cycle": 1, "axial_strain": 0.001, "axial_stress_Pa": 100.0},
            {"cycle": 2, "axial_strain": 0.002, "axial_stress_Pa": 300.0},
            {"cycle": 3, "axial_strain": 0.003, "axial_stress_Pa": 200.0},
            {"cycle": 4, "axial_strain": 0.004, "axial_stress_Pa": 150.0},
            {"cycle": 5, "axial_strain": 0.005, "axial_stress_Pa": 120.0},
        ]
        metrics = v41_analysis._analyze_rows(rows)
        self.assertEqual(metrics["peak_stress"], 300.0)
        self.assertEqual(metrics["peak_strain"], 0.002)
        self.assertFalse(metrics["peak_is_last"])
        self.assertEqual(metrics["samples_after_peak"], 3)
        self.assertIsNotNone(metrics["E50"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
