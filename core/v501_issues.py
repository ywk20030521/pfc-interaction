"""PFC Interaction 5.0.1: research issue tree and backlog.

Implements PFCI-ARCH-5.0.1 sections 4/7/8 and PFCI-HUMAN-5.0.1 section 8.
An issue is the durable unit of research, not a single question or a card.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class IssueType(str, Enum):
    SCIENTIFIC_QUESTION = "SCIENTIFIC_QUESTION"
    MECHANISM = "MECHANISM"
    HYPOTHESIS = "HYPOTHESIS"
    EXPERIMENT_DESIGN = "EXPERIMENT_DESIGN"
    CONTROL_AND_COMPARISON = "CONTROL_AND_COMPARISON"
    MODEL_SELECTION = "MODEL_SELECTION"
    BOUNDARY_CONDITION = "BOUNDARY_CONDITION"
    PARAMETER = "PARAMETER"
    CALIBRATION = "CALIBRATION"
    MEASUREMENT = "MEASUREMENT"
    NUMERICAL_RISK = "NUMERICAL_RISK"
    ANOMALY = "ANOMALY"
    DATA_QUALITY = "DATA_QUALITY"
    INTERPRETATION = "INTERPRETATION"
    LIMITATION = "LIMITATION"
    NEXT_STUDY = "NEXT_STUDY"


class IssueStatus(str, Enum):
    OPEN = "OPEN"
    UNDER_DISCUSSION = "UNDER_DISCUSSION"
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"
    NEEDS_USER_INPUT = "NEEDS_USER_INPUT"
    PROVISIONAL = "PROVISIONAL"
    DECIDED = "DECIDED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"
    REOPENED = "REOPENED"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"


class IssuePriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"

    @classmethod
    def order(cls) -> List[str]:
        return [p.value for p in cls]


CLOSED_STATUSES = {
    IssueStatus.DECIDED, IssueStatus.VALIDATED, IssueStatus.REJECTED,
    IssueStatus.SUPERSEDED, IssueStatus.INVALIDATED,
}


@dataclass
class ResearchIssue:
    issue_id: str
    title: str
    issue_type: IssueType
    status: IssueStatus = IssueStatus.OPEN
    priority: IssuePriority = IssuePriority.P1
    parent_id: Optional[str] = None
    stage_id: str = "S1"
    dependencies: List[str] = field(default_factory=list)
    evidence_needs: List[str] = field(default_factory=list)
    owner_module: str = "Core"
    next_action: str = ""
    evidence_refs: List[str] = field(default_factory=list)
    version: int = 1
    history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.history:
            self.history.append({
                "event": "CREATED", "status": self.status.value,
                "reason": "议题建立", "version": self.version, "at": self.created_at,
            })

    def set_status(self, status: IssueStatus, reason: str,
                   evidence_refs: Optional[List[str]] = None) -> None:
        if status == IssueStatus.VALIDATED and not evidence_refs:
            raise ValueError("VALIDATED 议题必须提供证据引用")
        self.status = status
        if evidence_refs:
            self.evidence_refs = sorted(set(self.evidence_refs) | set(evidence_refs))
        self.history.append({
            "event": "STATUS", "status": status.value, "reason": reason,
            "evidence_refs": list(evidence_refs or []), "version": self.version,
            "at": _now(),
        })

    def reopen(self, reason: str, evidence_refs: List[str]) -> None:
        if not evidence_refs:
            raise ValueError("重开议题必须提供触发证据")
        self.status = IssueStatus.REOPENED
        self.evidence_refs = sorted(set(self.evidence_refs) | set(evidence_refs))
        self.version += 1
        self.history.append({
            "event": "REOPENED", "reason": reason, "evidence_refs": list(evidence_refs),
            "version": self.version, "at": _now(),
        })

    def invalidate(self, reason: str, evidence_refs: Optional[List[str]] = None) -> None:
        self.status = IssueStatus.INVALIDATED
        self.history.append({
            "event": "INVALIDATED", "reason": reason,
            "evidence_refs": list(evidence_refs or []), "version": self.version,
            "at": _now(),
        })

    def supersede(self, new_issue_id: str, reason: str) -> None:
        self.status = IssueStatus.SUPERSEDED
        self.history.append({
            "event": "SUPERSEDED", "by": new_issue_id, "reason": reason,
            "version": self.version, "at": _now(),
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_id": self.issue_id, "title": self.title,
            "issue_type": self.issue_type.value, "status": self.status.value,
            "priority": self.priority.value, "parent_id": self.parent_id,
            "stage_id": self.stage_id, "dependencies": list(self.dependencies),
            "evidence_needs": list(self.evidence_needs),
            "owner_module": self.owner_module, "next_action": self.next_action,
            "evidence_refs": list(self.evidence_refs), "version": self.version,
            "history": list(self.history), "created_at": self.created_at,
        }


class IssueTree:
    """Research issue tree with dependency and reopen semantics."""

    def __init__(self, research_task_id: str) -> None:
        self.research_task_id = research_task_id
        self.issues: Dict[str, ResearchIssue] = {}

    def create(self, title: str, issue_type: IssueType,
               priority: IssuePriority = IssuePriority.P1,
               parent_id: Optional[str] = None,
               stage_id: str = "S1", dependencies: Optional[Iterable[str]] = None,
               evidence_needs: Optional[Iterable[str]] = None,
               owner_module: str = "Core", next_action: str = "") -> ResearchIssue:
        if parent_id and parent_id not in self.issues:
            raise KeyError("父议题不存在: %s" % parent_id)
        issue = ResearchIssue(
            issue_id="iss-" + uuid.uuid4().hex[:8], title=title,
            issue_type=issue_type, priority=priority, parent_id=parent_id,
            stage_id=stage_id, dependencies=list(dependencies or []),
            evidence_needs=list(evidence_needs or []),
            owner_module=owner_module, next_action=next_action,
        )
        self.issues[issue.issue_id] = issue
        return issue

    def get(self, issue_id: str) -> ResearchIssue:
        if issue_id not in self.issues:
            raise KeyError("议题不存在: %s" % issue_id)
        return self.issues[issue_id]

    def children(self, issue_id: Optional[str] = None) -> List[ResearchIssue]:
        return [i for i in self.issues.values() if i.parent_id == issue_id]

    def depend_on(self, issue_id: str, dependency_id: str) -> None:
        issue = self.get(issue_id)
        self.get(dependency_id)
        if dependency_id == issue_id or dependency_id in issue.dependencies:
            return
        # Reject a direct cycle; deeper chains are left to review, not silently pruned.
        other = self.get(dependency_id)
        if issue_id in other.dependencies:
            raise ValueError("议题依赖形成直接环路")
        issue.dependencies.append(dependency_id)

    def reopen(self, issue_id: str, reason: str, evidence_refs: List[str]) -> ResearchIssue:
        issue = self.get(issue_id)
        issue.reopen(reason, evidence_refs)
        for child in self.children(issue_id):
            if child.status not in CLOSED_STATUSES:
                child.set_status(IssueStatus.REOPENED, "父议题重开: %s" % reason)
        return issue

    def invalidate_affected(self, changed_assets: Iterable[str],
                            reason: str) -> List[str]:
        changed = set(changed_assets)
        affected: List[str] = []
        for issue in self.issues.values():
            if changed.intersection(issue.evidence_needs):
                issue.invalidate(reason, sorted(changed))
                affected.append(issue.issue_id)
        return affected

    def backlog(self, priorities: Optional[Iterable[str]] = None,
                include_provisional: bool = False) -> List[ResearchIssue]:
        wanted = set(priorities or IssuePriority.order())
        result = [
            i for i in self.issues.values()
            if i.priority.value in wanted and i.status not in CLOSED_STATUSES
            and (include_provisional or i.status != IssueStatus.PROVISIONAL)
        ]
        return sorted(result, key=lambda i: (IssuePriority.order().index(i.priority.value),
                                             i.created_at))

    def snapshot(self) -> Dict[str, Any]:
        return {
            "research_task_id": self.research_task_id,
            "issues": [i.to_dict() for i in self.issues.values()],
            "backlog": [i.issue_id for i in self.backlog()],
        }


__all__ = [
    "IssueType", "IssueStatus", "IssuePriority", "ResearchIssue", "IssueTree",
    "CLOSED_STATUSES",
]
