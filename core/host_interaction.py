"""Host interaction adapter: probe the host once, never fake delivery.

The 5.x card protocol only creates ``PreparedCard`` data.  A host must actually
render it and deliver an answer.  This adapter makes the absence of a delivery
channel an explicit ``PENDING_NATIVE_CHAT`` outcome instead of silently
pretending that a question was delivered, and it de-duplicates by context
version so a changed model state can still raise a new question.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

from .v50_context import ResearchTask, StageID
from .v50_decisions import AUQ, NATIVE_CHAT, DecisionManager, InteractionRouter

L0 = "L0_NATIVE_CHAT"
L1 = "L1_STRUCTURED_ASK"
L2 = "L2_AUQ_CARDS"


@dataclass(frozen=True)
class HostCapability:
    """Detected host interaction capability; no capability is assumed."""

    level: str
    structured_ask: bool
    auq: bool
    card_ui: bool
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level, "structured_ask": self.structured_ask,
            "auq": self.auq, "card_ui": self.card_ui,
            "evidence": dict(self.evidence),
        }


def probe_host_capability(
    structured_ask: Optional[Callable[[Dict[str, Any]], Any]] = None,
    auq_available: bool = False,
    card_ui_available: bool = False,
) -> HostCapability:
    """Rank the host channel.  Absent tools are never treated as available."""
    evidence = {
        "structured_ask": bool(structured_ask),
        "auq": bool(auq_available),
        "card_ui": bool(card_ui_available),
    }
    if auq_available and structured_ask is not None and card_ui_available:
        level = L2
    elif structured_ask is not None:
        level = L1
    else:
        level = L0
    return HostCapability(level, bool(structured_ask), bool(auq_available),
                          bool(card_ui_available), evidence)


@dataclass
class AskOutcome:
    """The result of one ask attempt.  ``delivered`` is true only on real delivery."""

    status: str
    delivered: bool
    channel: str
    question_bundle_id: str
    answer: Any = None
    pending_decision_id: str = ""
    native_chat_request: str = ""
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status, "delivered": self.delivered,
            "channel": self.channel, "question_bundle_id": self.question_bundle_id,
            "answer": self.answer, "pending_decision_id": self.pending_decision_id,
            "native_chat_request": self.native_chat_request, "note": self.note,
        }


class HostInteractionAdapter:
    """Unified ``ask(question_bundle) -> answer_or_pending`` entry point."""

    def __init__(self, task: ResearchTask, decisions: DecisionManager,
                 router: InteractionRouter, capability: HostCapability) -> None:
        self.task = task
        self.decisions = decisions
        self.router = router
        self.capability = capability
        self._delivered: Dict[Tuple[str, str, str, str], AskOutcome] = {}

    def _key(self, topic: str, stage_id: str,
             context_version: str) -> Tuple[str, str, str, str]:
        return (self.task.research_task_id, stage_id, topic, context_version)

    def ask(
        self,
        question_bundle: Dict[str, Any],
        topic: str,
        stage: Optional[StageID] = None,
        context_version: str = "",
        decision_id: Optional[str] = None,
    ) -> AskOutcome:
        """Deliver through the host if possible; otherwise stop in Native Chat.

        ``question_bundle`` must contain ``question`` (str) and may contain
        ``options`` and ``understanding``.  The adapter never writes an answer
        into Core and never grants confirmation or execution authority.
        """
        if not isinstance(question_bundle, dict) or not str(
                question_bundle.get("question", "")).strip():
            raise ValueError("question_bundle 必须包含非空 question")
        stage_id = (stage or self.task.current_stage).value
        key = self._key(topic, stage_id, context_version)
        if key in self._delivered:
            previous = self._delivered[key]
            return AskOutcome(
                status="BLOCKED_DUPLICATE", delivered=False,
                channel=previous.channel, question_bundle_id=key[2],
                note="同一事项与上下文版本已投递，不得重复打扰用户",
            )

        # Router dedup uses topic only; carry context_version in the topic so a
        # changed model state can legitimately reopen the same decision topic.
        router_topic = "%s@%s" % (topic, context_version) if context_version else topic
        event, is_new, reason = self.router.open(
            topic=router_topic, purpose=str(question_bundle["question"]), stage=stage,
            channel=AUQ if (self.capability.auq and not self.capability.structured_ask)
            else NATIVE_CHAT,
            options=list(question_bundle.get("options") or []),
            decision_id=decision_id,
        )
        bundle_id = event.interaction_id
        render = self._render(question_bundle)

        if self.capability.structured_ask:
            result = self._call_host(question_bundle, decision_id=event.decision_id)
            outcome = self._structured_outcome(bundle_id, event.channel, result, reason)
        else:
            outcome = AskOutcome(
                status="PENDING_NATIVE_CHAT", delivered=False, channel=NATIVE_CHAT,
                question_bundle_id=bundle_id, pending_decision_id=event.decision_id or "",
                native_chat_request=render,
                note="宿主无结构化提问通道；Agent 必须在 Native Chat 提问并结束本轮等待",
            )
        self._delivered[key] = outcome
        return outcome

    def _call_host(self, question_bundle: Dict[str, Any],
                   decision_id: str) -> Any:
        # Injected by the host; a callback is the only proof of a real channel.
        callback: Callable[[Dict[str, Any]], Any] = getattr(self, "_ask_callback", None)
        if callback is None:
            raise RuntimeError("capability 声明结构化提问但没有注入宿主回调")
        payload = dict(question_bundle)
        payload["decision_id"] = decision_id
        return callback(payload)

    def _structured_outcome(self, bundle_id: str, channel: str, result: Any,
                            reason: str) -> AskOutcome:
        if isinstance(result, dict):
            status = str(result.get("status", "ANSWERED"))
            answer = result.get("answer")
        else:
            status, answer = "ANSWERED", result
        pending = status in ("PENDING", "WAITING", "WAITING_FOR_USER")
        return AskOutcome(
            status="PENDING_NATIVE_CHAT" if pending else "ANSWERED",
            delivered=True, channel=channel, question_bundle_id=bundle_id,
            answer=None if pending else answer,
            note=("宿主已接收问题，尚未收到回答" if pending else reason),
        )

    @staticmethod
    def _render(question_bundle: Dict[str, Any]) -> str:
        lines = []
        understanding = str(question_bundle.get("understanding", "")).strip()
        if understanding:
            lines.append("当前理解：%s" % understanding)
        lines.append("问题：%s" % str(question_bundle["question"]).strip())
        options = question_bundle.get("options") or []
        if options:
            lines.append("可选方案：")
            for option in options:
                if isinstance(option, dict):
                    label = option.get("label") or option.get("text") or str(option)
                else:
                    label = option
                lines.append("- %s" % label)
        return "\n".join(lines)


def attach_host_ask(adapter: HostInteractionAdapter,
                    callback: Callable[[Dict[str, Any]], Any]) -> None:
    """Attach the host's real structured ask tool to an adapter instance."""
    adapter._ask_callback = callback


__all__ = [
    "L0", "L1", "L2", "HostCapability", "probe_host_capability",
    "AskOutcome", "HostInteractionAdapter", "attach_host_ask",
]
