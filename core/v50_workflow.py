"""PFC Interaction 5.0: six-stage workflow orchestrator.

Implements PFCI-ARCH-5.0 sections 4-6 and technical report sections 3/9.
Stages are user-visible work; M1-M6 are on-demand capabilities and are never
identified with a stage. Rollback carries explicit evidence and impact analysis.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .v50_context import (
    EvidenceItem, EvidenceKind, ResearchTask, STAGE_ARTIFACTS, STAGE_COMPLETION,
    STAGE_MODULE_HINTS, STAGE_ORDER, StageID, StageStatus,
)
from .v50_decisions import DecisionManager

ALLOWED_ROLLBACKS: Dict[StageID, List[StageID]] = {
    StageID.S1: [],
    StageID.S2: [StageID.S1],
    StageID.S3: [StageID.S2],
    StageID.S4: [StageID.S3, StageID.S2],
    StageID.S5: [StageID.S3, StageID.S4],
    StageID.S6: [StageID.S1, StageID.S2, StageID.S3, StageID.S4, StageID.S5],
}


@dataclass
class StageTransition:
    transition_id: str
    from_stage: str
    to_stage: str
    kind: str                       # ENTER / COMPLETE / ROLLBACK / REOPEN
    reason: str
    trigger_evidence: List[Dict[str, Any]] = field(default_factory=list)
    affected_assets: List[str] = field(default_factory=list)
    invalidated_decisions: List[str] = field(default_factory=list)
    artifacts_to_redo: List[str] = field(default_factory=list)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            from .v50_context import _now
            self.created_at = _now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transition_id": self.transition_id, "from_stage": self.from_stage,
            "to_stage": self.to_stage, "kind": self.kind, "reason": self.reason,
            "trigger_evidence": list(self.trigger_evidence),
            "affected_assets": list(self.affected_assets),
            "invalidated_decisions": list(self.invalidated_decisions),
            "artifacts_to_redo": list(self.artifacts_to_redo),
            "created_at": self.created_at,
        }


class WorkflowOrchestrator:
    """Owns stage transitions; never calls a PFC tool directly."""

    def __init__(self, task: ResearchTask, decisions: DecisionManager) -> None:
        self.task = task
        self.decisions = decisions
        self.transitions: List[StageTransition] = []

    def enter(self, stage: StageID) -> StageTransition:
        current = self.task.current_stage
        if stage == current:
            raise ValueError("当前已处于 %s" % stage.value)
        if stage in ALLOWED_ROLLBACKS.get(current, []):
            raise ValueError("回退必须显式调用 rollback() 并提供触发证据")
        expected_next = STAGE_ORDER[STAGE_ORDER.index(current) + 1] \
            if current != StageID.S6 else None
        if stage != expected_next:
            raise ValueError("不能直接从 %s 进入 %s" % (current.value, stage.value))
        trans = StageTransition(
            transition_id="tr-" + uuid.uuid4().hex[:8],
            from_stage=current.value, to_stage=stage.value, kind="ENTER",
            reason="按主线进入下一阶段",
        )
        self.task.current_stage = stage
        self.task.set_stage_status(stage, StageStatus.DISCUSSING, "enter")
        self.transitions.append(trans)
        return trans

    def plan_modules(self, stage: Optional[StageID] = None) -> List[Dict[str, str]]:
        sid = stage or self.task.current_stage
        return [
            {"module_id": mid, "stage_id": sid.value,
             "reason": "按需专业能力；阶段与模块不一一绑定"}
            for mid in STAGE_MODULE_HINTS[sid]
        ]

    def submit_for_review(self, artifacts: Dict[str, str],
                          evidence: Optional[List[EvidenceItem]] = None,
                          unresolved: Optional[List[str]] = None) -> Dict[str, Any]:
        stage = self.task.current_stage
        required = STAGE_ARTIFACTS[stage]
        missing = [a for a in required if not artifacts.get(a)]
        if missing:
            raise ValueError("阶段产物缺失: %s" % ", ".join(missing))
        evs = list(evidence or [])
        for ev in evs:
            self.task.add_evidence(ev)
        if stage in (StageID.S3, StageID.S4, StageID.S5, StageID.S6) and not evs:
            raise ValueError("S3-S6 提交审核必须提供证据")
        self.task.set_stage_status(stage, StageStatus.READY_FOR_REVIEW, "artifacts submitted")
        for name, ref in artifacts.items():
            if not any(a.get("name") == name for a in self.task.artifacts):
                self.task.add_artifact({"name": name, "ref": ref, "stage": stage.value})
        unresolved_items = list(unresolved or [])
        self.task.discussion["unresolved"] = unresolved_items
        self.task.bump_version("review:%s" % stage.value)
        return {"stage": stage.value, "status": StageStatus.READY_FOR_REVIEW.value,
                "artifacts": dict(artifacts), "unresolved": unresolved_items}

    def complete(self, conditions_met: Dict[str, bool], user_confirmed: bool,
                 provisional_assumptions: Optional[List[str]] = None) -> StageTransition:
        stage = self.task.current_stage
        if self.task.stage_status[stage.value] != StageStatus.READY_FOR_REVIEW.value:
            raise ValueError("必须先提交阶段产物审核")
        required = STAGE_COMPLETION[stage]
        missing = [c for c in required if not conditions_met.get(c, False)]
        assumptions = list(provisional_assumptions or [])
        if missing and not (user_confirmed and assumptions):
            raise ValueError("阶段完成条件未满足且未记录暂定假设: %s" % ", ".join(missing))
        if missing:
            self.task.discussion["unresolved"] = sorted(
                set(self.task.discussion.get("unresolved", [])) | set(assumptions))
        trans = StageTransition(
            transition_id="tr-" + uuid.uuid4().hex[:8],
            from_stage=stage.value, to_stage=stage.value, kind="COMPLETE",
            reason="阶段完成条件满足" if not missing else "用户明确要求暂定推进",
            affected_assets=[a for a in STAGE_ARTIFACTS[stage]],
        )
        self.task.set_stage_status(stage, StageStatus.COMPLETED, trans.reason)
        self.transitions.append(trans)
        return trans

    def rollback(self, target: StageID, reason: str,
                 trigger_evidence: List[EvidenceItem],
                 affected_assets: Iterable[str]) -> StageTransition:
        current = self.task.current_stage
        if target not in ALLOWED_ROLLBACKS.get(current, []):
            raise ValueError("禁止从 %s 回退到 %s" % (current.value, target.value))
        if not reason:
            raise ValueError("回退必须说明原因")
        if not trigger_evidence:
            raise ValueError("回退必须提供触发证据")
        for ev in trigger_evidence:
            self.task.add_evidence(ev)
        if all(e.kind in EvidenceKind.non_conclusive() for e in trigger_evidence):
            raise ValueError("回退证据不能只是 Agent 建议或推断")
        assets = list(affected_assets)
        invalidated = self.decisions.invalidate_affected(assets, reason)
        redo = sorted({a for a in assets if a in STAGE_ARTIFACTS[target]})
        trans = StageTransition(
            transition_id="tr-" + uuid.uuid4().hex[:8],
            from_stage=current.value, to_stage=target.value, kind="ROLLBACK",
            reason=reason, trigger_evidence=[e.to_dict() for e in trigger_evidence],
            affected_assets=assets, invalidated_decisions=invalidated,
            artifacts_to_redo=redo,
        )
        self.task.current_stage = target
        self.task.set_stage_status(target, StageStatus.REOPENED, reason)
        self.transitions.append(trans)
        return trans

    def reopen(self, stage: StageID, reason: str) -> StageTransition:
        if not reason:
            raise ValueError("重开阶段必须说明原因")
        trans = StageTransition(
            transition_id="tr-" + uuid.uuid4().hex[:8],
            from_stage=self.task.current_stage.value, to_stage=stage.value,
            kind="REOPEN", reason=reason,
        )
        self.task.current_stage = stage
        self.task.set_stage_status(stage, StageStatus.REOPENED, reason)
        self.transitions.append(trans)
        return trans

    def snapshot(self) -> Dict[str, Any]:
        return {
            "current_stage": self.task.current_stage.value,
            "stage_status": dict(self.task.stage_status),
            "transitions": [t.to_dict() for t in self.transitions],
            "module_plan": self.plan_modules(),
        }


__all__ = ["ALLOWED_ROLLBACKS", "StageTransition", "WorkflowOrchestrator"]
