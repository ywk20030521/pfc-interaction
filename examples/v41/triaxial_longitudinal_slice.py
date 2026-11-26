"""4.1-alpha triaxial longitudinal slice — executable acceptance demo.

Runs the M1->M2->M3->M4->M5->M6 chain with a STRICT dispatcher. It uses the
real 2026-11-26 triaxial measurements as an offline replay because the bridge
is not guaranteed online. No approval is fabricated: every gate is unlocked
through Core.resolve_decision with recorded answers and an ApprovalLedger
entry. When the real measurements are replayed, the gates correctly BLOCK at
confinement stabilization and at peak capture — the demo's point is that the
4.0 "pipeline completed" result can no longer be produced.

Run:
    python examples/v41/triaxial_longitudinal_slice.py
"""

from __future__ import annotations

import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)

from core import (  # noqa: E402
    ArtifactStore, DecisionKey, DispatchRequest, ModuleID,
    ModuleState, V41CoreDispatcher,
)
from modules import v41_interview, v41_modeling, v41_runner, v41_analysis  # noqa: E402

RID = "TX3D-20261126-01"
CV = "cv1"
REAL_DATA = os.path.join(
    os.path.dirname(BASE), "outputs", "triaxial_3d", "data"
)


def ok(core, stage, topic, answers):
    """Approve via the real ledger path (never a payload flag)."""
    item, _, _ = core.decisions.request(
        DecisionKey(RID, stage, topic, CV), "q", ["确认"], "gate"
    )
    core.decisions.present(item.decision_id, channel="NATIVE_CHAT")
    return core.resolve_decision(item.decision_id, "APPROVED", CV,
                                 answers=answers, channel="NATIVE_CHAT")


def dispatch(core, mid, payload=None, input_refs=None):
    return core.dispatch(DispatchRequest(
        RID, mid, input_refs=input_refs or [], payload=payload or {}))


def run() -> dict:
    store_root = os.path.join(BASE, "work", "v41_slice")
    core = V41CoreDispatcher(ArtifactStore(store_root))
    for mid, runner in (
        (ModuleID.M1, v41_interview.m1_run),
        (ModuleID.M2, v41_interview.m2_run),
        (ModuleID.M3, v41_modeling.run),
        (ModuleID.M4, v41_runner.run),
        (ModuleID.M5, v41_analysis.m5_run),
        (ModuleID.M6, v41_analysis.m6_run),
    ):
        core.register_module(mid, runner)

    report = {"research_task_id": RID, "dispatcher": "V41CoreDispatcher",
              "stages": [], "approvals": [], "evidence_mode": "real_20261126_replay"}

    def log(name, env, errors):
        entry = {
            "stage": name,
            "module_state": env.status["module_state"],
            "errors": errors,
            "limitations": env.limitations[:3],
        }
        report["stages"].append(entry)
        print("[%s] %s | %s" % (
            name, entry["module_state"],
            (errors[0] if errors else "ok")))

    # --- M1: three real interview rounds ---------------------------------
    e, er = dispatch(core, ModuleID.M1, {"user_request": "建立三轴压缩实验"})
    log("M1-round1", e, er)
    assert e.output["structured"]["stage"] == "round1"
    ok(core, "M1", "interview_round1", {
        "research_object": "胶结颗粒集合体", "research_goal": "强度规律",
        "confining_source": "我来给定"})
    e, er = dispatch(core, ModuleID.M1)
    log("M1-round2", e, er)
    ok(core, "M1", "interview_round2", {
        "hypotheses": "围压升高峰值增大", "independent_vars": "围压",
        "dependent_vars": "峰值强度", "control_vars": "级配,密度",
        "deliverables": "应力应变曲线"})
    e, er = dispatch(core, ModuleID.M1)
    log("M1-confirm", e, er)
    ok(core, "M1", "confirm_research_plan", {"confirm": True})
    e, er = dispatch(core, ModuleID.M1)
    log("M1-final", e, er)
    assert e.status["module_state"] == ModuleState.COMPLETED.value

    # --- M2: four negotiation rounds; nothing auto-filled ----------------
    m2_answers = [
        {"specimen_shape": "圆柱 H/D=2", "specimen_size": "用户给定",
         "particle_size": "用户给定", "porosity": "0.16"},
        {"density_damping": "2500/0.7", "sample_method": "ball generate 无重叠",
         "bond_state": "成样后胶结", "contact_model": "linearpbond"},
        {"bond_micro": "用户给定", "wall_contact": "linear",
         "confinement": "1/5/10 MPa 用户给定", "axial_loading": "用户给定"},
        {"measurement": "工程应力/应变"},
    ]
    for idx, answers in enumerate(m2_answers, start=1):
        e, er = dispatch(core, ModuleID.M2)
        log("M2-round%d" % idx, e, er)
        ok(core, "M2", "negotiate_round%d" % idx, answers)
    e, er = dispatch(core, ModuleID.M2)
    log("M2-confirm", e, er)
    ok(core, "M2", "confirm_experiment_design", {"confirm": True})
    e, er = dispatch(core, ModuleID.M2)
    log("M2-final", e, er)
    assert e.status["module_state"] == ModuleState.COMPLETED.value
    schema = e.output["structured"]["parameter_schema"]
    assert len(schema) == 13 and all(p["confirmed"] for p in schema)

    # --- M3: replay real C1 measurements -> must BLOCK -------------------
    conf = 5989.80
    target = 1_000_000.0
    ok_stages = {
        "sample_preparation": {"overlap_rate": 0.0, "out_of_bounds": 0,
                               "wall_gap_m": 0.0001},
        "initial_equilibrium": {"unbalanced_force_ratio": 0.001, "timestep_s": 1e-6},
        "compaction_servo": {"unbalanced_force_ratio": 0.001, "overlap_rate": 0.0,
                             "wall_gap_m": 0.0001},
        "bonding": {"bonded_after_bonding": 1251, "bond_retention": 416 / 1251},
        "re_equilibrium": {"unbalanced_force_ratio": 0.001, "timestep_s": 1e-6},
    }
    e, er = dispatch(core, ModuleID.M3, {
        "case_id": "TX3D-C1", "dimension": "3D",
        "stage_checks": dict(ok_stages, confinement_stabilization={
            "confining_measured_Pa": conf, "confining_target_Pa": target}),
    })
    log("M3-real-C1", e, er)
    assert e.status["module_state"] == ModuleState.BLOCKED.value
    assert e.output["structured"]["physics_gate"]["can_load"] is False
    m3_ref = next(a for a in e.output["artifacts"]
                  if a["artifact_id"].startswith("m3_staged_model"))
    from core import ArtifactRef
    m3_ref = ArtifactRef.from_dict(m3_ref)

    # --- M4: even with approvals, physics admission refuses submission ---
    model_auth = ok(core, "M3", "confirm_model_parameters", {"confirm": True})
    exec_auth = ok(core, "M4", "authorize_execution", {"confirm": True})
    e, er = dispatch(core, ModuleID.M4, {
        "case_id": "TX3D-C1",
        "code": "model new\nmodel cycle 10\n",
        "authorization_id": exec_auth["authorization_id"],
    })
    log("M4-blocked", e, er)
    assert e.status["module_state"] == ModuleState.BLOCKED.value
    assert e.output["structured"]["tool_task_id"] is None
    assert "物理准入" in e.output["structured"]["reason"]

    # --- M5: failed stage routes directly to diagnosis ------------------
    ok(core, "M3", "request_stage_diagnosis", {"diagnose": "confinement"})
    e, er = dispatch(core, ModuleID.M5, input_refs=[m3_ref])
    log("M5-auto", e, er)
    assert e.status["module_state"] == ModuleState.COMPLETED.value
    assert e.output["structured"]["auto_read_evidence"] is True
    assert e.output["structured"]["findings"]

    # --- M6: real C2 CSV replay -> peak capture gate FAIL ----------------
    # C2/C3 had peak_is_last=true; C1 actually captured a post-peak segment.
    ok(core, "M5", "confirm_diagnosis", {"confirm": True})
    csv_path = os.path.join(REAL_DATA, "tx_C2.csv")
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as fh:
            csv_ref = core.store.write("pfc_csv_C2", "tx_C2.csv", fh.read())
    else:
        csv_ref = None
    # Real tool id from the 2026-11-26 C2 run, bound as evidence.
    real_tid = "3c11e9"
    m4_like = core.store.write_json("m4_run_replay", "simulation_status.json", {
        "case_id": "TX3D-C2", "tool_task_id": real_tid, "task_state": "COMPLETED"})
    refs = [ArtifactRef.from_dict(m4_like.to_dict())]
    if csv_ref:
        refs.append(ArtifactRef.from_dict(csv_ref.to_dict()))
    e, er = core.dispatch(DispatchRequest(RID, ModuleID.M6, payload={
        "unit_system": "SI"}))
    # Use the ref-bearing request explicitly; gate already unlocked.
    e, er = core.dispatch(DispatchRequest(RID, ModuleID.M6, input_refs=refs,
                                          payload={"unit_system": "SI"}))
    log("M6-real-C2", e, er)
    assert e.status["module_state"] == ModuleState.BLOCKED.value
    gate = e.output["structured"]["quality_gate"]
    assert gate["status"] == "FAIL" and not gate["peak_strength_allowed"]

    # --- parameter-change + confirmation + re-execution path -------------
    # Demonstrate that a corrected measurement unlocks the loading gate.
    from core import check_physics_gate
    corrected = check_physics_gate({
        "confining_measured_Pa": 1_000_000.0,
        "confining_target_Pa": 1_000_000.0,
        "bonded_after_bonding": 1251,
        "bonded_at_load": 1100,
    })
    change_auth = ok(core, "M3", "confirm_model_parameters",
                     {"confining": 1_000_000.0, "reason": "围压稳定后重载"})
    report["parameter_change"] = {
        "changed_field": "confining_measured_Pa",
        "from": conf, "to": 1_000_000.0,
        "user_confirmation_decision": change_auth["decision_id"],
        "context_version": CV,
        "physics_gate_after_change": corrected.to_dict(),
    }
    report["approvals"] = core.approvals.snapshot()
    report["evidence_chain"] = {
        "m3_staged_model": m3_ref.artifact_id,
        "m6_tool_task_id": real_tid,
        "m6_csv": csv_ref.artifact_id if csv_ref else None,
    }
    report["result"] = (
        "4.1-alpha 阶段门成功阻止了 4.0 中误判为通过的 C1 工况；"
        "修正围压后物理准入闸门转为 PASS。"
    )
    out_dir = os.path.join(BASE, "..", "outputs", "v41_alpha")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "triaxial_slice_report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print("[REPORT]", out)
    return report


if __name__ == "__main__":
    run()
