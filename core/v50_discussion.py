"""PFC Interaction 5.0: discussion manager and reasoning/proposal rules.

Implements PFCI-HUMAN-5.0 sections 3-6 and technical report 6.2-6.5.
There is deliberately no fixed question count and no automatic stage advance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .v50_context import (
    EvidenceItem, EvidenceKind, ResearchTask, STAGE_COMPLETION, StageID,
)


@dataclass
class ProposalOption:
    name: str
    description: str
    applicability: str
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    recommended: bool = False

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self.name or not self.description or not self.applicability:
            errors.append("备选方案必须说明名称、内容与适用条件: %s" % self.name)
        if not self.pros or not self.cons:
            errors.append("备选方案必须比较优缺点: %s" % self.name)
        if self.recommended and not self.evidence_refs:
            errors.append("推荐方案必须有依据: %s" % self.name)
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "description": self.description,
            "applicability": self.applicability, "pros": list(self.pros),
            "cons": list(self.cons), "evidence_refs": list(self.evidence_refs),
            "recommended": self.recommended,
        }


def make_proposal(observation: str, rationale: str, options: List[ProposalOption],
                  risks: List[str], needs_evidence: List[str],
                  user_viewpoint: Optional[str] = None,
                  understanding: Optional[str] = None) -> Dict[str, Any]:
    """Reasoning & Proposal: evidence-grounded alternatives, never blind contradiction."""
    errors: List[str] = []
    if not observation:
        errors.append("缺少观察事实")
    if not rationale:
        errors.append("缺少专业分析依据")
    if len(options) < 2:
        errors.append("存在真实替代路线时至少给出两个方案")
    for opt in options:
        errors.extend(opt.validate())
    if user_viewpoint and not understanding:
        errors.append("用户提出观点后必须先复述和理解，再提出建议")
    if errors:
        raise ValueError("方案建议质量检查未通过: %s" % "; ".join(errors))
    return {
        "observation": observation, "rationale": rationale,
        "alternatives": [o.to_dict() for o in options], "risks": list(risks),
        "needs_evidence": list(needs_evidence),
        "user_viewpoint": user_viewpoint, "understanding": understanding,
        "source": "agent_proposal",
    }


# Content dimensions required BEFORE a discussion item is turned into a card.
# These are dimensions of analysis, never a fixed question count or round count.
DEPTH_PROFILES: Dict[str, Dict[str, int]] = {
    "default": {
        "understanding": 1, "analysis": 1, "evidence_or_assumption": 1,
        "alternatives": 1, "impact": 1,
    },
    "high_stakes": {
        "understanding": 1, "analysis": 1, "evidence_or_assumption": 1,
        "alternatives": 2, "impact": 1,
    },
    "authorization": {
        "understanding": 1, "analysis": 1, "evidence_or_assumption": 1,
        "impact": 1,
    },
}


class DiscussionManager:
    """Maintains the live discussion topic, positions, alternatives and open points."""

    def __init__(self, task: ResearchTask) -> None:
        self.task = task
        self.turns: List[Dict[str, Any]] = []
        self.proposals: List[Dict[str, Any]] = []

    def add_turn(self, topic: str, *, understanding: str = "", analysis: str = "",
                 evidence: Optional[List[EvidenceItem]] = None,
                 assumptions: Optional[List[str]] = None,
                 alternatives: Optional[List[Dict[str, Any]]] = None,
                 impact: Optional[List[str]] = None,
                 disagreements: Optional[List[str]] = None,
                 next_step: str = "", question: str = "") -> Dict[str, Any]:
        """Question-only turns are forbidden: analysis must precede more questions."""
        if not topic or not next_step:
            raise ValueError("每轮讨论必须有主题和下一步")
        if not (analysis or alternatives or impact):
            raise ValueError("不得用没有专业分析的连续追问代替讨论")
        if question and not analysis:
            raise ValueError("追问前必须先给出当前理解与专业分析")
        turn = {
            "topic": topic, "understanding": understanding, "analysis": analysis,
            "evidence": [e.to_dict() for e in (evidence or [])],
            "assumptions": list(assumptions or []),
            "alternatives": list(alternatives or []),
            "impact": list(impact or []),
            "disagreements": list(disagreements or []),
            "next_step": next_step, "question": question,
        }
        self.turns.append(turn)
        self.task.discussion["current_topic"] = topic
        for item in assumptions or []:
            if item not in self.task.discussion["unresolved"]:
                self.task.discussion["unresolved"].append(item)
        for item in disagreements or []:
            if item not in self.task.discussion["unresolved"]:
                self.task.discussion["unresolved"].append(item)
        self.task.bump_version("discussion:%s" % topic)
        return turn

    def respond_to_user(self, viewpoint: str, understanding: str, analysis: str,
                        impact: List[str], alternatives: Optional[List[Dict[str, Any]]] = None,
                        next_step: str = "", question: str = "") -> Dict[str, Any]:
        """Analyse the user's position before asking anything else."""
        if not viewpoint or not understanding or not analysis:
            raise ValueError("用户提出观点后必须先复述理解并给出专业分析")
        return self.add_turn(
            topic="用户观点: %s" % viewpoint[:20], understanding=understanding,
            analysis=analysis, impact=impact, alternatives=alternatives,
            next_step=next_step or "请用户确认分析结果或补充约束", question=question,
        )

    def gate_for_card(self, topic: str, profile: str = "default") -> Dict[str, Any]:
        """Check analysis depth BEFORE structuring a topic into a card.

        Deep discussion is content-based: understanding, professional analysis,
        evidence/assumptions, alternatives and impact. No question count is used.
        """
        required = DEPTH_PROFILES.get(profile)
        if required is None:
            raise ValueError("未知讨论深度档位: %s" % profile)
        related = [
            t for t in self.turns
            if t.get("topic") == topic or topic in t.get("topic", "")
            or t.get("topic", "") in topic
        ]
        supplied = {
            "understanding": sum(1 for t in related if t.get("understanding")),
            "analysis": sum(1 for t in related if t.get("analysis")),
            "evidence_or_assumption": sum(
                1 for t in related if t.get("evidence") or t.get("assumptions")),
            "alternatives": sum(len(t.get("alternatives") or []) for t in related),
            "impact": sum(len(t.get("impact") or []) for t in related),
        }
        missing = [
            "%s(%d/%d)" % (dim, supplied.get(dim, 0), need)
            for dim, need in required.items() if supplied.get(dim, 0) < need
        ]
        return {
            "ready": not missing, "topic": topic, "profile": profile,
            "missing": missing, "supplied": supplied,
            "related_turns": len(related),
            "note": "讨论深度按分析维度检查，不按问题数量检查",
        }

    def require_depth(self, topic: str, profile: str = "default") -> Dict[str, Any]:
        gate = self.gate_for_card(topic, profile)
        if not gate["ready"]:
            raise ValueError(
                "讨论深度不足，禁止生成卡片：%s 缺少 %s"
                % (topic, ", ".join(gate["missing"])))
        return gate

    def add_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        self.proposals.append(proposal)
        self.task.discussion["alternatives"] = [
            o["name"] for p in self.proposals for o in p.get("alternatives", [])
        ]
        self.task.bump_version("proposal")
        return proposal

    def resolve(self, item: str, resolution: str) -> None:
        unresolved = self.task.discussion.get("unresolved", [])
        self.task.discussion["unresolved"] = [x for x in unresolved if x != item]
        key = "confirmed" if resolution.lower().startswith("confirm") else "rejected"
        bucket = self.task.discussion.setdefault(key, [])
        if item not in bucket:
            bucket.append(item)
        self.task.bump_version("resolve:%s" % item)

    def stage_summary(self, stage: Optional[StageID] = None) -> Dict[str, Any]:
        confirmed_decisions = [
            d.topic for d in self.task.decisions.values()
            if d.status.value == "CONFIRMED" and (stage is None or d.stage_id == stage.value)
        ]
        suggestions = [
            d.topic for d in self.task.decisions.values()
            if d.status.value in ("PROPOSED", "DISCUSSING", "DEFERRED")
            and (stage is None or d.stage_id == stage.value)
        ]
        risks: List[str] = []
        for turn in self.turns:
            risks.extend(turn.get("impact", []))
        return {
            "confirmed": confirmed_decisions + list(self.task.discussion.get("confirmed", [])),
            "agent_suggestions_not_confirmed": suggestions,
            "unresolved": list(self.task.discussion.get("unresolved", [])),
            "assumptions_in_use": list(self.task.discussion.get("unresolved", [])),
            "risks": risks,
            "next_stage_prerequisites": list(
                STAGE_COMPLETION.get(stage or self.task.current_stage, [])),
            "note": "阶段总结不是讨论终止；已确认内容可随时修改并触发影响分析",
        }

    def can_advance(self, conditions_met: Dict[str, bool],
                    user_requested_provisional: bool = False) -> Dict[str, Any]:
        """Advance on completion conditions, not question counts."""
        required = STAGE_COMPLETION[self.task.current_stage]
        missing = [c for c in required if not conditions_met.get(c, False)]
        unresolved = list(self.task.discussion.get("unresolved", []))
        allowed = not missing and not unresolved
        provisional = False
        if missing and user_requested_provisional:
            # Provisional advance is only a documented, verifiable fallback.
            provisional = True
            allowed = True
        reasons: List[str] = []
        if missing:
            reasons.append("未完成条件: %s" % ", ".join(missing))
        if unresolved:
            reasons.append("未决问题: %s" % ", ".join(unresolved))
        if allowed:
            reasons.append("按阶段完成条件推进" if not provisional
                           else "用户明确要求暂定推进；已记录假设与待验证项")
        return {"allowed": allowed, "provisional": provisional,
                "missing": missing, "unresolved": unresolved, "reasons": reasons}


__all__ = ["ProposalOption", "DiscussionManager", "make_proposal", "DEPTH_PROFILES"]
