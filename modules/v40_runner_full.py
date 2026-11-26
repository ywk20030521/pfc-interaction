"""4.0 full implementation: M4 Simulation Management (technical report 4.4).

10 functions: task creation, environment detection, script execution,
multi-case organisation, progress, checkpoints, status inspection, exception
interruption, recovery/rerun, run-record integrity. Emits all 6 standard
outputs including checkpoint_manifest.json and execution_report.md.

Real tool_task_id is mandatory; offline bridge -> BLOCKED, never fabricated.
Reruns create new versioned artifacts so old evidence is never overwritten.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from core import (
    DispatchRequest, Envelope, Evidence, EvidenceSource, ModuleID,
    ModuleState, TaskState, CoreDispatcher,
)

MODULE_VERSION = "4.0.0"
CHECKPOINT_STAGES = ("sample_preparation", "confinement_stabilization", "axial_loading")


def create_task(case_id: str, module_task_id: str) -> Dict[str, Any]:
    """M4.1 仿真任务创建."""
    return {"sim_task_id": "SIM-%s" % uuid.uuid4().hex[:8],
            "case_id": case_id, "module_task_id": module_task_id,
            "task_state": TaskState.CREATED.value}


def detect_environment(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """M4.2 PFC2D/PFC3D 执行环境识别."""
    dim = str(cfg.get("dimension", "3D")).upper()
    return {"dimension": "2D" if dim in ("2D", "PFC2D") else "3D",
            "bridge_url": cfg.get("bridge_url", "http://localhost:9001")}


def checkpoint_manifest(case_id: str) -> List[Dict[str, Any]]:
    """M4.6 检查点管理."""
    return [{"checkpoint_id": "CP%d" % (i + 1), "stage": stage,
             "action": "core_decision_required", "status": "PENDING"}
            for i, stage in enumerate(CHECKPOINT_STAGES)]


def status_summary(task_state: str) -> Dict[str, Any]:
    """M4.7 运行状态检查（状态只来自工具）."""
    return {"task_state": task_state, "state_source": "itasca_mcp_tool_result_only"}


def integrity_check(status: Dict[str, Any]) -> List[str]:
    """M4.10 运行记录和结果完整性检查."""
    errors = []
    if not status.get("tool_task_id"):
        errors.append("missing tool_task_id")
    if status.get("task_state") == TaskState.CREATED.value:
        errors.append("task never executed (CREATED)")
    return errors


def recovery_plan(status: Dict[str, Any], sav_ref: Optional[str]) -> Dict[str, Any]:
    """M4.9 任务恢复与重跑."""
    return {"can_resume": bool(sav_ref) and status.get("task_state") in
            ("FAILED", "CANCELLED", "PAUSED"),
            "sav_ref": sav_ref, "strategy": "resume_from_sav" if sav_ref else "rerun_from_start"}


def _load_m3(request: DispatchRequest, core: CoreDispatcher) -> Dict[str, Any]:
    for ref in request.input_refs:
        if ref.artifact_id.startswith("m3_staged_model"):
            return core.store.get_json(ref)
    return (request.payload or {}).get("staged_model", {})


def run(module_task_id: str, request: DispatchRequest,
        core: CoreDispatcher) -> Envelope:
    payload = request.payload or {}
    m3 = _load_m3(request, core)
    physics = m3.get("physics_gate", {})
    case_id = str(payload.get("case_id", "C00"))
    cases = list(payload.get("cases", []))

    # M4.2 env detection
    env_info = detect_environment(payload)
    # M4.6 checkpoints
    cps = checkpoint_manifest(case_id)

    if not physics.get("can_load", False):
        status = create_task(case_id, module_task_id)
        return Envelope(
            module_id=ModuleID.M4, module_version=MODULE_VERSION,
            research_task_id=request.research_task_id, module_task_id=module_task_id,
            parent_task_id=request.parent_task_id, input_refs=request.input_refs,
            status={"module_state": ModuleState.BLOCKED.value, "task_state": "CREATED"},
            output={"structured": {"case_id": case_id, "tool_task_id": None,
                    "physics_gate": physics, "reason": "M3 物理准入未通过，禁止提交加载任务",
                    "checkpoints": cps, "environment": env_info},
                    "artifacts": [], "verified_by_execution": False},
            evidence=[], decisions=[], limitations=["M3 阶段检查未通过"])

    code = str(payload.get("code") or payload.get("script_text") or "")
    authorization_id = str(payload.get("authorization_id", ""))
    if not code or not authorization_id:
        return Envelope(
            module_id=ModuleID.M4, module_version=MODULE_VERSION,
            research_task_id=request.research_task_id, module_task_id=module_task_id,
            status={"module_state": ModuleState.BLOCKED.value, "task_state": "CREATED"},
            output={"structured": {"reason": "缺少脚本或 I5 授权；M4 不伪造执行",
                                   "checkpoints": cps}, "artifacts": [],
                    "verified_by_execution": False},
            decisions=[], limitations=["无脚本或无授权；未提交任务"])

    result, errors = core.execute(
        module_task_id=module_task_id, operation="execute_dat", model_ref=None,
        case_id=case_id, authorization_id=authorization_id, scope="run_model",
        context_version=request.context_version, code=code)

    if errors or result is None:
        return Envelope(
            module_id=ModuleID.M4, module_version=MODULE_VERSION,
            research_task_id=request.research_task_id, module_task_id=module_task_id,
            status={"module_state": ModuleState.BLOCKED.value, "task_state": "CREATED"},
            output={"structured": {"reason": "I5 执行被拒绝", "errors": errors},
                    "artifacts": [], "verified_by_execution": False},
            decisions=[], limitations=errors or ["执行被拒绝"])

    tool_task_id = result.tool_task_id
    task_state = result.task_state
    if not tool_task_id or tool_task_id.startswith("unknown"):
        return Envelope(
            module_id=ModuleID.M4, module_version=MODULE_VERSION,
            research_task_id=request.research_task_id, module_task_id=module_task_id,
            status={"module_state": ModuleState.BLOCKED.value,
                    "task_state": task_state.value},
            output={"structured": {"reason": "工具未返回真实 task_id", "error": result.error},
                    "artifacts": [], "verified_by_execution": False},
            decisions=[], limitations=["无真实 tool_task_id；拒绝标记完成"])

    # M4.3/4/5 multi-case organisation + progress
    run_key = uuid.uuid4().hex[:8]
    status_doc = {
        "sim_task_id": "SIM-%s" % run_key, "case_id": case_id,
        "tool_task_id": tool_task_id, "task_state": task_state.value,
        "state_source": "itasca_mcp_tool_result_only",
        "total_cases": len(cases) or 1, "cases": cases,
        "checkpoints": cps, "environment": env_info,
        "verified_by_execution": False, "physically_valid": False,
        "recovery": recovery_plan({"task_state": task_state.value}, payload.get("sav_ref")),
    }
    integrity = integrity_check(status_doc)
    status_doc["integrity_errors"] = integrity

    artifacts = []
    artifacts.append(core.store.write_json("m4_run_%s" % run_key,
                     "simulation_status.json", status_doc).to_dict())
    artifacts.append(core.store.write_json("m4_checkpoint_%s" % run_key,
                     "checkpoint_manifest.json", {"checkpoints": cps}).to_dict())
    artifacts.append(core.store.write_json("m4_config_%s" % run_key,
                     "simulation_config.json", {"case_id": case_id,
                     "environment": env_info, "checkpoint_policy": "stage_boundary"}).to_dict())
    evidence: List[Evidence] = []
    if result.output_artifacts:
        out = result.output_artifacts[0].get("output", "")
        artifacts.append(core.store.write("m4_log_%s" % run_key,
                         "simulation_log", str(out)).to_dict())
        evidence.append(Evidence(EvidenceSource.PFC_EXECUTED, tool_task_id,
                        "真实 itasca-mcp 执行输出", tool_task_id=tool_task_id))
    report_md = "# 执行报告\n\ncase=%s tool_task_id=%s state=%s\n\n完整性与物理有效性须经 M5 检查。\n" % (
        case_id, tool_task_id, task_state.value)
    artifacts.append(core.store.write("m4_report_%s" % run_key,
                     "execution_report.md", report_md).to_dict())
    artifacts.append(core.store.write_json("m4_artifacts_%s" % run_key,
                     "simulation_artifacts", {"files": [a["artifact_id"] for a in artifacts]}).to_dict())

    state = (ModuleState.COMPLETED.value if task_state == TaskState.COMPLETED
             else ModuleState.BLOCKED.value)
    return Envelope(
        module_id=ModuleID.M4, module_version=MODULE_VERSION,
        research_task_id=request.research_task_id, module_task_id=module_task_id,
        parent_task_id=request.parent_task_id, input_refs=request.input_refs,
        status={"module_state": state, "task_state": task_state.value},
        output={"structured": status_doc, "artifacts": artifacts,
                "verified_by_execution": False},
        evidence=evidence, decisions=[],
        limitations=["工具状态 %s 不等于物理有效；须经 M5" % task_state.value,
                     "检查点尚未确认"])


__all__ = ["create_task", "detect_environment", "checkpoint_manifest",
           "status_summary", "integrity_check", "recovery_plan", "run",
           "CHECKPOINT_STAGES"]
