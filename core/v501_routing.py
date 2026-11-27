"""PFC Interaction 5.0.1: automatic discussion-mode routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .v501_deep_discussion import DiscussionMode
from .v501_issues import IssueStatus, IssueType


@dataclass(frozen=True)
class ModeRoute:
    mode: DiscussionMode
    reason: str

    def to_dict(self) -> Dict[str, str]:
        return {"mode": self.mode.value, "reason": self.reason}


_TYPE_ROUTES = {
    IssueType.SCIENTIFIC_QUESTION: DiscussionMode.DISCOVERY,
    IssueType.MECHANISM: DiscussionMode.DISCOVERY,
    IssueType.HYPOTHESIS: DiscussionMode.ADVERSARIAL_REVIEW,
    IssueType.EXPERIMENT_DESIGN: DiscussionMode.DESIGN_REVIEW,
    IssueType.CONTROL_AND_COMPARISON: DiscussionMode.DESIGN_REVIEW,
    IssueType.MODEL_SELECTION: DiscussionMode.DESIGN_REVIEW,
    IssueType.BOUNDARY_CONDITION: DiscussionMode.DESIGN_REVIEW,
    IssueType.PARAMETER: DiscussionMode.PARAMETER_NEGOTIATION,
    IssueType.CALIBRATION: DiscussionMode.PARAMETER_NEGOTIATION,
    IssueType.MEASUREMENT: DiscussionMode.CLARIFICATION,
    IssueType.NUMERICAL_RISK: DiscussionMode.ANOMALY_CONFERENCE,
    IssueType.ANOMALY: DiscussionMode.ANOMALY_CONFERENCE,
    IssueType.DATA_QUALITY: DiscussionMode.ANOMALY_CONFERENCE,
    IssueType.INTERPRETATION: DiscussionMode.INTERPRETATION,
    IssueType.LIMITATION: DiscussionMode.INTERPRETATION,
    IssueType.NEXT_STUDY: DiscussionMode.RETROSPECTIVE,
}


def recommend_mode(issue: Any, cycle: Optional[Any] = None,
                   stage: Optional[str] = None) -> ModeRoute:
    """Choose a discussion mode from issue type, state and current evidence need."""
    issue_type = issue.issue_type if hasattr(issue, "issue_type") else IssueType(issue["issue_type"])
    status = issue.status if hasattr(issue, "status") else IssueStatus(issue["status"])
    stage_id = stage or (issue.stage_id if hasattr(issue, "stage_id") else "S1")

    if status in (IssueStatus.NEEDS_EVIDENCE, IssueStatus.NEEDS_USER_INPUT):
        return ModeRoute(DiscussionMode.CLARIFICATION, "议题缺少证据或用户输入，先澄清")
    if stage_id == "S6" and issue_type not in (IssueType.ANOMALY, IssueType.NUMERICAL_RISK):
        return ModeRoute(DiscussionMode.INTERPRETATION, "结果阶段优先解释与边界审查")
    mode = _TYPE_ROUTES.get(issue_type, DiscussionMode.DISCOVERY)
    reason = "按议题类型路由到 %s" % mode.value
    if cycle is not None and getattr(cycle, "revisions", None):
        if mode == DiscussionMode.DESIGN_REVIEW:
            return ModeRoute(DiscussionMode.ADVERSARIAL_REVIEW,
                             "方案已修订，转入反方审查避免过早收敛")
    return ModeRoute(mode, reason)


__all__ = ["ModeRoute", "recommend_mode"]
