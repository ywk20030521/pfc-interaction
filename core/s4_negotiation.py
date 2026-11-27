"""S4 per-parameter negotiation (S4_SPEC V2.0 chapters 5, 6).

Key semantics:
  * "per-parameter" means each parameter has its OWN scientific argument and
    decision record, NOT isolated tuning. Independent archive + joint group
    analysis must coexist from the start (scheme B, mandatory).
  * A card submission records an OPINION. It NEVER confirms a parameter nor
    authorises execution. Only approve() with a real user response confirms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.s4_contracts import (
    CalibrationDecision, CalibrationProject, ParamState, ParameterGroup, _uid,
)

SEVEN_STEPS = [
    "parameter_identification",
    "mechanism_analysis",
    "evidence_and_range",
    "uncertainty_and_coupling",
    "candidate_discussion",
    "user_decision",
    "state_confirmation",
]


@dataclass
class NegotiationCard:
    card_id: str
    parameter_id: str
    question: str
    context: List[str] = field(default_factory=list)
    options: List[str] = field(default_factory=list)
    submitted_opinion: str = ""
    confirmed: bool = False
    authorized: bool = False

    def submit(self, opinion: str) -> None:
        if not opinion:
            raise ValueError("讨论意见不能为空")
        self.submitted_opinion = opinion
        # Deliberately does NOT set confirmed or authorized.

    def confirm(self, response: str) -> None:
        if not self.submitted_opinion:
            raise ValueError("必须先提交讨论意见，不能直接确认")
        if not response:
            raise ValueError("确认必须记录用户真实回答")
        self.confirmed = True

    def authorize(self, response: str) -> None:
        if not self.confirmed:
            raise ValueError("未确认的参数协商卡片不得授权执行")
        if not response:
            raise ValueError("授权必须记录用户真实回答")
        self.authorized = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "card_id": self.card_id, "parameter_id": self.parameter_id,
            "question": self.question, "context": list(self.context),
            "options": list(self.options), "submitted_opinion": self.submitted_opinion,
            "confirmed": self.confirmed, "authorized": self.authorized,
            "semantics": "submit != confirm != authorize",
        }


class NegotiationEngine:
    def __init__(self, project: CalibrationProject) -> None:
        self.project = project
        self.progress: Dict[str, List[str]] = {}
        self.cards: Dict[str, NegotiationCard] = {}

    def start(self, parameter_id: str) -> List[str]:
        if parameter_id not in self.project.parameters:
            raise KeyError("参数不存在: %s" % parameter_id)
        self.progress[parameter_id] = []
        return list(SEVEN_STEPS)

    def advance(self, parameter_id: str, step: str, content: str) -> List[str]:
        if parameter_id not in self.progress:
            raise ValueError("必须先启动该参数的协商流程")
        done = self.progress[parameter_id]
        if step not in SEVEN_STEPS:
            raise ValueError("未知协商步骤: %s" % step)
        if SEVEN_STEPS.index(step) != len(done):
            raise ValueError("协商必须按七步顺序推进，当前应执行: %s"
                             % (SEVEN_STEPS[len(done)] if len(done) < 7 else "已完成"))
        if not content:
            raise ValueError("每步协商必须记录实质内容")
        done.append(step)
        self.project.record("negotiate:%s" % parameter_id, "%s:%s" % (step, content[:40]))
        return list(done)

    def create_card(self, parameter_id: str, question: str, context: List[str],
                    options: List[str]) -> NegotiationCard:
        if parameter_id not in self.project.parameters:
            raise KeyError("参数不存在: %s" % parameter_id)
        if not options:
            raise ValueError("协商卡片必须给出可选判断项")
        card = NegotiationCard(card_id=_uid("card"), parameter_id=parameter_id,
                               question=question, context=list(context),
                               options=list(options))
        self.cards[card.card_id] = card
        return card

    def decide(self, parameter_id: str, topic: str, recommendation: str,
               candidates: List[str], evidence_refs: List[str]) -> CalibrationDecision:
        if self.progress.get(parameter_id) != list(SEVEN_STEPS):
            raise ValueError("七步协商未完成，不得形成参数决策")
        decision = CalibrationDecision(
            decision_id=_uid("dec"), topic=topic, problem=topic,
            candidates=list(candidates), recommendation=recommendation,
            evidence_refs=list(evidence_refs),
        )
        self.project.decisions[decision.decision_id] = decision
        self.project.record("decision", topic)
        return decision

    def confirm_state(self, parameter_id: str, decision_id: str,
                      response: str, state: ParamState = ParamState.USER_CONFIRMED) -> None:
        decision = self.project.decisions.get(decision_id)
        if not decision:
            raise KeyError("决策不存在: %s" % decision_id)
        if decision.approval_state != "CONFIRMED":
            raise ValueError("决策尚未获得用户确认，不得流转参数状态")
        if parameter_id not in self.project.parameters:
            raise KeyError("参数不存在: %s" % parameter_id)
        param = self.project.parameters[parameter_id]
        param.set_state(state, "用户确认决策 %s" % decision_id)
        self.project.record("confirm_state", "%s:%s" % (parameter_id, state.value))

    def create_group(self, name: str, parameter_ids: List[str],
                     rationale: str) -> ParameterGroup:
        """Scheme B: joint analysis begins immediately; archives stay independent."""
        if len(parameter_ids) < 2:
            raise ValueError("参数组至少包含两个参数")
        for pid in parameter_ids:
            if pid not in self.project.parameters:
                raise KeyError("参数组引用了不存在的参数: %s" % pid)
            if not self.project.parameters[pid].change_log:
                raise ValueError("参数 %s 尚无独立论证记录，禁止加入联合组" % pid)
        group = ParameterGroup(group_id=_uid("grp"), name=name,
                               parameter_ids=list(parameter_ids),
                               rationale=rationale)
        self.project.groups[group.group_id] = group
        self.project.record("create_group", name)
        return group

    def set_coupling_answer(self, group_id: str, param_a: str, param_b: str,
                            question: str, answer: bool) -> None:
        if group_id not in self.project.groups:
            raise KeyError("参数组不存在: %s" % group_id)
        if question not in ("direction", "compensation", "distinguishable"):
            raise ValueError("未知耦合问题: %s" % question)
        self.project.groups[group_id].coupling_questions[
            "%s|%s|%s" % (param_a, param_b, question)] = answer

    def joint_decision(self, group_id: str, decision: str) -> None:
        group = self.project.groups.get(group_id)
        if not group:
            raise KeyError("参数组不存在: %s" % group_id)
        pairs = {(a, b) for i, a in enumerate(group.parameter_ids)
                 for b in group.parameter_ids[i + 1:]}
        expected = {"%s|%s|%s" % (a, b, q)
                    for a, b in pairs
                    for q in ("direction", "compensation", "distinguishable")}
        missing = [k for k in expected if group.coupling_questions.get(k) is None]
        if missing:
            raise ValueError("耦合四问尚未全部回答，不得形成联合决策: %s" % missing[:2])
        group.joint_decision = decision
        self.project.record("joint_decision", group_id)


__all__ = ["SEVEN_STEPS", "NegotiationCard", "NegotiationEngine"]
