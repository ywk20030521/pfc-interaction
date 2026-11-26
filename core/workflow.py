"""4.0 workflow orchestration: full pipeline + cross-module iteration.

Technical report section 5.3 requires four feedback paths:
  M5 -> M3 (model setting), M6 -> M4 (data quality),
  M6 -> M2 (insufficient metrics), result -> M1 (hypothesis review).

This module implements them as ITERATION requests that create a NEW child
task, preserve the parent history, and require a fresh approval when research
assumptions change (tracked in ApprovalLedger via the strict dispatcher).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .contract import ModuleID
from .dispatcher import DispatchRequest, V41CoreDispatcher
from .gates import DecisionKey


class InteractionEventType(str, Enum):
    """Technical report section 3.3: seven interaction event types."""

    CLARIFICATION = "需求澄清"
    RESEARCH_DECISION = "科研决策"
    PARAMETER_CONFIRMATION = "参数确认"
    EXECUTION_AUTHORIZATION = "执行授权"
    CHECKPOINT = "检查点决策"
    EXCEPTION_HANDLING = "异常处理"
    RESULT_CONFIRMATION = "结果确认"


# Valid feedback routes: source module -> allowed target modules.
FEEDBACK_ROUTES: Dict[str, List[str]] = {
    "M5": ["M3"],
    "M6": ["M4", "M2"],
    "M1": ["M1"],  # result -> M1 hypothesis review
    "M4": ["M3"],  # runtime failure back to model
}


@dataclass
class IterationRequest:
    request_id: str
    source_module: str
    target_module: str
    trigger_layer: str
    reason: str
    evidence_refs: List[str] = field(default_factory=list)
    parent_task_id: str = ""
    research_task_id: str = ""
    context_version: str = "cv1"
    changes_research_assumption: bool = False
    event_type: str = InteractionEventType.RESULT_CONFIRMATION.value
    approval_decision_id: Optional[str] = None
    approved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "source_module": self.source_module,
            "target_module": self.target_module,
            "trigger_layer": self.trigger_layer,
            "reason": self.reason,
            "evidence_refs": self.evidence_refs,
            "parent_task_id": self.parent_task_id,
            "research_task_id": self.research_task_id,
            "context_version": self.context_version,
            "changes_research_assumption": self.changes_research_assumption,
            "event_type": self.event_type,
            "approval_decision_id": self.approval_decision_id,
            "approved": self.approved,
        }


class WorkflowOrchestrator:
    """Organises the full M1-M6 chain and cross-module iterations."""

    def __init__(self, core: V41CoreDispatcher):
        self.core = core
        self.iterations: List[IterationRequest] = []
        self._seq = 0

    def propose_iteration(
        self,
        source_module: str,
        target_module: str,
        trigger_layer: str,
        reason: str,
        evidence_refs: List[str],
        parent_task_id: str,
        research_task_id: str,
        context_version: str = "cv1",
        changes_research_assumption: bool = False,
        event_type: str = InteractionEventType.RESULT_CONFIRMATION.value,
    ) -> IterationRequest:
        """Create an iteration request. No module is re-run here."""
        if target_module not in FEEDBACK_ROUTES.get(source_module, []):
            raise ValueError(
                "invalid feedback route %s -> %s" % (source_module, target_module)
            )
        if not evidence_refs:
            raise ValueError("iteration requires evidence_refs")
        if parent_task_id not in self.core._module_tasks:
            raise KeyError("parent task not found: %s" % parent_task_id)
        self._seq += 1
        req = IterationRequest(
            request_id="IT-%03d" % self._seq,
            source_module=source_module,
            target_module=target_module,
            trigger_layer=trigger_layer,
            reason=reason,
            evidence_refs=list(evidence_refs),
            parent_task_id=parent_task_id,
            research_task_id=research_task_id,
            context_version=context_version,
            changes_research_assumption=changes_research_assumption,
            event_type=event_type,
        )
        self.iterations.append(req)
        return req

    def request_iteration_approval(
        self, req: IterationRequest, channel: str = "NATIVE_CHAT"
    ) -> Dict[str, Any]:
        """Present the iteration to the operator through Core (never silently)."""
        item, should_present, _ = self.core.request_decision(
            key=DecisionKey(req.research_task_id, req.source_module,
                            "iteration_%s" % req.request_id, req.context_version),
            question="%s 发现 %s 层问题，建议回退到 %s：%s。是否授权？" % (
                req.source_module, req.trigger_layer, req.target_module, req.reason),
            options=["授权回退", "仅记录", "拒绝"],
            blocks_module_task_id=req.parent_task_id,
            evidence_refs=req.evidence_refs,
            channel=channel,
        )
        req.approval_decision_id = item["decision_id"]
        return {"decision_id": item["decision_id"], "should_present": should_present}

    def approve_iteration(
        self,
        req: IterationRequest,
        approved: bool,
        answers: Optional[Dict[str, Any]] = None,
        channel: str = "NATIVE_CHAT",
    ) -> Dict[str, Any]:
        """Record the operator's decision in the approval ledger."""
        if not req.approval_decision_id:
            raise ValueError("iteration approval not requested: %s" % req.request_id)
        resolution = "APPROVED" if approved else "REJECTED"
        result = self.core.resolve_decision(
            req.approval_decision_id, resolution, req.context_version,
            answers=answers or {"iteration": req.request_id, "approved": approved},
            channel=channel,
        )
        req.approved = approved
        return result

    def build_child_request(
        self, req: IterationRequest, payload: Optional[Dict[str, Any]] = None
    ) -> DispatchRequest:
        """Build a NEW child DispatchRequest; parent history is preserved."""
        if not req.approved:
            raise ValueError("iteration not approved: %s" % req.request_id)
        parent = self.core._module_tasks.get(req.parent_task_id)
        if parent is None:
            raise KeyError("parent task not found")
        target = ModuleID(req.target_module)
        return DispatchRequest(
            research_task_id=req.research_task_id,
            module_id=target,
            input_refs=parent.input_refs,
            context_version=req.context_version,
            parent_task_id=req.parent_task_id,
            payload=payload or {
                "iteration_reason": req.reason,
                "iteration_source": req.source_module,
                "evidence_refs": req.evidence_refs,
                "changes_research_assumption": req.changes_research_assumption,
            },
        )

    def run_child(
        self, req: IterationRequest, payload: Optional[Dict[str, Any]] = None
    ) -> Tuple[Any, List[str]]:
        """Approve-gated re-dispatch of the target module."""
        child = self.build_child_request(req, payload)
        return self.core.dispatch(child)

    def snapshot(self) -> List[Dict[str, Any]]:
        return [i.to_dict() for i in self.iterations]


__all__ = [
    "InteractionEventType", "FEEDBACK_ROUTES", "IterationRequest",
    "WorkflowOrchestrator",
]
