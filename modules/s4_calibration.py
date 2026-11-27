"""S4 Parameter Identification & Calibration subsystem facade (V2.0 spec).

C1-C8 orchestration over the s4_* engines. Enforces the three non-degradable
rules: scientific relation before tuning, independent argument + joint
identification (scheme B), and scientific judgement for freezing.

This facade does NOT reproduce M4 execution or M6 analysis. CalibrationRun
objects require a real tool_task_id; this module only organizes state,
decisions, relations and validation. No numeric calibration success is
declared here.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.s4_contracts import (
    CalibrationPlan, CalibrationProject, CalibrationRun, CalibrationValidation,
    EvidenceGrade, FitPhase, FiveLayerRelation, MacroTarget, MicroParameter,
    ModelCondition, ParamClass, ParamState, ParameterRelation, RelationStatus,
    _uid,
)
from core.s4_identifiability import IdentifiabilityEngine
from core.s4_negotiation import SEVEN_STEPS, NegotiationEngine
from core.s4_next_experiment import NextExperimentEngine
from core.s4_relation import RelationEngine
from core.s4_rules import RuleLibrary

C1_C8 = ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"]


class S4CalibrationSubsystem:
    """Independent core subsystem for S4; not a 7th module, not inside M4."""

    def __init__(self, project: CalibrationProject) -> None:
        self.project = project
        self.relations = RelationEngine(project)
        self.identifiability = IdentifiabilityEngine(project)
        self.negotiation = NegotiationEngine(project)
        self.rules = RuleLibrary(project)
        self.next_experiment = NextExperimentEngine(project)
        self.completed: List[str] = []

    # ---- C1 / C2: goals and parameter system -------------------------------
    def c1_define_goal(self, metric: str, value: float, unit: str, tolerance: float,
                       role: FitPhase = FitPhase.FIT, weight: float = 1.0,
                       priority: str = "soft") -> MacroTarget:
        self._require("C1")
        target = self.relations.register_target(
            metric, value, unit, tolerance, weight=weight, priority=priority, role=role)
        self.project.record("C1", "宏观目标 %s (%s)" % (metric, role.value))
        self._complete("C1")
        return target

    def c2_register_parameter(self, name: str, param_class: ParamClass,
                              unit: str = "", current_value: Any = None,
                              bounds: Optional[List[Any]] = None,
                              physical_meaning: str = "") -> MicroParameter:
        self._require("C2")
        param = self.relations.register_parameter(
            name, param_class, self.project.condition.contact_model,
            unit=unit, current_value=current_value, bounds=bounds,
            physical_meaning=physical_meaning)
        self.project.record("C2", "参数 %s (%s)" % (name, param_class.value))
        self._complete("C2")
        return param

    # ---- C3: macro-micro relation analysis ---------------------------------
    def c3_add_relation(self, parameter_id: str, target_id: str, macro_goal: str,
                        micro_mechanism: str, micro_parameter: str,
                        structure_condition: str, evidence: str,
                        relation_type: str = "unknown",
                        grade: EvidenceGrade = EvidenceGrade.E0) -> ParameterRelation:
        self._require("C3")
        layers = FiveLayerRelation(macro_goal, micro_mechanism, micro_parameter,
                                   structure_condition, evidence)
        rel = self.relations.add_relation(parameter_id, target_id, layers,
                                          relation_type=relation_type,
                                          evidence_grade=grade)
        self._complete("C3")
        return rel

    # ---- C4 / C5: initial values, ranges and plan --------------------------
    def c4_plan(self, stages: Optional[List[str]] = None,
                budget: Optional[Dict[str, Any]] = None,
                validation_cases: Optional[List[str]] = None) -> CalibrationPlan:
        self._require("C4")
        plan = CalibrationPlan(
            plan_id=_uid("plan"), stages=list(stages or C1_C8),
            budget=dict(budget or {}), validation_cases=list(validation_cases or []))
        self.project.plans[plan.plan_id] = plan
        self.project.record("C4", "标定计划")
        self._complete("C4")
        return plan

    def c5_approve_plan(self, plan_id: str, user_response: str) -> CalibrationPlan:
        """C5: the calibration plan needs user approval before any PFC run."""
        self._require("C5")
        plan = self.project.plans.get(plan_id)
        if not plan:
            raise KeyError("标定计划不存在: %s" % plan_id)
        if not user_response:
            raise ValueError("标定方案必须经用户确认才能进入执行")
        self.project.record("C5", "方案确认:%s" % user_response[:30])
        self._complete("C5")
        return plan

    # ---- C6: real runs and diagnostics -------------------------------------
    def c6_add_run(self, parameter_id: str, tool_task_id: str, data_ref: str,
                   metrics: Dict[str, float],
                   phase: FitPhase = FitPhase.CALIBRATION,
                   condition: Optional[ModelCondition] = None) -> CalibrationRun:
        self._require("C6")
        param = self.project.parameters.get(parameter_id)
        if not param:
            raise KeyError("参数不存在: %s" % parameter_id)
        cond_ref = (condition.fingerprint if condition
                    else self.project.condition.fingerprint)
        run = CalibrationRun(
            run_id=_uid("run"),
            parameter_version_ref="%s:v%s" % (parameter_id, len(param.change_log) + 1),
            condition_ref=cond_ref, tool_task_id=tool_task_id, data_ref=data_ref,
            phase=phase, metrics=dict(metrics))
        self.project.runs[run.run_id] = run
        self.project.record("C6", "%s:%s" % (run.run_id, phase.value))
        self._complete("C6")
        return run

    # ---- C7: identifiability check + negotiation + next-best ---------------
    def c7_assess_identifiability(self, parameter_id: str, target_ids: List[str],
                                  sensitivities: Dict[str, Dict[str, float]],
                                  corr: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        self._require("C7")
        result = self.identifiability.assess(parameter_id, target_ids, sensitivities, corr)
        self._complete("C7")
        return result

    def c7_next_experiment(self, candidates: List[Dict[str, Any]],
                           compensation_detected: bool = False,
                           equivalent_solutions: bool = False) -> Dict[str, Any]:
        return self.next_experiment.evaluate(candidates, compensation_detected,
                                             equivalent_solutions)

    # ---- C8: three-way distinction, validation and freeze ------------------
    def c8_fit_status(self, parameter_id: str, errors: Dict[str, float],
                      tolerance_by_metric: Dict[str, float]) -> Dict[str, Any]:
        """Fitting good is NOT calibration complete, NOT validation passed."""
        within = all(abs(errors.get(m, float("inf"))) <= tol
                     for m, tol in tolerance_by_metric.items())
        return {
            "parameter_id": parameter_id, "errors": dict(errors),
            "fit_good": within,
            "calibration_complete": False,
            "independent_validation_passed": False,
            "note": "拟合良好不得直接等同标定完成或独立验证通过",
        }

    def c8_validate(self, held_out_conditions: List[str], outcomes: Dict[str, float],
                    criteria: Optional[Dict[str, float]] = None,
                    mechanism_check: str = "") -> CalibrationValidation:
        self._require("C8")
        validation = CalibrationValidation(
            validation_id=_uid("val"), held_out_conditions=list(held_out_conditions),
            outcomes=dict(outcomes), criteria=dict(criteria or {}),
            mechanism_check=mechanism_check)
        passed = bool(outcomes) and (
            not criteria or all(abs(outcomes.get(m, float("inf"))) <= c
                                for m, c in criteria.items()))
        validation.passed = passed and bool(mechanism_check)
        self.project.validations[validation.validation_id] = validation
        self.project.record("C8", "独立验证:%s" % passed)
        self._complete("C8")
        return validation

    def freeze(self, parameter_id: str, validation_id: str,
               user_response: str) -> Dict[str, Any]:
        """Only science judgement + independent validation can freeze."""
        validation = self.project.validations.get(validation_id)
        if not validation or not validation.passed:
            raise ValueError("独立验证未通过，不得冻结参数")
        param = self.project.parameters.get(parameter_id)
        if not param:
            raise KeyError("参数不存在: %s" % parameter_id)
        if param.state not in (ParamState.USER_CONFIRMED, ParamState.CALIBRATED):
            raise ValueError("参数未经用户确认或标定，不得冻结")
        if not user_response:
            raise ValueError("冻结必须由科研判断决定并记录用户回答")
        param.set_state(ParamState.VALIDATED, "独立验证通过+用户确认冻结")
        snapshot = {
            "project_id": self.project.project_id,
            "parameter": param.to_dict(),
            "validation": validation.to_dict(),
            "relations": [r.to_dict() for r in self.project.relations.values()],
            "experience": [e.to_dict() for e in self.project.experience.values()],
            "condition": self.project.condition.to_dict(),
            "user_response": user_response,
        }
        self.project.frozen_snapshot = snapshot
        self.project.status = "frozen"
        self.project.record("freeze", parameter_id)
        return snapshot

    # ---- helpers -----------------------------------------------------------
    def _require(self, stage: str, mode: str = "before") -> None:
        if stage not in C1_C8:
            raise ValueError("未知 C 环节: %s" % stage)
        idx = C1_C8.index(stage)
        for prior in C1_C8[:idx]:
            if prior not in self.completed:
                raise ValueError("必须先完成 %s 才能执行 %s" % (prior, stage))

    def _complete(self, stage: str) -> None:
        if stage not in self.completed:
            self.completed.append(stage)
            self.project.status = stage

    def snapshot(self) -> Dict[str, Any]:
        return {
            "project": self.project.to_dict(),
            "completed_c_stages": list(self.completed),
            "next_experiment_history": list(self.next_experiment.history),
        }


__all__ = ["C1_C8", "S4CalibrationSubsystem"]
