"""卡片顺序契约：卡片先后必须跟随模型阶段顺序 M1→M2→M3→M4→M5→M6。

规范要点（用户 2026-11-26 明确）：
  1. A/B/C 是三种卡片*形式模板*，不是每类只能一张；同一类型可出现 N 张，
     直到实验完成。
  2. 卡片之间的提问顺序 = 模型阶段顺序。不得把 M2 的参数卡放到 M1，
     也不得把执行确认(C)放到参数讨论(B)之前。
  3. 阶段内部顺序：科研讨论(A) → 参数决策(B) → 执行确认(C)。

本模块是顺序的单一真相源；v41_interview 的轮次与 question_cards 的工厂
都从这里取顺序，避免两处漂移。
"""

from __future__ import annotations

from typing import Any, Dict, List

from core import CardType

# 阶段顺序（不可调换）
STAGE_ORDER: List[str] = ["M1", "M2", "M3", "M4", "M5", "M6"]

# 每个阶段内的卡片序列。元素 = (卡片 id, 类型, 说明)。
# M1/M2 是实际向用户提问的轮次；M3-M6 的确认点由阶段门触发（当前由 Core
# 门控批准，卡片内容已定义，待 dispatcher 接入发起）。
CARD_SEQUENCE: Dict[str, List[Dict[str, Any]]] = {
    "M1": [
        {"id": "research_object", "type": CardType.DISCUSSION,
         "topic": "interview_round1", "label": "研究目标与实验假设"},
        {"id": "research_goal", "type": CardType.DISCUSSION,
         "topic": "interview_round1", "label": "研究目标与实验假设"},
        {"id": "confining_source", "type": CardType.DISCUSSION,
         "topic": "interview_round1", "label": "研究边界来源"},
        {"id": "hypotheses", "type": CardType.DISCUSSION,
         "topic": "interview_round2", "label": "待验证假设"},
        {"id": "independent_vars", "type": CardType.PARAMETER,
         "topic": "interview_round2", "label": "自变量选择"},
        {"id": "dependent_vars", "type": CardType.PARAMETER,
         "topic": "interview_round2", "label": "响应变量选择"},
        {"id": "control_vars", "type": CardType.PARAMETER,
         "topic": "interview_round2", "label": "控制量选择"},
        {"id": "deliverables", "type": CardType.PARAMETER,
         "topic": "interview_round2", "label": "交付物选择"},
        {"id": "confirm", "type": CardType.EXECUTION,
         "topic": "confirm_research_plan", "label": "研究计划审核与授权"},
    ],
    "M2": [
        {"id": "specimen_shape", "type": CardType.PARAMETER,
         "topic": "negotiate_round1", "label": "试样几何"},
        {"id": "specimen_size", "type": CardType.PARAMETER,
         "topic": "negotiate_round1", "label": "试样尺寸"},
        {"id": "particle_size", "type": CardType.PARAMETER,
         "topic": "negotiate_round1", "label": "粒径级配"},
        {"id": "porosity", "type": CardType.PARAMETER,
         "topic": "negotiate_round1", "label": "目标孔隙率"},
        {"id": "density_damping", "type": CardType.PARAMETER,
         "topic": "negotiate_round2", "label": "密度与阻尼"},
        {"id": "sample_method", "type": CardType.PARAMETER,
         "topic": "negotiate_round2", "label": "成样方式"},
        {"id": "bond_state", "type": CardType.PARAMETER,
         "topic": "negotiate_round2", "label": "胶结阶段"},
        {"id": "contact_model", "type": CardType.PARAMETER,
         "topic": "negotiate_round2", "label": "接触模型"},
        {"id": "bond_micro", "type": CardType.PARAMETER,
         "topic": "negotiate_round3", "label": "胶结细观参数"},
        {"id": "wall_contact", "type": CardType.PARAMETER,
         "topic": "negotiate_round3", "label": "墙体接触"},
        {"id": "confinement", "type": CardType.PARAMETER,
         "topic": "negotiate_round3", "label": "围压与伺服"},
        {"id": "axial_loading", "type": CardType.PARAMETER,
         "topic": "negotiate_round3", "label": "轴向加载"},
        {"id": "measurement", "type": CardType.PARAMETER,
         "topic": "negotiate_round4", "label": "测量口径"},
        {"id": "confirm", "type": CardType.EXECUTION,
         "topic": "confirm_experiment_design", "label": "实验方案审核与授权"},
    ],
    "M3": [
        {"id": "confirm_model_parameters", "type": CardType.EXECUTION,
         "topic": "confirm_model_parameters", "label": "模型参数审核与授权"},
    ],
    "M4": [
        {"id": "authorize_execution", "type": CardType.EXECUTION,
         "topic": "authorize_execution", "label": "运行授权"},
        {"id": "confirm_stage_results", "type": CardType.EXECUTION,
         "topic": "confirm_stage_results", "label": "阶段结果确认"},
    ],
    "M5": [
        {"id": "confirm_diagnosis", "type": CardType.EXECUTION,
         "topic": "confirm_diagnosis", "label": "诊断结论确认"},
    ],
    "M6": [
        {"id": "confirm_result", "type": CardType.EXECUTION,
         "topic": "confirm_result", "label": "分析结果确认"},
    ],
}


def flatten_sequence() -> List[Dict[str, Any]]:
    """按阶段顺序展开全部卡片（含阶段名），用于顺序校验与展示。"""
    out: List[Dict[str, Any]] = []
    for stage in STAGE_ORDER:
        for card in CARD_SEQUENCE.get(stage, []):
            out.append(dict(card, stage=stage))
    return out


def validate_sequence() -> List[str]:
    """校验：阶段顺序正确、阶段内 A→B→C 单调、无跨阶段错位。"""
    errors: List[str] = []
    rank = {CardType.DISCUSSION: 0, CardType.PARAMETER: 1, CardType.EXECUTION: 2}
    for stage in STAGE_ORDER:
        last = -1
        for card in CARD_SEQUENCE.get(stage, []):
            r = rank.get(card["type"], -1)
            if r < last:
                errors.append("%s: %s 类型顺序倒退（A→B→C）" % (stage, card["id"]))
            last = max(last, r)
    return errors


def cards_for_topic(stage: str, topic: str) -> List[Dict[str, Any]]:
    """取某阶段某轮应展示的卡片，顺序即 CARD_SEQUENCE 中的顺序。"""
    return [c for c in CARD_SEQUENCE.get(stage, []) if c["topic"] == topic]


__all__ = [
    "STAGE_ORDER", "CARD_SEQUENCE", "flatten_sequence",
    "validate_sequence", "cards_for_topic",
]
