"""M1 Research Planning - first batch module.

IF0 contract fields:
  research_objective, research_scope, hypotheses[], independent_vars[],
  dependent_vars[], control_vars[], constraints[], expected_outputs[],
  fact_vs_suggestion[], confirmation_state

Standard outputs (report section 4.1.4):
  research_question.md, research_plan.md, research_hypotheses.md,
  research_workflow.md, research_requirements.json

Important: M1 never auto-confirms a plan. Unconfirmed information is represented
as Agent suggestion / pending assumption, and the module stays WAITING_FOR_USER.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core import (
    ArtifactRef,
    DecisionKey,
    DispatchRequest,
    Envelope,
    Evidence,
    EvidenceSource,
    ModuleID,
    ModuleState,
    CoreDispatcher,
)

MODULE_VERSION = "0.1.0"
MODULE_ID = ModuleID.M1


@dataclass
class ResearchRequirements:
    research_objective: str = ""
    research_scope: str = ""
    hypotheses: List[str] = field(default_factory=list)
    independent_vars: List[str] = field(default_factory=list)
    dependent_vars: List[str] = field(default_factory=list)
    control_vars: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    expected_outputs: List[str] = field(default_factory=list)
    fact_vs_suggestion: List[Dict[str, Any]] = field(default_factory=list)
    confirmation_state: str = "UNCONFIRMED"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchRequirements":
        return cls(
            research_objective=str(data.get("research_objective", "")),
            research_scope=str(data.get("research_scope", "")),
            hypotheses=list(data.get("hypotheses", [])),
            independent_vars=list(data.get("independent_vars", [])),
            dependent_vars=list(data.get("dependent_vars", [])),
            control_vars=list(data.get("control_vars", [])),
            constraints=list(data.get("constraints", [])),
            expected_outputs=list(data.get("expected_outputs", [])),
            fact_vs_suggestion=list(data.get("fact_vs_suggestion", [])),
            confirmation_state=str(data.get("confirmation_state", "UNCONFIRMED")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "research_objective": self.research_objective,
            "research_scope": self.research_scope,
            "hypotheses": self.hypotheses,
            "independent_vars": self.independent_vars,
            "dependent_vars": self.dependent_vars,
            "control_vars": self.control_vars,
            "constraints": self.constraints,
            "expected_outputs": self.expected_outputs,
            "fact_vs_suggestion": self.fact_vs_suggestion,
            "confirmation_state": self.confirmation_state,
        }

    def validate(self) -> List[str]:
        """IF0 section 4.2 + report section 4.1.5 completeness rules."""
        errors: List[str] = []
        if not self.research_objective:
            errors.append("research_objective is required")
        if not self.dependent_vars:
            errors.append("dependent_vars is required (response metrics)")
        if not self.independent_vars:
            errors.append("independent_vars is required (study variables)")
        if not self.fact_vs_suggestion:
            errors.append(
                "fact_vs_suggestion is required; user facts and agent suggestions must be separated"
            )
        for item in self.fact_vs_suggestion:
            origin = item.get("origin")
            if origin not in ("user_provided", "agent_inferred"):
                errors.append("fact_vs_suggestion origin must be user_provided or agent_inferred")
            if origin == "agent_inferred" and not item.get("evidence_ref"):
                errors.append("agent suggestion must reference evidence")
        if self.confirmation_state not in ("UNCONFIRMED", "CONFIRMED"):
            errors.append("invalid confirmation_state")
        return errors

    def missing_for_confirmation(self) -> List[str]:
        missing: List[str] = []
        if not self.research_scope:
            missing.append("research_scope")
        if not self.hypotheses:
            missing.append("hypotheses")
        if any(i.get("origin") == "agent_inferred" for i in self.fact_vs_suggestion):
            missing.append("agent suggestions require user confirmation")
        return missing


def render_documents(req: ResearchRequirements) -> Dict[str, str]:
    """Render the five standard markdown/json outputs from structured requirements."""
    def bullet(items: List[str]) -> str:
        return "\n".join("- %s" % i for i in items) if items else "- （未明确，待澄清）"

    origin_lines = "\n".join(
        "- [%s] %s%s"
        % (
            i.get("origin", "?"),
            i.get("claim", ""),
            "（依据：%s）" % i.get("evidence_ref") if i.get("evidence_ref") else "",
        )
        for i in req.fact_vs_suggestion
    )

    question = "# 研究问题\n\n## 研究目标\n%s\n\n## 研究范围\n%s\n\n## 主要科学问题\n%s\n" % (
        req.research_objective or "（待明确）",
        req.research_scope or "（待明确）",
        bullet(req.hypotheses),
    )
    plan = "# 研究计划\n\n## 自变量\n%s\n\n## 因变量\n%s\n\n## 控制变量\n%s\n\n## 约束条件\n%s\n\n## 预期成果\n%s\n\n## 确认状态\n%s\n" % (
        bullet(req.independent_vars),
        bullet(req.dependent_vars),
        bullet(req.control_vars),
        bullet(req.constraints),
        bullet(req.expected_outputs),
        req.confirmation_state,
    )
    hypotheses = "# 研究假设\n\n%s\n\n## 待确认假设\n%s\n" % (
        bullet(req.hypotheses),
        "\n".join(
            "- %s" % i.get("claim")
            for i in req.fact_vs_suggestion
            if i.get("origin") == "agent_inferred"
        ) or "- 无",
    )
    workflow = "# 研究路线\n\n1. M1 研究规划（本阶段）\n2. 用户确认研究计划\n3. M2 实验设计\n4. M3 数值建模\n5. M4–M6（第二批）\n\n> 进入 M2 的前置条件：研究计划获研究人员确认。\n"
    return {
        "research_question.md": question,
        "research_plan.md": plan,
        "research_hypotheses.md": hypotheses,
        "research_workflow.md": workflow,
    }


def run(module_task_id: str, request: DispatchRequest, core: CoreDispatcher) -> Envelope:
    """M1 runner (I1/I2). Input is a dict with key 'research_requirements'."""
    data = request.payload or {}
    req = ResearchRequirements.from_dict(data.get("research_requirements", {}))
    errors = req.validate()
    if errors:
        return Envelope(
            module_id=MODULE_ID,
            module_version=MODULE_VERSION,
            research_task_id=request.research_task_id,
            module_task_id=module_task_id,
            parent_task_id=request.parent_task_id,
            input_refs=request.input_refs,
            status={"module_state": ModuleState.BLOCKED.value},
            output={
                "structured": req.to_dict(),
                "artifacts": [],
                "verified_by_execution": False,
            },
            evidence=[
                Evidence(EvidenceSource.USER_PROVIDED, "user-input", "M1 structured input")
            ],
            limitations=errors,
        )

    key = DecisionKey(
        experiment_id=request.research_task_id,
        stage_id="M1",
        topic="确认研究计划",
        context_version=request.context_version,
    )
    decision, should_present, _reason = core.request_decision(
        key=key,
        question="是否确认以下研究计划并进入实验设计？目标：%s" % req.research_objective,
        options=["确认，进入 M2", "需要修改", "暂缓"],
        blocks_module_task_id=module_task_id,
        evidence_refs=["user-input"],
        authorization_scope=None,  # Confirmation is NOT execution authorization.
    )
    scope = {
        "module_state": (
            ModuleState.WAITING_FOR_USER.value
            if should_present
            else ModuleState.COMPLETED.value
        )
    }
    docs = render_documents(req)
    artifacts: List[Dict[str, Any]] = []
    for name, text in docs.items():
        ref = core.store.write("m1_" + name.replace(".", "_"), name, text)
        artifacts.append(ref.to_dict())
    json_ref = core.store.write_json("m1_research_requirements", "research_requirements.json", req.to_dict())
    artifacts.append(json_ref.to_dict())

    return Envelope(
        module_id=MODULE_ID,
        module_version=MODULE_VERSION,
        research_task_id=request.research_task_id,
        module_task_id=module_task_id,
        parent_task_id=request.parent_task_id,
        input_refs=request.input_refs,
        status=scope,
        output={
            "structured": req.to_dict(),
            "artifacts": artifacts,
            "verified_by_execution": False,
        },
        evidence=[
            Evidence(EvidenceSource.USER_PROVIDED, "user-input", "研究目标与变量来自用户"),
            Evidence(EvidenceSource.AGENT_INFERRED, "m1-plan", "研究路线由 Agent 建议"),
        ],
        decisions=[
            {
                "decision_id": decision["decision_id"],
                "delivery_status": decision["delivery_status"],
            }
        ],
        limitations=req.missing_for_confirmation(),
    )
