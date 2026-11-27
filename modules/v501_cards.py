"""PFC Interaction 5.0.1: five card types bound to research issues.

PFCI-CARD-5.0.1: cards are structured convergence tools, never a substitute
for deep discussion and never a bypass of Core authorization.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from core.question import CardType, Option, Question
from core.v501_issues import IssueTree
from .v50_interaction import InteractionCoordinator


class CardKind(str, Enum):
    DISCUSSION_CONVERGENCE = "DISCUSSION_CONVERGENCE"
    PARAMETER_REGISTRATION = "PARAMETER_REGISTRATION"
    PLAN_CONFIRMATION = "PLAN_CONFIRMATION"
    EXECUTION_AUTHORIZATION = "EXECUTION_AUTHORIZATION"
    CHECKPOINT_DECISION = "CHECKPOINT_DECISION"


SOURCE_TYPES = ("user_specified", "measured", "literature", "empirical_initial",
                "inverse_estimate", "to_be_calibrated")


def _han_len(value: str) -> int:
    return int(sum(1 if ord(ch) > 0x2E80 else 0.5 for ch in value))


@dataclass
class V501Card:
    card_id: str
    kind: CardKind
    issue_id: str
    research_task_id: str
    title: str
    summary: str
    stage_id: str = "S1"
    options: List[Option] = field(default_factory=list)
    discussed_points: List[str] = field(default_factory=list)
    open_disagreements: List[str] = field(default_factory=list)
    impact: str = ""
    parameter_name: str = ""
    symbol: str = ""
    unit: str = ""
    current_value: Any = None
    suggested_range: str = ""
    source_type: str = ""
    basis: str = ""
    calibration_status: str = "待标定"
    coupling_note: str = ""
    applicability: str = ""
    rejected_alternatives: List[str] = field(default_factory=list)
    unresolved_risks: List[str] = field(default_factory=list)
    action: str = ""
    target: str = ""
    model_version: str = ""
    parameter_version: str = ""
    matrix_version: str = ""
    overwrite_or_batch: str = ""
    risks: List[str] = field(default_factory=list)
    authorization_scope: str = ""
    evidence_refs: List[str] = field(default_factory=list)
    allow_free_text: bool = True
    allow_defer: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        data = {k: v for k, v in self.__dict__.items()}
        data["kind"] = self.kind.value
        data["options"] = [o.to_dict() for o in self.options]
        return data


def validate_v501_card(card: V501Card) -> List[str]:
    errors: List[str] = []
    if _han_len(card.title) > 20:
        errors.append("标题超过20汉字")
    if _han_len(card.summary) > 50:
        errors.append("摘要超过50汉字")
    if not (2 <= len(card.options) <= 5):
        errors.append("选项数量必须为2-5")
    if not card.issue_id:
        errors.append("卡片必须绑定议题")
    if card.kind == CardKind.DISCUSSION_CONVERGENCE:
        if not card.discussed_points or not card.open_disagreements or not card.impact:
            errors.append("讨论收敛卡必须显示已讨论观点、分歧和影响")
        if not card.allow_defer:
            errors.append("讨论收敛卡应允许暂定/暂缓")
    elif card.kind == CardKind.PARAMETER_REGISTRATION:
        required = ["parameter_name", "symbol", "unit", "source_type", "basis"]
        missing = [k for k in required if not getattr(card, k)]
        if missing:
            errors.append("参数登记卡缺少: %s" % ", ".join(missing))
        if card.source_type not in SOURCE_TYPES:
            errors.append("参数来源类型非法: %s" % card.source_type)
        if str(card.current_value) == "" or not card.suggested_range:
            errors.append("参数登记卡必须显示当前值与建议范围")
    elif card.kind == CardKind.PLAN_CONFIRMATION:
        if not card.applicability or not card.rejected_alternatives or not card.unresolved_risks:
            errors.append("方案确认卡必须显示适用条件、未选替代方案和未决风险")
    elif card.kind == CardKind.EXECUTION_AUTHORIZATION:
        required = ["action", "target", "model_version", "parameter_version",
                    "matrix_version", "authorization_scope"]
        missing = [k for k in required if not getattr(card, k)]
        if missing:
            errors.append("执行授权卡缺少绑定: %s" % ", ".join(missing))
        if card.allow_defer:
            errors.append("执行授权卡不得静默延后")
        if not card.risks:
            errors.append("执行授权卡必须列出风险")
    elif card.kind == CardKind.CHECKPOINT_DECISION:
        if not card.evidence_refs:
            errors.append("检查点决策卡必须附真实运行状态证据")
        labels = [o.label for o in card.options]
        if not any("继续" in label for label in labels) or not any(
                ("暂停" in label or "停止" in label or "调整" in label) for label in labels):
            errors.append("检查点决策卡必须提供继续/暂停/停止/调整等明确动作")
    return errors


_KIND_TO_CARD_TYPE = {
    CardKind.DISCUSSION_CONVERGENCE: CardType.DISCUSSION,
    CardKind.PARAMETER_REGISTRATION: CardType.PARAMETER,
    CardKind.PLAN_CONFIRMATION: CardType.PARAMETER,
    CardKind.EXECUTION_AUTHORIZATION: CardType.EXECUTION,
    CardKind.CHECKPOINT_DECISION: CardType.PARAMETER,
}


class V501CardCoordinator:
    """Card preparation with issue/discussion-depth enforcement."""

    def __init__(self, coordinator: InteractionCoordinator, issues: IssueTree,
                 discussion_engine: Any = None) -> None:
        self.coordinator = coordinator
        self.issues = issues
        self.discussion_engine = discussion_engine
        self.cards: Dict[str, V501Card] = {}

    def _depth_check(self, card: V501Card) -> Dict[str, Any]:
        if self.discussion_engine is None:
            return {"checked": False, "note": "未接入 DeepDiscussionEngine"}
        gate = self.discussion_engine.gate(card.issue_id)
        depth = "D1" if card.kind == CardKind.PARAMETER_REGISTRATION else "D2"
        if not gate["ready"]:
            raise ValueError("%s 议题讨论深度不足，不得卡片化: %s"
                             % (depth, ", ".join(gate["missing"])))
        return {**gate, "checked": True, "required_depth": depth}

    def to_question(self, card: V501Card) -> Question:
        # Panel description stays within the card spec; execution details live
        # in question_meta / known_context for audit, not in the one-liner.
        known_context = list(card.discussed_points) + list(card.evidence_refs)
        if card.kind == CardKind.EXECUTION_AUTHORIZATION:
            known_context.extend([
                card.action, card.target,
                "模型v%s/参数v%s/工况v%s" % (card.model_version, card.parameter_version,
                                       card.matrix_version),
                *card.risks,
            ])
        return Question(
            id=card.card_id, prompt=card.title, title=card.title,
            description=card.summary, reason=card.impact,
            card_type=_KIND_TO_CARD_TYPE[card.kind],
            stage_id=card.stage_id, options=list(card.options),
            known_context=known_context,
            allow_free_text=card.allow_free_text, allow_defer=card.allow_defer,
            submit_label=("确认执行（明确授权）" if card.kind == CardKind.EXECUTION_AUTHORIZATION
                          else "提交选择"),
        )

    def prepare(self, card: V501Card) -> Dict[str, Any]:
        errors = validate_v501_card(card)
        if errors:
            raise ValueError("5.0.1 卡片自检未通过: %s" % "; ".join(errors))
        self.issues.get(card.issue_id)
        gate = self._depth_check(card)
        question = self.to_question(card)
        prepared = self.coordinator.prepare(question)
        self.cards[prepared.interaction_id] = card
        return {
            "interaction_id": prepared.interaction_id,
            "decision_id": prepared.decision_id,
            "panel_header": prepared.panel_header,
            "panel_prompt": prepared.panel_prompt,
            "options": prepared.options,
            "question_meta": {**prepared.question_meta, "v501_card": card.to_dict(),
                              "issue_id": card.issue_id},
            "depth_gate": gate,
            "requires_writeback": True,
            "execution_performed": False,
        }

    def submit(self, interaction_id: str, answer: Any) -> Dict[str, Any]:
        card = self.cards[interaction_id]
        result = self.coordinator.submit(interaction_id, answer)
        return {
            **result,
            "issue_id": card.issue_id,
            "card_kind": card.kind.value,
            "requires_issue_writeback": True,
            "requires_archive_writeback": True,
            "is_execution_authorization": card.kind == CardKind.EXECUTION_AUTHORIZATION,
        }


def new_card(kind: CardKind, issue_id: str, research_task_id: str,
             title: str, summary: str, **kwargs: Any) -> V501Card:
    return V501Card(
        card_id="v501c-" + uuid.uuid4().hex[:8], kind=kind, issue_id=issue_id,
        research_task_id=research_task_id, title=title, summary=summary, **kwargs)


__all__ = ["CardKind", "V501Card", "validate_v501_card", "V501CardCoordinator", "new_card"]
