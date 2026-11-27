"""5.0 cross-module parameter calibration loop (PFCI-MOD-5.0 section 11).

M2 defines targets/cases; M3 applies a parameter version; M4 contributes real
tool evidence; M5 judges data trust; M6 computes errors/sensitivity; Core and
the user decide the next round. No module can declare calibration alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from core.v50_context import (
    EvidenceItem, EvidenceKind, ParameterRecord, ParameterStatus, ResearchTask,
    StageID, _now,
)
from core.v50_decisions import DecisionManager, DecisionRecord

_FAKE_TASK_IDS = ("recorded-", "synthetic", "fake", "mock", "demo")


@dataclass
class CalibrationCase:
    case_id: str
    parameter_id: str
    parameter_version: int
    model_version: str
    tool_task_id: str
    data_ref: str
    metrics: Dict[str, float] = field(default_factory=dict)
    trusted: Optional[bool] = None
    trust_reason: str = ""
    errors: Dict[str, float] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id, "parameter_id": self.parameter_id,
            "parameter_version": self.parameter_version,
            "model_version": self.model_version, "tool_task_id": self.tool_task_id,
            "data_ref": self.data_ref, "metrics": dict(self.metrics),
            "trusted": self.trusted, "trust_reason": self.trust_reason,
            "errors": dict(self.errors), "created_at": self.created_at,
        }


class ParameterCalibrationLoop:
    """S4 workflow implementation; writes only through the unified context."""

    def __init__(self, task: ResearchTask, decisions: DecisionManager,
                 max_iterations: int = 8) -> None:
        self.task = task
        self.decisions = decisions
        self.max_iterations = max_iterations
        self.cases: Dict[str, CalibrationCase] = {}
        self.iterations: Dict[str, int] = {}
        self.matrices: Dict[str, Dict[str, Any]] = {}

    def register_parameter(self, name: str, value: Any, unit: str,
                           physical_meaning: str = "", source_type: str = "user_provided",
                           source_reference: str = "", rationale: str = "",
                           value_range: Optional[List[Any]] = None) -> ParameterRecord:
        from core.v50_context import _uid
        param = ParameterRecord(
            parameter_id=_uid("par"), name=name, value=value, unit=unit,
            physical_meaning=physical_meaning, source_type=source_type,
            source_reference=source_reference, rationale=rationale,
            value_range=list(value_range or []),
            calibration_status=(
                ParameterStatus.USER_PROVIDED if source_type == "user_provided"
                else ParameterStatus.AGENT_SUGGESTED
            ),
        )
        return self.task.add_parameter(param)

    def define_target(self, parameter_id: str, metric: str, target_value: float,
                      unit: str, tolerance: float, source_evidence: EvidenceItem,
                      description: str = "") -> Dict[str, Any]:
        param = self._param(parameter_id)
        if tolerance < 0:
            raise ValueError("容差不能为负")
        if source_evidence.kind not in (EvidenceKind.USER_INPUT,
                                        EvidenceKind.TOOL_EVIDENCE,
                                        EvidenceKind.COMPUTED_RESULT):
            raise ValueError("标定目标必须来自用户、工具或计算证据")
        self.task.add_evidence(source_evidence)
        target = {
            "target": target_value, "unit": unit, "tolerance": tolerance,
            "source": source_evidence.kind.value, "ref": source_evidence.ref,
            "description": description,
        }
        param.target_metrics[metric] = target
        param.acceptance_criteria[metric] = tolerance
        self.task.bump_version("target:%s:%s" % (parameter_id, metric))
        return target

    def design_matrix(self, parameter_id: str, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """M2 output: calibration cases, never a claim of calibrated parameters."""
        self._param(parameter_id)
        if len(cases) < 2:
            raise ValueError("标定工况矩阵至少需要基准工况和对比工况")
        if not any(c.get("role") == "baseline" for c in cases):
            raise ValueError("标定矩阵缺少基准工况")
        version = "mx%d" % (len(self.matrices) + 1)
        matrix = {"matrix_version": version, "parameter_id": parameter_id,
                  "cases": list(cases), "owner": "M2"}
        self.matrices[parameter_id] = matrix
        self.task.experiments.append(dict(matrix))
        self.task.bump_version("matrix:%s" % version)
        return matrix

    def apply_parameter(self, parameter_id: str, value: Any, reason: str,
                        confirmation_decision_id: str,
                        model_version_after: str) -> ParameterRecord:
        """M3: write a user-confirmed parameter version into the model."""
        param = self._param(parameter_id)
        decision = self.decisions._get(confirmation_decision_id)
        if decision.status.value != "CONFIRMED":
            raise ValueError("参数调整必须先取得用户确认决策")
        if parameter_id not in decision.affected_assets and param.name not in decision.affected_assets:
            raise ValueError("确认决策未绑定该参数，不能套用授权")
        if self.iterations.get(parameter_id, 0) >= self.max_iterations:
            raise ValueError("标定迭代次数已达上限，必须重新讨论目标或模型结构")
        param.propose_value(value, reason, "inverse_calibration", confirmation_decision_id)
        param.start_calibration()
        self.iterations[parameter_id] = self.iterations.get(parameter_id, 0) + 1
        self.task.models.append({
            "parameter_id": parameter_id, "parameter_version": param.version,
            "model_version": model_version_after, "applied_by": "M3",
            "confirmation_decision_id": confirmation_decision_id,
        })
        self.task.bump_version("apply:%s:v%d" % (parameter_id, param.version))
        return param

    def add_run(self, parameter_id: str, case_id: str, tool_task_id: str,
                data_ref: str, metrics: Dict[str, float], model_version: str,
                evidence: Optional[List[EvidenceItem]] = None) -> CalibrationCase:
        """M4: only a real tool task id makes a run admissible."""
        param = self._param(parameter_id)
        if not tool_task_id or tool_task_id.lower().startswith(_FAKE_TASK_IDS):
            raise ValueError("拒绝无真实 tool_task_id 的标定运行记录")
        if not data_ref:
            raise ValueError("运行必须关联数据产物")
        if case_id in self.cases:
            raise ValueError("不允许覆盖已有标定运行，请创建新 case_id")
        for item in evidence or []:
            self.task.add_evidence(item)
        tool_evidence = EvidenceItem(
            kind=EvidenceKind.TOOL_EVIDENCE, ref=data_ref,
            description="M4 标定工况 %s 的真实执行证据" % case_id,
            tool_task_id=tool_task_id,
        )
        self.task.add_evidence(tool_evidence)
        case = CalibrationCase(
            case_id=case_id, parameter_id=parameter_id,
            parameter_version=param.version, model_version=model_version,
            tool_task_id=tool_task_id, data_ref=data_ref, metrics=dict(metrics),
        )
        self.cases[case_id] = case
        self.task.simulations.append(case.to_dict())
        param.start_calibration()
        return case

    def diagnose_trust(self, case_id: str, trusted: bool, reason: str,
                       evidence_refs: Optional[List[str]] = None) -> CalibrationCase:
        """M5: data trust is a separate judgement, never inferred from success."""
        case = self._case(case_id)
        if trusted and not evidence_refs:
            raise ValueError("判定数据可信必须给出证据引用")
        case.trusted = bool(trusted)
        case.trust_reason = reason
        self.task.diagnoses.append({
            "case_id": case_id, "trusted": trusted, "reason": reason,
            "evidence_refs": list(evidence_refs or []), "owner": "M5",
        })
        self.task.bump_version("diagnose:%s" % case_id)
        return case

    def compute_error(self, case_id: str) -> Dict[str, float]:
        """M6: compute error from data; never accept a pre-computed payload conclusion."""
        case = self._case(case_id)
        param = self._param(case.parameter_id)
        if case.trusted is None:
            raise ValueError("必须先经 M5 数据可信度诊断")
        if not case.trusted:
            raise ValueError("数据不可信，不得进入误差计算")
        if not param.target_metrics:
            raise ValueError("未定义标定目标，不得计算误差")
        errors: Dict[str, float] = {}
        for metric, target in param.target_metrics.items():
            if metric not in case.metrics:
                raise ValueError("工况缺少目标指标: %s" % metric)
            measured = float(case.metrics[metric])
            goal = float(target["target"])
            errors[metric] = abs(measured - goal) / abs(goal) if goal else abs(measured - goal)
        case.errors = errors
        param.error_metrics.update(errors)
        self.task.add_evidence(EvidenceItem(
            kind=EvidenceKind.COMPUTED_RESULT,
            ref="error:%s" % case_id, description="M6 误差计算",
            input_refs=[case.data_ref] + [r["ref"] for r in param.target_metrics.values()],
        ))
        self.task.analyses.append({"case_id": case_id, "errors": errors, "owner": "M6"})
        return errors

    def sensitivity(self, parameter_id: str) -> Dict[str, Any]:
        param = self._param(parameter_id)
        runs = [c for c in self.cases.values()
                if c.parameter_id == parameter_id and c.errors and c.trusted]
        if len(runs) < 2:
            raise ValueError("敏感性分析至少需要两个可信运行")
        result: Dict[str, Any] = {"parameter_id": parameter_id, "metrics": {}}
        low_spread = True
        for metric in param.target_metrics:
            values = [c.metrics[metric] for c in runs]
            lo, hi = min(values), max(values)
            spread = (hi - lo) / abs(hi) if hi else 0.0
            low_spread = low_spread and spread < 0.05
            result["metrics"][metric] = {"min": lo, "max": hi, "relative_spread": spread}
        result["non_uniqueness_warning"] = bool(low_spread)
        result["note"] = "单一拟合不构成参数唯一解；变化范围过小需说明识别性"
        self.task.analyses.append(dict(result))
        self.task.bump_version("sensitivity:%s" % parameter_id)
        return result

    def evaluate(self, parameter_id: str) -> Dict[str, Any]:
        param = self._param(parameter_id)
        runs = [c for c in self.cases.values() if c.parameter_id == parameter_id]
        # Acceptance belongs to the CURRENT parameter version: earlier versions
        # remain in the history for traceability but cannot block or inflate it.
        active = [c for c in runs if c.parameter_version == param.version]
        reasons: List[str] = []
        if not param.target_metrics:
            reasons.append("未定义目标指标")
        if not runs:
            reasons.append("没有标定运行")
        if not active:
            reasons.append("当前参数版本 v%d 没有标定运行" % param.version)
        for case in active:
            if case.trusted is not True:
                reasons.append("工况 %s 未通过数据可信度诊断" % case.case_id)
            if not case.errors:
                reasons.append("工况 %s 未计算误差" % case.case_id)
        param.error_metrics = {}
        for case in active:
            param.error_metrics.update(case.errors)
        for metric, tol in param.acceptance_criteria.items():
            values = [c.errors.get(metric) for c in active if c.errors]
            if not values:
                reasons.append("指标 %s 缺少误差值" % metric)
            elif any(v > tol for v in values):
                reasons.append("指标 %s 误差超出容差: %s" % (metric, values))
        iterations = self.iterations.get(parameter_id, 0)
        if iterations >= self.max_iterations:
            reasons.append("迭代次数达到上限，必须重新讨论方案")
        accepted = not reasons
        status = "PASS" if accepted else ("EXHAUSTED" if iterations >= self.max_iterations
                                          else "NEEDS_ITERATION")
        return {"parameter_id": parameter_id, "status": status,
                "acceptance_met": accepted, "reasons": reasons,
                "errors": dict(param.error_metrics), "iterations": iterations}

    def confirm_calibrated(self, parameter_id: str, user_response: str) -> ParameterRecord:
        param = self._param(parameter_id)
        evaluation = self.evaluate(parameter_id)
        if not evaluation["acceptance_met"]:
            raise ValueError("未达到接受标准，不得标记已标定: %s" % "; ".join(evaluation["reasons"]))
        if not user_response:
            raise ValueError("标定结论必须记录用户确认")
        evidence = [e for e in self.task.evidence
                    if e.kind in (EvidenceKind.TOOL_EVIDENCE, EvidenceKind.COMPUTED_RESULT)]
        param.mark_calibrated(evidence, True,
                              "%s；用户确认: %s" % (evaluation["status"], user_response))
        param.confirm(user_response)
        self.task.bump_version("calibrated:%s" % parameter_id)
        return param

    def propose_adjustment(self, parameter_id: str, new_value: Any, reason: str,
                           evidence_refs: List[str]) -> DecisionRecord:
        param = self._param(parameter_id)
        if not evidence_refs:
            raise ValueError("调参建议必须关联误差或诊断证据")
        return self.decisions.propose(
            topic="calibration_adjustment:%s" % param.name,
            content="将 %s 调整为 %s %s" % (param.name, new_value, param.unit),
            rationale=reason, evidence=list(evidence_refs),
            affected_assets=[parameter_id, param.name], stage=StageID.S4,
        )

    def snapshot(self) -> Dict[str, Any]:
        return {
            "parameters": [p.to_dict() for p in self.task.parameters.values()],
            "cases": [c.to_dict() for c in self.cases.values()],
            "matrices": list(self.matrices.values()),
            "iterations": dict(self.iterations),
            "evaluation": {pid: self.evaluate(pid) for pid in self.task.parameters},
        }

    def _param(self, parameter_id: str) -> ParameterRecord:
        if parameter_id not in self.task.parameters:
            raise KeyError("参数不存在: %s" % parameter_id)
        return self.task.parameters[parameter_id]

    def _case(self, case_id: str) -> CalibrationCase:
        if case_id not in self.cases:
            raise KeyError("工况不存在: %s" % case_id)
        return self.cases[case_id]


__all__ = ["CalibrationCase", "ParameterCalibrationLoop"]
