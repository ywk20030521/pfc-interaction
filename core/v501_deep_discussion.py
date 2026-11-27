"""PFC Interaction 5.0.1: deep discussion engine.

Implements PFCI-HUMAN-5.0.1 sections 2-6 and 15. D2/D3 issues must pass
substantive stages (analysis, alternatives, adversarial review, user feedback,
revision, validation plan) before a structured card is permitted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .v501_issues import IssueStatus, IssueTree


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DepthLevel(str, Enum):
    D0 = "D0"
    D1 = "D1"
    D2 = "D2"
    D3 = "D3"


class DiscussionMode(str, Enum):
    DISCOVERY = "DISCOVERY"
    CLARIFICATION = "CLARIFICATION"
    DESIGN_REVIEW = "DESIGN_REVIEW"
    ADVERSARIAL_REVIEW = "ADVERSARIAL_REVIEW"
    PARAMETER_NEGOTIATION = "PARAMETER_NEGOTIATION"
    INTERPRETATION = "INTERPRETATION"
    RETROSPECTIVE = "RETROSPECTIVE"
    ANOMALY_CONFERENCE = "ANOMALY_CONFERENCE"


SUBSTANTIVE_STAGES = (
    "problem_definition", "candidate_solutions", "adversarial_review",
    "user_feedback", "revision_synthesis", "validation_plan", "source_check",
)

REQUIRED_STAGES: Dict[DepthLevel, List[str]] = {
    DepthLevel.D0: ["source_check"],
    DepthLevel.D1: ["problem_definition", "candidate_solutions", "user_feedback"],
    DepthLevel.D2: ["problem_definition", "candidate_solutions", "adversarial_review",
                    "user_feedback", "revision_synthesis"],
    DepthLevel.D3: ["problem_definition", "candidate_solutions", "adversarial_review",
                    "user_feedback", "revision_synthesis", "validation_plan"],
}
MIN_SUBSTANTIVE_STAGES = {DepthLevel.D0: 1, DepthLevel.D1: 2, DepthLevel.D2: 3,
                          DepthLevel.D3: 5}


@dataclass
class DiscussionCycle:
    issue_id: str
    depth: DepthLevel
    mode: DiscussionMode
    stages: List[Dict[str, Any]] = field(default_factory=list)
    revisions: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=_now)

    def stage_names(self) -> List[str]:
        return [s["stage"] for s in self.stages]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_id": self.issue_id, "depth": self.depth.value,
            "mode": self.mode.value, "stages": list(self.stages),
            "revisions": list(self.revisions), "created_at": self.created_at,
        }


class DeepDiscussionEngine:
    """Maintains one discussion cycle per research issue."""

    def __init__(self, issues: IssueTree) -> None:
        self.issues = issues
        self.cycles: Dict[str, DiscussionCycle] = {}

    def start(self, issue_id: str, depth: DepthLevel,
              mode: DiscussionMode = DiscussionMode.DISCOVERY) -> DiscussionCycle:
        self.issues.get(issue_id)
        if issue_id in self.cycles and self.cycles[issue_id].stages:
            raise ValueError("议题已有讨论记录，使用现有 cycle 继续")
        cycle = DiscussionCycle(issue_id, depth, mode)
        self.cycles[issue_id] = cycle
        issue = self.issues.get(issue_id)
        issue.set_status(IssueStatus.UNDER_DISCUSSION, "开始深度讨论")
        return cycle

    def record_stage(self, issue_id: str, stage: str, contribution: str,
                     evidence_refs: Optional[List[str]] = None,
                     alternatives: Optional[List[Dict[str, Any]]] = None,
                     counterexample: str = "", user_feedback: str = "",
                     revision: str = "", validation_plan: str = "",
                     next_step: str = "") -> Dict[str, Any]:
        if stage not in SUBSTANTIVE_STAGES:
            raise ValueError("未知实质阶段: %s" % stage)
        if not contribution.strip():
            raise ValueError("每轮讨论必须有实质性专业贡献")
        if stage == "adversarial_review" and not (alternatives or counterexample):
            raise ValueError("反方审查必须给出替代方案或反例")
        if stage == "user_feedback" and not user_feedback:
            raise ValueError("用户反馈阶段必须记录真实用户意见")
        if stage == "revision_synthesis" and not revision:
            raise ValueError("修订综合必须说明方案如何变化，不能只追加备注")
        if stage == "validation_plan" and not validation_plan:
            raise ValueError("验证计划必须说明需要什么证据")
        cycle = self.cycles.get(issue_id)
        if cycle is None:
            raise KeyError("议题尚未开始深度讨论: %s" % issue_id)
        record = {
            "stage": stage, "contribution": contribution,
            "evidence_refs": list(evidence_refs or []),
            "alternatives": list(alternatives or []),
            "counterexample": counterexample, "user_feedback": user_feedback,
            "revision": revision, "validation_plan": validation_plan,
            "next_step": next_step, "is_substantive": True, "at": _now(),
        }
        cycle.stages.append(record)
        if revision:
            cycle.revisions.append({
                "revision": revision, "based_on": len(cycle.stages), "at": _now(),
            })
            self.issues.get(issue_id).set_status(
                IssueStatus.PROVISIONAL, "讨论产生方案修订: %s" % revision[:40])
        return record

    def apply_user_correction(self, issue_id: str, original: str,
                              corrected: str, reason: str) -> Dict[str, Any]:
        """Record that a user correction changed the plan, not just a note."""
        correction = {
            "original": original, "corrected": corrected, "reason": reason,
            "at": _now(),
        }
        cycle = self.cycles.get(issue_id)
        if cycle is None:
            raise KeyError("议题尚未开始深度讨论: %s" % issue_id)
        cycle.revisions.append(correction)
        self.record_stage(
            issue_id, "user_feedback",
            "用户修正方案: %s；Agent 接受并检查影响" % corrected[:40],
            user_feedback=corrected,
            revision="由「%s」修订为「%s」" % (original[:40], corrected[:40]),
        )
        return correction

    def gate(self, issue_id: str) -> Dict[str, Any]:
        cycle = self.cycles.get(issue_id)
        if cycle is None:
            return {"ready": False, "missing": ["尚未开始深度讨论"], "depth": None}
        required = REQUIRED_STAGES[cycle.depth]
        names = set(cycle.stage_names())
        missing = [stage for stage in required if stage not in names]
        if len(names) < MIN_SUBSTANTIVE_STAGES[cycle.depth]:
            missing.append("实质阶段不足 %d" % MIN_SUBSTANTIVE_STAGES[cycle.depth])
        if cycle.depth in (DepthLevel.D2, DepthLevel.D3):
            if "adversarial_review" not in names:
                missing.append("缺少反方审查")
            if not cycle.revisions:
                missing.append("缺少基于反馈的方案修订")
        return {
            "ready": not missing, "issue_id": issue_id, "depth": cycle.depth.value,
            "missing": missing, "stages": sorted(names),
            "revision_count": len(cycle.revisions),
            "note": "按实质阶段检查，不按问题数量或对话轮数检查",
        }

    def can_card(self, issue_id: str) -> Dict[str, Any]:
        gate = self.gate(issue_id)
        if not gate["ready"]:
            raise ValueError(
                "D2/D3 议题未达到卡片化门槛: %s 缺少 %s"
                % (issue_id, ", ".join(gate["missing"])))
        return gate

    def summary(self, issue_id: str) -> Dict[str, Any]:
        gate = self.gate(issue_id)
        cycle = self.cycles[issue_id]
        return {
            **gate,
            "mode": cycle.mode.value,
            "stage_sequence": cycle.stage_names(),
            "revisions": list(cycle.revisions),
            "maturity_suggestion": (
                "PLANNED_FOR_VALIDATION" if gate["ready"] and
                "validation_plan" in gate["stages"] else "ARGUED"
                if gate["ready"] else "UNRESOLVED"),
        }

    def snapshot(self) -> Dict[str, Any]:
        return {iid: cycle.to_dict() for iid, cycle in self.cycles.items()}


__all__ = [
    "DepthLevel", "DiscussionMode", "SUBSTANTIVE_STAGES", "DiscussionCycle",
    "DeepDiscussionEngine",
]
