"""IF0 sections 3, 5.3, 6: decision dedup, authorization and evidence chain."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .contract import DeliveryStatus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class DecisionKey:
    """Four-field item key. Context version is mandatory (dedup rule)."""

    experiment_id: str
    stage_id: str
    topic: str
    context_version: str

    def as_tuple(self) -> Tuple[str, str, str, str]:
        return (
            self.experiment_id,
            self.stage_id,
            self.topic,
            self.context_version,
        )

    def to_dict(self) -> Dict[str, str]:
        return {
            "experiment_id": self.experiment_id,
            "stage_id": self.stage_id,
            "topic": self.topic,
            "context_version": self.context_version,
        }


@dataclass
class Authorization:
    authorization_id: str
    decision_id: str
    scope: str
    bound_context_version: str
    created_at: str = field(default_factory=_now)
    revoked: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "authorization_id": self.authorization_id,
            "decision_id": self.decision_id,
            "scope": self.scope,
            "bound_context_version": self.bound_context_version,
            "created_at": self.created_at,
            "revoked": self.revoked,
        }


@dataclass
class DecisionItem:
    decision_id: str
    key: DecisionKey
    question: str
    options: List[str]
    evidence_refs: List[str]
    authorization_scope: Optional[str]
    blocks_module_task_id: str
    delivery_status: DeliveryStatus = DeliveryStatus.UNDELIVERED
    resolution: Optional[str] = None
    superseded_by: Optional[str] = None
    channel: Optional[str] = None  # A6: NATIVE_CHAT / AUQ, recorded at delivery
    created_at: str = field(default_factory=_now)
    # 4.1: structured multi-round interview payload. question_set is a list of
    # {id, question, options} items; answers is the operator's recorded reply.
    # Both default to None so 4.0 behaviour and tests are unchanged.
    question_set: Optional[List[Dict[str, Any]]] = None
    answers: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "key": self.key.to_dict(),
            "question": self.question,
            "options": self.options,
            "evidence_refs": self.evidence_refs,
            "authorization_scope": self.authorization_scope,
            "blocks_module_task_id": self.blocks_module_task_id,
            "delivery_status": self.delivery_status.value,
            "resolution": self.resolution,
            "superseded_by": self.superseded_by,
            "channel": self.channel,
            "created_at": self.created_at,
            "question_set": self.question_set,
            "answers": self.answers,
        }


class DecisionRegistry:
    """Core-owned decision register with A6 dedup rules (design-level)."""

    def __init__(self) -> None:
        self._items: Dict[str, DecisionItem] = {}
        self._by_key: Dict[Tuple[str, str, str, str], str] = {}
        self._authorizations: Dict[str, Authorization] = {}

    def check_duplicate(self, key: DecisionKey) -> Tuple[bool, str]:
        """Return (should_present, reason)."""
        existing_id = self._by_key.get(key.as_tuple())
        if existing_id is None:
            # Same topic with a different context_version is a new item.
            return True, "new item"
        item = self._items[existing_id]
        status = item.delivery_status
        if status == DeliveryStatus.ANSWERED:
            return False, "already answered; reuse the answer"
        if status in (DeliveryStatus.DELIVERED, DeliveryStatus.WAITING_ANSWER):
            return False, "already presented; do not ask again"
        if status == DeliveryStatus.SUPERSEDED:
            return False, "superseded; use the replacement item"
        if status == DeliveryStatus.CANCELLED and item.resolution == "REJECTED":
            # A rejected decision is final for this context version. The
            # refusal semantics live in resolution, so check it explicitly.
            return False, "rejected; do not re-present in the same context"
        if status in (DeliveryStatus.EXPIRED, DeliveryStatus.CANCELLED):
            return True, "expired or cancelled; may re-present"
        # UNDELIVERED still occupies the item key: a second request must reuse
        # the existing item instead of creating a duplicate (A6 dedup).
        return False, "already requested; reuse existing item"

    def request(
        self,
        key: DecisionKey,
        question: str,
        options: List[str],
        blocks_module_task_id: str,
        evidence_refs: Optional[List[str]] = None,
        authorization_scope: Optional[str] = None,
        question_set: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[DecisionItem, bool, str]:
        should_present, reason = self.check_duplicate(key)
        existing_id = self._by_key.get(key.as_tuple())
        if not should_present and existing_id:
            return self._items[existing_id], False, reason
        item = DecisionItem(
            decision_id="d-" + uuid.uuid4().hex[:8],
            key=key,
            question=question,
            options=options,
            evidence_refs=list(evidence_refs or []),
            authorization_scope=authorization_scope,
            blocks_module_task_id=blocks_module_task_id,
            question_set=question_set,
        )
        self._items[item.decision_id] = item
        self._by_key[key.as_tuple()] = item.decision_id
        return item, True, reason

    def present(self, decision_id: str, channel: Optional[str] = None) -> None:
        item = self._get(decision_id)
        if item.delivery_status in (
            DeliveryStatus.DELIVERED,
            DeliveryStatus.WAITING_ANSWER,
        ):
            return
        item.delivery_status = DeliveryStatus.WAITING_ANSWER
        if channel:
            item.channel = channel

    def resolve(
        self,
        decision_id: str,
        resolution: str,
        current_context_version: Optional[str] = None,
        answers: Optional[Dict[str, Any]] = None,
    ) -> Optional[Authorization]:
        """I4 DecisionResolution. APPROVED produces a context-bound authorization.

        4.1: ``answers`` records the operator's actual reply to a structured
        question_set. It is stored on the DecisionItem so the approval ledger
        can prove *what* was confirmed, not merely that something was approved.
        """
        item = self._get(decision_id)
        if resolution not in ("APPROVED", "REJECTED", "ANSWERED", "EXPIRED"):
            raise ValueError("unsupported resolution: %s" % resolution)
        if answers is not None:
            item.answers = dict(answers)
        item.resolution = resolution
        if resolution == "APPROVED":
            item.delivery_status = DeliveryStatus.ANSWERED
            if current_context_version is None:
                current_context_version = item.key.context_version
            auth = Authorization(
                authorization_id="a-" + uuid.uuid4().hex[:8],
                decision_id=decision_id,
                scope=item.authorization_scope or "",
                bound_context_version=current_context_version,
            )
            self._authorizations[auth.authorization_id] = auth
            return auth
        if resolution == "EXPIRED":
            item.delivery_status = DeliveryStatus.EXPIRED
        elif resolution == "REJECTED":
            # Preserve the refusal semantics: a rejection is not an ordinary
            # answered item. resolution=REJECTED stays on the item, and the
            # delivery status marks it CANCELLED so downstream consumers
            # cannot mistake it for an approved / usable answer.
            item.delivery_status = DeliveryStatus.CANCELLED
        else:
            item.delivery_status = DeliveryStatus.ANSWERED
        return None

    def supersede(self, old_decision_id: str) -> DecisionItem:
        """Mark SUPERSEDED and create a linked replacement in a new channel."""
        old = self._get(old_decision_id)
        old.delivery_status = DeliveryStatus.SUPERSEDED
        new_key = DecisionKey(
            experiment_id=old.key.experiment_id,
            stage_id=old.key.stage_id,
            topic=old.key.topic,
            context_version=old.key.context_version + "+resend",
        )
        new_item = DecisionItem(
            decision_id="d-" + uuid.uuid4().hex[:8],
            key=new_key,
            question=old.question,
            options=list(old.options),
            evidence_refs=list(old.evidence_refs),
            authorization_scope=old.authorization_scope,
            blocks_module_task_id=old.blocks_module_task_id,
        )
        old.superseded_by = new_item.decision_id
        self._items[new_item.decision_id] = new_item
        self._by_key[new_key.as_tuple()] = new_item.decision_id
        return new_item

    def valid_authorization(
        self, authorization_id: str, current_context_version: str, scope: str
    ) -> Tuple[bool, str]:
        """Old approvals auto-expire when context changed (IF0 5.3 rule 4)."""
        auth = self._authorizations.get(authorization_id)
        if auth is None:
            return False, "authorization not found"
        if auth.revoked:
            return False, "authorization revoked"
        if auth.bound_context_version != current_context_version:
            return False, "context changed; approval no longer valid"
        if auth.scope != scope:
            return False, "operation outside approved scope"
        return True, "valid"

    def _get(self, decision_id: str) -> DecisionItem:
        if decision_id not in self._items:
            raise KeyError("decision not found: %s" % decision_id)
        return self._items[decision_id]

    def snapshot(self, decision_id: str) -> Dict[str, Any]:
        return self._get(decision_id).to_dict()


def evidence_chain(
    decision_id: str,
    authorization_id: Optional[str],
    tool_task_id: Optional[str],
    evidence_id: Optional[str],
    artifact_id: Optional[str],
) -> Dict[str, Any]:
    """IF0 6.1: a conclusion must be traceable along the full chain."""
    chain = {
        "decision_id": decision_id,
        "authorization_id": authorization_id,
        "tool_task_id": tool_task_id,
        "evidence_id": evidence_id,
        "artifact_id": artifact_id,
    }
    missing = [k for k, v in chain.items() if not v]
    chain["complete"] = not missing
    chain["missing"] = missing
    return chain
