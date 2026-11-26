"""4.0 six-module interactive walkthrough — automatic pass.

Runs M1-M6 with real triaxial data, records per-module I/O, state, decisions,
artifacts and any bug. This is the AUTO pass (no human answers); a second
MANUAL pass follows with the operator.

Run: python examples/v40/interactive_walkthrough.py
Output: outputs/v40_full/walkthrough_auto.json
"""

from __future__ import annotations

import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)

from core import (  # noqa: E402
    ArtifactStore, ArtifactRef, DecisionKey, DispatchRequest,
    ModuleID, ModuleState, V41CoreDispatcher,
)
from modules import v40_design as m12  # noqa: E402
from modules import v40_modeling_full as m3  # noqa: E402
from modules import v40_runner_full as m4  # noqa: E402
from modules import v40_analysis_full as m56  # noqa: E402

RID = "WALK-4.0-AUTO"
CV = "cv1"
DATA = os.path.join(os.path.dirname(BASE), "outputs", "triaxial_3d", "v40_science", "data")


def main():
    core = V41CoreDispatcher(ArtifactStore(os.path.join(BASE, "work", "walk_auto")))
    for mid, runner in (
        (ModuleID.M1, m12.m1_full_run), (ModuleID.M2, m12.m2_full_run),
        (ModuleID.M3, m3.run), (ModuleID.M4, m4.run),
        (ModuleID.M5, m56.m5_full_run), (ModuleID.M6, m56.m6_full_run),
    ):
        core.register_module(mid, runner)

    report = {"mode": "auto", "research_task_id": RID, "modules": [], "bugs": []}

    def record(name, env, errs, note=""):
        entry = {
            "module": name,
            "module_state": env.status.get("module_state"),
            "errors": errs,
            "structured_keys": list(env.output["structured"].keys()),
            "artifacts": [a["artifact_id"] for a in env.output.get("artifacts", [])],
            "decisions": len(env.decisions),
            "limitations": env.limitations[:4],
            "note": note,
        }
        report["modules"].append(entry)
        print("[%s] %s | artifacts=%d | decisions=%d" % (
            name, entry["module_state"], len(entry["artifacts"]), entry["decisions"]))
        return env

    def approve(stage, topic, answers=None):
        item, _, _ = core.request_decision(
            DecisionKey(RID, stage, topic, CV), "q", ["确认"], "gate")
        return core.resolve_decision(item["decision_id"], "APPROVED", CV,
                                     answers=answers or {"confirm": True})

    def dispatch(mid, payload=None, input_refs=None):
        return core.dispatch(DispatchRequest(RID, mid, input_refs=input_refs or [],
                                             payload=payload or {}))

    # ---- M1: 3 rounds + confirm ----
    e, er = dispatch(ModuleID.M1, {"user_request": "研究围压对胶结颗粒三轴峰值强度的影响"})
    record("M1-round1", e, er, "检查首轮只问 3 个关键问题")
    approve("M1", "interview_round1", {"research_object": "胶结颗粒集合体",
        "research_goal": "强度规律", "research_scope": "PFC3D"})
    e, er = dispatch(ModuleID.M1); record("M1-round2", e, er)
    approve("M1", "interview_round2", {"hypotheses": "围压升高峰值增大",
        "independent_vars": "围压", "dependent_vars": "峰值强度", "control_vars": "级配,密度"})
    e, er = dispatch(ModuleID.M1); record("M1-round3", e, er)
    approve("M1", "interview_round3", {"work_packages": "建模,仿真,分析",
        "deliverables": "应力应变曲线,分析报告"})
    e, er = dispatch(ModuleID.M1); record("M1-confirm", e, er)
    approve("M1", "confirm_research_plan")
    e, er = dispatch(ModuleID.M1)
    m1 = record("M1-final", e, er, "5 标准输出应齐全")
    m1_ref = next(a for a in e.output["artifacts"] if a["artifact_id"] == "m1_research_requirements")
    if e.status["module_state"] != "COMPLETED":
        report["bugs"].append("M1: 未 COMPLETED")
    if len(e.output["artifacts"]) < 5:
        report["bugs"].append("M1: 标准输出不足 5 个")

    # ---- M2: 3 rounds + confirm ----
    dispatch(ModuleID.M2, input_refs=[ArtifactRef.from_dict(m1_ref)])
    approve("M2", "negotiate_round1", {"experiment_type": "三轴压缩",
        "independent_spec": "围压=1,5,10 MPa", "repeat_count": "1"})
    e, er = dispatch(ModuleID.M2); record("M2-round2", e, er)
    approve("M2", "negotiate_round2", {"specimen": "圆柱 H/D=2",
        "particle": "用户给定", "contact": "linearpbond", "loading": "用户给定"})
    e, er = dispatch(ModuleID.M2); record("M2-round3", e, er)
    approve("M2", "negotiate_round3", {"measurement_spec": "工程应力应变",
        "sensitivity": "是", "control_group": "默认"})
    e, er = dispatch(ModuleID.M2); record("M2-nature", e, er)
    approve("M2", "negotiate_round4", {"control_group": "baseline_first",
        "independent_unit": "pfc_seed_3", "randomization": "not_applicable",
        "stat_plan": "mean_sd_effect"})
    e, er = dispatch(ModuleID.M2); record("M2-confirm", e, er)
    approve("M2", "confirm_experiment_design")
    e, er = dispatch(ModuleID.M2)
    m2 = record("M2-final", e, er)
    m2_ref = next(a for a in e.output["artifacts"] if a["artifact_id"] == "m2_parameter_schema")
    design = e.output["structured"]["experiment_design"]
    if len(design.get("cases", [])) != 3:
        report["bugs"].append("M2: 工况矩阵应为 3 个，实为 %d" % len(design.get("cases", [])))
    if len(e.output["artifacts"]) < 5:
        report["bugs"].append("M2: 标准输出不足 5 个")

    # ---- M3: real science measurements -> gate ----
    approve("M3", "confirm_model_parameters")
    checks = {
        "sample_preparation": {"overlap_rate": 0.0, "out_of_bounds": 0, "wall_gap_m": 0.0001},
        "initial_equilibrium": {"unbalanced_force_ratio": 0.001, "timestep_s": 1e-6},
        "compaction_servo": {"unbalanced_force_ratio": 0.001, "overlap_rate": 0.0, "wall_gap_m": 0.0001},
        "bonding": {"bonded_after_bonding": 1251, "bond_retention": 0.4764},
        "re_equilibrium": {"unbalanced_force_ratio": 0.001, "timestep_s": 1e-6},
        "confinement_stabilization": {"confining_measured_Pa": 5989.8,
            "confining_target_Pa": 1e6, "confinement_ratio": 0.0059898,
            "bonded_after_bonding": 1251, "bonded_at_load": 596},
        "axial_loading": {"peak_is_last": False, "samples_after_peak": 14},
        "data_acquisition": {"peak_is_last": False, "samples_after_peak": 14},
    }
    e, er = dispatch(ModuleID.M3, {"experiment_type": "三轴压缩", "case_id": "C1",
        "dimension": "3D", "stage_checks": checks},
        [ArtifactRef.from_dict(m2_ref)])
    m3env = record("M3-real-C1", e, er, "真实旧数据应 BLOCKED")
    m3_ref = next(a for a in e.output["artifacts"] if a["artifact_id"] == "m3_staged_model")
    if e.status["module_state"] != "BLOCKED":
        report["bugs"].append("M3: 围压未达标却未 BLOCKED")

    # ---- M4: physics gate must refuse ----
    approve("M4", "authorize_execution")
    e, er = dispatch(ModuleID.M4, {"case_id": "C1", "code": "model new\n",
        "authorization_id": "a-auto"}, [ArtifactRef.from_dict(m3_ref)])
    m4env = record("M4-blocked", e, er, "物理准入失败应 BLOCKED")
    if e.output["structured"].get("tool_task_id") is not None:
        report["bugs"].append("M4: 物理失败却伪造了 tool_task_id")

    # ---- M5: diagnosis from failed stage ----
    approve("M4", "confirm_stage_results")
    e, er = dispatch(ModuleID.M5, input_refs=[ArtifactRef.from_dict(m3_ref)])
    m5 = record("M5-auto", e, er)
    if not e.output["structured"]["findings"]:
        report["bugs"].append("M5: 阶段失败却无诊断发现")

    # ---- M6: real science CSV (post-peak captured) ----
    approve("M5", "confirm_diagnosis")
    refs = [ArtifactRef.from_dict(m3_ref)]
    csv_path = os.path.join(DATA, "tx_science_1.csv")
    if os.path.exists(csv_path):
        r = core.store.write("pfc_csv_science", "tx_science_1.csv",
                             open(csv_path, encoding="utf-8").read())
        refs.append(ArtifactRef.from_dict(r.to_dict()))
    m4r = core.store.write_json("m4_run_science", "simulation_status.json",
        {"tool_task_id": "task-b9ffb103", "task_state": "COMPLETED"})
    refs.append(ArtifactRef.from_dict(m4r.to_dict()))
    e, er = dispatch(ModuleID.M6, input_refs=refs)
    m6 = record("M6-science", e, er, "真实科学数据：峰后已捕获，应可出结论")
    gate = e.output["structured"]["quality_gate"]
    print("[M6 GATE]", gate["status"], gate["reasons"][:2])
    if gate["status"] != "PASS":
        report["bugs"].append("M6: 科学数据质量闸门未通过: %s" % gate["reasons"][:2])

    report["approvals"] = len(core.approvals.snapshot())
    out = os.path.join(BASE, "..", "outputs", "v40_full", "walkthrough_auto.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print("[REPORT]", out)
    print("[BUGS]", len(report["bugs"]))
    for b in report["bugs"]:
        print("  -", b)


if __name__ == "__main__":
    main()
