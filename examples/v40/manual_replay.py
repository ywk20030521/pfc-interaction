"""4.0 manual walkthrough: replay operator answers across M1-M6.

Reads outputs/v40_full/manual_answers.json. Each run replays all recorded
answers through a fresh strict dispatcher, then prints the NEXT question that
needs an operator answer. Fill that answer into the JSON and run again.

This keeps a single source of truth for the manual walkthrough despite each
CLI run being stateless (decisions live in memory, artifacts on disk).

Run: python examples/v40/manual_replay.py
"""

from __future__ import annotations

import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)

from core import (  # noqa: E402
    ArtifactStore, ArtifactRef, DecisionKey, DispatchRequest,
    ModuleID, V41CoreDispatcher,
)
from modules import v40_design as m12  # noqa: E402
from modules import v40_modeling_full as m3  # noqa: E402
from modules import v40_runner_full as m4  # noqa: E402
from modules import v40_analysis_full as m56  # noqa: E402

RID = "WALK-4.0-MANUAL"
CV = "cv1"
ANS = os.path.join(BASE, "..", "outputs", "v40_full", "manual_answers.json")


def load_answers():
    if os.path.exists(ANS):
        with open(ANS, encoding="utf-8") as f:
            return json.load(f)
    return {}


def main():
    answers = load_answers()
    core = V41CoreDispatcher(ArtifactStore(os.path.join(BASE, "work", "walk_manual")))
    for mid, runner in (
        (ModuleID.M1, m12.m1_full_run), (ModuleID.M2, m12.m2_full_run),
        (ModuleID.M3, m3.run), (ModuleID.M4, m4.run),
        (ModuleID.M5, m56.m5_full_run), (ModuleID.M6, m56.m6_full_run),
    ):
        core.register_module(mid, runner)

    def approve(stage, topic, ans=None):
        item, _, _ = core.request_decision(
            DecisionKey(RID, stage, topic, CV), "q", ["确认"], "gate")
        return core.resolve_decision(item["decision_id"], "APPROVED", CV,
                                     answers=ans or {"confirm": True})

    def dispatch(mid, payload=None, input_refs=None):
        return core.dispatch(DispatchRequest(RID, mid, input_refs=input_refs or [],
                                             payload=payload or {}))

    def need(key, stage, topic):
        """Return answers if recorded, else print pending question and exit."""
        if key in answers:
            return answers[key]
        env, _ = dispatch(ModuleID(stage),
                          {"user_request": "研究围压对岩石三轴峰值强度的影响"}
                          if stage == "M1" else None)
        qs = env.output["structured"].get("pending_questions", [])
        print("\n>>> NEXT QUESTION [%s/%s]:" % (stage, topic))
        if qs:
            for q in qs:
                print("  - %s: %s (选项: %s)" % (
                    q.get("id"), q.get("question"), ", ".join(q.get("options", []))))
        else:
            print("  - 请回答: %s" % env.output["structured"].get("stage", "confirm"))
        print("\n请把它写入 %s 的 \"%s\" 键后重跑。" % (ANS, key))
        return None

    m1 = answers.get("m1", {})
    # M1 rounds
    if "interview_round1" not in m1:
        env, _ = dispatch(ModuleID.M1, {"user_request": "研究围压对岩石三轴峰值强度的影响"})
        qs = env.output["structured"].get("pending_questions", [])
        print("\n>>> M1 第一轮问题（请回答后写入 manual_answers.json 的 m1.interview_round1）:")
        for q in qs:
            print("  - %s: %s [%s]" % (q.get("id"), q.get("question"),
                                       ", ".join(q.get("options", []))))
        return
    approve("M1", "interview_round1", m1["interview_round1"])
    if "interview_round2" not in m1:
        env, _ = dispatch(ModuleID.M1)
        qs = env.output["structured"].get("pending_questions", [])
        print("\n>>> M1 第二轮问题（写入 m1.interview_round2）:")
        for q in qs:
            print("  - %s: %s [%s]" % (q.get("id"), q.get("question"),
                                       ", ".join(q.get("options", []))))
        return
    approve("M1", "interview_round2", m1["interview_round2"])
    if "interview_round3" not in m1:
        env, _ = dispatch(ModuleID.M1)
        qs = env.output["structured"].get("pending_questions", [])
        print("\n>>> M1 第三轮问题（写入 m1.interview_round3）:")
        for q in qs:
            print("  - %s: %s [%s]" % (q.get("id"), q.get("question"),
                                       ", ".join(q.get("options", []))))
        return
    approve("M1", "interview_round3", m1["interview_round3"])
    approve("M1", "confirm_research_plan", m1.get("confirm", {"confirm": True}))
    e1, _ = dispatch(ModuleID.M1)
    print("[M1]", e1.status["module_state"], "artifacts", len(e1.output["artifacts"]))
    m1_ref = next(a for a in e1.output["artifacts"]
                  if a["artifact_id"] == "m1_research_requirements")

    # M2 rounds
    m2 = answers.get("m2", {})
    dispatch(ModuleID.M2, input_refs=[ArtifactRef.from_dict(m1_ref)])
    for idx in (1, 2, 3, 4):
        key = "negotiate_round%d" % idx
        if key not in m2:
            # M2 questions live in the decision's question_set, not structured.
            items = core.decision_items()
            qs = []
            for it in reversed(items):
                if (it["key"]["stage_id"] == "M2" and
                        it["key"]["topic"] == key and it.get("question_set")):
                    qs = it["question_set"]
                    break
            print("\n>>> M2 第%d轮问题（写入 m2.%s）:" % (idx, key))
            for q in qs:
                print("  - %s: %s [%s]" % (q.get("id"), q.get("question"),
                                           ", ".join(q.get("options", []))))
            if not qs:
                print("  - (问题集未找到，检查 decision topic=%s)" % key)
            return
        approve("M2", key, m2[key])
        dispatch(ModuleID.M2)
    approve("M2", "confirm_experiment_design", m2.get("confirm", {"confirm": True}))
    e2, _ = dispatch(ModuleID.M2)
    print("[M2]", e2.status["module_state"], "artifacts", len(e2.output["artifacts"]))
    m2_ref = next(a for a in e2.output["artifacts"]
                  if a["artifact_id"] == "m2_parameter_schema")

    # M3-M6 with fixed real measurements (no further operator Q needed)
    approve("M3", "confirm_model_parameters")
    checks = {
        "sample_preparation": {"overlap_rate": 0.0, "out_of_bounds": 0, "wall_gap_m": 0.0001},
        "initial_equilibrium": {"unbalanced_force_ratio": 0.001, "timestep_s": 1e-6},
        "compaction_servo": {"unbalanced_force_ratio": 0.001, "overlap_rate": 0.0, "wall_gap_m": 0.0001},
        "bonding": {"bonded_after_bonding": 1251, "bond_retention": 0.4764},
        "re_equilibrium": {"unbalanced_force_ratio": 0.001, "timestep_s": 1e-6},
        "confinement_stabilization": {"confining_measured_Pa": 1007481.0,
            "confining_target_Pa": 1e6, "confinement_ratio": 1.0075,
            "bonded_after_bonding": 1251, "bonded_at_load": 596},
        "axial_loading": {"peak_is_last": False, "samples_after_peak": 14},
        "data_acquisition": {"peak_is_last": False, "samples_after_peak": 14},
    }
    e3, _ = dispatch(ModuleID.M3, {"experiment_type": "三轴压缩", "case_id": "C1",
        "dimension": "3D", "stage_checks": checks},
        [ArtifactRef.from_dict(m2_ref)])
    print("[M3]", e3.status["module_state"])
    m3_ref = next(a for a in e3.output["artifacts"] if a["artifact_id"] == "m3_staged_model")
    approve("M4", "authorize_execution")
    e4, _ = dispatch(ModuleID.M4, {"case_id": "C1", "code": "model new\n",
        "authorization_id": "a-manual"}, [ArtifactRef.from_dict(m3_ref)])
    print("[M4]", e4.status["module_state"])
    approve("M4", "confirm_stage_results")
    e5, _ = dispatch(ModuleID.M5, input_refs=[ArtifactRef.from_dict(m3_ref)])
    print("[M5]", e5.status["module_state"], "findings",
          len(e5.output["structured"]["findings"]))
    approve("M5", "confirm_diagnosis")
    refs = [ArtifactRef.from_dict(m3_ref)]
    csv_path = os.path.join(BASE, "..", "outputs", "triaxial_3d", "v40_science",
                            "data", "tx_science_1.csv")
    if os.path.exists(csv_path):
        r = core.store.write("pfc_csv_science", "tx.csv", open(csv_path, encoding="utf-8").read())
        refs.append(ArtifactRef.from_dict(r.to_dict()))
    m4r = core.store.write_json("m4_run_science", "s.json",
        {"tool_task_id": "task-b9ffb103", "task_state": "COMPLETED"})
    refs.append(ArtifactRef.from_dict(m4r.to_dict()))
    e6, _ = dispatch(ModuleID.M6, input_refs=refs)
    print("[M6]", e6.status["module_state"], "gate",
          e6.output["structured"]["quality_gate"]["status"])
    print("\n[MANUAL WALKTHROUGH COMPLETE] approvals:", len(core.approvals.snapshot()))


if __name__ == "__main__":
    main()
