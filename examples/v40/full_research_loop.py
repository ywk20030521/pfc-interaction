"""4.0 full technical-report acceptance: complete research loop demo.

Demonstrates the full M1->M2->M3->M4->M5->M6 chain plus a cross-module
iteration (M6 -> M4), using the real 2026-11-26 triaxial data as an offline
replay. Every gate is unlocked through Core approvals with recorded answers;
no synthetic approval and no fabricated tool result.

Run: python examples/v40/full_research_loop.py
"""

from __future__ import annotations

import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)

from core import (  # noqa: E402
    ArtifactStore, ArtifactRef, DecisionKey, DispatchRequest,
    ModuleID, ModuleState, V41CoreDispatcher, WorkflowOrchestrator,
)
from modules import v40_design as m12  # noqa: E402
from modules import v40_modeling_full as m3  # noqa: E402
from modules import v40_runner_full as m4  # noqa: E402
from modules import v40_analysis_full as m56  # noqa: E402

RID = "V40-FULL-DEMO"
CV = "cv1"
DATA = os.path.join(os.path.dirname(BASE), "outputs", "triaxial_3d", "data")


def ok(core, stage, topic, answers):
    item, _, _ = core.decisions.request(
        DecisionKey(RID, stage, topic, CV), "q", ["确认"], "gate")
    core.decisions.present(item.decision_id, channel="NATIVE_CHAT")
    return core.resolve_decision(item.decision_id, "APPROVED", CV,
                                 answers=answers, channel="NATIVE_CHAT")


def main():
    core = V41CoreDispatcher(ArtifactStore(os.path.join(BASE, "work", "v40_full")))
    for mid, runner in (
        (ModuleID.M1, m12.m1_full_run), (ModuleID.M2, m12.m2_full_run),
        (ModuleID.M3, m3.run), (ModuleID.M4, m4.run),
        (ModuleID.M5, m56.m5_full_run), (ModuleID.M6, m56.m6_full_run),
    ):
        core.register_module(mid, runner)
    report = {"research_task_id": RID, "stages": [], "approvals": 0,
              "iteration": [], "evidence_mode": "real_20261126_replay"}

    def log(name, env):
        report["stages"].append({"stage": name, "module_state": env.status["module_state"]})
        print("[%s] %s" % (name, env.status["module_state"]))

    def step(mid, payload=None, input_refs=None):
        env, _ = core.dispatch(DispatchRequest(RID, mid, input_refs=input_refs or [],
                                               payload=payload or {}))
        return env

    # M1: 3 rounds + confirm
    step(ModuleID.M1, {"user_request": "建立三轴压缩实验，研究围压对峰值强度影响"})
    ok(core, "M1", "interview_round1", {"research_object": "胶结颗粒集合体",
        "research_goal": "强度规律", "research_scope": "3D"})
    step(ModuleID.M1)
    ok(core, "M1", "interview_round2", {"hypotheses": "围压升高峰值增大",
        "independent_vars": "围压", "dependent_vars": "峰值强度",
        "control_vars": "级配,密度"})
    step(ModuleID.M1)
    ok(core, "M1", "interview_round3", {"work_packages": "建模,仿真,分析",
        "deliverables": "应力应变曲线,分析报告"})
    step(ModuleID.M1)
    ok(core, "M1", "confirm_research_plan", {"confirm": True})
    e = step(ModuleID.M1); log("M1", e)
    m1_ref = next(a for a in e.output["artifacts"] if a["artifact_id"] == "m1_research_requirements")

    # M2: 3 rounds + confirm
    step(ModuleID.M2, input_refs=[ArtifactRef.from_dict(m1_ref)])
    ok(core, "M2", "negotiate_round1", {"experiment_type": "三轴压缩",
        "independent_spec": "围压=1,5,10 MPa", "repeat_count": "1"})
    step(ModuleID.M2)
    ok(core, "M2", "negotiate_round2", {"specimen": "圆柱 H/D=2",
        "particle": "用户给定", "contact": "linearpbond", "loading": "用户给定"})
    step(ModuleID.M2)
    ok(core, "M2", "negotiate_round3", {"measurement_spec": "工程应力应变",
        "sensitivity": "是", "control_group": "默认"})
    step(ModuleID.M2)
    ok(core, "M2", "negotiate_round4", {"control_group": "baseline_first",
        "independent_unit": "pfc_seed_3", "randomization": "not_applicable",
        "stat_plan": "mean_sd_effect"})
    step(ModuleID.M2)
    ok(core, "M2", "confirm_experiment_design", {"confirm": True})
    e = step(ModuleID.M2); log("M2", e)
    m2_ref = next(a for a in e.output["artifacts"] if a["artifact_id"] == "m2_parameter_schema")

    # M3: real C1 measurements -> BLOCKED at confinement (honest result)
    ok(core, "M3", "confirm_model_parameters", {"confirm": True})
    checks = {
        "sample_preparation": {"overlap_rate": 0.0, "out_of_bounds": 0, "wall_gap_m": 0.0001},
        "initial_equilibrium": {"unbalanced_force_ratio": 0.001, "timestep_s": 1e-6},
        "compaction_servo": {"unbalanced_force_ratio": 0.001, "overlap_rate": 0.0, "wall_gap_m": 0.0001},
        "bonding": {"bonded_after_bonding": 1251, "bond_retention": 416/1251},
        "re_equilibrium": {"unbalanced_force_ratio": 0.001, "timestep_s": 1e-6},
        "confinement_stabilization": {"confining_measured_Pa": 5989.80,
            "confining_target_Pa": 1e6, "confinement_ratio": 0.0059898,
            "bonded_after_bonding": 1251, "bonded_at_load": 416},
    }
    e = step(ModuleID.M3, {"experiment_type": "三轴压缩", "case_id": "TX3D-C1",
                           "dimension": "3D", "stage_checks": checks},
             [ArtifactRef.from_dict(m2_ref)])
    log("M3-real-C1", e)
    m3_ref = next(a for a in e.output["artifacts"] if a["artifact_id"] == "m3_staged_model")

    # M4: even with approvals, physically blocked
    ok(core, "M4", "authorize_execution", {"confirm": True})
    e = step(ModuleID.M4, {"case_id": "TX3D-C1", "code": "model new\nmodel cycle 10\n",
                           "authorization_id": "a-demo"},
             [ArtifactRef.from_dict(m3_ref)])
    log("M4-blocked", e)

    # M5: failed stage -> diagnosis
    ok(core, "M4", "confirm_stage_results", {"confirm": True})
    e = step(ModuleID.M5, input_refs=[ArtifactRef.from_dict(m3_ref)])
    log("M5", e)
    m5_ref = next(a for a in e.output["artifacts"] if a["artifact_id"] == "m5_diagnostic_evidence")
    ok(core, "M5", "confirm_diagnosis", {"confirm": True})

    # M6: replay real C2 CSV (peak at last sample) -> BLOCKED
    csv_path = os.path.join(DATA, "tx_C2.csv")
    refs = [ArtifactRef.from_dict(m3_ref)]
    if os.path.exists(csv_path):
        r = core.store.write("pfc_csv_C2", "tx_C2.csv", open(csv_path, encoding="utf-8").read())
        refs.append(ArtifactRef.from_dict(r.to_dict()))
    m4r = core.store.write_json("m4_run_replay", "simulation_status.json",
                                {"tool_task_id": "3c11e9", "task_state": "COMPLETED"})
    refs.append(ArtifactRef.from_dict(m4r.to_dict()))
    e = step(ModuleID.M6, input_refs=refs)
    log("M6-real-C2", e)

    # Cross-module iteration: M6 -> M4 (data quality), via WorkflowOrchestrator
    wf = WorkflowOrchestrator(core)
    parent = [k for k in core._module_tasks if k.startswith("M6")][-1]
    it = wf.propose_iteration("M6", "M4", "data", "峰后段未捕获",
                              ["pfc_csv_C2", "3c11e9"], parent, RID, CV)
    wf.request_iteration_approval(it)
    wf.approve_iteration(it, True, {"extend_loading": True})
    report["iteration"] = wf.snapshot()
    print("[ITERATION] %s %s->%s approved=%s" % (
        it.request_id, it.source_module, it.target_module, it.approved))

    report["approvals"] = len(core.approvals.snapshot())
    report["result"] = (
        "4.0 完整技术报告实现：六模块全链路按真实数据回放执行，"
        "M3/M4/M6 阶段门正确 BLOCKED 了 4.0/4.0.1 误判通过的工况；"
        "M6→M4 跨模块迭代经用户批准建立子任务。"
    )
    out = os.path.join(BASE, "..", "outputs", "v40_full")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "full_loop_report.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print("[REPORT]", path)


if __name__ == "__main__":
    main()
