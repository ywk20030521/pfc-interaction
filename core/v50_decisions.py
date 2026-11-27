"""PFC Interaction 5.0: decision lifecycle, authorization and channel routing.

Implements PFCI-HUMAN-5.0 sections 7-10 and technical report sections 8-9.
An interaction answer, a confirmed decision, an execution authorization, an
actual tool execution and scientific validation remain five distinct states.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .v50_context import (
    DecisionRecord, DecisionStatus, InteractionEvent, InteractionStatus,
    ResearchTask, StageID, _now,
)

NATIVE_CHAT = "native_chat"
AUQ = "auq"

HIGH_IMPACT_OPERATIONS = (
    "start_formal_simulation", "run_batch", "overwrite_model", "overwrite_results",
    "reset_model_state", "delete_state", "change_key_parameter_and_rerun",
    "interrupt_running_task", "irreversible_operation",
)


@dataclass
class AuthorizationRecord:
    authorization_id: str
    decision_id: str
    research_task_id: str
    stage_id: str
    topic: str
    operation: str
    target: str
    scope: str
    model_version: str
    parameter_version: str
    matrix_version: str
    assumption_version: str
    context_version: str
    created_at: str = field(default_factory=_now)
    revoked: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "authorization_id": self.authorization_id, "decision_id": self.decision_id,
            "research_task_id": self.research_task_id, "stage_id": self.stage_id,
            "topic": self.topic, "operation": self.operation, "target": self.target,
            "scope": self.scope, "model_version": self.model_version,
            "parameter_version": self.parameter_version,
            "matrix_version": self.matrix_version,
            "assumption_version": self.assumption_version,
            "context_version": self.context_version, "created_at": self.created_at,
            "revoked": self.revoked,
        }


class DecisionManager:
    """Core-owned decision register. Agent proposals never auto-confirm."""

    def __init__(self, task: ResearchTask) -> None:
        self.task = task
        self.authorizations: Dict[str, AuthorizationRecord] = {}
        self.by_topic: Dict[str, str] = {}

    def propose(self, topic: str, content: str, rationale: str,
                alternatives: Optional[List[Dict[str, Any]]] = None,
                evidence: Optional[List[str]] = None,
                affected_assets: Optional[List[str]] = None,
                stage: Optional[StageID] = None) -> DecisionRecord:
        if not content or not rationale:
            raise ValueError("决策建议必须包含内容和依据")
        stage_id = (stage or self.task.current_stage).value
        rec = DecisionRecord(
            decision_id="dec-" + uuid.uuid4().hex[:8],
            research_task_id=self.task.research_task_id, stage_id=stage_id,
            topic=topic,
            proposal={"content": content, "source": "agent_proposal",
                      "rationale": rationale, "alternatives": list(alternatives or [])},
            evidence=list(evidence or []), affected_assets=list(affected_assets or []),
        )
        return self.task.add_decision(rec)

    def discuss(self, decision_id: str, note: str) -> DecisionRecord:
        rec = self._get(decision_id)
        rec.discuss(note)
        self.task.discussion["current_topic"] = rec.topic
        self.task.bump_version("discuss:%s" % decision_id)
        return rec

    def confirm(self, decision_id: str, user_response: str) -> DecisionRecord:
        rec = self._get(decision_id)
        rec.confirm(user_response)
        self.task.discussion["confirmed"] = [
            t for t in self.task.discussion["confirmed"] if t != rec.topic]
        self.task.discussion["confirmed"].append(rec.topic)
        self.task.discussion["pending"] = [
            t for t in self.task.discussion["pending"] if t != rec.topic]
        self.task.bump_version("confirm:%s" % decision_id)
        return rec

    def reject(self, decision_id: str, user_response: str) -> DecisionRecord:
        rec = self._get(decision_id)
        rec.reject(user_response)
        self.task.discussion["rejected"].append(rec.topic)
        self.task.discussion["pending"] = [
            t for t in self.task.discussion["pending"] if t != rec.topic]
        self.task.bump_version("reject:%s" % decision_id)
        return rec

    def defer(self, decision_id: str, reason: str) -> DecisionRecord:
        rec = self._get(decision_id)
        rec.defer(reason)
        self.task.discussion["deferred"] = list(self.task.discussion.get("deferred", []))
        if rec.topic not in self.task.discussion["deferred"]:
            self.task.discussion["deferred"].append(rec.topic)
        self.task.bump_version("defer:%s" % decision_id)
        return rec

    def supersede(self, old_decision_id: str, content: str, rationale: str) -> DecisionRecord:
        old = self._get(old_decision_id)
        new = self.propose(
            topic=old.topic, content=content, rationale=rationale,
            evidence=list(old.evidence), affected_assets=list(old.affected_assets),
            stage=StageID(old.stage_id),
        )
        old.supersede(new.decision_id)
        self.task.bump_version("supersede:%s" % old_decision_id)
        return new

    def invalidate_affected(self, changed_assets: Iterable[str],
                            reason: str) -> List[str]:
        """Changing an assumption, model, parameter or matrix invalidates approvals."""
        changed = set(changed_assets)
        invalidated: List[str] = []
        for rec in self.task.decisions.values():
            overlap = changed.intersection(rec.affected_assets)
            if not overlap:
                continue
            if rec.status in (DecisionStatus.CONFIRMED, DecisionStatus.DISCUSSING,
                              DecisionStatus.DEFERRED, DecisionStatus.PROPOSED):
                rec.invalidate("%s; 受影响资产: %s" % (reason, ", ".join(sorted(overlap))))
                invalidated.append(rec.decision_id)
        for aid, auth in self.authorizations.items():
            if auth.decision_id in invalidated or auth.topic in changed:
                auth.revoked = True
        if invalidated:
            self.task.bump_version("invalidate:%s" % reason)
        return invalidated

    def authorize(self, decision_id: str, operation: str, target: str, scope: str,
                  model_version: str, parameter_version: str,
                  matrix_version: str, assumption_version: str = "v1") -> AuthorizationRecord:
        rec = self._get(decision_id)
        if rec.status != DecisionStatus.CONFIRMED:
            raise ValueError("只有已确认决策才能产生执行授权；当前状态 %s" % rec.status.value)
        if not target or not scope:
            raise ValueError("执行授权必须绑定操作对象与范围")
        if not rec.user_response.get("confirmed"):
            raise ValueError("缺少明确用户回答，不得授权")
        auth = AuthorizationRecord(
            authorization_id="auth-" + uuid.uuid4().hex[:8],
            decision_id=decision_id, research_task_id=self.task.research_task_id,
            stage_id=rec.stage_id, topic=rec.topic, operation=operation, target=target,
            scope=scope, model_version=model_version,
            parameter_version=parameter_version, matrix_version=matrix_version,
            assumption_version=assumption_version,
            context_version=self.task.context_version,
        )
        self.authorizations[auth.authorization_id] = auth
        self.task.bump_version("authorize:%s" % operation)
        # Re-read the version after bumping: the authorization must bind the
        # version that actually exists at the moment of execution.
        auth.context_version = self.task.context_version
        return auth

    def validate_authorization(self, authorization_id: str, operation: str,
                               target: str, scope: str, model_version: str,
                               parameter_version: str, matrix_version: str,
                               assumption_version: str = "v1") -> Tuple[bool, List[str]]:
        auth = self.authorizations.get(authorization_id)
        if auth is None:
            return False, ["授权记录不存在"]
        issues: List[str] = []
        if auth.revoked:
            issues.append("授权已撤销或前置条件变化导致失效")
        if auth.context_version != self.task.context_version:
            issues.append("科研上下文版本变化，旧授权失效")
        for name, expected, actual in (
            ("operation", auth.operation, operation),
            ("target", auth.target, target),
            ("scope", auth.scope, scope),
            ("model_version", auth.model_version, model_version),
            ("parameter_version", auth.parameter_version, parameter_version),
            ("matrix_version", auth.matrix_version, matrix_version),
            ("assumption_version", auth.assumption_version, assumption_version),
        ):
            if expected != actual:
                issues.append("%s 与授权绑定不一致: %s != %s" % (name, actual, expected))
        return not issues, issues

    def revoke(self, authorization_id: str, reason: str) -> None:
        auth = self.authorizations.get(authorization_id)
        if auth is None:
            raise KeyError(authorization_id)
        auth.revoked = True
        self.task.bump_version("revoke:%s:%s" % (authorization_id, reason))

    def snapshot(self) -> Dict[str, Any]:
        return {
            "decisions": [d.to_dict() for d in self.task.decisions.values()],
            "authorizations": [a.to_dict() for a in self.authorizations.values()],
        }

    def _get(self, decision_id: str) -> DecisionRecord:
        if decision_id not in self.task.decisions:
            raise KeyError("决策不存在: %s" % decision_id)
        return self.task.decisions[decision_id]


class InteractionRouter:
    """Native Chat / AUQ dedup and channel transition (PFCI-HUMAN-5.0 7.4)."""

    def __init__(self, task: ResearchTask, decisions: DecisionManager,
                 auq_available: bool = True) -> None:
        self.task = task
        self.decisions = decisions
        self.auq_available = auq_available

    def open(self, topic: str, purpose: str, stage: Optional[StageID] = None,
             channel: str = NATIVE_CHAT, options: Optional[List[Dict[str, Any]]] = None,
             context_refs: Optional[List[str]] = None,
             decision_id: Optional[str] = None,
             authorization_scope: Optional[str] = None,
             expires_at: Optional[str] = None) -> Tuple[InteractionEvent, bool, str]:
        stage_id = (stage or self.task.current_stage).value
        base_key = "%s::%s::%s" % (self.task.research_task_id, stage_id, topic)
        for event in self.task.interactions.values():
            if event.dedup_key != base_key:
                continue
            if event.status == InteractionStatus.PENDING:
                return event, False, "同一事项已有有效交互实例，不得重复投递"
            if event.status == InteractionStatus.ANSWERED:
                return event, False, "同一事项已获得回答，除非条件变化不得重问"
        if channel == AUQ and not self.auq_available:
            channel = NATIVE_CHAT
        if decision_id is None:
            decision = self.decisions.propose(
                topic=topic, content=purpose,
                rationale="待与研究人员讨论的科研事项",
                evidence=context_refs, stage=stage,
            )
            decision_id = decision.decision_id
        event = InteractionEvent(
            interaction_id="ix-" + uuid.uuid4().hex[:8],
            research_task_id=self.task.research_task_id, stage_id=stage_id,
            decision_topic=topic, channel=channel,
            prompt_purpose=purpose, context_refs=list(context_refs or []),
            options=list(options or []), decision_id=decision_id,
            authorization_scope=authorization_scope, expires_at=expires_at,
            note="AUQ 不可用，回退 Native Chat" if channel == NATIVE_CHAT
                 and not self.auq_available else "",
        )
        self.task.interactions[event.interaction_id] = event
        self.task.bump_version("interaction:%s" % topic)
        return event, True, "new interaction"

    def answer(self, interaction_id: str, response: Any,
               channel: Optional[str] = None) -> Dict[str, Any]:
        event = self._get(interaction_id)
        if event.status != InteractionStatus.PENDING:
            raise ValueError("只能回答待决交互: %s" % event.status.value)
        event.user_response = response
        event.status = InteractionStatus.ANSWERED
        if channel:
            event.channel = channel
        self.task.bump_version("answer:%s" % interaction_id)
        return {
            "interaction_id": interaction_id, "decision_id": event.decision_id,
            "answer_recorded": True, "decision_confirmed": False,
            "execution_authorized": False,
            "note": "回答已回写上下文；确认、授权与执行仍需分别完成",
        }

    def confirm_from_answer(self, interaction_id: str, user_response: Optional[str] = None,
                            explicit_confirm: bool = False) -> DecisionRecord:
        """Answer != confirmation. Caller must pass an explicit confirmation intent."""
        event = self._get(interaction_id)
        if event.status != InteractionStatus.ANSWERED:
            raise ValueError("必须先记录用户回答")
        if not explicit_confirm:
            raise ValueError("缺少明确确认意图；回答不等于确认")
        text = user_response or str(event.user_response)
        return self.decisions.confirm(event.decision_id, text)

    def cancel(self, interaction_id: str, reason: str) -> InteractionEvent:
        event = self._get(interaction_id)
        event.status = InteractionStatus.CANCELLED
        event.note = "取消不等于拒绝: %s" % reason
        self.task.bump_version("cancel:%s" % interaction_id)
        return event

    def timeout(self, interaction_id: str) -> InteractionEvent:
        event = self._get(interaction_id)
        event.status = InteractionStatus.TIMED_OUT
        event.note = "超时不等于用户拒绝；需要重新检查上下文后决定是否重发"
        self.task.bump_version("timeout:%s" % interaction_id)
        return event

    def switch_channel(self, interaction_id: str, new_channel: str) -> InteractionEvent:
        old = self._get(interaction_id)
        if new_channel == AUQ and not self.auq_available:
            raise ValueError("AUQ 不可用，不能切换到 AUQ")
        old.status = InteractionStatus.SUPERSEDED
        old.note = "通道切换前关闭旧实例，避免同一事项两个有效交互"
        new, _, _ = self.open(
            topic=old.decision_topic, purpose=old.prompt_purpose,
            stage=StageID(old.stage_id), channel=new_channel,
            options=list(old.options), context_refs=list(old.context_refs),
            decision_id=old.decision_id,
            authorization_scope=old.authorization_scope,
        )
        return new

    def pending(self) -> List[InteractionEvent]:
        return [e for e in self.task.interactions.values()
                if e.status == InteractionStatus.PENDING]

    def _get(self, interaction_id: str) -> InteractionEvent:
        if interaction_id not in self.task.interactions:
            raise KeyError("交互不存在: %s" % interaction_id)
        return self.task.interactions[interaction_id]


__all__ = [
    "NATIVE_CHAT", "AUQ", "HIGH_IMPACT_OPERATIONS", "AuthorizationRecord",
    "DecisionManager", "InteractionRouter",
]
