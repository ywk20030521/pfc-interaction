"""S4 macro-micro relation analysis engine (S4_SPEC V2.0 chapter 3).

Builds a condition-dependent relation network, NOT a static lookup table.
A relation must carry five layers, a contact model and a condition fingerprint.
Local sensitivity S_ij is explicitly local and never promoted to a global law.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.s4_contracts import (
    CalibrationProject, EvidenceGrade, FitPhase, FiveLayerRelation,
    MacroTarget, MicroParameter, ParameterRelation, RelationStatus, _uid,
)


class RelationEngine:
    """Manages parameter relations inside a CalibrationProject."""

    def __init__(self, project: CalibrationProject) -> None:
        self.project = project

    def register_parameter(self, name: str, param_class: Any, contact_model: str,
                           unit: str = "", current_value: Any = None,
                           bounds: Optional[List[Any]] = None,
                           physical_meaning: str = "", transform: str = "linear",
                           source: str = "") -> MicroParameter:
        param = MicroParameter(
            parameter_id=_uid("par"), name=name, param_class=param_class,
            unit=unit, current_value=current_value, bounds=list(bounds or []),
            contact_model=contact_model, physical_meaning=physical_meaning,
            transform=transform, source=source,
            condition_ref=self.project.condition.fingerprint,
        )
        self.project.parameters[param.parameter_id] = param
        self.project.record("register_parameter", name)
        return param

    def register_target(self, metric: str, value: float, unit: str, tolerance: float,
                        weight: float = 1.0, priority: str = "soft",
                        role: Any = None, source: str = "") -> MacroTarget:
        target = MacroTarget(
            target_id=_uid("tgt"), metric=metric, value=value, unit=unit,
            tolerance=tolerance, weight=weight, priority=priority, source=source,
            role=role or FitPhase.FIT,
        )
        self.project.targets[target.target_id] = target
        self.project.record("register_target", metric)
        return target

    def add_relation(self, parameter_id: str, target_id: str, five_layers: FiveLayerRelation,
                     relation_type: str = "unknown", contact_model: str = "",
                     evidence_grade: EvidenceGrade = EvidenceGrade.E0,
                     effect_estimate: Optional[float] = None,
                     uncertainty: Optional[float] = None,
                     limitations: Optional[List[str]] = None) -> ParameterRelation:
        if parameter_id not in self.project.parameters:
            raise KeyError("参数不存在: %s" % parameter_id)
        if target_id not in self.project.targets:
            raise KeyError("宏观目标不存在: %s" % target_id)
        model = contact_model or self.project.condition.contact_model
        relation = ParameterRelation(
            relation_id=_uid("rel"), parameter_id=parameter_id, target_id=target_id,
            five_layers=five_layers, relation_type=relation_type,
            effect_estimate=effect_estimate, uncertainty=uncertainty,
            contact_model=model, condition_ref=self.project.condition.fingerprint,
            evidence_grade=evidence_grade,
            parameter_domain=list(self.project.parameters[parameter_id].bounds),
            limitations=list(limitations or []),
        )
        status = self._status_from_grade(evidence_grade)
        relation.status = status
        self.project.relations[relation.relation_id] = relation
        self.project.record("add_relation", "%s->%s" % (parameter_id, target_id))
        return relation

    def reject_static_mapping(self, parameter_id: str, target_id: str) -> None:
        """Explicit guard: a bare mapping without layers/conditions is invalid."""
        raise ValueError(
            "拒绝静态一一对应表：%s ↔ %s 必须附带五层机制、接触模型与工况条件指纹"
            % (parameter_id, target_id)
        )

    def local_sensitivity(self, relation_id: str, y_base: float, y_perturbed: float,
                          p_base: float, p_perturbed: float) -> Dict[str, Any]:
        relation = self._relation(relation_id)
        if p_base == 0:
            raise ValueError("参数基准值为 0，不得使用相对扰动计算 S_ij")
        dp = (p_perturbed - p_base) / p_base
        if dp == 0:
            raise ValueError("参数未发生扰动")
        dy = (y_perturbed - y_base) / y_base if y_base else None
        s_ij = dy / dp if dy is not None else None
        relation.effect_estimate = s_ij
        self.project.record("local_sensitivity", relation_id)
        return {
            "relation_id": relation_id, "s_ij": s_ij,
            "note": "仅表示当前参数位置附近的局部响应，不得视为全局规律",
        }

    def query_relations(self, parameter_id: Optional[str] = None,
                        target_id: Optional[str] = None,
                        min_status: Optional[RelationStatus] = None) -> List[ParameterRelation]:
        out = []
        for rel in self.project.relations.values():
            if parameter_id and rel.parameter_id != parameter_id:
                continue
            if target_id and rel.target_id != target_id:
                continue
            if min_status and _STATUS_RANK[rel.status] < _STATUS_RANK[min_status]:
                continue
            out.append(rel)
        return out

    def _relation(self, relation_id: str) -> ParameterRelation:
        if relation_id not in self.project.relations:
            raise KeyError("关系不存在: %s" % relation_id)
        return self.project.relations[relation_id]

    @staticmethod
    def _status_from_grade(grade: EvidenceGrade) -> RelationStatus:
        return {
            EvidenceGrade.E0: RelationStatus.PROPOSED,
            EvidenceGrade.E1: RelationStatus.MECHANISM_INFERRED,
            EvidenceGrade.E2: RelationStatus.LITERATURE_SUPPORTED,
            EvidenceGrade.E3: RelationStatus.PROJECT_SCREENING,
            EvidenceGrade.E4: RelationStatus.PROJECT_SCREENING,
            EvidenceGrade.E5: RelationStatus.MULTI_CASE_VALIDATED,
        }[grade]


_STATUS_RANK = {
    RelationStatus.PROPOSED: 0,
    RelationStatus.MECHANISM_INFERRED: 1,
    RelationStatus.LITERATURE_SUPPORTED: 2,
    RelationStatus.PROJECT_SCREENING: 3,
    RelationStatus.MULTI_CASE_VALIDATED: 4,
    RelationStatus.NEGATED: -1,
}


__all__ = ["RelationEngine", "_STATUS_RANK"]
