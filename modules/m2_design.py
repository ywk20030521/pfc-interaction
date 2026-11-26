"""M2 Experiment Design - first batch module.

IF0 contract fields:
  experiment_type, parameter_schema[] (name/unit/range/default/source/confirmed),
  cases[] (case_id + values), control_groups[], measurement_plan[], trace_to_vars[]

Standard outputs (report section 4.2.4):
  experiment_design.md, parameter_schema.json, experiment_matrix.csv,
  control_groups.md, measurement_plan.md

Rules: the matrix must be traceable to M1 variables; no unexplained
omissions or duplicates; important assumptions must be user-confirmed.
"""

from __future__ import annotations

import csv
import io
import itertools
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core import (
    DecisionKey,
    DispatchRequest,
    Envelope,
    Evidence,
    EvidenceSource,
    ModuleID,
    ModuleState,
    CoreDispatcher,
)

MODULE_VERSION = "0.1.0"
MODULE_ID = ModuleID.M2

# Minimal type knowledge. Templates are references, not auto-applied plans.
EXPERIMENT_KNOWLEDGE: Dict[str, Dict[str, Any]] = {
    "单轴压缩": {
        "required_measurements": ["轴向应力", "轴向应变", "峰值强度", "弹性模量"],
        "typical_parameters": ["试样几何", "粒径及级配", "密度", "接触模型", "细观参数", "加载速率"],
    },
    "三轴压缩": {
        "required_measurements": ["轴向应力", "轴向应变", "围压", "峰值强度"],
        "typical_parameters": ["围压", "加载速率", "接触模型", "细观参数"],
    },
    "巴西劈裂": {
        "required_measurements": ["劈裂载荷", "抗拉强度", "裂纹演化"],
        "typical_parameters": ["圆盘几何", "粒径", "胶结参数", "加载速率"],
    },
    "直剪试验": {
        "required_measurements": ["剪切应力", "剪切位移", "法向应力"],
        "typical_parameters": ["法向应力", "剪切速率", "结构面参数"],
    },
    "颗粒流动": {
        "required_measurements": ["质量流量", "速度场", "停留时间"],
        "typical_parameters": ["粒径", "摩擦系数", "出口尺寸"],
    },
}


@dataclass
class ParameterDef:
    name: str
    unit: str
    values: List[Any]
    default: Any
    source: str
    confirmed: bool = False
    role: str = "independent"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "unit": self.unit,
            "range": [min(self.values), max(self.values)] if self.values else [],
            "values": self.values,
            "default": self.default,
            "source": self.source,
            "confirmed": self.confirmed,
            "role": self.role,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ParameterDef":
        values = list(d.get("values", []))
        if not values and d.get("range"):
            lo, hi = d["range"][0], d["range"][-1]
            values = [lo, hi]
        return cls(
            name=str(d.get("name", "")),
            unit=str(d.get("unit", "")),
            values=values,
            default=d.get("default", values[0] if values else None),
            source=str(d.get("source", "")),
            confirmed=bool(d.get("confirmed", False)),
            role=str(d.get("role", "independent")),
        )


@dataclass
class ExperimentDesign:
    experiment_type: str
    parameter_schema: List[ParameterDef] = field(default_factory=list)
    cases: List[Dict[str, Any]] = field(default_factory=list)
    control_groups: List[Dict[str, Any]] = field(default_factory=list)
    measurement_plan: List[Dict[str, Any]] = field(default_factory=list)
    trace_to_vars: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_type": self.experiment_type,
            "parameter_schema": [p.to_dict() for p in self.parameter_schema],
            "cases": self.cases,
            "control_groups": self.control_groups,
            "measurement_plan": self.measurement_plan,
            "trace_to_vars": self.trace_to_vars,
        }

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.experiment_type not in EXPERIMENT_KNOWLEDGE:
            errors.append(
                "unsupported experiment_type: %s (supported: %s)"
                % (self.experiment_type, ", ".join(EXPERIMENT_KNOWLEDGE))
            )
        names: set = set()
        for p in self.parameter_schema:
            if not p.name:
                errors.append("parameter name is required")
            if p.name in names:
                errors.append("duplicate parameter name: %s" % p.name)
            names.add(p.name)
            if not p.unit:
                errors.append("parameter %s missing unit" % p.name)
            if not p.source:
                errors.append("parameter %s missing source" % p.name)
            if not p.values:
                errors.append("parameter %s has no values" % p.name)
        case_ids: set = set()
        seen_values: List[tuple] = []
        for case in self.cases:
            cid = case.get("case_id")
            if cid in case_ids:
                errors.append("duplicate case_id: %s" % cid)
            case_ids.add(cid)
            values = tuple(sorted((case.get("values") or {}).items(), key=lambda x: x[0]))
            if values in seen_values:
                errors.append("duplicate case values: %s" % cid)
            seen_values.append(values)
        trace_params = {t.get("parameter") for t in self.trace_to_vars}
        for p in self.parameter_schema:
            if p.role == "independent" and p.name not in trace_params:
                errors.append("independent parameter not traced to M1 variable: %s" % p.name)
        measured = {m.get("metric") for m in self.measurement_plan}
        for metric in EXPERIMENT_KNOWLEDGE.get(self.experiment_type, {}).get(
            "required_measurements", []
        ):
            if metric not in measured:
                errors.append("measurement plan missing required metric: %s" % metric)
        return errors


def build_matrix(design: ExperimentDesign) -> None:
    """Generate full Cartesian product of independent variable values."""
    independent = [p for p in design.parameter_schema if p.role == "independent"]
    if not independent:
        design.cases = []
        return
    combos = itertools.product(*[p.values for p in independent])
    design.cases = []
    for idx, combo in enumerate(combos, start=1):
        values = {p.name: v for p, v in zip(independent, combo)}
        design.cases.append(
            {"case_id": "C%02d" % idx, "group": "test", "values": values}
        )
    if design.control_groups:
        base = design.control_groups[0].get("values", {})
        control_values = {
            p.name: base.get(p.name, p.default)
            for p in independent
        }
        design.cases.insert(
            0, {"case_id": "C00", "group": "control", "values": control_values}
        )


def render_documents(design: ExperimentDesign) -> Dict[str, str]:
    csv_buf = io.StringIO()
    fields = ["case_id", "group"] + [p.name for p in design.parameter_schema if p.role == "independent"]
    writer = csv.DictWriter(csv_buf, fieldnames=fields)
    writer.writeheader()
    for case in design.cases:
        row = {"case_id": case["case_id"], "group": case.get("group", "")}
        row.update(case.get("values", {}))
        writer.writerow({k: row.get(k, "") for k in fields})

    design_md = "# 实验设计\n\n## 实验类型\n%s\n\n## 设计依据\n%s\n\n## 工况数\n%d\n" % (
        design.experiment_type,
        "结合 M1 研究问题与变量生成；非固定模板套用。",
        len(design.cases),
    )
    groups_md = "# 对照组设计\n\n%s\n" % (
        "\n".join(
            "- %s: %s"
            % (g.get("name", "未命名"), g.get("description", ""))
            for g in design.control_groups
        )
        or "- 无对照组"
    )
    measure_md = "# 测量计划\n\n%s\n" % "\n".join(
        "- %s（口径：%s，来源：%s）"
        % (m.get("metric"), m.get("definition", ""), m.get("source", ""))
        for m in design.measurement_plan
    )
    return {
        "experiment_design.md": design_md,
        "experiment_matrix.csv": csv_buf.getvalue(),
        "control_groups.md": groups_md,
        "measurement_plan.md": measure_md,
    }


def _load_m1_requirements(request: DispatchRequest, core: CoreDispatcher) -> Dict[str, Any]:
    for ref in request.input_refs:
        if ref.artifact_id.startswith("m1_research_requirements"):
            return core.store.get_json(ref)
    return (request.payload or {}).get("research_requirements", {})


def run(module_task_id: str, request: DispatchRequest, core: CoreDispatcher) -> Envelope:
    m1 = _load_m1_requirements(request, core)
    payload = request.payload or {}
    config = payload.get("experiment_design", {})

    design = ExperimentDesign(
        experiment_type=str(config.get("experiment_type", "")),
        parameter_schema=[ParameterDef.from_dict(p) for p in config.get("parameter_schema", [])],
        control_groups=list(config.get("control_groups", [])),
        measurement_plan=list(config.get("measurement_plan", [])),
        trace_to_vars=list(config.get("trace_to_vars", [])),
    )
    if not design.experiment_type:
        # Infer from M1 objective only as a suggestion, never silently finalize.
        design.experiment_type = str(
            config.get("suggested_type", "单轴压缩")
        )

    for p in design.parameter_schema:
        if p.role == "independent" and not p.source:
            p.source = "M1.independent_vars"
    for var in m1.get("independent_vars", []):
        matching = [p.name for p in design.parameter_schema if p.name == var]
        design.trace_to_vars.append(
            {"m1_var": var, "parameter": matching[0] if matching else var}
        )
    if not design.measurement_plan:
        for metric in EXPERIMENT_KNOWLEDGE.get(design.experiment_type, {}).get(
            "required_measurements", []
        ):
            design.measurement_plan.append(
                {
                    "metric": metric,
                    "definition": "待与研究人员确认口径",
                    "source": "M2.measurement_plan建议",
                }
            )

    build_matrix(design)
    errors = design.validate()

    decision, presented, _reason = core.request_decision(
        key=DecisionKey(
            experiment_id=request.research_task_id,
            stage_id="M2",
            topic="确认实验方案",
            context_version=request.context_version,
        ),
        question="是否确认实验方案？类型=%s，工况数=%d" % (design.experiment_type, len(design.cases)),
        options=["确认，进入 M3", "需要修改参数", "暂缓"],
        blocks_module_task_id=module_task_id,
        evidence_refs=[r.artifact_id for r in request.input_refs],
        authorization_scope=None,
    )

    artifacts: List[Dict[str, Any]] = []
    for name, text in render_documents(design).items():
        aid = "m2_" + name.replace(".", "_")
        artifacts.append(core.store.write(aid, name, text).to_dict())
    artifacts.append(
        core.store.write_json("m2_parameter_schema", "parameter_schema.json", design.to_dict()).to_dict()
    )

    state = (
        ModuleState.BLOCKED.value
        if errors
        else (ModuleState.WAITING_FOR_USER.value if presented else ModuleState.COMPLETED.value)
    )
    return Envelope(
        module_id=MODULE_ID,
        module_version=MODULE_VERSION,
        research_task_id=request.research_task_id,
        module_task_id=module_task_id,
        parent_task_id=request.parent_task_id,
        input_refs=request.input_refs,
        status={"module_state": state},
        output={
            "structured": design.to_dict(),
            "artifacts": artifacts,
            "verified_by_execution": False,
        },
        evidence=[
            Evidence(EvidenceSource.USER_PROVIDED, "M1.research_requirements", "M1 已确认输入"),
            Evidence(EvidenceSource.AGENT_INFERRED, "M2.matrix", "参数矩阵由 Agent 生成"),
        ],
        decisions=[
            {"decision_id": decision["decision_id"], "delivery_status": decision["delivery_status"]}
        ],
        limitations=errors + [
            "实验方案仍需用户确认；确认前不得作为 M3 的授权输入"
        ],
    )
