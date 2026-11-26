"""Nature-grade experiment-design questions for M2 (design-review only).

Scope (per user): ONLY experiment-design thinking / evaluation advice from
nature-skills-main. No post-hoc visualisation or data analysis is imported.

Sources:
  - nature-skills-main/skills/nature-statistics/SKILL.md and
    references/statistical-reporting.md / nature-article-requirements.md:
    independent experimental unit, technical vs biological replicates,
    randomization / blinding, effect sizes, AUTHOR_INPUT_NEEDED when a factual
    value is absent (never invent n, test, software or exclusion rules).
  - local PFC 9 manual (doc/pfc/.../cmd_ball.generate.html):
    `ball generate` = non-overlapping placement; `ball distribute` = porosity
    target without regard for overlap. Used as the basis for sample-prep options.
"""

from __future__ import annotations

from typing import Any, Dict, List

from core import AUTHOR_INPUT_NEEDED, Option, Question, QuestionPriority
from modules.question_cards import parameter_card

PFC_MANUAL_ROOT = "D:/Itasca/PFC900/exe64/doc/pfc/pfcmodule/doc/manual"
PFC_MANUAL_BASIS = {
    "ball generate": (
        "PFC9 手册 ball.generate: Generate non-overlapping balls; "
        "ceases at target number or tries. 适合胶结试样（避免初始重叠破坏键）"
    ),
    "ball distribute": (
        "PFC9 手册 ball.generate: distributed without regard for overlap "
        "until target porosity. 孔隙率目标可达但初始重叠大，胶结阶段易断键"
    ),
    "porosity": (
        "PFC9 手册: porosity 目标不检查重叠；需与 ball generate 的 "
        "non-overlapping 语义区分"
    ),
}


def nature_questions(experiment_type: str, progress_start: int = 1,
                     total: int = 5) -> List[Question]:
    """M2 design-review cards (controls / repeats / randomization / stats).

    Spec-compliant parameter cards: one decision each, title<=20 hanzi,
    description<=50 hanzi, defer path, validate_card() enforced.
    """
    return [
        parameter_card(
            "control_group", "对照组如何设置?", "选择一个反事实基准用于组间比较。",
            [Option("基准组=第一水平", "baseline_first", source="agent_proposal",
                    recommended=True, rationale="最低水平作反事实基准"),
             Option("阴性对照（无胶结）", "negative_control", source="nature_statistics",
                    rationale="排除处理本身以外因素"),
             Option("阳性对照（已知响应）", "positive_control", source="nature_statistics",
                    rationale="验证测量链路有效")],
            stage_id="设计", known_context=["实验类型: %s" % experiment_type],
            reason="无反事实基准则无法归因于自变量",
            recommendation="优先基准组=第一水平，便于单因素对比。",
            progress_idx=progress_start, progress_total=total,
        ),
        parameter_card(
            "independent_unit", "同一工况做几次独立重复?", "PFC 为确定性计算，重复须靠差异产生。",
            [Option("3 次（不同随机种子）", "pfc_seed_3", source="pfc_practice",
                    recommended=True, rationale="seed 不同→初始装配不同"),
             Option("5 次（不同随机种子）", "pfc_seed_5", source="pfc_practice",
                    rationale="更高置信"),
             Option("3 次（不同初始装配）", "pfc_pack_3", source="pfc_practice",
                    rationale="检验装配敏感性"),
             Option(AUTHOR_INPUT_NEEDED, AUTHOR_INPUT_NEEDED, source="pfc_practice",
                    rationale="不替你编造重复次数")],
            stage_id="设计", reason="同一初态重复结果相同，需明确差异来源",
            author_input_needed=True,
            progress_idx=progress_start + 1, progress_total=total,
        ),
        parameter_card(
            "randomization", "是否随机化工况顺序?", "数值实验可声明不适用，但需说明。",
            [Option("不适用（确定性计算）", "not_applicable", source="agent_proposal",
                    recommended=True, rationale="PFC 确定性，可声明 N/A"),
             Option("随机化工况顺序/种子", "randomized", source="nature_statistics",
                    rationale="分散未知扰动"),
             Option(AUTHOR_INPUT_NEEDED, AUTHOR_INPUT_NEEDED, source="nature_statistics",
                    rationale="由你决定")],
            stage_id="设计", reason="不适用也需显式说明，不留空",
            progress_idx=progress_start + 2, progress_total=total,
        ),
        parameter_card(
            "stat_plan", "统计口径与效应量如何报告?", "需给出效应量、不确定度与检验定义。",
            [Option("均值±标准差 + 效应量", "mean_sd_effect", source="nature_statistics",
                    recommended=True, rationale="效应量优先于显著性"),
             Option("均值±95%CI + 检验", "mean_ci_test", source="nature_statistics",
                    rationale="给出不确定区间"),
             Option(AUTHOR_INPUT_NEEDED, AUTHOR_INPUT_NEEDED, source="nature_statistics",
                    rationale="统计方法不得由 Agent 编造")],
            stage_id="设计", reason="仅报显著性不足以支撑结论",
            author_input_needed=True,
            progress_idx=progress_start + 3, progress_total=total,
        ),
    ]


def sample_preparation_question(progress_idx: int = 2,
                                total: int = 5) -> Question:
    """M2 sample-prep card with PFC manual as option basis."""
    return parameter_card(
        "sample_method", "成样方式选哪种?", "初始重叠会影响胶结保留与初始平衡。",
        [Option("ball generate（无重叠）", "ball_generate", source="PFC_manual",
                recommended=True, is_default=True,
                basis=PFC_MANUAL_BASIS["ball generate"],
                rationale="手册: Generate non-overlapping balls"),
         Option("ball distribute（目标孔隙率）", "ball_distribute", source="PFC_manual",
                basis=PFC_MANUAL_BASIS["ball distribute"],
                rationale="手册: without regard for overlap"),
         Option("伺服预压", "servo_compaction", source="agent_proposal",
                basis="成熟 brazil-pfc 流程 br_02_yuya",
                rationale="预压提高接触密度")],
        stage_id="设计", reason="初始重叠会破坏平行键",
        technical_basis="PFC9 手册 cmd_ball.generate.html",
        progress_idx=progress_idx, progress_total=total,
    )


def design_review(answers: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate a design against Nature reporting principles.

    Returns structured findings (P0/P1/P2) — advisory only, never a gate.
    """
    findings: List[Dict[str, str]] = []
    unit = str(answers.get("independent_unit", ""))
    if not unit or unit == AUTHOR_INPUT_NEEDED:
        findings.append({
            "severity": "P0", "issue": "独立重复次数未定义",
            "why": "PFC 确定性计算必须靠不同随机种子/初始装配产生差异，否则重复无意义",
            "fix": "明确重复次数与差异方式（随机种子或初始装配）",
        })
    elif unit not in ("pfc_seed_3", "pfc_seed_5", "pfc_pack_3") and "次" not in unit:
        findings.append({
            "severity": "P2", "issue": "重复方式描述不够具体",
            "why": "复现实验需要明确次数与差异来源",
            "fix": "写出次数与 seed/初始装配方式",
        })
    if answers.get("control_group") in (None, "", AUTHOR_INPUT_NEEDED):
        findings.append({
            "severity": "P0", "issue": "缺少对照组",
            "why": "无反事实基准，因果归因不成立",
            "fix": "设置基准组/阴性对照，并说明差异仅在自变量",
        })
    stats = str(answers.get("stat_plan", ""))
    if stats == AUTHOR_INPUT_NEEDED or not stats:
        findings.append({
            "severity": "P1", "issue": "统计口径为 AUTHOR_INPUT_NEEDED",
            "why": "Nature 要求效应量/不确定度/样本数/检验定义",
            "fix": "由作者提供检验方法与效应量口径",
        })
    if answers.get("randomization") in (None, ""):
        findings.append({
            "severity": "P2", "issue": "未说明随机化/盲法或不适用理由",
            "why": "缺失信息应显式标注",
            "fix": "确定性数值模拟可声明不适用",
        })
    return {
        "findings": findings,
        "scope": "experiment_design_only",
        "imports_posthoc_analysis": False,
        "counts": {
            "P0": sum(1 for f in findings if f["severity"] == "P0"),
            "P1": sum(1 for f in findings if f["severity"] == "P1"),
            "P2": sum(1 for f in findings if f["severity"] == "P2"),
        },
    }


__all__ = [
    "PFC_MANUAL_ROOT", "PFC_MANUAL_BASIS", "nature_questions",
    "sample_preparation_question", "design_review", "AUTHOR_INPUT_NEEDED",
]
