"""PFC Interaction 5.0.1: evidence classification and hypothesis maturity."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EvidenceClass(str, Enum):
    USER_FACT = "USER_FACT"
    USER_EXPERIENCE = "USER_EXPERIENCE"
    SOURCE_FACT = "SOURCE_FACT"
    TOOL_OBSERVATION = "TOOL_OBSERVATION"
    COMPUTED_RESULT = "COMPUTED_RESULT"
    AGENT_INFERENCE = "AGENT_INFERENCE"
    AGENT_PROPOSAL = "AGENT_PROPOSAL"
    UNVERIFIED_ASSUMPTION = "UNVERIFIED_ASSUMPTION"

    @classmethod
    def non_conclusive(cls) -> set:
        return {cls.USER_EXPERIENCE, cls.AGENT_INFERENCE, cls.AGENT_PROPOSAL,
                cls.UNVERIFIED_ASSUMPTION}


class Maturity(str, Enum):
    IDEA = "IDEA"
    FORMULATED = "FORMULATED"
    ARGUED = "ARGUED"
    REVIEWED = "REVIEWED"
    PLANNED_FOR_VALIDATION = "PLANNED_FOR_VALIDATION"
    EMPIRICALLY_SUPPORTED = "EMPIRICALLY_SUPPORTED"
    VALIDATED_WITHIN_SCOPE = "VALIDATED_WITHIN_SCOPE"
    UNRESOLVED = "UNRESOLVED"


@dataclass
class EvidenceEntry:
    evidence_id: str
    evidence_class: EvidenceClass
    ref: str
    description: str = ""
    source: str = ""
    tool_task_id: str = ""
    confidence: str = "medium"
    created_at: str = field(default_factory=_now)

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self.ref:
            errors.append("证据必须有关联对象")
        if self.evidence_class == EvidenceClass.TOOL_OBSERVATION and not self.tool_task_id:
            errors.append("TOOL_OBSERVATION 必须提供真实 tool_task_id")
        if self.evidence_class == EvidenceClass.COMPUTED_RESULT and not self.source:
            errors.append("COMPUTED_RESULT 必须说明输入来源")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id, "evidence_class": self.evidence_class.value,
            "ref": self.ref, "description": self.description, "source": self.source,
            "tool_task_id": self.tool_task_id, "confidence": self.confidence,
            "created_at": self.created_at,
        }


class EvidenceManager:
    """Append-only evidence register with class promotion guard."""

    def __init__(self) -> None:
        self.entries: Dict[str, EvidenceEntry] = {}

    def add(self, evidence_class: EvidenceClass, ref: str, description: str = "",
            source: str = "", tool_task_id: str = "", confidence: str = "medium"
            ) -> EvidenceEntry:
        entry = EvidenceEntry(
            evidence_id="ev-" + uuid.uuid4().hex[:8], evidence_class=evidence_class,
            ref=ref, description=description, source=source,
            tool_task_id=tool_task_id, confidence=confidence,
        )
        errors = entry.validate()
        if errors:
            raise ValueError("证据登记失败: %s" % "; ".join(errors))
        self.entries[entry.evidence_id] = entry
        return entry

    def get(self, evidence_id: str) -> EvidenceEntry:
        if evidence_id not in self.entries:
            raise KeyError("证据不存在: %s" % evidence_id)
        return self.entries[evidence_id]

    def by_class(self, evidence_class: EvidenceClass) -> List[EvidenceEntry]:
        return [e for e in self.entries.values() if e.evidence_class == evidence_class]

    def assert_conclusive(self, evidence_ids: Iterable[str]) -> None:
        """Do not let experience/inference/proposal stand as conclusive evidence."""
        bad = [
            eid for eid in evidence_ids
            if self.get(eid).evidence_class in EvidenceClass.non_conclusive()
        ]
        if bad:
            raise ValueError("非结论性证据不得单独支持验证: %s" % ", ".join(bad))

    def snapshot(self) -> Dict[str, Any]:
        return {"evidence": [e.to_dict() for e in self.entries.values()]}


@dataclass
class Hypothesis:
    hypothesis_id: str
    statement: str
    maturity: Maturity = Maturity.IDEA
    competing: List[str] = field(default_factory=list)
    supporting_evidence: List[str] = field(default_factory=list)
    contradicting_evidence: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    version: int = 1
    history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id, "statement": self.statement,
            "maturity": self.maturity.value, "competing": list(self.competing),
            "supporting_evidence": list(self.supporting_evidence),
            "contradicting_evidence": list(self.contradicting_evidence),
            "limitations": list(self.limitations), "version": self.version,
            "history": list(self.history),
        }


class HypothesisManager:
    """Hypothesis register that never turns a user decision into validation."""

    def __init__(self, evidence: EvidenceManager) -> None:
        self.evidence = evidence
        self.hypotheses: Dict[str, Hypothesis] = {}

    def register(self, statement: str, competing: Optional[List[str]] = None,
                 limitations: Optional[List[str]] = None) -> Hypothesis:
        hyp = Hypothesis(
            hypothesis_id="hyp-" + uuid.uuid4().hex[:8], statement=statement,
            competing=list(competing or []), limitations=list(limitations or []),
        )
        self.hypotheses[hyp.hypothesis_id] = hyp
        return hyp

    def set_maturity(self, hypothesis_id: str, maturity: Maturity,
                     supporting: Optional[List[str]] = None,
                     contradicting: Optional[List[str]] = None,
                     reason: str = "") -> Hypothesis:
        hyp = self.hypotheses[hypothesis_id]
        if maturity in (Maturity.EMPIRICALLY_SUPPORTED, Maturity.VALIDATED_WITHIN_SCOPE):
            conclusive = list(supporting or [])
            if not conclusive:
                raise ValueError("数据支持必须有证据引用")
            self.evidence.assert_conclusive(conclusive)
        hyp.maturity = maturity
        hyp.supporting_evidence = sorted(set(hyp.supporting_evidence) | set(supporting or []))
        hyp.contradicting_evidence = sorted(
            set(hyp.contradicting_evidence) | set(contradicting or []))
        hyp.version += 1
        hyp.history.append({
            "maturity": maturity.value, "reason": reason, "version": hyp.version,
            "at": _now(),
        })
        return hyp

    def assess(self, hypothesis_id: str) -> Dict[str, Any]:
        hyp = self.hypotheses[hypothesis_id]
        if hyp.contradicting_evidence:
            maturity = Maturity.UNRESOLVED
            reason = "存在反证或证据不足，不能确认假设"
        elif hyp.supporting_evidence:
            maturity = Maturity.EMPIRICALLY_SUPPORTED
            reason = "有结论性证据支持；仍不等于限定范围内验证"
        else:
            maturity = Maturity.UNRESOLVED
            reason = "尚无结论性证据"
        self.set_maturity(hypothesis_id, maturity, reason=reason)
        return {
            "hypothesis_id": hypothesis_id, "maturity": maturity.value,
            "reason": reason, "competing": list(hyp.competing),
        }

    def snapshot(self) -> Dict[str, Any]:
        return {"hypotheses": [h.to_dict() for h in self.hypotheses.values()]}


__all__ = [
    "EvidenceClass", "Maturity", "EvidenceEntry", "EvidenceManager",
    "Hypothesis", "HypothesisManager",
]
