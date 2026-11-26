"""IF0-1.0.0 contract data types and validation.

Pure standard library. No PFC / itasca dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

CONTRACT_VERSION = "IF0-1.0.0"


class ModuleID(str, Enum):
    M1 = "M1"
    M2 = "M2"
    M3 = "M3"
    M4 = "M4"
    M5 = "M5"
    M6 = "M6"


class EvidenceSource(str, Enum):
    """IF0 section 6.3: exactly five allowed sources."""

    USER_PROVIDED = "user_provided"
    PFC_EXECUTED = "pfc_executed"
    DERIVED_COMPUTED = "derived_computed"
    AGENT_INFERRED = "agent_inferred"
    PENDING_ASSUMPTION = "pending_assumption"
    INVALID_EVIDENCE = "invalid_evidence"

    @classmethod
    def non_conclusive(cls) -> set:
        """Sources that cannot alone support COMPLETED or a research conclusion."""
        return {
            cls.AGENT_INFERRED,
            cls.PENDING_ASSUMPTION,
            cls.INVALID_EVIDENCE,
        }


class DeliveryStatus(str, Enum):
    UNDELIVERED = "UNDELIVERED"
    DELIVERED = "DELIVERED"
    WAITING_ANSWER = "WAITING_ANSWER"
    ANSWERED = "ANSWERED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


@dataclass
class ArtifactRef:
    artifact_id: str
    path: str
    version: str
    hash: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "artifact_id": self.artifact_id,
            "path": self.path,
            "version": self.version,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactRef":
        return cls(
            artifact_id=str(data.get("artifact_id", "")),
            path=str(data.get("path", "")),
            version=str(data.get("version", "")),
            hash=str(data.get("hash", "")),
        )


@dataclass
class Evidence:
    source: EvidenceSource
    ref: str
    description: str = ""
    tool_task_id: Optional[str] = None

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not isinstance(self.source, EvidenceSource):
            try:
                self.source = EvidenceSource(str(self.source))
            except ValueError:
                errors.append("evidence.source must be one of the five IF0 values")
                return errors
        if not self.ref:
            errors.append("evidence.ref is required")
        if self.source == EvidenceSource.PFC_EXECUTED and not self.tool_task_id:
            errors.append("pfc_executed evidence requires tool_task_id")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "source": self.source.value,
            "ref": self.ref,
            "description": self.description,
        }
        if self.tool_task_id:
            out["tool_task_id"] = self.tool_task_id
        return out


@dataclass
class DecisionRef:
    decision_id: str
    delivery_status: DeliveryStatus = DeliveryStatus.UNDELIVERED
    resolution: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "decision_id": self.decision_id,
            "delivery_status": self.delivery_status.value,
        }
        if self.resolution:
            out["resolution"] = self.resolution
        return out


@dataclass
class Envelope:
    """IF0 section 4.1: unified module result envelope."""

    module_id: ModuleID
    module_version: str
    research_task_id: str
    module_task_id: str
    contract_version: str = CONTRACT_VERSION
    parent_task_id: Optional[str] = None
    input_refs: List[ArtifactRef] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    status: Dict[str, Any] = field(default_factory=dict)
    output: Dict[str, Any] = field(default_factory=dict)
    evidence: List[Evidence] = field(default_factory=list)
    decisions: List[DecisionRef] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.contract_version != CONTRACT_VERSION:
            errors.append(
                "contract_version mismatch: expected %s, got %s"
                % (CONTRACT_VERSION, self.contract_version)
            )
        for key, value in (
            ("module_id", self.module_id),
            ("module_version", self.module_version),
            ("research_task_id", self.research_task_id),
            ("module_task_id", self.module_task_id),
        ):
            if not value:
                errors.append("%s is required" % key)
        if "module_state" not in self.status:
            errors.append("status.module_state is required")
        if "structured" not in self.output:
            errors.append("output.structured is required")
        for ref in self.input_refs:
            if not all([ref.artifact_id, ref.path, ref.version, ref.hash]):
                errors.append(
                    "artifact reference incomplete: artifact_id/path/version/hash required"
                )
        for ev in self.evidence:
            errors.extend(ev.validate())
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "module_id": self.module_id.value,
            "module_version": self.module_version,
            "research_task_id": self.research_task_id,
            "module_task_id": self.module_task_id,
            "parent_task_id": self.parent_task_id,
            "input_refs": [r.to_dict() for r in self.input_refs],
            "preconditions": self.preconditions,
            "status": self.status,
            "output": self.output,
            "evidence": [e.to_dict() for e in self.evidence],
            "decisions": [d.to_dict() for d in self.decisions],
            "limitations": self.limitations,
        }


def validate_envelope_dict(data: Dict[str, Any]) -> List[str]:
    """Validate a raw envelope dict (used by I2 Result gate)."""
    errors: List[str] = []
    if data.get("contract_version") != CONTRACT_VERSION:
        errors.append("contract_version mismatch")
    if not data.get("module_task_id"):
        errors.append("module_task_id is required")
    status = data.get("status") or {}
    if "module_state" not in status:
        errors.append("status.module_state is required")
    output = data.get("output") or {}
    if "structured" not in output:
        errors.append("output.structured is required")
    for item in output.get("artifacts", []):
        if not all(k in item for k in ("artifact_id", "path", "version", "hash")):
            errors.append("output artifact must have artifact_id/path/version/hash")
    for item in data.get("evidence", []):
        try:
            src = EvidenceSource(str(item.get("source")))
        except ValueError:
            errors.append("invalid evidence source: %s" % item.get("source"))
            continue
        if src == EvidenceSource.PFC_EXECUTED and not item.get("tool_task_id"):
            errors.append("pfc_executed evidence requires tool_task_id")
    return errors
