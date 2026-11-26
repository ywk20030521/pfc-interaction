"""三种标准提问卡片工厂（规范 6.4，强制）。

DISCUSSION / PARAMETER / EXECUTION — all cards go through validate_card()
before being shown (spec 6.8). One card = one decision.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core import (
    AUTHOR_INPUT_NEEDED, CardStatus, CardType, Option, Question,
    QuestionPriority, validate_card,
)


def _check(q: Question) -> Question:
    errors = validate_card(q)
    if errors:
        raise ValueError("卡片自检未通过 %s: %s" % (q.id, "; ".join(errors)))
    return q


def discussion_card(
    qid: str, title: str, description: str,
    options: List[Option], recommendation: str = "",
    stage_id: str = "研究", known_context: Optional[List[str]] = None,
    priority: QuestionPriority = QuestionPriority.P1,
    reason: str = "", progress_idx: int = 0, progress_total: int = 0,
) -> Question:
    """A 科研讨论卡：开放目标/假设/机理，保留补充说明与暂不确定。"""
    q = Question(
        id=qid, prompt=title, title=title, description=description,
        card_type=CardType.DISCUSSION, priority=priority, stage_id=stage_id,
        options=options, recommendation=recommendation,
        known_context=known_context or [], reason=reason,
        allow_free_text=True, free_text_hint="其他变量",
        allow_defer=True, submit_label="形成暂定方案",
        progress_idx=progress_idx, progress_total=progress_total,
    )
    q.recommendation = recommendation  # panel_prompt() adds the "建议：" label
    return _check(q)


def parameter_card(
    qid: str, title: str, description: str,
    options: List[Option], unit: str = "",
    stage_id: str = "设计", known_context: Optional[List[str]] = None,
    priority: QuestionPriority = QuestionPriority.P1,
    reason: str = "", recommendation: str = "",
    technical_basis: str = "", allow_free_text: bool = True,
    author_input_needed: bool = False,
    progress_idx: int = 0, progress_total: int = 0,
) -> Question:
    """B 参数决策卡：单选/多选/数值+单位，标注来源与确认状态。"""
    q = Question(
        id=qid, prompt=title, title=title, description=description,
        card_type=CardType.PARAMETER, priority=priority, stage_id=stage_id,
        options=options, unit=unit,
        known_context=known_context or [], reason=reason,
        recommendation=recommendation, technical_basis=technical_basis,
        allow_free_text=allow_free_text,
        free_text_hint="其他变量",
        allow_defer=True, submit_label="提交答案",
        author_input_needed=author_input_needed,
        progress_idx=progress_idx, progress_total=progress_total,
    )
    q.recommendation = recommendation  # panel_prompt() adds the "建议：" label
    return _check(q)


def execution_card(
    qid: str, title: str, description: str,
    action: str, target: str, impact: str,
    stage_id: str = "执行", priority: QuestionPriority = QuestionPriority.P0,
    technical_basis: str = "",
) -> Question:
    """C 执行确认卡：列出动作/对象/影响，明确授权，无默认勾选与静默延后。"""
    opts = [
        Option("确认执行", "CONFIRM_EXECUTE", source="agent_proposal",
               rationale="仅在用户明确选择后获得执行授权"),
        Option("取消 / 返回检查", "CANCEL", source="agent_proposal",
               rationale="不执行任何操作"),
    ]
    q = Question(
        id=qid, prompt=title, title=title, description=description,
        card_type=CardType.EXECUTION, priority=priority, stage_id=stage_id,
        options=opts, known_context=[action, target, impact],
        reason="; ".join([action, target, impact]),
        technical_basis=technical_basis,
        allow_defer=False, required=True, submit_label="确认执行",
    )
    return _check(q)


def card_from_question_set(item: Dict[str, Any], stage_id: str = "设计") -> Question:
    """Convert an existing question_set item into a spec-compliant card.

    Used by the panel renderer so that every question shown to the operator —
    including M1/M2 legacy question sets — passes validate_card() first.
    Shortens over-long titles/descriptions by splitting into discussion only
    when necessary; otherwise the original concise text is kept.
    """
    qid = str(item.get("id") or item.get("question_id") or "q")
    prompt = str(item.get("question") or item.get("prompt") or qid)
    title = prompt.split("\n")[0][:20]
    desc = ""
    if "\n" in prompt:
        desc = prompt.split("\n", 1)[1][:50]
    if not desc:
        desc = "请作出一个明确决策，结果将进入后续分析。"
    opts: List[Option] = []
    for o in item.get("options", []):
        if isinstance(o, str):
            opts.append(Option(o[:18], o, source="agent_proposal"))
        elif isinstance(o, dict):
            label = str(o.get("label") or o.get("question") or "")[:18]
            opts.append(Option(
                label, o.get("value", label),
                unit=str(o.get("unit", "")),
                source=str(o.get("source") or "agent_proposal"),
                basis=str(o.get("basis") or o.get("description") or "")[:40],
                recommended=bool(o.get("recommended")),
            ))
    if not opts:
        opts = [Option("确认", "CONFIRM", source="agent_proposal"),
                Option("返回讨论", "DISCUSS", source="agent_proposal")]
    ctype = CardType(item.get("card_type", CardType.PARAMETER.value))
    return parameter_card(
        qid, title, desc, opts,
        stage_id=stage_id,
        priority=QuestionPriority(item.get("priority", QuestionPriority.P1.value)),
        reason=str(item.get("why", "")),
    ) if ctype != CardType.EXECUTION else execution_card(
        qid, title, desc, "执行操作", "当前模型", "见卡片说明", stage_id=stage_id)


def decision_summary(q: Question, answer: Any) -> Dict[str, Any]:
    """规范 6.7/6.10：提交后复述将被记录的选择。"""
    return {
        "question_id": q.question_id,
        "card_type": q.card_type.value,
        "title": q.title,
        "answer": answer,
        "deferred": str(answer) == "DEFERRED",
        "author_input_needed": str(answer) == AUTHOR_INPUT_NEEDED,
        "requires_execution_approval": q.card_type == CardType.EXECUTION,
        "status": CardStatus.DEFERRED.value if str(answer) == "DEFERRED"
                  else CardStatus.ANSWERED.value,
        "known_context": q.known_context,
        "submit_label": q.submit_label,
    }


__all__ = [
    "discussion_card", "parameter_card", "execution_card", "decision_summary",
]
