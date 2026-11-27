"""PFC Interaction 5.0.1: change impact, review gate and issue reopening."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from .v501_issues import IssueStatus, IssueTree


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ChangeRecord:
    change_id: str
    reason: str
    changed_assets: List[str]
    evidence_refs: List[str]
    invalidated_decisions: List[str] = field(default_factory=list)
    invalidated_issues: List[str] = field(default_factory=list)
    reopened_issues: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_id": self.change_id, "reason": self.reason,
            "changed_assets": list(self.changed_assets),
            "evidence_refs": list(self.evidence_refs),
            "invalidated_decisions": list(self.invalidated_decisions),
            "invalidated_issues": list(self.invalidated_issues),
            "reopened_issues": list(self.reopened_issues),
            "created_at": self.created_at,
        }


class ChangeManager:
    """Records evidence-driven changes and their affected decisions/issues."""

    def __init__(self, issues: IssueTree, decisions: Any = None,
                 evidence: Any = None) -> None:
        self.issues = issues
        self.decisions = decisions
        self.evidence = evidence
        self.changes: List[ChangeRecord] = []

    def analyze(self, reason: str, changed_assets: Iterable[str],
                evidence_refs: List[str],
                reopen_issue_ids: Optional[Iterable[str]] = None) -> ChangeRecord:
        if not reason:
            raise ValueError("变更必须说明原因")
        if not evidence_refs:
            raise ValueError("变更影响分析必须提供触发证据")
        assets = list(changed_assets)
        record = ChangeRecord(
            change_id="chg-" + uuid.uuid4().hex[:8], reason=reason,
            changed_assets=assets, evidence_refs=list(evidence_refs),
        )
        if self.decisions is not None and hasattr(self.decisions, "invalidate_affected"):
            record.invalidated_decisions = list(
                self.decisions.invalidate_affected(assets, reason))
        if self.evidence is not None and hasattr(self.evidence, "get"):
            for ref in evidence_refs:
                self.evidence.get(ref)
        record.invalidated_issues = self.issues.invalidate_affected(assets, reason)
        for issue_id in reopen_issue_ids or []:
            self.issues.reopen(issue_id, reason, evidence_refs)
            record.reopened_issues.append(issue_id)
        self.changes.append(record)
        return record

    def review_gate(self, issue_id: str, discussion_engine: Any,
                    target_status: IssueStatus) -> Dict[str, Any]:
        """DECIDED/VALIDATED cannot bypass deep-discussion review."""
        issue = self.issues.get(issue_id)
        if target_status in (IssueStatus.DECIDED, IssueStatus.VALIDATED,
                             IssueStatus.PROVISIONAL):
            gate = discussion_engine.gate(issue_id)
            if not gate["ready"]:
                return {"allowed": False, "gate": gate,
                        "reason": "深度讨论门槛未满足，不能进入 %s" % target_status.value}
        if target_status == IssueStatus.VALIDATED and not issue.evidence_refs:
            return {"allowed": False, "gate": None,
                    "reason": "VALIDATED 必须关联证据引用"}
        return {"allowed": True, "gate": None, "reason": "审查通过"}

    def snapshot(self) -> Dict[str, Any]:
        return {"changes": [c.to_dict() for c in self.changes]}


__all__ = ["ChangeRecord", "ChangeManager"]
