"""PFC Interaction 5.0: unified research context, states and evidence.

Implements PFCI-ARCH-5.0 sections 4/7/8/9 and the data model in the 5.0
technical report section 8. Pure standard library; the 4.0 core is untouched.

Key rule: stage state, module task state, discussion state, decision state and
execution state are separate fields. No single ambiguous ``status`` is used.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    return "%s-%s" % (prefix, uuid.uuid4().hex[:8])


class StageID(str, Enum):
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    S4 = "S4"
    S5 = "S5"
    S6 = "S6"

    @property
    def label(self) -> str:
        return STAGE_LABELS[self]


STAGE_LABELS: Dict[StageID, str] = {
    StageID.S1: "研究对象与科研目标",
    StageID.S2: "实验类别与实验设计",
    StageID.S3: "技术方案与建模路线",
    StageID.S4: "参数确定与标定",
    StageID.S5: "仿真执行与异常干预",
    StageID.S6: "结果分析与科研总结",
}
STAGE_ORDER: List[StageID] = list(StageID)

# User-visible stage artifacts (PFCI-ARCH-5.0 4, technical report 3.x).
STAGE_ARTIFACTS: Dict[StageID, List[str]] = {
    StageID.S1: ["research_brief", "research_question", "research_hypotheses", "research_scope"],
    StageID.S2: ["experiment_design", "experiment_matrix", "variable_schema", "measurement_plan"],
    StageID.S3: ["technical_route", "model_design", "model_requirements",
                 "measurement_schema", "model_validation_plan"],
    StageID.S4: ["parameter_register", "calibration_plan", "calibration_matrix",
                 "calibration_history", "calibration_results", "calibrated_parameters"],
    StageID.S5: ["simulation_config", "simulation_status", "simulation_log",
                 "checkpoint_manifest", "anomaly_records", "execution_report"],
    StageID.S6: ["raw_data_manifest", "processed_data", "analysis_config",
                 "analysis_results", "comparison_report", "diagnosis_report",
                 "analysis_report", "research_conclusion"],
}

# Qualitative completion conditions. None of these is a question count.
STAGE_COMPLETION: Dict[StageID, List[str]] = {
    StageID.S1: ["research_object_defined", "scientific_question_defined",
                 "boundary_recorded", "user_agreed_to_advance"],
    StageID.S2: ["experiment_type_defined", "variable_relations_defined",
                 "control_strategy_justified", "measurements_defined",
                 "design_choices_confirmed"],
    StageID.S3: ["technical_route_justified", "model_design_defined",
                 "validation_plan_defined", "key_assumptions_confirmed"],
    StageID.S4: ["parameter_sources_and_units_recorded", "calibration_executed_or_failure_recorded",
                 "errors_evaluated", "calibration_state_truthful"],
    StageID.S5: ["tool_evidence_present", "cases_completed_or_marked",
                 "output_integrity_checked", "anomaly_actions_traceable"],
    StageID.S6: ["metric_definitions_clear", "data_limitations_stated",
                 "conclusion_within_evidence", "user_confirmed_or_unverified_recorded"],
}

# Hints only: a stage may call several modules; a module may serve several stages.
STAGE_MODULE_HINTS: Dict[StageID, List[str]] = {
    StageID.S1: ["M1"],
    StageID.S2: ["M1", "M2"],
    StageID.S3: ["M2", "M3"],
    StageID.S4: ["M2", "M3", "M4", "M5", "M6"],
    StageID.S5: ["M4", "M5", "M3"],
    StageID.S6: ["M5", "M6", "M1"],
}


class StageStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    DISCUSSING = "DISCUSSING"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    REOPENED = "REOPENED"
    CANCELLED = "CANCELLED"


class ModuleTaskStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class EvidenceKind(str, Enum):
    USER_INPUT = "USER_INPUT"
    AGENT_PROPOSAL = "AGENT_PROPOSAL"
    TOOL_EVIDENCE = "TOOL_EVIDENCE"
    COMPUTED_RESULT = "COMPUTED_RESULT"
    INFERENCE = "INFERENCE"
    UNVERIFIED_ASSUMPTION = "UNVERIFIED_ASSUMPTION"

    @classmethod
    def non_conclusive(cls) -> set:
        return {cls.AGENT_PROPOSAL, cls.INFERENCE, cls.UNVERIFIED_ASSUMPTION}


class ParameterStatus(str, Enum):
    USER_PROVIDED = "USER_PROVIDED"
    AGENT_SUGGESTED = "AGENT_SUGGESTED"
    TO_BE_CALIBRATED = "TO_BE_CALIBRATED"
    CALIBRATING = "CALIBRATING"
    CALIBRATED = "CALIBRATED"
    CONFIRMED = "CONFIRMED"
    USED_IN_SIMULATION = "USED_IN_SIMULATION"
    DEPRECATED = "DEPRECATED"


class ConfirmationStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"
    INVALIDATED = "INVALIDATED"


class DecisionStatus(str, Enum):
    PROPOSED = "PROPOSED"
    DISCUSSING = "DISCUSSING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"


class InteractionStatus(str, Enum):
    PENDING = "PENDING"
    ANSWERED = "ANSWERED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    SUPERSEDED = "SUPERSEDED"


@dataclass
class EvidenceItem:
    kind: EvidenceKind
    ref: str
    description: str = ""
    tool_task_id: str = ""
    input_refs: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self.ref:
            errors.append("证据必须有关联对象 ref")
        if self.kind == EvidenceKind.TOOL_EVIDENCE and not self.tool_task_id:
            errors.append("TOOL_EVIDENCE 必须提供真实 tool_task_id")
        if self.kind == EvidenceKind.COMPUTED_RESULT and not self.input_refs:
            errors.append("COMPUTED_RESULT 必须声明输入数据引用")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value, "ref": self.ref,
            "description": self.description, "tool_task_id": self.tool_task_id,
            "input_refs": list(self.input_refs), "created_at": self.created_at,
        }


@dataclass
class ParameterRecord:
    parameter_id: str
    name: str
    physical_meaning: str = ""
    value: Any = None
    unit: str = ""
    value_range: List[Any] = field(default_factory=list)
    source_type: str = "user_provided"
    source_reference: str = ""
    rationale: str = ""
    calibration_status: ParameterStatus = ParameterStatus.TO_BE_CALIBRATED
    confirmation_status: ConfirmationStatus = ConfirmationStatus.PENDING
    target_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    error_metrics: Dict[str, float] = field(default_factory=dict)
    acceptance_criteria: Dict[str, Any] = field(default_factory=dict)
    version: int = 1
    change_history: List[Dict[str, Any]] = field(default_factory=list)

    def propose_value(self, value: Any, reason: str, source_type: str,
                      source_reference: str = "") -> None:
        if not reason:
            raise ValueError("参数取值变更必须给出原因")
        if source_type not in ("user_provided", "agent_proposal", "literature",
                               "experiment_measurement", "empirical_estimate", "inverse_calibration"):
            raise ValueError("未知参数来源: %s" % source_type)
        self.value = value
        self.source_type = source_type
        self.source_reference = source_reference
        self.rationale = reason
        self.version += 1
        self.calibration_status = (
            ParameterStatus.USER_PROVIDED if source_type == "user_provided"
            else ParameterStatus.AGENT_SUGGESTED
        )
        self.confirmation_status = ConfirmationStatus.PENDING
        self.change_history.append({
            "version": self.version, "value": value, "reason": reason,
            "source_type": source_type, "source_reference": source_reference,
            "at": _now(),
        })

    def start_calibration(self) -> None:
        self.calibration_status = ParameterStatus.CALIBRATING

    def mark_calibrated(self, evidence: Iterable[EvidenceItem], acceptance_met: bool,
                        reason: str) -> None:
        ev = list(evidence)
        if not self.target_metrics:
            raise ValueError("没有目标指标不得标记已标定")
        if not self.error_metrics:
            raise ValueError("没有误差计算不得标记已标定")
        if not self.acceptance_criteria:
            raise ValueError("没有预设接受标准不得标记已标定")
        if not acceptance_met:
            raise ValueError("未达到接受标准不得标记已标定")
        if not any(e.kind in (EvidenceKind.TOOL_EVIDENCE, EvidenceKind.COMPUTED_RESULT)
                   for e in ev):
            raise ValueError("标定结论缺少工具或计算证据")
        self.calibration_status = ParameterStatus.CALIBRATED
        self.change_history.append({
            "version": self.version, "event": "CALIBRATED", "reason": reason,
            "errors": dict(self.error_metrics), "at": _now(),
        })

    def confirm(self, user_response: str) -> None:
        if not user_response:
            raise ValueError("参数确认必须记录用户回答")
        if self.calibration_status == ParameterStatus.CALIBRATING:
            raise ValueError("标定中的参数不能标记为已确认")
        self.confirmation_status = ConfirmationStatus.CONFIRMED
        self.calibration_status = ParameterStatus.CONFIRMED

    def invalidate(self, reason: str) -> None:
        self.confirmation_status = ConfirmationStatus.INVALIDATED
        self.change_history.append({
            "version": self.version, "event": "INVALIDATED", "reason": reason,
            "at": _now(),
        })

    def mark_used(self) -> None:
        if self.calibration_status not in (ParameterStatus.CALIBRATED, ParameterStatus.CONFIRMED):
            raise ValueError("未标定/未确认参数不得标记为已用于正式仿真")
        self.calibration_status = ParameterStatus.USED_IN_SIMULATION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parameter_id": self.parameter_id, "name": self.name,
            "physical_meaning": self.physical_meaning, "value": self.value,
            "unit": self.unit, "range": list(self.value_range),
            "source_type": self.source_type, "source_reference": self.source_reference,
            "rationale": self.rationale,
            "calibration_status": self.calibration_status.value,
            "confirmation_status": self.confirmation_status.value,
            "target_metrics": self.target_metrics, "error_metrics": self.error_metrics,
            "acceptance_criteria": self.acceptance_criteria,
            "version": self.version, "change_history": list(self.change_history),
        }


@dataclass
class DecisionRecord:
    decision_id: str
    research_task_id: str
    stage_id: str
    topic: str
    proposal: Dict[str, Any]
    status: DecisionStatus = DecisionStatus.PROPOSED
    user_response: Dict[str, Any] = field(default_factory=lambda: {"content": "", "confirmed": False})
    evidence: List[str] = field(default_factory=list)
    affected_assets: List[str] = field(default_factory=list)
    supersedes: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)

    def discuss(self, note: str) -> None:
        if self.status in (DecisionStatus.CONFIRMED, DecisionStatus.REJECTED,
                           DecisionStatus.SUPERSEDED, DecisionStatus.INVALIDATED):
            raise ValueError("终态决策不能重新讨论: %s" % self.status.value)
        self.status = DecisionStatus.DISCUSSING
        self.history.append({"event": "DISCUSSING", "note": note, "at": _now()})

    def confirm(self, user_response: str) -> None:
        if not user_response:
            raise ValueError("确认决策必须记录真实用户回答")
        if self.status in (DecisionStatus.REJECTED, DecisionStatus.SUPERSEDED,
                           DecisionStatus.INVALIDATED):
            raise ValueError("不能确认 %s 决策" % self.status.value)
        self.status = DecisionStatus.CONFIRMED
        self.user_response = {"content": user_response, "confirmed": True}
        self.history.append({"event": "CONFIRMED", "response": user_response, "at": _now()})

    def reject(self, user_response: str) -> None:
        self.status = DecisionStatus.REJECTED
        self.user_response = {"content": user_response, "confirmed": False}
        self.history.append({"event": "REJECTED", "response": user_response, "at": _now()})

    def defer(self, reason: str) -> None:
        self.status = DecisionStatus.DEFERRED
        self.history.append({"event": "DEFERRED", "reason": reason, "at": _now()})

    def invalidate(self, reason: str) -> None:
        self.status = DecisionStatus.INVALIDATED
        self.history.append({"event": "INVALIDATED", "reason": reason, "at": _now()})

    def supersede(self, new_id: str) -> None:
        self.status = DecisionStatus.SUPERSEDED
        self.history.append({"event": "SUPERSEDED", "by": new_id, "at": _now()})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id, "research_task_id": self.research_task_id,
            "stage_id": self.stage_id, "topic": self.topic,
            "proposal": dict(self.proposal), "status": self.status.value,
            "user_response": dict(self.user_response), "evidence": list(self.evidence),
            "affected_assets": list(self.affected_assets), "supersedes": self.supersedes,
            "history": list(self.history),
        }


@dataclass
class InteractionEvent:
    interaction_id: str
    research_task_id: str
    stage_id: str
    decision_topic: str
    channel: str = "native_chat"
    status: InteractionStatus = InteractionStatus.PENDING
    prompt_purpose: str = ""
    context_refs: List[str] = field(default_factory=list)
    options: List[Dict[str, Any]] = field(default_factory=list)
    user_response: Any = None
    decision_id: Optional[str] = None
    authorization_scope: Optional[str] = None
    created_at: str = field(default_factory=_now)
    expires_at: Optional[str] = None
    note: str = ""

    @property
    def dedup_key(self) -> str:
        return "%s::%s::%s" % (
            self.research_task_id, self.stage_id, self.decision_topic)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interaction_id": self.interaction_id,
            "research_task_id": self.research_task_id, "stage_id": self.stage_id,
            "decision_topic": self.decision_topic, "channel": self.channel,
            "status": self.status.value, "prompt_purpose": self.prompt_purpose,
            "context_refs": list(self.context_refs), "options": list(self.options),
            "user_response": self.user_response, "decision_id": self.decision_id,
            "authorization_scope": self.authorization_scope,
            "created_at": self.created_at, "expires_at": self.expires_at,
            "note": self.note, "dedup_key": self.dedup_key,
        }


@dataclass
class ResearchTask:
    research_task_id: str
    title: str
    current_stage: StageID = StageID.S1
    stage_status: Dict[str, str] = field(default_factory=dict)
    objectives: List[str] = field(default_factory=list)
    research_questions: List[str] = field(default_factory=list)
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    discussion: Dict[str, Any] = field(default_factory=lambda: {
        "current_topic": "", "confirmed": [], "pending": [], "rejected": [],
        "unresolved": [], "alternatives": [],
    })
    decisions: Dict[str, DecisionRecord] = field(default_factory=dict)
    parameters: Dict[str, ParameterRecord] = field(default_factory=dict)
    experiments: List[Dict[str, Any]] = field(default_factory=list)
    models: List[Dict[str, Any]] = field(default_factory=list)
    simulations: List[Dict[str, Any]] = field(default_factory=list)
    diagnoses: List[Dict[str, Any]] = field(default_factory=list)
    analyses: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[EvidenceItem] = field(default_factory=list)
    interactions: Dict[str, InteractionEvent] = field(default_factory=dict)
    provenance: List[Dict[str, Any]] = field(default_factory=list)
    version_counter: int = 1

    def __post_init__(self) -> None:
        if not self.stage_status:
            self.stage_status = {s.value: StageStatus.NOT_STARTED.value for s in STAGE_ORDER}
            self.stage_status[StageID.S1.value] = StageStatus.DISCUSSING.value

    @property
    def context_version(self) -> str:
        return "cv%d" % self.version_counter

    def bump_version(self, reason: str) -> str:
        self.version_counter += 1
        self.provenance.append({
            "version": self.context_version, "reason": reason, "at": _now(),
            "stage": self.current_stage.value,
        })
        return self.context_version

    def add_evidence(self, item: EvidenceItem) -> EvidenceItem:
        errors = item.validate()
        if errors:
            raise ValueError("证据无效: %s" % "; ".join(errors))
        self.evidence.append(item)
        self.bump_version("evidence:%s" % item.kind.value)
        return item

    def add_decision(self, decision: DecisionRecord) -> DecisionRecord:
        self.decisions[decision.decision_id] = decision
        self.bump_version("decision:%s" % decision.topic)
        return decision

    def add_parameter(self, parameter: ParameterRecord) -> ParameterRecord:
        self.parameters[parameter.parameter_id] = parameter
        self.bump_version("parameter:%s" % parameter.name)
        return parameter

    def add_artifact(self, artifact: Dict[str, Any]) -> Dict[str, Any]:
        self.artifacts.append(dict(artifact))
        self.bump_version("artifact:%s" % artifact.get("name", "unnamed"))
        return artifact

    def set_stage_status(self, stage: StageID, status: StageStatus, reason: str) -> None:
        self.stage_status[stage.value] = status.value
        self.bump_version("stage:%s:%s:%s" % (stage.value, status.value, reason))

    def snapshot(self) -> Dict[str, Any]:
        return {
            "research_task": {
                "research_task_id": self.research_task_id, "title": self.title,
                "current_stage": self.current_stage.value,
                "stage_status": dict(self.stage_status),
                "context_version": self.context_version,
                "objectives": list(self.objectives),
                "research_questions": list(self.research_questions),
                "hypotheses": list(self.hypotheses),
                "constraints": list(self.constraints),
                "discussion": dict(self.discussion),
                "decisions": [d.to_dict() for d in self.decisions.values()],
                "parameters": [p.to_dict() for p in self.parameters.values()],
                "experiments": list(self.experiments),
                "models": list(self.models),
                "simulations": list(self.simulations),
                "diagnoses": list(self.diagnoses),
                "analyses": list(self.analyses),
                "artifacts": list(self.artifacts),
                "evidence": [e.to_dict() for e in self.evidence],
                "interactions": [i.to_dict() for i in self.interactions.values()],
                "provenance": list(self.provenance),
            }
        }


__all__ = [
    "StageID", "StageStatus", "ModuleTaskStatus", "EvidenceKind", "ParameterStatus",
    "ConfirmationStatus", "DecisionStatus", "InteractionStatus", "STAGE_ORDER",
    "STAGE_LABELS", "STAGE_ARTIFACTS", "STAGE_COMPLETION", "STAGE_MODULE_HINTS",
    "EvidenceItem", "ParameterRecord", "DecisionRecord", "InteractionEvent",
    "ResearchTask", "_uid", "_now",
]
