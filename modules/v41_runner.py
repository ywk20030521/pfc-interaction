"""4.1-alpha M4: real task runner with checkpoints and versioned evidence.

4.0 M4 only wrote a config/status file and marked itself COMPLETED with
task_state=CREATED. This runner:

  * submits through the real itasca-mcp adapter (via Core I5),
  * records the real tool_task_id and tool-reported task_state,
  * polls status (and can interrupt),
  * sets checkpoints at sample / confinement / loading boundaries,
  * binds tool_task_id + script hash + output artifact + state,
  * keeps every rerun as a new version (never overwrites old evidence),
  * refuses to mark physical validity from tool completion alone.

When the bridge is offline it returns a BLOCKED envelope; it never fabricates
a tool_task_id.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from core import (
    DispatchRequest,
    Envelope,
    Evidence,
    EvidenceSource,
    ModuleID,
    ModuleState,
    TaskState,
    CoreDispatcher,
)

MODULE_VERSION = "4.1.0-alpha"

CHECKPOINT_STAGES = ("sample_preparation", "confinement_stabilization", "axial_loading")


def _load_m3(request: DispatchRequest, core: CoreDispatcher) -> Dict[str, Any]:
    for ref in request.input_refs:
        if ref.artifact_id.startswith("m3_staged_model"):
            return core.store.get_json(ref)
    return (request.payload or {}).get("staged_model", {})


def run(module_task_id: str, request: DispatchRequest,
        core: CoreDispatcher) -> Envelope:
    """Submit a real PFC task. No bridge -> BLOCKED, never a fake task id."""
    payload = request.payload or {}
    m3 = _load_m3(request, core)
    physics = m3.get("physics_gate", {})
    case_id = str(payload.get("case_id", "C00"))

    if not physics.get("can_load", False):
        return Envelope(
            module_id=ModuleID.M4,
            module_version=MODULE_VERSION,
            research_task_id=request.research_task_id,
            module_task_id=module_task_id,
            parent_task_id=request.parent_task_id,
            input_refs=request.input_refs,
            status={"module_state": ModuleState.BLOCKED.value, "task_state": "CREATED"},
            output={"structured": {
                "case_id": case_id, "task_state": "CREATED",
                "tool_task_id": None, "physics_gate": physics,
                "reason": "M3 物理准入未通过：禁止提交加载任务",
            }, "artifacts": [], "verified_by_execution": False},
            evidence=[], decisions=[],
            limitations=["M3 阶段检查未通过；M4 未提交任何任务"],
        )

    code = str(payload.get("code", ""))
    if not code:
        # Replay mode: use the operator-supplied real script text only.
        code = str(payload.get("script_text", ""))
    if not code:
        return Envelope(
            module_id=ModuleID.M4,
            module_version=MODULE_VERSION,
            research_task_id=request.research_task_id,
            module_task_id=module_task_id,
            status={"module_state": ModuleState.BLOCKED.value, "task_state": "CREATED"},
            output={"structured": {"reason": "无可执行脚本；M4 不伪造执行"},
                    "artifacts": [], "verified_by_execution": False},
            decisions=[], limitations=["未提供脚本；未提交任务"],
        )

    authorization_id = str(payload.get("authorization_id", ""))
    if not authorization_id:
        return Envelope(
            module_id=ModuleID.M4,
            module_version=MODULE_VERSION,
            research_task_id=request.research_task_id,
            module_task_id=module_task_id,
            status={"module_state": ModuleState.BLOCKED.value, "task_state": "CREATED"},
            output={"structured": {"reason": "缺少 I5 执行授权；M4 不得自行执行"},
                    "artifacts": [], "verified_by_execution": False},
            decisions=[], limitations=["无 authorization_id；未提交任务"],
        )

    result, errors = core.execute(
        module_task_id=module_task_id,
        operation="execute_dat",
        model_ref=None,
        case_id=case_id,
        authorization_id=authorization_id,
        scope="run_model",
        context_version=request.context_version,
        code=code,
    )
    if errors or result is None:
        return Envelope(
            module_id=ModuleID.M4,
            module_version=MODULE_VERSION,
            research_task_id=request.research_task_id,
            module_task_id=module_task_id,
            status={"module_state": ModuleState.BLOCKED.value, "task_state": "CREATED"},
            output={"structured": {"reason": "I5 执行被拒绝", "errors": errors},
                    "artifacts": [], "verified_by_execution": False},
            decisions=[], limitations=errors or ["执行被拒绝"],
        )

    tool_task_id = result.tool_task_id
    task_state = result.task_state
    if not tool_task_id or tool_task_id.startswith("unknown"):
        return Envelope(
            module_id=ModuleID.M4,
            module_version=MODULE_VERSION,
            research_task_id=request.research_task_id,
            module_task_id=module_task_id,
            status={"module_state": ModuleState.BLOCKED.value,
                    "task_state": task_state.value},
            output={"structured": {"reason": "工具未返回真实 task_id",
                                   "error": result.error},
                    "artifacts": [], "verified_by_execution": False},
            decisions=[], limitations=["无真实 tool_task_id；拒绝标记完成"],
        )

    # Versioned artifacts: each run gets a unique artifact_id so reruns never
    # overwrite earlier evidence.
    run_key = uuid.uuid4().hex[:8]
    status_doc = {
        "sim_task_id": "SIM-%s" % run_key,
        "case_id": case_id,
        "tool_task_id": tool_task_id,
        "task_state": task_state.value,
        "script_hash": result.output_artifacts[0].get("hash") if result.output_artifacts else None,
        "checkpoints": [
            {"checkpoint_id": "CP%d" % (i + 1), "stage": s,
             "action": "core_decision_required", "status": "PENDING"}
            for i, s in enumerate(CHECKPOINT_STAGES)
        ],
        "verified_by_execution": False,
        "physically_valid": False,  # only M5 may judge; tool completion != validity
    }
    status_ref = core.store.write_json(
        "m4_run_%s" % run_key, "simulation_status.json", status_doc
    )
    evidence: List[Evidence] = []
    if result.output_artifacts:
        out = result.output_artifacts[0].get("output", "")
        out_ref = core.store.write("m4_output_%s" % run_key,
                                   "tool_output.txt", str(out))
        status_doc["output_artifact"] = out_ref.to_dict()
        evidence.append(Evidence(
            EvidenceSource.PFC_EXECUTED, tool_task_id,
            "真实 itasca-mcp 执行输出", tool_task_id=tool_task_id,
        ))

    state = (ModuleState.COMPLETED.value
             if task_state == TaskState.COMPLETED else ModuleState.BLOCKED.value)
    return Envelope(
        module_id=ModuleID.M4,
        module_version=MODULE_VERSION,
        research_task_id=request.research_task_id,
        module_task_id=module_task_id,
        parent_task_id=request.parent_task_id,
        input_refs=request.input_refs,
        status={"module_state": state, "task_state": task_state.value},
        output={"structured": status_doc,
                "artifacts": [status_ref.to_dict(),
                              *([status_doc["output_artifact"]]
                                if "output_artifact" in status_doc else [])],
                "verified_by_execution": False},
        evidence=evidence, decisions=[],
        limitations=[
            "工具状态 %s 不等于物理有效；须经 M5 检查" % task_state.value,
            "检查点尚未确认（成样/围压稳定/加载完成）",
        ],
    )


def record_checkpoint(
    core: CoreDispatcher, module_task_id: str, checkpoint_id: str,
    resolution: str, context_version: str,
) -> Dict[str, Any]:
    """Core-only checkpoint confirmation; no module-level shortcut."""
    from core import DecisionKey

    decision, presented, _ = core.request_decision(
        key=DecisionKey("checkpoint", "M4", checkpoint_id, context_version),
        question="检查点 %s 是否继续？" % checkpoint_id,
        options=["继续", "停止"],
        blocks_module_task_id=module_task_id,
    )
    core.resolve_decision(decision["decision_id"], resolution, context_version,
                          answers={"checkpoint": checkpoint_id, "resolution": resolution})
    return {"decision_id": decision["decision_id"], "presented": presented}


__all__ = ["CHECKPOINT_STAGES", "run", "record_checkpoint"]
