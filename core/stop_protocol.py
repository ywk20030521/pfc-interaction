"""Mandatory stop protocol: ask before a high-impact choice, never self-authorize.

This is a runtime boundary, not prose advice.  When a formal simulation is
requested with missing critical parameters, the only accepted output is a
``WAITING_FOR_USER`` result whose ``allowed_next_action`` is ``none``.
Formal execution additionally requires a user authorization bound to the
exact research task, decision and model/parameter/matrix versions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .v50_context import ResearchTask
from .v50_decisions import DecisionManager

WAITING_FOR_USER = "WAITING_FOR_USER"
BLOCKED = "BLOCKED"
READY = "READY"

# A formal triaxial/consolidation Run cannot be designed without these.
CRITICAL_PARAMETERS = (
    "experiment_purpose", "boundary_type", "specimen_size",
    "confining_pressure", "loading_endpoint", "parameter_source",
)


@dataclass
class GateResult:
    status: str
    pending_decision_id: str = ""
    question: str = ""
    allowed_next_action: str = "none"
    missing_parameters: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    authorization_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "pending_decision_id": self.pending_decision_id,
            "question": self.question,
            "allowed_next_action": self.allowed_next_action,
            "missing_parameters": list(self.missing_parameters),
            "issues": list(self.issues),
            "authorization_metadata": dict(self.authorization_metadata),
        }


def missing_critical_parameters(context: Dict[str, Any]) -> List[str]:
    """Return the critical fields that are absent or merely assumed."""
    missing: List[str] = []
    for key in CRITICAL_PARAMETERS:
        value = context.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(key)
        elif isinstance(value, dict) and value.get("source") == "agent_assumption":
            missing.append(key)
    return missing


def require_user_decision(
    task: ResearchTask, decisions: DecisionManager,
    context: Dict[str, Any], topic: str = "正式仿真方案确认",
    alternatives: Optional[List[Dict[str, Any]]] = None,
) -> GateResult:
    """Propose a decision and stop.  The proposal is never a user decision."""
    missing = missing_critical_parameters(context)
    if not missing:
        return GateResult(READY, allowed_next_action="request_execution_authorization")
    labels = {
        "experiment_purpose": "教学演示/模型试跑/真实岩样标定",
        "boundary_type": "方形刚壁/圆柱柔性膜",
        "specimen_size": "试样尺寸",
        "confining_pressure": "目标围压",
        "loading_endpoint": "加载终点",
        "parameter_source": "参数来源与依据",
    }
    question_parts = ["请先确认以下未定事项："]
    question_parts.extend("- %s" % labels.get(key, key) for key in missing)
    question_parts.append("请给出至少两个可行方案及选择依据；Agent 的建议不得视为您的决定。")
    alternatives = alternatives or []
    if alternatives:
        question_parts.append("候选方案：")
        question_parts.extend("- %s" % str(a.get("label", a)) for a in alternatives)
    decision = decisions.propose(
        topic=topic,
        content="；".join(labels.get(key, key) for key in missing),
        rationale="关键参数缺失或仅为 Agent 假设，必须先由研究人员确认",
        alternatives=alternatives,
    )
    return GateResult(
        status=WAITING_FOR_USER,
        pending_decision_id=decision.decision_id,
        question="\n".join(question_parts),
        missing_parameters=missing,
        issues=["本轮不得调用 model new / itasca_execute_task 或创建正式 Run"],
    )


def minimum_native_chat_requirements(message: Dict[str, Any]) -> List[str]:
    """Check the irreducible content of a Native Chat clarification turn."""
    issues: List[str] = []
    if not str(message.get("understanding", "")).strip():
        issues.append("缺少当前理解")
    alternatives = message.get("alternatives") or []
    if len(alternatives) < 2:
        issues.append("至少需要两个方案及其影响")
    if not message.get("unresolved_parameters"):
        issues.append("未列出仍未确定的参数")
    questions = message.get("questions") or []
    if not (1 <= len(questions) <= 3):
        issues.append("本轮只能问最关键的一到三个问题")
    if message.get("stopped") is not True:
        issues.append("未结束本轮等待用户回答")
    return issues


@dataclass(frozen=True)
class FormalRunAuthorization:
    """Values that must be copied verbatim into pfc-headless run metadata."""

    authorization_id: str
    research_task_id: str
    decision_id: str
    model_version: str
    parameter_version: str
    matrix_version: str
    assumption_version: str = "v1"
    context_version: str = ""
    scope: str = "run_model"

    def to_headless_args(self) -> Dict[str, str]:
        return {
            "--authorization-id": self.authorization_id,
            "--research-task-id": self.research_task_id,
            "--decision-id": self.decision_id,
            "--model-version": self.model_version,
            "--parameter-version": self.parameter_version,
            "--matrix-version": self.matrix_version,
            "--assumption-version": self.assumption_version,
            "--context-version": self.context_version,
        }


def gate_formal_execution(
    decisions: DecisionManager,
    authorization: FormalRunAuthorization,
    operation: str = "start_formal_simulation",
    target: str = "pfc3d_console",
) -> GateResult:
    """Last in-Process gate before any formal execution request."""
    ok, issues = decisions.validate_authorization(
        authorization.authorization_id, operation, target, authorization.scope,
        authorization.model_version, authorization.parameter_version,
        authorization.matrix_version, authorization.assumption_version,
    )
    if not ok:
        return GateResult(BLOCKED, issues=issues)
    return GateResult(
        READY, allowed_next_action="execute_via_authorized_adapter",
        authorization_metadata=authorization.to_headless_args(),
    )


__all__ = [
    "WAITING_FOR_USER", "BLOCKED", "READY", "CRITICAL_PARAMETERS",
    "GateResult", "missing_critical_parameters", "require_user_decision",
    "minimum_native_chat_requirements", "FormalRunAuthorization",
    "gate_formal_execution",
]
