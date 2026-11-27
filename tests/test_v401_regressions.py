"""Regression tests for the three defects fixed in v4.0.1.

Run: python tests/test_v401_regressions.py

Covers:
  R1 - FISH block execution via bridge-native splitter (needs live bridge)
  R2 - M6 invalid PFC evidence must block conclusions
  R3 - REJECTED decision semantics + same-context dedup
"""

import os
import sys
import tempfile
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core import (  # noqa: E402
    ArtifactStore, CoreDispatcher, DecisionKey, DecisionRegistry,
    DeliveryStatus, DispatchRequest, EvidenceSource, ModuleID,
)
from modules import m6_analysis  # noqa: E402


class TestR2InvalidEvidence(unittest.TestCase):
    """Defect 2: pfc-* without tool_task_id must be INVALID, not inference."""

    def setUp(self):
        self.core = CoreDispatcher(ArtifactStore(tempfile.mkdtemp()))
        self.core.register_module(ModuleID.M6, m6_analysis.run)
        self.base_payload = {
            "raw_manifest": [{"id": "x"}],
            "processed_data": [{"id": "y"}],
            "measurement_plan": [{"metric": "峰值强度", "definition": "max"}],
        }

    def test_invalid_pfc_evidence_blocks(self):
        payload = dict(self.base_payload)
        payload["results"] = [{
            "statement": "峰值强度=50MPa",
            "evidence_ref": "pfc-fake",
            "confidence": "confirmed",
        }]
        env, errors = self.core.dispatch(DispatchRequest("R", ModuleID.M6, payload=payload))
        self.assertEqual(errors, [])
        self.assertEqual(env.status["module_state"], "BLOCKED")
        self.assertEqual(env.output["structured"]["quality_gate"]["status"], "FAIL")
        self.assertEqual(
            env.output["structured"]["interpretation"][0]["confidence"], "hypothesis"
        )
        sources = [e.source for e in env.evidence]
        self.assertIn(EvidenceSource.INVALID_EVIDENCE, sources)
        self.assertNotIn(EvidenceSource.PFC_EXECUTED, sources)

    def test_valid_pfc_evidence_passes(self):
        payload = dict(self.base_payload)
        payload["results"] = [{
            "statement": "峰值强度=50MPa",
            "evidence_ref": "pfc-real",
            "tool_task_id": "pfc-1234",
            "confidence": "confirmed",
        }]
        env, errors = self.core.dispatch(DispatchRequest("R", ModuleID.M6, payload=payload))
        self.assertEqual(errors, [])
        self.assertEqual(env.status["module_state"], "COMPLETED")
        self.assertEqual(env.output["structured"]["quality_gate"]["status"], "PASS")
        self.assertEqual(
            env.output["structured"]["interpretation"][0]["confidence"], "confirmed"
        )


class TestR3RejectionSemantics(unittest.TestCase):
    """Defect 3: REJECTED keeps refusal semantics and same-context dedup."""

    def test_rejected_is_cancelled_with_resolution(self):
        reg = DecisionRegistry()
        key = DecisionKey("E", "M2", "确认参数", "cv1")
        item, presented, _ = reg.request(key, "q", ["a"], "t")
        self.assertTrue(presented)
        reg.present(item.decision_id)
        reg.resolve(item.decision_id, "REJECTED")
        snap = reg.snapshot(item.decision_id)
        self.assertEqual(snap["delivery_status"], DeliveryStatus.CANCELLED.value)
        self.assertEqual(snap["resolution"], "REJECTED")

    def test_rejected_not_represented_same_context(self):
        reg = DecisionRegistry()
        key = DecisionKey("E", "M2", "确认参数", "cv1")
        item, _, _ = reg.request(key, "q", ["a"], "t")
        reg.present(item.decision_id)
        reg.resolve(item.decision_id, "REJECTED")
        _, presented, _ = reg.request(key, "q", ["a"], "t")
        self.assertFalse(presented)

    def test_rejected_can_reopen_in_new_context(self):
        reg = DecisionRegistry()
        item, _, _ = reg.request(DecisionKey("E", "M2", "确认参数", "cv1"), "q", ["a"], "t")
        reg.present(item.decision_id)
        reg.resolve(item.decision_id, "REJECTED")
        _, presented, _ = reg.request(
            DecisionKey("E", "M2", "确认参数", "cv2"), "q", ["a"], "t"
        )
        self.assertTrue(presented)


class TestR1FishBlockNativeSplitter(unittest.TestCase):
    """Defect 1: FISH blocks must execute via bridge's preprocess_source."""

    def setUp(self):
        from adapters.itasca_mcp import ItascaMcpAdapter, BridgeUnavailable
        self.adapter = ItascaMcpAdapter(timeout=25)
        self.BridgeUnavailable = BridgeUnavailable

    def test_fish_block_executes_without_wedging_bridge(self):
        # Detect the attached engine: the same FISH splitter must work in 2D/3D.
        probe = self.adapter.execute_code(
            "import itasca\nitasca.command('model new')\n"
            "itasca.command('model domain extent -2 2 -2 2 -2 2')\n"
            "print('DIM3D_OK')\n")
        probe_out = (probe.output_artifacts[0].get("output", "")
                     if probe.output_artifacts else "")
        extent = "-2 2 -2 2 -2 2" if "DIM3D_OK" in probe_out else "-2 2 -2 2"
        position = "(0,0,0)" if "DIM3D_OK" in probe_out else "(0,0)"
        dat = """model new
model large-strain on
model domain extent %s
fish define regression_sum
  regression_sum = 6 + 7
end
ball create id=1 position=%s radius=0.5
ball attribute density 2500
model cycle 5
""" % (extent, position)
        try:
            result = self.adapter.execute_dat_script(dat)
        except self.BridgeUnavailable as exc:
            self.skipTest("bridge unavailable: %s" % exc)
        self.assertEqual(result.task_state.value, "COMPLETED")
        self.assertIsNone(result.error)
        self.assertTrue(self.adapter.health().get("status") == "success")


if __name__ == "__main__":
    unittest.main(verbosity=2)
