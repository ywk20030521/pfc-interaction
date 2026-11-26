"""4.0 提问卡片规范实现（PFC_Interaction_提问卡片强制设计规范_V2）。

Implements the MUST requirements from sections 6 and 12 of the spec:
  - three card types (DISCUSSION / PARAMETER / EXECUTION)
  - 12 card states, with answered != confirmed != authorized != executed != verified
  - single decision per card, length caps, deferred path, decision summary
  - Question / Decision objects (spec section 7)
  - mandatory pre-generation self-check (section 6.8)
  - de-dup key experiment_id + stage_id + decision_topic

Panel text follows the operator's explicit feedback (2026-11-26): the main
prompt contains ONLY the title + one short sentence. Stage tags live in the
panel header, and technical basis stays in option descriptions / question_meta
(not in the main prompt).

Backward compatibility: Question(id=...), prompt=..., display_prompt(),
to_decision_questions(), meta_for(), apply_answers() are preserved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

AUTHOR_INPUT_NEEDED = "AUTHOR_INPUT_NEEDED"
DEFER_LABEL = "暂不确定 / 稍后决定"


class CardType(str, Enum):
    DISCUSSION = "DISCUSSION"   # 科研讨论卡：开放目标/假设/机理
    PARAMETER = "PARAMETER"     # 参数决策卡：单选/多选/数值+单位
    EXECUTION = "EXECUTION"     # 执行确认卡：高风险动作明确授权


class CardStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    ANSWERED = "answered"
    NEEDS_CLARIFICATION = "needs_clarification"
    CONFIRMED = "confirmed"
    DEFERRED = "deferred"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    AUTHORIZED = "authorized"
    EXECUTED = "executed"
    VERIFIED = "verified"
    FAILED = "failed"


class QuestionPriority(str, Enum):
    P0 = "P0"   # 必须澄清，阻塞后续
    P1 = "P1"   # 高影响，先讨论再确认
    P2 = "P2"   # 可建议默认，需标明依据
    P3 = "P3"   # 可延后
    P4 = "P4"   # 不应询问：自动读取或已知


@dataclass
class Option:
    label: str
    value: Any = None
    unit: str = ""
    source: str = ""          # user_provided / agent_proposal / PFC_manual / literature
    basis: str = ""           # 技术依据（折叠/选项说明）
    is_default: bool = False
    recommended: bool = False
    rationale: str = ""       # 推荐理由

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "value": self.value if self.value is not None else self.label,
            "unit": self.unit, "source": self.source, "basis": self.basis,
            "is_default": self.is_default, "recommended": self.recommended,
            "rationale": self.rationale,
        }


@dataclass
class Question:
    id: str
    prompt: str
    # 规范 section 7.1 fields
    question_id: str = ""
    experiment_id: str = ""
    stage_id: str = ""
    intent: str = "clarification"
    priority: QuestionPriority = QuestionPriority.P1
    card_type: CardType = CardType.PARAMETER
    title: str = ""
    description: str = ""
    reason: str = ""                   # 为什么需要决定（不放主问题）
    known_context: List[str] = field(default_factory=list)
    allow_free_text: bool = False
    free_text_hint: str = ""
    allow_defer: bool = True
    required: bool = True
    submit_label: str = "提交答案"
    recommendation: str = ""           # ≤2 句，标注"建议"
    technical_basis: str = ""          # 可折叠技术依据
    status: CardStatus = CardStatus.PENDING
    created_at: str = ""
    # 兼容旧字段
    group: str = ""
    why: str = ""
    unit: str = ""
    options: List[Option] = field(default_factory=list)
    author_input_needed: bool = False
    progress_idx: int = 0
    progress_total: int = 0
    default: Any = None
    basis: str = ""

    def __post_init__(self):
        if not self.question_id:
            self.question_id = self.id
        if not self.title:
            self.title = self.prompt
        if not self.description:
            self.description = self.why or self.reason
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        # 执行卡必须显式授权，默认不允许静默延后
        if self.card_type == CardType.EXECUTION:
            self.allow_defer = False
            self.submit_label = "确认执行"

    def panel_header(self) -> str:
        """规范 6.6: [阶段标签 · 卡片类型]，≤12 字符."""
        tags = {
            CardType.DISCUSSION: "科研讨论",
            CardType.PARAMETER: "关键决策" if self.priority == QuestionPriority.P1
                                else "参数决策",
            CardType.EXECUTION: "执行确认",
        }
        tag = tags.get(self.card_type, self.stage_id or "决策")
        stage = self.stage_id or "实验设计"
        return "%s·%s" % (stage, tag)

    def panel_prompt(self) -> str:
        """规范 6.2 层级: 标题 / 一句话说明 / 独立建议区.

        No group tags, no '为什么问' / '依据' prefixes (operator feedback).
        The recommendation gets its own block, matching the spec's screenshot.
        """
        out = self.title
        if self.description and self.description != self.title:
            out += "\n" + self.description
        if self.recommendation:
            rec = self.recommendation
            if not rec.startswith("建议"):
                rec = "建议：" + rec
            out += "\n\n" + rec
        return out

    # 向后兼容别名
    def display_prompt(self) -> str:
        return self.panel_prompt()

    def to_decision_question(self) -> Dict[str, Any]:
        """Shape compatible with Core.request_decision question_set."""
        opts: List[Dict[str, Any]] = []
        for o in self.options:
            # Spec screenshot: option text is a short physical-meaning line.
            # Source/unit/rationale stay in question_meta for audit; only unit
            # is shown inline for numeric parameters (spec 6.12).
            desc_bits = []
            if o.unit and o.unit != "-":
                desc_bits.append("单位 %s" % o.unit)
            if o.basis:
                desc_bits.append(o.basis)
            elif o.rationale:
                desc_bits.append(o.rationale)
            label = o.label + ("（建议）" if o.recommended else "")
            opts.append({
                "id": self.id, "label": label, "question": o.label,
                "description": "; ".join(desc_bits),
                "options": [o.label],
                "value": o.value if o.value is not None else o.label,
                "recommended": o.recommended,
            })
        if self.allow_free_text:
            label = self.free_text_hint or "其他变量"
            opts.append({
                "id": self.id, "label": label, "question": label,
                "description": "由用户补充研究因素",
                "options": [label], "value": "__FREE_TEXT__", "free_text": True,
            })
        if self.allow_defer and self.card_type != CardType.EXECUTION:
            opts.append({
                "id": self.id, "label": DEFER_LABEL, "question": DEFER_LABEL,
                "description": "暂缓影响：%s" % (self.reason or "相关阶段保持待定"),
                "options": [DEFER_LABEL], "value": "DEFERRED", "defer": True,
            })
        return {
            "id": self.id,
            "question": self.panel_prompt(),
            "prompt": self.panel_prompt(),
            "header": self.panel_header(),
            "card_type": self.card_type.value,
            "priority": self.priority.value,
            "question_id": self.question_id,
            "group": self.group, "why": self.why, "unit": self.unit,
            "options": opts,
            "allow_free_text": self.allow_free_text,
            "allow_defer": self.allow_defer,
            "required": self.required,
            "author_input_needed": self.author_input_needed,
            "progress": {"index": self.progress_idx, "total": self.progress_total},
            "basis": self.basis, "technical_basis": self.technical_basis,
            "recommendation": self.recommendation,
            "known_context": self.known_context,
            "submit_label": self.submit_label,
            "status": self.status.value,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "question_id": self.question_id,
            "experiment_id": self.experiment_id, "stage_id": self.stage_id,
            "intent": self.intent, "priority": self.priority.value,
            "card_type": self.card_type.value,
            "title": self.title, "prompt": self.prompt,
            "description": self.description, "reason": self.reason,
            "known_context": self.known_context,
            "options": [o.to_dict() for o in self.options],
            "allow_free_text": self.allow_free_text,
            "free_text_hint": self.free_text_hint,
            "allow_defer": self.allow_defer, "required": self.required,
            "submit_label": self.submit_label,
            "recommendation": self.recommendation,
            "technical_basis": self.technical_basis,
            "status": self.status.value, "created_at": self.created_at,
            "group": self.group, "why": self.why, "unit": self.unit,
            "author_input_needed": self.author_input_needed,
            "progress_idx": self.progress_idx, "progress_total": self.progress_total,
            "default": self.default, "basis": self.basis,
        }


@dataclass
class Decision:
    """规范 section 7.2 + 6.7 状态机."""
    decision_id: str
    experiment_id: str
    stage_id: str
    question_id: str
    decision: str = ""
    decision_source: str = "user"
    status: CardStatus = CardStatus.ANSWERED
    affected_variables: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    requires_execution_approval: bool = False
    verified: bool = False
    created_at: str = ""
    answer: Any = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def confirm(self) -> None:
        if self.status in (CardStatus.REJECTED, CardStatus.SUPERSEDED):
            raise ValueError("cannot confirm a %s decision" % self.status.value)
        self.status = CardStatus.CONFIRMED

    def authorize(self) -> None:
        if self.status != CardStatus.CONFIRMED:
            raise ValueError("authorization requires a confirmed decision")
        self.status = CardStatus.AUTHORIZED

    def mark_executed(self) -> None:
        if self.status != CardStatus.AUTHORIZED:
            raise ValueError("execution requires explicit authorization")
        self.status = CardStatus.EXECUTED

    def mark_verified(self, ok: bool) -> None:
        if self.status != CardStatus.EXECUTED:
            raise ValueError("verification requires an executed decision")
        self.status = CardStatus.VERIFIED if ok else CardStatus.FAILED
        self.verified = ok

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id, "experiment_id": self.experiment_id,
            "stage_id": self.stage_id, "question_id": self.question_id,
            "decision": self.decision, "decision_source": self.decision_source,
            "status": self.status.value,
            "affected_variables": self.affected_variables,
            "constraints": self.constraints,
            "requires_execution_approval": self.requires_execution_approval,
            "verified": self.verified, "created_at": self.created_at,
            "answer": self.answer,
        }


def dedup_key(experiment_id: str, stage_id: str, decision_topic: str) -> str:
    """规范 section 8: 同一事项不得在 Chat/AUQ 重复投递."""
    return "%s::%s::%s" % (experiment_id, stage_id, decision_topic)


def _han_len(s: str) -> int:
    """Approximate display length: CJK counts 1, ascii counts 0.5."""
    n = 0
    for ch in s:
        n += 1 if ord(ch) > 0x2E80 else 0.5
    return int(n)


def validate_card(q: Question) -> List[str]:
    """规范 section 6.8 mandatory self-check. Returns violations."""
    errors: List[str] = []
    if not q.title:
        errors.append("缺少问题标题")
    if _han_len(q.title) > 20:
        errors.append("标题超过20汉字")
    if not q.description:
        errors.append("缺少一句话说明")
    if _han_len(q.description) > 50:
        errors.append("说明超过50汉字")
    if not (2 <= len(q.options) <= 5):
        errors.append("选项数量必须为2-5")
    for o in q.options:
        if _han_len(o.label) > 18:
            errors.append("选项标题超过18汉字: %s" % o.label)
        if o.source and o.source not in (
            "user_provided", "agent_proposal", "PFC_manual", "literature",
            "pfc_practice", "nature_statistics", "experiment_measurement",
        ):
            errors.append("选项来源未标注: %s" % o.label)
    if q.card_type == CardType.EXECUTION:
        if q.allow_defer:
            errors.append("执行确认卡不得提供静默延后")
        if "确认执行" not in q.submit_label:
            errors.append("执行确认卡动作文案必须明确为确认执行")
        if not q.known_context and not q.reason:
            errors.append("执行确认卡必须列出动作/对象/影响范围")
    else:
        if not q.allow_defer and q.priority != QuestionPriority.P0:
            errors.append("非阻塞问题必须提供暂不确定路径")
    if q.priority == QuestionPriority.P4:
        errors.append("P4 信息不得询问用户，应自动读取")
    if q.card_type == CardType.DISCUSSION and len(q.options) > 4:
        errors.append("科研讨论卡选项不得超过4个")
    return errors


def to_decision_questions(questions: List[Question]) -> List[Dict[str, Any]]:
    return [q.to_decision_question() for q in questions]


def meta_for(questions: List[Question]) -> List[Dict[str, Any]]:
    return [q.to_dict() for q in questions]


def apply_answers(questions: List[Question], answers: Dict[str, Any]) -> Dict[str, Any]:
    """Free text kept verbatim; AUTHOR_INPUT_NEEDED never replaced by a guess."""
    out: Dict[str, Any] = {}
    for q in questions:
        if q.id not in answers or answers[q.id] in (None, ""):
            continue
        val = answers[q.id]
        out[q.id] = AUTHOR_INPUT_NEEDED if str(val) == AUTHOR_INPUT_NEEDED else val
    return out


__all__ = [
    "AUTHOR_INPUT_NEEDED", "DEFER_LABEL", "CardType", "CardStatus",
    "QuestionPriority", "Option", "Question", "Decision",
    "dedup_key", "validate_card", "to_decision_questions", "meta_for",
    "apply_answers",
]
