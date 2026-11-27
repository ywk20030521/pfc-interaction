"""5.0 card interaction adapter (PFCI-CARD-5.0 + PFCI-HUMAN-5.0 section 12).

Cards only render a clear item and collect an answer. They never trigger PFC
execution, never auto-confirm a decision, and never grant authorization by
themselves. The 4.0 card implementation is reused, not duplicated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.v50_discussion import DiscussionManager

from core.question import CardType, Question, validate_card
from core.v50_context import ResearchTask, StageID
from core.v50_decisions import (
    NATIVE_CHAT, AuthorizationRecord, DecisionManager, InteractionRouter,
)
from .question_cards import decision_summary


@dataclass
class PreparedCard:
    interaction_id: str
    decision_id: str
    panel_header: str
    panel_prompt: str
    options: List[Dict[str, Any]]
    question_meta: Dict[str, Any]
    card_type: str
    new_interaction: bool
    dedup_reason: str
    depth_gate: Dict[str, Any] = field(default_factory=dict)


class InteractionCoordinator:
    """Thin bridge between validated cards and the Core decision protocol."""

    def __init__(self, task: ResearchTask, decisions: DecisionManager,
                 router: InteractionRouter) -> None:
        self.task = task
        self.decisions = decisions
        self.router = router
        self._cards: Dict[str, Question] = {}

    def validate_batch(self, questions: List[Question],
                       group_topic: str = "") -> List[str]:
        """Default one card; at most three related cards."""
        errors: List[str] = []
        if len(questions) > 3:
            errors.append("同屏最多三张卡片")
        if len(questions) > 1 and not group_topic:
            errors.append("多张卡片必须声明共同事项，否则应逐张展示")
        ids = [q.id for q in questions]
        if len(set(ids)) != len(ids):
            errors.append("同一批次出现重复卡片事项")
        for question in questions:
            errors.extend(validate_card(question))
        return errors

    def prepare(self, question: Question, stage: Optional[StageID] = None,
                decision_id: Optional[str] = None,
                channel: str = NATIVE_CHAT,
                expires_at: Optional[str] = None,
                discussion: Optional[DiscussionManager] = None,
                depth_profile: str = "default",
                topic: str = "") -> PreparedCard:
        """Only structure an item after sufficient discussion.

        Omitting ``discussion`` keeps 4.0-era callers working but records that
        the depth gate was not checked. Real research runs must pass it.
        """
        errors = validate_card(question)
        if errors:
            raise ValueError("卡片自检未通过: %s" % "; ".join(errors))
        if discussion is not None:
            gate = discussion.require_depth(
                topic or question.title, depth_profile)
        else:
            gate = {
                "ready": False, "checked": False,
                "note": "未接入 DiscussionManager，讨论深度未检查",
            }
        rendered = question.to_decision_question()
        event, is_new, reason = self.router.open(
            topic=question.title, purpose=question.panel_prompt(), stage=stage,
            channel=channel, options=rendered["options"],
            context_refs=question.known_context, decision_id=decision_id,
            authorization_scope=("execute:%s" % question.id
                                 if question.card_type == CardType.EXECUTION else None),
            expires_at=expires_at,
        )
        self._cards[event.interaction_id] = question
        return PreparedCard(
            interaction_id=event.interaction_id, decision_id=event.decision_id or "",
            panel_header=rendered["header"], panel_prompt=rendered["question"],
            options=rendered["options"],
            question_meta=question.to_dict(), card_type=question.card_type.value,
            new_interaction=is_new, dedup_reason=reason, depth_gate=gate,
        )

    def submit(self, interaction_id: str, answer: Any,
               channel: Optional[str] = None) -> Dict[str, Any]:
        question = self._cards.get(interaction_id)
        if question is None:
            raise KeyError("未知卡片交互: %s" % interaction_id)
        result = self.router.answer(interaction_id, answer, channel)
        summary = decision_summary(question, answer)
        decision = self.decisions._get(result["decision_id"])
        return {
            **result, "card": summary,
            "impact": {
                "affected_assets": list(decision.affected_assets),
                "informs_stage": decision.stage_id,
                "may_change_parameters": bool(decision.affected_assets),
            },
            "requires_agent_feedback": True,
            "feedback_requirement": "Agent 必须解释该回答对方案与后续步骤的影响",
            "execution_performed": False,
        }

    def authorize_execution(self, interaction_id: str, operation: str,
                            target: str, model_version: str,
                            parameter_version: str, matrix_version: str,
                            assumption_version: str = "v1") -> AuthorizationRecord:
        """Only an explicit execution card with a clear answer grants authority."""
        question = self._cards.get(interaction_id)
        if question is None or question.card_type != CardType.EXECUTION:
            raise ValueError("只有执行确认卡可以请求执行授权")
        event = self.router._get(interaction_id)
        if event.user_response not in ("CONFIRM_EXECUTE", "确认执行"):
            raise ValueError("未获得明确执行授权，不得执行")
        self.router.confirm_from_answer(
            interaction_id, str(event.user_response), explicit_confirm=True)
        return self.decisions.authorize(
            event.decision_id, operation=operation, target=target,
            scope="execute:%s" % question.id, model_version=model_version,
            parameter_version=parameter_version, matrix_version=matrix_version,
            assumption_version=assumption_version,
        )

    def snapshot(self) -> Dict[str, Any]:
        return {
            "cards": [
                {"interaction_id": iid, "card_type": q.card_type.value,
                 "title": q.title, "status": q.status.value}
                for iid, q in self._cards.items()
            ],
            "interactions": [e.to_dict() for e in self.task.interactions.values()],
        }


__all__ = ["PreparedCard", "InteractionCoordinator"]
