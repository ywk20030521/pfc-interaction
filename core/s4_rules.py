"""S4 rule and experience library (S4_SPEC V2.0 chapter 7).

Twelve efficient calibration rules, three rule classes with priority,
model-specific isolation, E0-E5 experience grading with success cases and
counterexamples. E5 never migrates across contact model / material / dimension.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.s4_contracts import (
    CalibrationProject, EvidenceGrade, ExperienceRecord, ModelCondition, _uid,
)

RULES: List[Dict[str, Any]] = [
    {"id": 1, "title": "先固定模型基础条件，再调整细观参数",
     "mandate": "标定前检查粒径/形状/级配、试样尺寸/孔隙率/密实度、接触模型与CMAT、边界/加载、初始应力/平衡、阻尼/时间步"},
    {"id": 2, "title": "参数分直接测量类与宏观反演类",
     "mandate": "可直接测量或约束的参数不纳入宏观反演"},
    {"id": 3, "title": "先筛选、再验证、后定量（三阶段）",
     "mandate": "Screening→Validation→Quantification；禁止一开始就几十参数联合优化"},
    {"id": 4, "title": "建立宏观—细观优先调节关系",
     "mandate": "关系须标注模型与条件，仅作筛选初始假设"},
    {"id": 5, "title": "优先处理参数耦合而非单参数试错",
     "mandate": "维护两个矩阵+联合策略+可辨识性；执行耦合四问"},
    {"id": 6, "title": "采用自适应步长，不用固定幅度",
     "mandate": "粗扫→缩范围→精搜；跨数量级用对数；近边界/突变缩小步长；S_ij 仅局部"},
    {"id": 7, "title": "优先标定相对独立的参数组",
     "mandate": "按敏感性与耦合组织参数组，不按参数表顺序机械标定"},
    {"id": 8, "title": "不只用单一宏观指标标定",
     "mandate": "J(p)=Σ w_i((y_i^sim−y_i^exp)/s_i)^2；权重依据实验误差/科学目标"},
    {"id": 9, "title": "善用正交试验、响应面与代理模型",
     "mandate": "低成本筛选→代理→候选优化→真实PFC验证；代理预测不得标记为已标定"},
    {"id": 10, "title": "每次仿真必须有明确的试算目的",
     "mandate": "运行前回答：验证什么关系、哪些参数变/不变、预期指标、支持/否定标准"},
    {"id": 11, "title": "区分拟合、标定与独立验证",
     "mandate": "拟合良好≠标定完成≠独立验证通过；至少一个独立验证工况"},
    {"id": 12, "title": "建立经验的项目化学习机制",
     "mandate": "成功与失败均记录；单项目关系不得直接推广为通用经验"},
]

RULE_CLASSES = ("general", "model_specific", "project_validated")

# Priority: project-validated > model-specific > general.
RULE_CLASS_PRIORITY = {"general": 1, "model_specific": 2, "project_validated": 3}

# PBM example mapping: initial candidate recall only, never a universal law.
PBM_MAPPING: List[Dict[str, str]] = [
    {"macro": "弹性模量 E", "parameters": "接触刚度、黏结刚度及刚度比",
     "note": "也受颗粒结构、孔隙率影响", "model": "LINEAR_PARALLEL_BOND"},
    {"macro": "泊松比 ν", "parameters": "法向/切向刚度比、接触网络",
     "note": "不能仅凭 E 判断", "model": "LINEAR_PARALLEL_BOND"},
    {"macro": "UCS", "parameters": "黏结强度、黏结半径、摩擦机制",
     "note": "强度参数可能高度耦合", "model": "LINEAR_PARALLEL_BOND"},
    {"macro": "峰后残余强度", "parameters": "摩擦系数、破坏后接触状态",
     "note": "与破坏机制密切相关", "model": "LINEAR_PARALLEL_BOND"},
]


class RuleLibrary:
    def __init__(self, project: CalibrationProject) -> None:
        self.project = project

    def list_rules(self, rule_class: str = "general") -> List[Dict[str, Any]]:
        if rule_class not in RULE_CLASSES:
            raise ValueError("未知规则类别: %s" % rule_class)
        return [dict(r) for r in RULES]

    def rule(self, rule_id: int) -> Dict[str, Any]:
        for r in RULES:
            if r["id"] == rule_id:
                return dict(r)
        raise KeyError("规则不存在: %s" % rule_id)

    def pbm_mapping(self, contact_model: str) -> List[Dict[str, str]]:
        if contact_model != "LINEAR_PARALLEL_BOND":
            raise ValueError("PBM 示例映射仅适用于 LINEAR_PARALLEL_BOND，禁止跨模型套用")
        return [dict(m) for m in PBM_MAPPING]

    def add_experience(self, claim: str, grade: EvidenceGrade, condition: ModelCondition,
                       scope: str, parameter_domain: Optional[List[Any]] = None,
                       response_change: str = "", success_cases: Optional[List[str]] = None,
                       counterexamples: Optional[List[str]] = None,
                       limitations: Optional[List[str]] = None) -> ExperienceRecord:
        if grade not in list(EvidenceGrade):
            raise ValueError("未知证据等级: %s" % grade)
        rec = ExperienceRecord(
            record_id=_uid("exp"), claim=claim, evidence_grade=grade,
            contact_model=condition.contact_model, dimension=condition.dimension,
            material_class=condition.material_class, pfc_version=condition.pfc_version,
            gradation=condition.gradation, porosity=condition.porosity,
            loading=condition.loading, parameter_domain=list(parameter_domain or []),
            response_change=response_change, scope=scope,
            success_cases=list(success_cases or []),
            counterexamples=list(counterexamples or []),
            limitations=list(limitations or []),
        )
        self.project.experience[rec.record_id] = rec
        self.project.record("add_experience", "%s:%s" % (grade.value, claim[:30]))
        return rec

    def query_experience(self, condition: ModelCondition,
                         min_grade: EvidenceGrade = EvidenceGrade.E0) -> List[ExperienceRecord]:
        order = list(EvidenceGrade)
        threshold = order.index(min_grade)
        return [rec for rec in self.project.experience.values()
                if rec.applies_to(condition) and order.index(rec.evidence_grade) >= threshold]

    def negate_experience(self, record_id: str, counterexample: str) -> None:
        rec = self.project.experience.get(record_id)
        if not rec:
            raise KeyError("经验记录不存在: %s" % record_id)
        if not counterexample:
            raise ValueError("否定经验必须给出反例")
        rec.negate(counterexample)
        self.project.record("negate_experience", record_id)

    def e5_scope_guard(self, record_id: str, other_condition: ModelCondition) -> bool:
        rec = self.project.experience.get(record_id)
        if not rec or rec.evidence_grade != EvidenceGrade.E5:
            return False
        return rec.applies_to(other_condition)


__all__ = ["RULES", "RULE_CLASSES", "RULE_CLASS_PRIORITY", "PBM_MAPPING", "RuleLibrary"]
