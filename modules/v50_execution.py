"""5.0 real execution carrier: unified module_result + Core-bound bridge gateway.

Closes the two remaining protocol gaps:
  1. 4.0 IF0 Envelope -> PFCI-MOD-5.0 ``module_result`` for on-demand modules;
  2. 5.0 calibration/discussion decisions -> real Itasca MCP bridge execution
     with a real tool_task_id and no fabricated success.

Scientific validity is NOT implied by a successful tool call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from adapters.itasca_mcp import BridgeUnavailable, ItascaMcpAdapter
from core.contract import Envelope, EvidenceSource
from core.state_machine import TaskState
from core.v50_context import EvidenceItem, EvidenceKind, ResearchTask, StageID
from core.v50_decisions import DecisionManager


@dataclass
class ModuleResult:
    """PFCI-MOD-5.0 section 10 unified module interface."""

    module_id: str
    module_version: str
    research_task_id: str
    stage_id: str
    input_refs: List[Dict[str, Any]] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    status: str = "completed"
    outputs: Dict[str, Any] = field(default_factory=dict)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    decisions_required: List[str] = field(default_factory=list)
    unresolved_items: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    affected_assets: List[str] = field(default_factory=list)
    next_recommendation: str = ""

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.status not in ("completed", "failed", "blocked", "waiting_for_user"):
            errors.append("非法 module_result 状态: %s" % self.status)
        if not self.module_id or not self.research_task_id or not self.stage_id:
            errors.append("module_result 缺少身份字段")
        if not isinstance(self.outputs, dict):
            errors.append("outputs 必须是对象")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id, "module_version": self.module_version,
            "research_task_id": self.research_task_id, "stage_id": self.stage_id,
            "input_refs": list(self.input_refs), "preconditions": list(self.preconditions),
            "status": self.status, "outputs": dict(self.outputs),
            "evidence": list(self.evidence),
            "decisions_required": list(self.decisions_required),
            "unresolved_items": list(self.unresolved_items),
            "limitations": list(self.limitations),
            "affected_assets": list(self.affected_assets),
            "next_recommendation": self.next_recommendation,
        }


_EVIDENCE_MAP = {
    EvidenceSource.USER_PROVIDED: EvidenceKind.USER_INPUT,
    EvidenceSource.PFC_EXECUTED: EvidenceKind.TOOL_EVIDENCE,
    EvidenceSource.DERIVED_COMPUTED: EvidenceKind.COMPUTED_RESULT,
    EvidenceSource.AGENT_INFERRED: EvidenceKind.INFERENCE,
    EvidenceSource.PENDING_ASSUMPTION: EvidenceKind.UNVERIFIED_ASSUMPTION,
    EvidenceSource.INVALID_EVIDENCE: EvidenceKind.UNVERIFIED_ASSUMPTION,
}


def module_result_from_envelope(envelope: Envelope, stage_id: str,
                                affected_assets: Optional[List[str]] = None) -> ModuleResult:
    """Convert a 4.0 IF0 envelope without changing 4.0 behaviour."""
    structured = envelope.output.get("structured", {}) or {}
    state = str((envelope.status or {}).get("module_state", "")).lower()
    status = state if state in ("completed", "failed", "blocked", "waiting_for_user") else "failed"
    evidence: List[Dict[str, Any]] = []
    limitations = list(envelope.limitations)
    for ev in envelope.evidence:
        kind = _EVIDENCE_MAP.get(ev.source, EvidenceKind.INFERENCE)
        evidence.append({
            "kind": kind.value, "ref": ev.ref, "description": ev.description,
            "tool_task_id": ev.tool_task_id or "",
        })
        if ev.source == EvidenceSource.INVALID_EVIDENCE:
            limitations.append("存在无效证据，不能支持结论: %s" % ev.ref)
    return ModuleResult(
        module_id=envelope.module_id.value, module_version=envelope.module_version,
        research_task_id=envelope.research_task_id, stage_id=stage_id,
        input_refs=[r.to_dict() for r in envelope.input_refs],
        preconditions=list(envelope.preconditions), status=status,
        outputs={"structured": structured, "artifacts": list(envelope.output.get("artifacts", []))},
        evidence=evidence,
        decisions_required=[d.decision_id for d in envelope.decisions],
        unresolved_items=list(structured.get("unresolved_items", [])),
        limitations=limitations,
        affected_assets=list(affected_assets or []),
        next_recommendation=str(structured.get("next_recommendation", "")),
    )


class V50ModuleBus:
    """Run 4.0 module runners on demand and expose 5.0 module_result."""

    def __init__(self, core: Any, task: ResearchTask) -> None:
        self.core = core
        self.task = task

    def run(self, module_id: Any, payload: Dict[str, Any],
            input_refs: Optional[List[Any]] = None) -> ModuleResult:
        from core.contract import ModuleID
        from core.dispatcher import DispatchRequest
        request = DispatchRequest(
            research_task_id=self.task.research_task_id,
            module_id=module_id if isinstance(module_id, ModuleID) else ModuleID(str(module_id)),
            input_refs=list(input_refs or []), context_version=self.task.context_version,
            payload=dict(payload),
        )
        envelope, errors = self.core.dispatch(request)
        if envelope is None:
            return ModuleResult(
                module_id=request.module_id.value, module_version="5.0.0",
                research_task_id=self.task.research_task_id,
                stage_id=self.task.current_stage.value, status="blocked",
                limitations=list(errors or ["module dispatch failed"]),
            )
        result = module_result_from_envelope(
            envelope, self.task.current_stage.value,
            list((payload.get("affected_assets") or [])))
        if errors:
            result.unresolved_items.extend(errors)
        self.task.bump_version("module_result:%s" % result.module_id)
        return result


class V50ExecutionGateway:
    """Core-owned bridge execution; requires an unexpired authorization."""

    def __init__(self, task: ResearchTask, decisions: DecisionManager,
                 adapter: Optional[ItascaMcpAdapter] = None) -> None:
        self.task = task
        self.decisions = decisions
        self.adapter = adapter if adapter is not None else ItascaMcpAdapter()

    def execute_code(self, code: str, authorization_id: str, operation: str,
                     target: str, model_version: str, parameter_version: str,
                     matrix_version: str, assumption_version: str = "v1",
                     description: str = "") -> Dict[str, Any]:
        ok, issues = self.decisions.validate_authorization(
            authorization_id, operation, target, "run_model",
            model_version, parameter_version, matrix_version, assumption_version)
        if not ok:
            return {"status": "BLOCKED", "reason": "; ".join(issues),
                    "tool_task_id": None, "execution_verified": False}
        try:
            result = self.adapter.execute_code(code)
        except BridgeUnavailable as exc:
            return {"status": "BLOCKED", "reason": "bridge 不可用: %s" % exc,
                    "tool_task_id": None, "execution_verified": False}
        if result.task_state != TaskState.COMPLETED:
            return {"status": "FAILED", "tool_task_id": result.tool_task_id,
                    "task_state": result.task_state.value if hasattr(result.task_state, "value")
                    else str(result.task_state),
                    "error": result.error, "execution_verified": False}
        output = ""
        if result.output_artifacts:
            output = str(result.output_artifacts[0].get("output", ""))
        evidence = EvidenceItem(
            kind=EvidenceKind.TOOL_EVIDENCE,
            ref="bridge:%s" % result.tool_task_id,
            description=description or "V50 网关真实执行证据",
            tool_task_id=result.tool_task_id,
        )
        self.task.add_evidence(evidence)
        return {
            "status": "EXECUTED", "tool_task_id": result.tool_task_id,
            "task_state": "COMPLETED", "output": output,
            "evidence_ref": evidence.ref, "execution_verified": True,
            "note": "仅表示取得真实工具证据，不代表科学结论成立",
        }


def parse_metric(output: str, key: str) -> Optional[float]:
    """Read a simple `KEY=<number>` line from real bridge output."""
    match = re.search(r"\b%s\s*=\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)" % re.escape(key),
                      output or "")
    return float(match.group(1)) if match else None


__all__ = [
    "ModuleResult", "module_result_from_envelope", "V50ModuleBus",
    "V50ExecutionGateway", "parse_metric",
]
