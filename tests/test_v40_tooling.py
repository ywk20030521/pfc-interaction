"""4.0 tooling-layer acceptance (technical report section 8.3) — REAL PFC.

These tests require a live itasca-mcp bridge at localhost:9001 with a PFC2D or
PFC3D Console attached. They are skipped automatically when the bridge is
offline, so the offline suite stays green.

Run with bridge online:
    python -m unittest tests.test_v40_tooling -v

Each test produces a REAL tool_task_id from the bridge and verifies:
  - M3 generated .dat executes through Core I5 (PR-B3 tooling)
  - M4 records the real tool_task_id / task_state (PR-C1 tooling)
  - environment (2D/3D) is correctly detected from the live engine
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core import (  # noqa: E402
    ArtifactStore, ArtifactRef, DecisionKey, DispatchRequest,
    ModuleID, ModuleState, TaskState, V41CoreDispatcher,
)
from adapters.itasca_mcp import ItascaMcpAdapter, BridgeUnavailable  # noqa: E402
from modules import v40_modeling_full as m3  # noqa: E402
from modules import v40_runner_full as m4  # noqa: E402

RID = "V40-TOOL-01"
CV = "cv1"


def bridge_online() -> bool:
    try:
        ItascaMcpAdapter().health()
        return True
    except BridgeUnavailable:
        return False


@unittest.skipUnless(bridge_online(), "bridge offline: tooling layer requires live PFC")
class TestToolingLayer(unittest.TestCase):
    def setUp(self):
        self.adapter = ItascaMcpAdapter()
        health = self.adapter.health()
        self.version = health.get("version")
        self.mode = health.get("runtime_mode")
        self.core = V41CoreDispatcher(ArtifactStore(tempfile.mkdtemp()), executor=self.adapter)
        self.core.register_module(ModuleID.M3, m3.run)
        self.core.register_module(ModuleID.M4, m4.run)
        self.authorization_id = None
        for stage, topic in (("M1", "confirm_research_plan"),
                             ("M2", "confirm_experiment_design"),
                             ("M3", "confirm_model_parameters"),
                             ("M4", "authorize_execution"),
                             ("M4", "confirm_stage_results"),
                             ("M5", "confirm_diagnosis")):
            item, _, _ = self.core.request_decision(
                DecisionKey(RID, stage, topic, CV), "q", ["确认"], "t",
                channel="NATIVE_CHAT")
            result = self.core.resolve_decision(item["decision_id"], "APPROVED", CV,
                                       answers={"confirm": True}, channel="NATIVE_CHAT")
            if topic == "authorize_execution":
                self.authorization_id = result["authorization_id"]
        self.assertTrue(self.authorization_id)

    def _authorize(self):
        return self.authorization_id

    def test_bridge_health(self):
        self.assertIn(self.mode, ("console", "gui"))
        print("\n[BRIDGE] version=%s mode=%s" % (self.version, self.mode))

    def test_m3_script_executes_on_real_pfc(self):
        """PR-B3: M3 generated script runs through Core I5 with real task id."""
        ok = {
            "sample_preparation": {"overlap_rate": 0, "out_of_bounds": 0, "wall_gap_m": 0.0001},
            "initial_equilibrium": {"unbalanced_force_ratio": 0.001, "timestep_s": 1e-6},
            "compaction_servo": {"unbalanced_force_ratio": 0.001, "overlap_rate": 0, "wall_gap_m": 0.0001},
            "bonding": {"bonded_after_bonding": 100, "bond_retention": 0.9},
            "re_equilibrium": {"unbalanced_force_ratio": 0.001, "timestep_s": 1e-6},
            "confinement_stabilization": {"confining_measured_Pa": 1e6,
                "confining_target_Pa": 1e6, "confinement_ratio": 1.0,
                "bonded_after_bonding": 100, "bonded_at_load": 90},
            "axial_loading": {"peak_is_last": False, "samples_after_peak": 5},
            "data_acquisition": {"peak_is_last": False, "samples_after_peak": 5},
        }
        env, errs = self.core.dispatch(DispatchRequest(RID, ModuleID.M3, payload={
            "experiment_type": "三轴压缩", "case_id": "TOOL-C1",
            "dimension": "2D" if self._is_2d() else "3D",
            "stage_checks": ok}))
        self.assertEqual(env.status["module_state"], ModuleState.COMPLETED.value, errs)
        self.assertTrue(env.output["structured"]["physics_gate"]["can_load"])
        # Take the sample-preparation script and run it for real.
        script_ref = next(a for a in env.output["artifacts"]
                          if a["artifact_id"] == "m3_dat_sample_preparation")
        script = self.core.store.get(ArtifactRef.from_dict(script_ref))
        auth_id = self._authorize()
        result, errors = self.core.execute(
            module_task_id=env.module_task_id, operation="execute_dat",
            model_ref=None, case_id="TOOL-C1", authorization_id=auth_id,
            scope="run_model", context_version=CV, code=script)
        self.assertFalse(errors, errors)
        self.assertTrue(result.tool_task_id)
        self.assertFalse(result.tool_task_id.startswith("unknown"))
        self.assertEqual(result.task_state, TaskState.COMPLETED,
                         msg=str(result.error))
        print("\n[PR-B3] tool_task_id=%s state=%s" % (
            result.tool_task_id, result.task_state.value))

    def test_m4_records_real_tool_task_id(self):
        """PR-C1: M4 binds a real tool_task_id, never a fabricated one."""
        m3doc = self.core.store.write_json("m3_staged_model", "staged.json",
            {"physics_gate": {"can_load": True}})
        auth_id = self._authorize()
        extent = "-2 2 -2 2" if self._is_2d() else "-2 2 -2 2 -2 2"
        code = "model new\nmodel large-strain on\nmodel domain extent %s\nmodel cycle 10\n" % extent
        env, errs = self.core.dispatch(DispatchRequest(RID, ModuleID.M4,
            input_refs=[ArtifactRef.from_dict(m3doc.to_dict())],
            payload={"case_id": "TOOL-C2", "code": code,
                     "authorization_id": auth_id}))
        self.assertEqual(errs, [])
        self.assertEqual(env.status["module_state"], ModuleState.COMPLETED.value)
        tid = env.output["structured"]["tool_task_id"]
        self.assertTrue(tid)
        self.assertFalse(tid.startswith("unknown"))
        self.assertEqual(env.output["structured"]["task_state"], "COMPLETED")
        chain = self.core.chain(env.module_task_id)
        self.assertTrue(chain["complete"])
        print("\n[PR-C1] tool_task_id=%s chain=%s" % (tid, chain))

    def _is_2d(self) -> bool:
        """Detect dimension by trying a 2D-only command (domain extent 4 args).

        PFC2D accepts `model domain extent xlo xhi ylo yhi`; PFC3D requires 6
        tokens. A failed 4-token command therefore means 3D. This avoids the
        vec2/vec3 constructor differences across PFC versions.
        """
        try:
            code = (
                "import itasca\n"
                "itasca.command('model new')\n"
                "itasca.command('model domain extent -2 2 -2 2')\n"
                "print('DIM_PROBE_OK')\n"
            )
            r = self.adapter.execute_code(code)
            out = r.output_artifacts[0]["output"] if r.output_artifacts else ""
            return "DIM_PROBE_OK" in out
        except Exception:
            return False


if __name__ == "__main__":
    unittest.main(verbosity=2)
