"""S4 core subsystem data contracts (S4_SPEC V2.0 chapters 2, 3, 11).

Parameter Identification & Calibration System. Pure standard library. This is
an independent core subsystem layered on the 5.x context; it does NOT change
4.0/5.0/5.0.1/5.1 carriers. No object here can declare a calibration result:
objects only carry structured state; engines and orchestration decide.

Three non-degradable rules are encoded here as invariants:
  1. scientific relation before numerical tuning (relations carry conditions);
  2. each parameter argued independently but never determined in isolation
     (independent archive + parameter group both exist);
  3. scientific judgement freezes parameters (status transitions need acts).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    return "%s-%s" % (prefix, uuid.uuid4().hex[:8])


def _fingerprint(payload: Dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return "cf-" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


class ParamClass(str, Enum):
    """Five ways a parameter is determined (spec 2.1)."""

    DIRECT_MEASURED = "DIRECT_MEASURED"
    EXPERIMENT_ESTIMATED = "EXPERIMENT_ESTIMATED"
    INVERSE = "INVERSE"
    NUMERICAL_CONTROL = "NUMERICAL_CONTROL"
    STRUCTURE_MODEL = "STRUCTURE_MODEL"


class EvidenceGrade(str, Enum):
    """Experience credibility E0-E5 (spec 7.5)."""

    E0 = "E0"
    E1 = "E1"
    E2 = "E2"
    E3 = "E3"
    E4 = "E4"
    E5 = "E5"


class RelationStatus(str, Enum):
    """Relation evidence states (spec 3.4)."""

    PROPOSED = "PROPOSED"
    MECHANISM_INFERRED = "MECHANISM_INFERRED"
    LITERATURE_SUPPORTED = "LITERATURE_SUPPORTED"
    PROJECT_SCREENING = "PROJECT_SCREENING"
    MULTI_CASE_VALIDATED = "MULTI_CASE_VALIDATED"
    NEGATED = "NEGATED"


class DataStatus(str, Enum):
    observed = "observed"
    computed = "computed"
    predicted = "predicted"
    inferred = "inferred"
    expert_prior = "expert_prior"
    validated = "validated"


NON_CONCLUSIVE_DATA = {DataStatus.predicted, DataStatus.inferred, DataStatus.expert_prior}


class ParamState(str, Enum):
    """Six-step parameter state (spec 5.5)."""

    INITIAL = "INITIAL"
    CANDIDATE = "CANDIDATE"
    PROVISIONAL = "PROVISIONAL"
    USER_CONFIRMED = "USER_CONFIRMED"
    CALIBRATED = "CALIBRATED"
    VALIDATED = "VALIDATED"


class FitPhase(str, Enum):
    """Fitting vs calibration vs independent validation (spec 12.1)."""

    FIT = "FIT"
    CALIBRATION = "CALIBRATION"
    INDEPENDENT_VALIDATION = "INDEPENDENT_VALIDATION"


class ContactModel(str, Enum):
    LINEAR = "LINEAR"
    LINEAR_PARALLEL_BOND = "LINEAR_PARALLEL_BOND"
    FLAT_JOINT = "FLAT_JOINT"
    ROLLING_RESISTANCE = "ROLLING_RESISTANCE"
    HERTZ = "HERTZ"
    OTHER = "OTHER"


@dataclass
class ModelCondition:
    """Structure/working-condition fingerprint (spec 3 layer 4, 11.2)."""

    contact_model: str
    pfc_version: str
    dimension: str = "3D"
    material_class: str = ""
    particle_shape: str = ""
    gradation: str = ""
    porosity: Optional[float] = None
    preparation: str = ""
    boundary: str = ""
    loading: str = ""
    condition_id: str = field(default_factory=lambda: _uid("cond"))

    @property
    def fingerprint(self) -> str:
        return _fingerprint({
            "contact_model": self.contact_model, "pfc_version": self.pfc_version,
            "dimension": self.dimension, "material_class": self.material_class,
            "particle_shape": self.particle_shape, "gradation": self.gradation,
            "porosity": self.porosity, "preparation": self.preparation,
            "boundary": self.boundary, "loading": self.loading,
        })

    def same_as(self, other: "ModelCondition") -> bool:
        return self.fingerprint == other.fingerprint

    def to_dict(self) -> Dict[str, Any]:
        return {
            "condition_id": self.condition_id, "contact_model": self.contact_model,
            "pfc_version": self.pfc_version, "dimension": self.dimension,
            "material_class": self.material_class, "particle_shape": self.particle_shape,
            "gradation": self.gradation, "porosity": self.porosity,
            "preparation": self.preparation, "boundary": self.boundary,
            "loading": self.loading, "fingerprint": self.fingerprint,
        }


@dataclass
class FiveLayerRelation:
    """Five-layer relation analysis record (spec 3.2)."""

    macro_goal: str
    micro_mechanism: str
    micro_parameter: str
    structure_condition: str
    evidence: str

    def validate(self) -> List[str]:
        errors: List[str] = []
        for name in ("macro_goal", "micro_mechanism", "micro_parameter",
                     "structure_condition", "evidence"):
            if not getattr(self, name).strip():
                errors.append("五层关系缺少 %s 层" % name)
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "macro_goal": self.macro_goal, "micro_mechanism": self.micro_mechanism,
            "micro_parameter": self.micro_parameter,
            "structure_condition": self.structure_condition, "evidence": self.evidence,
        }


@dataclass
class MacroTarget:
    target_id: str
    metric: str
    value: float
    unit: str
    tolerance: float
    weight: float = 1.0
    priority: str = "soft"          # hard / soft
    data_status: DataStatus = DataStatus.observed
    source: str = ""
    role: FitPhase = FitPhase.FIT   # fit vs independent validation
    description: str = ""

    def __post_init__(self) -> None:
        if self.tolerance < 0:
            raise ValueError("宏观目标容差不能为负")
        if self.priority not in ("hard", "soft"):
            raise ValueError("指标优先级只能是 hard 或 soft")
        if self.weight < 0:
            raise ValueError("指标权重不能为负")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_id": self.target_id, "metric": self.metric, "value": self.value,
            "unit": self.unit, "tolerance": self.tolerance, "weight": self.weight,
            "priority": self.priority, "data_status": self.data_status.value,
            "source": self.source, "role": self.role.value, "description": self.description,
        }


@dataclass
class MicroParameter:
    """Independent parameter archive; B scheme requires one per parameter."""

    parameter_id: str
    name: str
    param_class: ParamClass
    unit: str = ""
    current_value: Any = None
    bounds: List[Any] = field(default_factory=list)
    contact_model: str = ""
    physical_meaning: str = ""
    transform: str = "linear"       # linear / log
    source: str = ""
    state: ParamState = ParamState.INITIAL
    condition_ref: str = ""
    change_log: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.transform not in ("linear", "log"):
            raise ValueError("参数变换只能是 linear 或 log")
        if self.param_class == ParamClass.STRUCTURE_MODEL and not self.contact_model:
            # structure/model parameters must state which model they belong to
            self.contact_model = self.contact_model or "MODEL_STRUCTURE"

    def set_state(self, state: ParamState, reason: str) -> None:
        if not reason:
            raise ValueError("参数状态流转必须记录理由")
        self.state = state
        self.change_log.append({"state": state.value, "reason": reason, "at": _now()})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parameter_id": self.parameter_id, "name": self.name,
            "param_class": self.param_class.value, "unit": self.unit,
            "current_value": self.current_value, "bounds": list(self.bounds),
            "contact_model": self.contact_model, "physical_meaning": self.physical_meaning,
            "transform": self.transform, "source": self.source,
            "state": self.state.value, "condition_ref": self.condition_ref,
            "change_log": list(self.change_log),
        }


@dataclass
class ParameterRelation:
    """Traceable parameter-target relation (spec 3.6 / 9.2)."""

    relation_id: str
    parameter_id: str
    target_id: str
    five_layers: FiveLayerRelation
    relation_type: str = "unknown"  # positive/negative/nonlinear/interaction/unknown
    effect_estimate: Optional[float] = None
    uncertainty: Optional[float] = None
    status: RelationStatus = RelationStatus.PROPOSED
    evidence_grade: EvidenceGrade = EvidenceGrade.E0
    contact_model: str = ""
    condition_ref: str = ""
    parameter_domain: List[Any] = field(default_factory=list)
    source_run_ids: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    valid_from: str = ""

    def __post_init__(self) -> None:
        errors = self.five_layers.validate()
        if errors:
            raise ValueError("; ".join(errors))
        if self.relation_type not in ("positive", "negative", "nonlinear", "interaction", "unknown"):
            raise ValueError("未知关系类型: %s" % self.relation_type)
        if not self.contact_model:
            raise ValueError("参数关系必须声明接触模型，禁止跨模型静态映射")
        if not self.condition_ref:
            raise ValueError("参数关系必须绑定结构/工况条件指纹")

    def upgrade_status(self, status: RelationStatus, evidence_grade: EvidenceGrade,
                       run_ids: List[str]) -> None:
        """Literature cannot be upgraded to project validation by decree."""
        if status in (RelationStatus.PROJECT_SCREENING, RelationStatus.MULTI_CASE_VALIDATED):
            if not run_ids:
                raise ValueError("项目试算/多工况验证状态必须关联真实运行 id")
            if evidence_grade.value not in ("E3", "E4", "E5"):
                raise ValueError("项目级状态需要 E3/E4/E5 证据，文献或理论不足")
        if status == RelationStatus.MULTI_CASE_VALIDATED and evidence_grade != EvidenceGrade.E5:
            raise ValueError("多工况验证状态必须是 E5 证据")
        self.status = status
        self.evidence_grade = evidence_grade
        self.source_run_ids = list(set(self.source_run_ids + run_ids))

    def negate(self, reason: str) -> None:
        self.status = RelationStatus.NEGATED
        self.limitations.append("被否定: %s" % reason)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relation_id": self.relation_id, "parameter_id": self.parameter_id,
            "target_id": self.target_id, "five_layers": self.five_layers.to_dict(),
            "relation_type": self.relation_type, "effect_estimate": self.effect_estimate,
            "uncertainty": self.uncertainty, "status": self.status.value,
            "evidence_grade": self.evidence_grade.value, "contact_model": self.contact_model,
            "condition_ref": self.condition_ref,
            "parameter_domain": list(self.parameter_domain),
            "source_run_ids": list(self.source_run_ids),
            "limitations": list(self.limitations), "created_at": self.created_at,
            "valid_from": self.valid_from,
        }


@dataclass
class CalibrationConstraint:
    constraint_id: str
    constraint_type: str      # model_condition / physical / budget / protocol
    description: str
    value: Any = None
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_id": self.constraint_id, "constraint_type": self.constraint_type,
            "description": self.description, "value": self.value, "source": self.source,
        }


@dataclass
class CalibrationPlan:
    plan_id: str
    stages: List[str] = field(default_factory=list)      # C1-C8 subset/order
    strategy: str = "screening_validation_quantification"
    objective: str = "multi_metric_weighted"
    budget: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    validation_cases: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        allowed = {"C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"}
        if not self.stages or any(s not in allowed for s in self.stages):
            raise ValueError("标定计划阶段必须是 C1-C8 的子集且非空")
        if "C8" not in self.stages:
            raise ValueError("标定计划必须包含 C8 独立验证与冻结环节")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id, "stages": list(self.stages),
            "strategy": self.strategy, "objective": self.objective,
            "budget": dict(self.budget), "constraints": list(self.constraints),
            "validation_cases": list(self.validation_cases),
        }


_FAKE_TASK_IDS = ("recorded-", "synthetic", "fake", "mock", "demo", "dryrun")


@dataclass
class CalibrationRun:
    run_id: str
    parameter_version_ref: str
    condition_ref: str
    tool_task_id: str
    data_ref: str
    phase: FitPhase = FitPhase.CALIBRATION
    metrics: Dict[str, float] = field(default_factory=dict)
    random_seed: str = ""
    created_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.tool_task_id or self.tool_task_id.lower().startswith(_FAKE_TASK_IDS):
            raise ValueError("拒绝无真实 tool_task_id 的标定运行记录")
        if not self.data_ref:
            raise ValueError("运行必须关联数据产物")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "parameter_version_ref": self.parameter_version_ref,
            "condition_ref": self.condition_ref, "tool_task_id": self.tool_task_id,
            "data_ref": self.data_ref, "phase": self.phase.value,
            "metrics": dict(self.metrics), "random_seed": self.random_seed,
            "created_at": self.created_at,
        }


@dataclass
class CalibrationResult:
    result_id: str
    run_ref: str
    errors: Dict[str, float] = field(default_factory=dict)
    weighted_error: Optional[float] = None
    diagnostics: List[str] = field(default_factory=list)
    data_status: DataStatus = DataStatus.computed
    quality: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id, "run_ref": self.run_ref,
            "errors": dict(self.errors), "weighted_error": self.weighted_error,
            "diagnostics": list(self.diagnostics), "data_status": self.data_status.value,
            "quality": self.quality,
        }


@dataclass
class CalibrationDecision:
    decision_id: str
    topic: str
    problem: str = ""
    candidates: List[str] = field(default_factory=list)
    recommendation: str = ""
    user_response: str = ""
    approval_state: str = "PENDING"   # PENDING / CONFIRMED / REJECTED / DEFERRED
    evidence_refs: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)

    def approve(self, response: str) -> None:
        if not response:
            raise ValueError("用户确认必须记录真实回答")
        self.user_response = response
        self.approval_state = "CONFIRMED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id, "topic": self.topic,
            "problem": self.problem, "candidates": list(self.candidates),
            "recommendation": self.recommendation, "user_response": self.user_response,
            "approval_state": self.approval_state, "evidence_refs": list(self.evidence_refs),
            "created_at": self.created_at,
        }


@dataclass
class CalibrationValidation:
    validation_id: str
    held_out_conditions: List[str] = field(default_factory=list)
    criteria: Dict[str, float] = field(default_factory=dict)
    outcomes: Dict[str, float] = field(default_factory=dict)
    mechanism_check: str = ""
    passed: bool = False
    validity_domain: List[str] = field(default_factory=list)
    unresolved: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.held_out_conditions:
            raise ValueError("独立验证必须至少包含一个未参与标定的工况")
        if self.passed and not self.outcomes:
            raise ValueError("独立验证通过必须给出结果数据")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "held_out_conditions": list(self.held_out_conditions),
            "criteria": dict(self.criteria), "outcomes": dict(self.outcomes),
            "mechanism_check": self.mechanism_check, "passed": self.passed,
            "validity_domain": list(self.validity_domain),
            "unresolved": list(self.unresolved),
        }


@dataclass
class ExperienceRecord:
    """Project-level rule/experience entry with explicit scope and grade."""

    record_id: str
    claim: str
    evidence_grade: EvidenceGrade
    contact_model: str
    dimension: str
    material_class: str = ""
    pfc_version: str = ""
    gradation: str = ""
    porosity: Optional[float] = None
    loading: str = ""
    parameter_domain: List[Any] = field(default_factory=list)
    response_change: str = ""
    scope: str = ""
    success_cases: List[str] = field(default_factory=list)
    counterexamples: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    active: bool = True

    def applies_to(self, condition: ModelCondition) -> bool:
        """E5 never propagates across material/model/dimension (spec 7.5)."""
        return (self.active and self.contact_model == condition.contact_model
                and self.dimension == condition.dimension
                and (not self.material_class or self.material_class == condition.material_class))

    def negate(self, reason: str) -> None:
        self.counterexamples.append(reason)
        self.active = False
        self.limitations.append("被新证据否定: %s" % reason)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id, "claim": self.claim,
            "evidence_grade": self.evidence_grade.value,
            "contact_model": self.contact_model, "dimension": self.dimension,
            "material_class": self.material_class, "pfc_version": self.pfc_version,
            "gradation": self.gradation, "porosity": self.porosity, "loading": self.loading,
            "parameter_domain": list(self.parameter_domain),
            "response_change": self.response_change, "scope": self.scope,
            "success_cases": list(self.success_cases),
            "counterexamples": list(self.counterexamples),
            "limitations": list(self.limitations), "active": self.active,
        }


@dataclass
class ParameterGroup:
    """Joint analysis group (B scheme): never replaces independent archives."""

    group_id: str
    name: str
    parameter_ids: List[str] = field(default_factory=list)
    rationale: str = ""
    coupling_questions: Dict[str, bool] = field(default_factory=dict)
    joint_decision: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id, "name": self.name,
            "parameter_ids": list(self.parameter_ids), "rationale": self.rationale,
            "coupling_questions": dict(self.coupling_questions),
            "joint_decision": self.joint_decision,
        }


@dataclass
class CalibrationProject:
    """S4 master object; cross-session state holder."""

    project_id: str
    title: str
    condition: ModelCondition
    status: str = "draft"          # C1-C8 workflow status
    targets: Dict[str, MacroTarget] = field(default_factory=dict)
    parameters: Dict[str, MicroParameter] = field(default_factory=dict)
    relations: Dict[str, ParameterRelation] = field(default_factory=dict)
    constraints: Dict[str, CalibrationConstraint] = field(default_factory=dict)
    plans: Dict[str, CalibrationPlan] = field(default_factory=dict)
    runs: Dict[str, CalibrationRun] = field(default_factory=dict)
    results: Dict[str, CalibrationResult] = field(default_factory=dict)
    decisions: Dict[str, CalibrationDecision] = field(default_factory=dict)
    validations: Dict[str, CalibrationValidation] = field(default_factory=dict)
    experience: Dict[str, ExperienceRecord] = field(default_factory=dict)
    groups: Dict[str, ParameterGroup] = field(default_factory=dict)
    frozen_snapshot: Optional[Dict[str, Any]] = None
    history: List[Dict[str, Any]] = field(default_factory=list)

    def record(self, event: str, detail: str = "") -> None:
        self.history.append({"event": event, "detail": detail, "at": _now()})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id, "title": self.title,
            "condition": self.condition.to_dict(), "status": self.status,
            "targets": {k: v.to_dict() for k, v in self.targets.items()},
            "parameters": {k: v.to_dict() for k, v in self.parameters.items()},
            "relations": {k: v.to_dict() for k, v in self.relations.items()},
            "constraints": {k: v.to_dict() for k, v in self.constraints.items()},
            "plans": {k: v.to_dict() for k, v in self.plans.items()},
            "runs": {k: v.to_dict() for k, v in self.runs.items()},
            "results": {k: v.to_dict() for k, v in self.results.items()},
            "decisions": {k: v.to_dict() for k, v in self.decisions.items()},
            "validations": {k: v.to_dict() for k, v in self.validations.items()},
            "experience": {k: v.to_dict() for k, v in self.experience.items()},
            "groups": {k: v.to_dict() for k, v in self.groups.items()},
            "frozen_snapshot": self.frozen_snapshot,
            "history": list(self.history),
        }


__all__ = [
    "_uid", "_now", "_fingerprint", "NON_CONCLUSIVE_DATA",
    "ParamClass", "EvidenceGrade", "RelationStatus", "DataStatus", "ParamState",
    "FitPhase", "ContactModel", "ModelCondition", "FiveLayerRelation", "MacroTarget",
    "MicroParameter", "ParameterRelation", "CalibrationConstraint", "CalibrationPlan",
    "CalibrationRun", "CalibrationResult", "CalibrationDecision", "CalibrationValidation",
    "ExperienceRecord", "ParameterGroup", "CalibrationProject",
]
