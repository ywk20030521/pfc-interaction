"""三种卡片的标准形式模板 —— 严格照录形式报告图片。

用户 2026-11-26 明确：“形式上以形式报告的图片为准”。
本模块是 A/B/C 卡片标题、说明、适用文字的单一真相源；v41_interview 的
问组与 question_cards 的工厂都引用这里，避免措辞漂移。

注意：这里只固定卡片的“形式文字”（类型名/标题/说明/适用）。
每张卡片的“内容”（具体问题、单位、选项、建议）由各模块提供。
"""

from __future__ import annotations

from typing import Any, Dict

from core import CardType

TEMPLATES: Dict[CardType, Dict[str, str]] = {
    CardType.DISCUSSION: {
        "type_label": "类型 A · 科研讨论",
        "title": "研究目标与实验假设",
        "description": "用于开放性问题，优先采用简短文字和自然语言输入。",
        "applicable": "适用：研究机制、实验假设、方案比较。",
    },
    CardType.PARAMETER: {
        "type_label": "类型 B · 参数决策",
        "title": "实验参数与条件选择",
        "description": "用于单选、多选、数值和单位输入。",
        "applicable": "适用：2D/3D、接触模型、围压、加载速率。",
    },
    CardType.EXECUTION: {
        "type_label": "类型 C · 执行确认",
        "title": "实验方案审核与授权",
        "description": "简洁展示变更内容、风险和影响，要求明确确认。",
        "applicable": "适用：模型初始化、参数修改、运行、覆盖和终止。",
    },
}


def template(ctype: CardType) -> Dict[str, str]:
    return dict(TEMPLATES[ctype])


def form_prompt(question: str, description: str = "",
                recommendation: str = "") -> str:
    """按设计标准生成面板展示文本（类型定义不出现在展示文本中）。

    设计标准（屏幕截图 220414）的卡片正文结构：
        问题标题
        一句话说明
        （空行）
        建议：<recommendation>

    卡片类型 A/B/C 是 Agent 内部分类元数据，只进 question_meta，
    绝不拼进用户看到的问题文本。
    """
    out = question
    if description:
        out += "\n" + description
    if recommendation:
        out += "\n\n建议：" + recommendation
    return out


def header_label(stage: str, decision: str = "关键决策") -> str:
    """按设计标准生成 header：`阶段 · 决策`，如 `实验设计 · 关键决策`。"""
    return "%s · %s" % (stage, decision)


__all__ = ["TEMPLATES", "template", "form_prompt", "header_label"]
