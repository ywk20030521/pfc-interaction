"""4.1-alpha M3: staged triaxial model with per-stage physics gates.

4.0 M3 emitted one hard-coded demo .dat (linear contact, density 2500,
ball distribute, no bonding, no loading). 4.1 splits the experiment into 8
stages, each with independent state and a check report. A failed check halts
the pipeline at that stage and routes to M5 diagnosis; the loading stage is
not generated and cannot run.

Stage sequence:
  1 sample_preparation -> 2 initial_equilibrium -> 3 compaction_servo
  -> 4 bonding -> 5 re_equilibrium -> 6 confinement_stabilization
  -> 7 axial_loading -> 8 data_acquisition
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core import (
    DispatchRequest,
    Envelope,
    Evidence,
    EvidenceSource,
    ModuleID,
    ModuleState,
    CoreDispatcher,
    check_physics_gate,
)

MODULE_VERSION = "4.1.0-alpha"

STAGES: List[Dict[str, str]] = [
    {"id": "sample_preparation", "name": "成样", "prerequisite": "-"},
    {"id": "initial_equilibrium", "name": "初始平衡", "prerequisite": "sample_preparation"},
    {"id": "compaction_servo", "name": "压实/预压伺服", "prerequisite": "initial_equilibrium"},
    {"id": "bonding", "name": "胶结", "prerequisite": "compaction_servo"},
    {"id": "re_equilibrium", "name": "再平衡", "prerequisite": "bonding"},
    {"id": "confinement_stabilization", "name": "围压加载与稳定", "prerequisite": "re_equilibrium"},
    {"id": "axial_loading", "name": "轴向加载", "prerequisite": "confinement_stabilization"},
    {"id": "data_acquisition", "name": "数据采集与停止", "prerequisite": "axial_loading"},
]

# Each stage publishes the checks that must pass before its successor runs.
STAGE_CHECK_KEYS: Dict[str, List[str]] = {
    "sample_preparation": ["overlap_rate", "out_of_bounds", "wall_gap_m"],
    "initial_equilibrium": ["unbalanced_force_ratio", "timestep_s"],
    "compaction_servo": ["overlap_rate", "unbalanced_force_ratio", "wall_gap_m"],
    "bonding": ["bonded_after_bonding", "bond_retention"],
    "re_equilibrium": ["unbalanced_force_ratio", "timestep_s"],
    "confinement_stabilization": [
        "confining_measured_Pa", "confining_target_Pa", "confinement_ratio"
    ],
    "axial_loading": ["peak_is_last", "samples_after_peak"],
    "data_acquisition": ["peak_is_last", "samples_after_peak"],
}


def _load_m2(request: DispatchRequest, core: CoreDispatcher) -> Dict[str, Any]:
    for ref in request.input_refs:
        if ref.artifact_id.startswith("m2_parameter_schema"):
            return core.store.get_json(ref)
    return (request.payload or {}).get("experiment_design", {})


def _measurements_for(stage: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Collect stage measurements from the caller.

    Measurements must come from real execution (M4 / bridge) or from a
    labelled historical replay. None are synthesised here.
    """
    all_m = dict(payload.get("stage_measurements", {}) or {})
    per_stage = dict(payload.get("stage_checks", {}) or {}).get(stage, {})
    all_m.update(per_stage)
    return all_m


def _check_stage(stage: str, m: Dict[str, Any]) -> Dict[str, Any]:
    """Return PASS / FAIL with findings for one stage."""
    findings: List[str] = []
    keys = STAGE_CHECK_KEYS.get(stage, [])
    missing = [k for k in keys if k not in m or m[k] is None]
    if missing:
        findings.append("阶段缺少必要测量: %s" % ", ".join(missing))

    if stage == "sample_preparation":
        overlap = m.get("overlap_rate")
        if isinstance(overlap, (int, float)) and overlap > 0.01:
            findings.append("颗粒重叠率 %.4f > 0.01" % float(overlap))
        oob = m.get("out_of_bounds")
        if isinstance(oob, (int, float)) and oob > 0:
            findings.append("颗粒越界 %d" % int(oob))
        gap = m.get("wall_gap_m")
        if isinstance(gap, (int, float)) and gap > 0.0005:
            findings.append("墙-试样间隙 %.6g m > 0.0005 m" % float(gap))
    elif stage in ("initial_equilibrium", "re_equilibrium"):
        ubf = m.get("unbalanced_force_ratio")
        if isinstance(ubf, (int, float)) and ubf > 0.01:
            findings.append("不平衡力比 %.4g > 0.01" % float(ubf))
        ts = m.get("timestep_s")
        if isinstance(ts, (int, float)) and (ts < 1e-12 or ts > 1e-1):
            findings.append("时步异常 %.6g s" % float(ts))
    elif stage == "compaction_servo":
        ubf = m.get("unbalanced_force_ratio")
        if isinstance(ubf, (int, float)) and ubf > 0.01:
            findings.append("预压后不平衡力比 %.4g > 0.01" % float(ubf))
    elif stage == "bonding":
        retention = m.get("bond_retention")
        if isinstance(retention, (int, float)) and retention < 0.80:
            findings.append("胶结保留率 %.3f < 0.80" % float(retention))
        after = m.get("bonded_after_bonding")
        if isinstance(after, (int, float)) and after <= 0:
            findings.append("成键数 %d，未成键" % int(after))
    elif stage == "confinement_stabilization":
        target = m.get("confining_target_Pa")
        measured = m.get("confining_measured_Pa")
        if isinstance(target, (int, float)) and isinstance(measured, (int, float)):
            if target > 0 and not (0.95 <= measured / target <= 1.05):
                findings.append(
                    "围压 %.3g Pa 与目标 %.3g Pa 偏差超过 ±5%%" % (float(measured), float(target))
                )
    elif stage in ("axial_loading", "data_acquisition"):
        if m.get("peak_is_last") is True:
            findings.append("峰值在最后采样点：未捕获峰后段")
        after = m.get("samples_after_peak")
        if isinstance(after, (int, float)) and after < 3:
            findings.append("峰后采样不足 %d < 3" % int(after))

    return {
        "stage": stage,
        "status": "PASS" if not findings else "FAIL",
        "findings": findings,
        "checks": {k: m.get(k) for k in keys},
    }


def run(module_task_id: str, request: DispatchRequest,
        core: CoreDispatcher) -> Envelope:
    """Generate staged scripts; halt at first failed stage."""
    payload = request.payload or {}
    m2 = _load_m2(request, core)
    schema = m2.get("parameter_schema", [])
    confirmed = [p for p in schema if p.get("confirmed")]

    states: List[Dict[str, Any]] = []
    scripts: List[Dict[str, Any]] = []
    halted: Optional[str] = None

    for stage in STAGES:
        sid = stage["id"]
        m = _measurements_for(sid, payload)
        result = _check_stage(sid, m)
        result["module_state"] = "COMPLETED" if result["status"] == "PASS" else "BLOCKED"
        states.append(result)

        if result["status"] == "FAIL":
            halted = sid
            break

        # Only generate a stage script after its checks pass.
        script_name = "m3_%s.dat" % sid
        config = {
            "stage": sid,
            "dimension": str(payload.get("dimension", "3D")),
            "case_id": payload.get("case_id", "C00"),
            "parameters": {p.get("name"): p.get("value") for p in confirmed},
        }
        ref = core.store.write_json("m3_stage_%s" % sid, script_name, config)
        scripts.append(ref.to_dict())

    physics_gate = {
        "status": "PASS" if halted is None else "FAIL",
        "halted_at": halted,
        "can_load": halted is None and all(
            s["status"] == "PASS" for s in states
            if s["stage"] in ("confinement_stabilization", "bonding")
        ),
    }
    # Re-check the authoritative physics admission against confinement and
    # bonding measurements regardless of per-stage conclusions.
    conf_m = _measurements_for("confinement_stabilization", payload)
    admission = check_physics_gate(conf_m)
    physics_gate["admission"] = admission.to_dict()
    if not admission.can_load:
        physics_gate["can_load"] = False
        physics_gate["status"] = "FAIL"
        if halted is None:
            halted = "confinement_stabilization"

    structured = {
        "experiment_type": "三轴压缩",
        "dimension": str(payload.get("dimension", "3D")),
        "stages": states,
        "stage_scripts": scripts,
        "physics_gate": physics_gate,
        "halted_at": halted,
        "verified_by_execution": False,
    }
    ref = core.store.write_json("m3_staged_model", "staged_model.json", structured)
    artifacts = [ref.to_dict()] + scripts

    state = ModuleState.COMPLETED.value if halted is None else ModuleState.BLOCKED.value
    limitations = [
        "脚本未执行；物理有效性仅基于提供的阶段测量检查",
        "M3 不设置 verified_by_execution=True",
    ]
    if halted:
        limitations.insert(0, "阶段 %s 检查失败，禁止进入加载与 M4" % halted)

    return Envelope(
        module_id=ModuleID.M3,
        module_version=MODULE_VERSION,
        research_task_id=request.research_task_id,
        module_task_id=module_task_id,
        parent_task_id=request.parent_task_id,
        input_refs=request.input_refs,
        status={"module_state": state, "physics_gate": physics_gate["status"]},
        output={"structured": structured, "artifacts": artifacts,
                "verified_by_execution": False},
        evidence=[Evidence(EvidenceSource.DERIVED_COMPUTED, "M3.stage_checks",
                           "阶段化物理检查")],
        decisions=[],
        limitations=limitations,
    )


__all__ = ["STAGES", "STAGE_CHECK_KEYS", "_check_stage", "run"]
