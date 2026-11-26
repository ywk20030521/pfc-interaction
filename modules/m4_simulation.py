"""M4 Simulation Management - second batch module.

IF0 contract fields (report 4.4.4):
  simulation_config, simulation_log, simulation_status, checkpoint_manifest,
  execution_report, simulation_artifacts

IF0 section 4.2 structured fields:
  sim_task_id, case_id, model_ref, tool_task_id, task_state,
  checkpoints[], artifacts[], evidence_refs

Rules:
  - task_state must come from the real tool (ItascaMcpAdapter), never inferred
  - checkpoints trigger Core interaction; M4 never asks the user directly
  - refusal to continue must stop the corresponding task
  - completed tool status != physically valid result (M5 checks that)
"""

from __future__ import annotations

from dataclasses import dataclass, field
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

MODULE_VERSION = "0.1.0"
MODULE_ID = ModuleID.M4


@dataclass
class SimulationRun:
    sim_task_id: str
    case_id: str
    model_ref: str
    tool_task_id: Optional[str] = None
    task_state: TaskState = TaskState.CREATED
    checkpoints: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sim_task_id": self.sim_task_id,
            "case_id": self.case_id,
            "model_ref": self.model_ref,
            "tool_task_id": self.tool_task_id,
            "task_state": self.task_state.value,
            "checkpoints": self.checkpoints,
            "artifacts": self.artifacts,
            "evidence_refs": self.evidence_refs,
        }


def _load_model(request: DispatchRequest, core: CoreDispatcher) -> Dict[str, Any]:
    for ref in request.input_refs:
        if ref.artifact_id.startswith("m3_model_parameters"):
            return core.store.get_json(ref)
    return (request.payload or {}).get("model", {})


def build_config(run: SimulationRun, model: Dict[str, Any]) -> Dict[str, Any]:
    """Build simulation_config.json content from the model manifest."""
    return {
        "sim_task_id": run.sim_task_id,
        "case_id": run.case_id,
        "model_ref": run.model_ref,
        "dimension": model.get("dimension", "2D"),
        "checkpoint_policy": {
            "enabled": True,
            "trigger": "stage_boundary",
            "on_user_refusal": "stop_task",
        },
        "status_source": "itasca_mcp_tool_result_only",
    }


def run(module_task_id: str, request: DispatchRequest, core: CoreDispatcher) -> Envelope:
    payload = request.payload or {}
    model = _load_model(request, core)
    case_id = str(payload.get("case_id", model.get("case_id", "C00")))
    sim = SimulationRun(
        sim_task_id="SIM-" + module_task_id,
        case_id=case_id,
        model_ref=str(payload.get("model_ref", "m3_model")),
    )

    checkpoints = list(payload.get("checkpoints", []))
    for cp in checkpoints:
        sim.checkpoints.append(
            {
                "checkpoint_id": cp.get("id", "CP%d" % (len(sim.checkpoints) + 1)),
                "stage": cp.get("stage", "unknown"),
                "action": "core_decision_required",
                "status": "PENDING",
            }
        )

    config = build_config(sim, model)
    config_ref = core.store.write_json("m4_simulation_config", "simulation_config.json", config)
    status_ref = core.store.write_json("m4_simulation_status", "simulation_status.json", sim.to_dict())
    sim.artifacts = [config_ref.to_dict(), status_ref.to_dict()]
    sim.evidence_refs = [status_ref.artifact_id]

    limitations: List[str] = []
    if not payload.get("executor_dispatched"):
        limitations.append(
            "no execution dispatched: task_state=CREATED is not a tool result; "
            "call Core I5 with a valid authorization to run"
        )
    else:
        limitations.append(
            "execution dispatched through Core I5; verify task_state from tool response"
        )

    return Envelope(
        module_id=MODULE_ID,
        module_version=MODULE_VERSION,
        research_task_id=request.research_task_id,
        module_task_id=module_task_id,
        parent_task_id=request.parent_task_id,
        input_refs=request.input_refs,
        status={"module_state": ModuleState.COMPLETED.value, "task_state": sim.task_state.value},
        output={
            "structured": sim.to_dict(),
            "artifacts": sim.artifacts,
            "verified_by_execution": False,
        },
        evidence=[
            Evidence(EvidenceSource.DERIVED_COMPUTED, "M3.model_manifest", "仿真配置来源")
        ],
        decisions=[],
        limitations=limitations,
    )


def record_execution(
    module_task_id: str,
    core: CoreDispatcher,
    tool_task_id: str,
    task_state: TaskState,
) -> Envelope:
    """Update M4 status after Core I5 returns a real execution result."""
    env = core.envelope(module_task_id)
    if env is None:
        raise KeyError("M4 module task not found: %s" % module_task_id)
    structured = env.output["structured"]
    structured["tool_task_id"] = tool_task_id
    structured["task_state"] = task_state.value
    structured["evidence_refs"] = [tool_task_id]
    status_ref = core.store.write_json(
        "m4_simulation_status", "simulation_status.json", structured
    )
    env.output["artifacts"].append(status_ref.to_dict())
    env.status["task_state"] = task_state.value
    env.evidence.append(
        Evidence(
            EvidenceSource.PFC_EXECUTED,
            tool_task_id,
            "真实 itasca-mcp 执行结果",
            tool_task_id=tool_task_id,
        )
    )
    return env
