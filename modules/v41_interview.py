"""4.1-alpha M1/M2: real multi-round research interview and parameter negotiation.

4.0 M1/M2 just rendered documents from a caller-supplied JSON blob and asked
one confirmation. This module makes the interview the actual work:

  * M1 round 1 asks only the 3 decisive questions (object / goal / confining
    source); round 2 covers hypotheses / variables / controls / deliverables.
    Nothing is auto-filled: unanswered items stay pending assumptions.
  * M2 asks at most 4 questions per round across 13 triaxial field groups.
    Every field records unit / source / confirmed / default / missing_risk.
    A field without an operator answer is NEVER confirmed, so M2 stays
    WAITING_FOR_USER and M3 remains gated.

Answers are read back from DecisionItem.answers (stored by Core.resolve_decision)
and their approval is verified against ApprovalLedger. A payload cannot forge
confirmation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core import (
    CardType,
    DecisionKey,
    DispatchRequest,
    Envelope,
    Evidence,
    EvidenceSource,
    ModuleID,
    ModuleState,
    CoreDispatcher,
)
from modules.card_templates import TEMPLATES, form_prompt, header_label

# 卡片形式严格照录形式报告图片；内容按模型阶段顺序 M1→M6 编排。
# 同一类型可出现 N 张（A/B/C 都是模板），不限制一类一张。
_A = TEMPLATES[CardType.DISCUSSION]
_B = TEMPLATES[CardType.PARAMETER]
_C = TEMPLATES[CardType.EXECUTION]

MODULE_VERSION = "4.1.0-alpha"

# ---- shared helpers ------------------------------------------------------


def _latest_answers(
    core: CoreDispatcher, research_task_id: str, stage_id: str,
    topic: str, context_version: str,
) -> Optional[Dict[str, Any]]:
    """Return answers of the most recent APPROVED decision for a topic."""
    for item in reversed(core.decision_items()):
        key = item.get("key", {})
        if (
            key.get("experiment_id") == research_task_id
            and key.get("stage_id") == stage_id
            and key.get("topic") == topic
            and key.get("context_version") == context_version
            and item.get("resolution") == "APPROVED"
            and item.get("answers")
        ):
            return dict(item["answers"])
    return None


def _decision_for(
    core: CoreDispatcher, research_task_id: str, stage_id: str,
    topic: str, context_version: str,
) -> Optional[Dict[str, Any]]:
    for item in core.decision_items():
        key = item.get("key", {})
        if (
            key.get("experiment_id") == research_task_id
            and key.get("stage_id") == stage_id
            and key.get("topic") == topic
            and key.get("context_version") == context_version
        ):
            return item
    return None


# ---- M1 research interview ----------------------------------------------

# 内容按规范 V2 的三种卡片类型组织（仅改内容，id / 轮次 / 答案字段不变）：
#   A 科研讨论  - 开放性目标、研究假设、方案比较，保留自然语言输入
#   B 参数决策  - 单选 / 多选 / 数值 + 单位，来源与默认值可见
#   C 执行确认  - 变更 / 风险 / 影响 + 明确授权（见 _confirm_card）
# M1 两轮：round1 全部 A（研究目标与边界），round2 中 hypotheses 为 A、
# 其余四个为 B（变量与交付是可枚举的参数决策）。

def _card(qid: str, ctype: CardType, stage: str, question: str,
          description: str, options: List[str], recommendation: str,
          why: str = "", unit: str = "-", decision: str = "关键决策") -> Dict[str, Any]:
    """按设计标准生成一张展示卡；类型仅作内部元数据，不进入面板文本。

    展示结构（截图 220414）：header=阶段·决策、正文=标题+说明+建议区、
    选项=物理意义短句。A/B/C 类型放在 card_type/type_label 字段供审计。
    """
    return {
        "id": qid,
        "card_type": ctype.value,
        "type_label": TEMPLATES[ctype]["type_label"],
        "header": header_label(stage, decision),
        "question": form_prompt(question, description, recommendation),
        "title": question, "description": description,
        "unit": unit, "options": options,
        "recommendation": recommendation, "why": why,
        "status": "pending",
    }


def _a_card(qid: str, content: str, options: List[str], recommendation: str,
            why: str) -> Dict[str, Any]:
    """A 科研讨论（内部类型）：展示为 科研规划 · 关键决策 卡。"""
    return _card(qid, CardType.DISCUSSION, "科研规划", content,
                 "请作出明确选择，结果将进入下一轮讨论。",
                 options, recommendation, why)


def _b_card(qid: str, content: str, options: List[str], recommendation: str,
            why: str, unit: str = "-") -> Dict[str, Any]:
    """B 参数决策（内部类型）：展示为 实验设计 · 关键决策 卡。"""
    return _card(qid, CardType.PARAMETER, "实验设计", content,
                 "确定主变量与条件，保证不同实验组之间具有可比性。",
                 options, recommendation, why, unit)


def _c_card(qid: str, action: str, target: str, impact: str) -> Dict[str, Any]:
    """C 执行确认（内部类型）：展示为 执行确认 卡，无静默延后。"""
    q = "确认进入下一步？"
    desc = "动作：%s；对象：%s；影响：%s。" % (action, target, impact)
    card = _card(qid, CardType.EXECUTION, "执行确认", q, desc,
                 ["确认执行", "取消 / 返回检查"], "", decision="授权")
    card["action"] = action
    card["target"] = target
    card["impact"] = impact
    card["allow_defer"] = False
    return card


# M1 第一轮：3 张 A 卡（研究目标与实验假设），按研究目标→材料→边界顺序。
ROUND1_QUESTIONS: List[Dict[str, Any]] = [
    _a_card("research_object", "本项目研究哪类材料？请补充材料名称与来源。",
            ["岩石", "胶结颗粒集合体", "煤体", "其他（请说明）"],
            "若研究胶结破坏机理，优先胶结颗粒集合体。", "决定接触模型与细观参数量级"),
    _a_card("research_goal", "本次研究希望回答什么科学问题？",
            ["强度规律", "参数敏感性", "破坏模式", "细观参数标定"],
            "先聚焦一个主目标，避免工况数膨胀。", "决定自变量与工况设计"),
    _a_card("confining_source", "围压等关键边界由谁给定？",
            ["我来给定", "先由 Agent 提议，我再确认"],
            "建议由你给定；Agent 提议须经你确认后才进入 M2。",
            "围压是三轴实验的核心变量，不得由 Agent 静默填入"),
]

# M1 第二轮：先 1 张 A 卡（假设），再 4 张 B 卡（变量与交付），符合 A→B 顺序。
ROUND2_QUESTIONS: List[Dict[str, Any]] = [
    _a_card("hypotheses", "要验证的假设是什么？写成“若…则…”的可检验句式。",
            ["输入假设"], "写成可检验句式，避免事后把结论写成假设。",
            "防止事后把结论写成假设"),
    _b_card("independent_vars", "本轮改变哪个自变量？",
            ["围压", "粒径", "胶结强度", "其他"],
            "优先单一主变量，便于单因素对比。", "决定实验矩阵"),
    _b_card("dependent_vars", "观测哪些响应变量？",
            ["峰值强度", "峰值应变", "E50", "破坏模式"],
            "至少选峰值强度与 E50，保证可比性。", "决定测量口径"),
    _b_card("control_vars", "哪些量保持不变？",
            ["试样几何", "级配", "密度", "加载速率"],
            "试样几何、级配、密度建议固定。", "保证可比性"),
    _b_card("deliverables", "期望哪些交付物？",
            ["应力应变曲线", "参数矩阵", "诊断报告", "对比报告"],
            "建议包含应力应变曲线与对比报告。", "决定 M6 输出"),
]


def _ask(
    core: CoreDispatcher, research_task_id: str, stage_id: str,
    topic: str, context_version: str, module_task_id: str,
    question: str, questions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    decision, should_present, _ = core.request_decision(
        key=DecisionKey(research_task_id, stage_id, topic, context_version),
        question=question,
        options=["提交本轮答复", "暂缓"],
        blocks_module_task_id=module_task_id,
        evidence_refs=[],
        authorization_scope=None,
        question_set=questions,
    )
    return {
        "decision_id": decision["decision_id"],
        "should_present": should_present,
        "questions": questions,
    }


def _interview_envelope(
    module_task_id: str, request: DispatchRequest, module_id: ModuleID,
    structured: Dict[str, Any], artifacts: List[Dict[str, Any]],
    decisions: List[Dict[str, Any]], state: str,
    limitations: Optional[List[str]] = None,
) -> Envelope:
    return Envelope(
        module_id=module_id,
        module_version=MODULE_VERSION,
        research_task_id=request.research_task_id,
        module_task_id=module_task_id,
        parent_task_id=request.parent_task_id,
        input_refs=request.input_refs,
        status={"module_state": state},
        output={"structured": structured, "artifacts": artifacts,
                "verified_by_execution": False},
        evidence=[Evidence(EvidenceSource.USER_PROVIDED, "interview", "多轮访谈记录")],
        decisions=decisions,
        limitations=limitations or [],
    )


def m1_run(module_task_id: str, request: DispatchRequest,
           core: CoreDispatcher) -> Envelope:
    """M1 three-round interview: round1 -> round2 -> confirm."""
    rid = request.research_task_id
    cv = request.context_version
    payload = request.payload or {}
    user_request = str(payload.get("user_request", ""))

    r1 = _latest_answers(core, rid, "M1", "interview_round1", cv)
    if r1 is None:
        asked = _ask(core, rid, "M1", "interview_round1", cv, module_task_id,
                     "三轴压缩实验：第一轮 3 个关键问题", ROUND1_QUESTIONS)
        return _interview_envelope(
            module_task_id, request, ModuleID.M1,
            {"stage": "round1", "user_request": user_request,
             "pending_questions": ROUND1_QUESTIONS,
             "confirmation_state": "UNCONFIRMED"},
            [], [{"decision_id": asked["decision_id"],
                  "delivery_status": "PRESENTED" if asked["should_present"] else "REUSED"}],
            ModuleState.WAITING_FOR_USER.value,
            ["研究计划未经用户确认；不得进入 M2"],
        )

    r2 = _latest_answers(core, rid, "M1", "interview_round2", cv)
    if r2 is None:
        asked = _ask(core, rid, "M1", "interview_round2", cv, module_task_id,
                     "第二轮：假设、变量、控制量与交付物", ROUND2_QUESTIONS)
        return _interview_envelope(
            module_task_id, request, ModuleID.M1,
            {"stage": "round2", "round1_answers": r1,
             "pending_questions": ROUND2_QUESTIONS,
             "confirmation_state": "UNCONFIRMED"},
            [], [{"decision_id": asked["decision_id"]}],
            ModuleState.WAITING_FOR_USER.value,
        )

    # Build requirements strictly from operator answers. Agent suggestions are
    # labelled as such and remain pending until the confirm decision.
    fact_vs_suggestion: List[Dict[str, Any]] = [
        {"claim": "研究对象=%s" % r1.get("research_object", "未回答"),
         "origin": "user_provided"},
        {"claim": "研究目标=%s" % r1.get("research_goal", "未回答"),
         "origin": "user_provided"},
        {"claim": "围压来源=%s" % r1.get("confining_source", "未回答"),
         "origin": "user_provided"},
    ]
    requirements = {
        "experiment_type": "三轴压缩",
        "research_object": r1.get("research_object", ""),
        "research_goal": r1.get("research_goal", ""),
        "confining_source": r1.get("confining_source", ""),
        "hypotheses": _split(r2.get("hypotheses")),
        "independent_vars": _split(r2.get("independent_vars")),
        "dependent_vars": _split(r2.get("dependent_vars")),
        "control_vars": _split(r2.get("control_vars")),
        "expected_outputs": _split(r2.get("deliverables")),
        "fact_vs_suggestion": fact_vs_suggestion,
        "confirmation_state": "UNCONFIRMED",
    }

    confirm = _decision_for(core, rid, "M1", "confirm_research_plan", cv)
    if confirm is None or confirm.get("resolution") != "APPROVED":
        asked = _ask(core, rid, "M1", "confirm_research_plan", cv, module_task_id,
                     _C["title"],
                     [_c_card("confirm", "进入 M2 实验设计", "研究计划（问题/假设/变量/交付）",
                              "后续 M2-M6 全部设计以本计划为准")])
        return _interview_envelope(
            module_task_id, request, ModuleID.M1,
            {"stage": "confirm", "round1_answers": r1, "round2_answers": r2,
             "research_requirements": requirements,
             "pending_questions": [], "confirmation_state": "UNCONFIRMED"},
            [], [{"decision_id": asked["decision_id"]}],
            ModuleState.WAITING_FOR_USER.value,
            ["研究计划未经用户确认；不得进入 M2"],
        )

    requirements["confirmation_state"] = "CONFIRMED"
    ref = core.store.write_json(
        "m1_research_requirements", "research_requirements.json", requirements
    )
    return _interview_envelope(
        module_task_id, request, ModuleID.M1,
        {"stage": "done", "round1_answers": r1, "round2_answers": r2,
         "research_requirements": requirements,
         "confirmation_state": "CONFIRMED"},
        [ref.to_dict()],
        [{"decision_id": confirm["decision_id"], "resolution": "APPROVED"}],
        ModuleState.COMPLETED.value,
    )


def _split(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [p.strip() for p in str(value).replace("，", ",").split(",") if p.strip()]


# ---- M2 parameter negotiation -------------------------------------------

# 13 triaxial field groups from the review. Each entry: key, unit, question,
# options. Nothing has an auto-confirmed default: a missing answer is a risk.
# 每个字段 = 一张 B 参数决策卡（单选 / 多选 / 数值 + 单位）；title<=20 字、
# description<=50 字，便于面板直接渲染为“类型 B · 参数决策”。
TRIAXIAL_FIELDS: List[Dict[str, Any]] = [
    {"key": "specimen_shape", "unit": "-", "question": "实验参数与条件选择\n试样形状与高径比取哪种？",
     "description": "单选；圆柱 H/D=2 为三轴常规几何，用于保证应力均匀。",
     "recommendation": "优先圆柱 H/D=2。", "options": ["圆柱 H/D=2", "方块", "自定义"]},
    {"key": "specimen_size", "unit": "m", "question": "实验参数与条件选择\n试样尺寸取多少？",
     "description": "数值 + 单位；尺寸影响颗粒数与计算量，未给定时不得进入 M3。",
     "recommendation": "请在 Other 输入数值和单位。", "options": ["由 Agent 提议后确认", "用户给定"]},
    {"key": "particle_size", "unit": "m", "question": "实验参数与条件选择\n粒径与级配如何设定？",
     "description": "单选；单粒径便于机理分析，级配分布更接近真实材料。",
     "recommendation": "机理研究优先单粒径。", "options": ["单粒径", "级配分布", "用户给定"]},
    {"key": "porosity", "unit": "-", "question": "实验参数与条件选择\n目标孔隙率取多少？",
     "description": "数值；孔隙率影响初始重叠与胶结保留，ball distribute 不检查重叠。",
     "recommendation": "参考 0.16；请确认。", "options": ["0.16", "0.36", "用户给定"]},
    {"key": "density_damping", "unit": "kg/m3", "question": "实验参数与条件选择\n颗粒密度与阻尼取多少？",
     "description": "数值 + 单位；密度决定质量量级，阻尼影响收敛。",
     "recommendation": "默认组合 2500/0.7 需你确认。", "options": ["2500/0.7", "用户给定"]},
    {"key": "sample_method", "unit": "-", "question": "实验参数与条件选择\n成样方式选哪种？",
     "description": "单选；ball generate 无重叠可避免初始重叠破坏平行键。",
     "recommendation": "优先 ball generate 无重叠。", "options": ["ball generate 无重叠", "压实", "伺服预压"]},
    {"key": "bond_state", "unit": "-", "question": "实验参数与条件选择\n胶结状态与胶结阶段如何安排？",
     "description": "单选；成样后胶结可避免加载前掉键。",
     "recommendation": "优先成样后胶结。", "options": ["成样后胶结", "加载前胶结", "无胶结"]},
    {"key": "contact_model", "unit": "-", "question": "实验参数与条件选择\n接触模型用哪种？",
     "description": "单选；linearpbond 提供平行键，适合胶结材料。",
     "recommendation": "胶结材料优先 linearpbond。", "options": ["linearpbond", "linear", "平节理"]},
    {"key": "bond_micro", "unit": "Pa", "question": "实验参数与条件选择\n胶结刚度/强度/摩擦角取多少？",
     "description": "数值 + 单位；细观参数需由你给定或确认 Agent 提议。",
     "recommendation": "Agent 提议须经你确认。", "options": ["用户给定", "Agent 建议后确认"]},
    {"key": "wall_contact", "unit": "-", "question": "实验参数与条件选择\n墙体接触模型及参数？",
     "description": "单选；墙体接触影响围压传递与边界效应。",
     "recommendation": "无特殊需求用 linear。", "options": ["linear", "用户给定"]},
    {"key": "confinement", "unit": "Pa", "question": "实验参数与条件选择\n围压与伺服参数如何设定？",
     "description": "数值 + 单位；围压目标/增益/限速/稳定判据不得由 Agent 静默填入。",
     "recommendation": "请给出目标值与判据。", "options": ["用户给定", "Agent 建议后确认"]},
    {"key": "axial_loading", "unit": "m/s", "question": "实验参数与条件选择\n轴向加载条件如何设定？",
     "description": "数值 + 单位；速率/目标应变/停止条件决定峰后能否捕获。",
     "recommendation": "目标应变建议超过峰值 10%。", "options": ["用户给定", "Agent 建议后确认"]},
    {"key": "measurement", "unit": "-", "question": "实验参数与条件选择\n测量口径与峰后判据？",
     "description": "单选；应力应变口径须明确，峰值在末点视为未捕获。",
     "recommendation": "采用工程应力/应变。", "options": ["工程应力/应变", "用户给定"]},
]

M2_ROUNDS: List[List[str]] = [
    ["specimen_shape", "specimen_size", "particle_size", "porosity"],
    ["density_damping", "sample_method", "bond_state", "contact_model"],
    ["bond_micro", "wall_contact", "confinement", "axial_loading"],
    ["measurement"],
]

_FIELD_BY_KEY = {f["key"]: f for f in TRIAXIAL_FIELDS}


def _field_questions(keys: List[str]) -> List[Dict[str, Any]]:
    """B 参数决策（内部类型）：展示为 实验设计 · 关键决策 卡；id 不变。"""
    qs = []
    for key in keys:
        f = _FIELD_BY_KEY[key]
        content = f["question"].split("\n", 1)[-1]  # 去掉旧标题前缀
        qs.append(_card(
            key, CardType.PARAMETER, "实验设计", content,
            f.get("description", "确定主变量与条件，保证不同实验组之间具有可比性。"),
            f["options"], f.get("recommendation", ""), unit=f["unit"],
        ))
    return qs


def _build_parameter_schema(all_answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    schema = []
    for f in TRIAXIAL_FIELDS:
        key = f["key"]
        answered = key in all_answers and all_answers[key] not in (None, "", "未回答")
        schema.append({
            "name": key,
            "unit": f["unit"],
            "value": all_answers.get(key),
            "source": "user_answers" if answered else "MISSING",
            "confirmed": bool(answered),
            "default": None,  # 4.1 never silently supplies a physical default
            "missing_risk": "" if answered else "关键字段未确认：不得进入 M3/M4",
        })
    return schema


def m2_run(module_task_id: str, request: DispatchRequest,
           core: CoreDispatcher) -> Envelope:
    """M2: negotiate the 13 triaxial field groups in rounds of <=4 questions."""
    rid = request.research_task_id
    cv = request.context_version

    all_answers: Dict[str, Any] = {}
    pending_decisions: List[Dict[str, Any]] = []
    for idx, keys in enumerate(M2_ROUNDS, start=1):
        topic = "negotiate_round%d" % idx
        answers = _latest_answers(core, rid, "M2", topic, cv)
        if answers is None:
            asked = _ask(core, rid, "M2", topic, cv, module_task_id,
                         "M2 参数协商第 %d 轮（%d 个关键字段）" % (idx, len(keys)),
                         _field_questions(keys))
            pending_decisions.append({"decision_id": asked["decision_id"],
                                      "round": idx})
            break
        for k, v in answers.items():
            if k in _FIELD_BY_KEY and v not in (None, ""):
                all_answers[k] = v

    if pending_decisions:
        unanswered = [f["key"] for f in TRIAXIAL_FIELDS if f["key"] not in all_answers]
        return _interview_envelope(
            module_task_id, request, ModuleID.M2,
            {"stage": "negotiating", "answers": all_answers,
             "pending_fields": unanswered, "confirmation_state": "UNCONFIRMED"},
            [], pending_decisions,
            ModuleState.WAITING_FOR_USER.value,
            ["参数协商中；关键字段未确认前不得进入 M3"],
        )

    schema = _build_parameter_schema(all_answers)
    unconfirmed = [p["name"] for p in schema if not p["confirmed"]]
    confirm = _decision_for(core, rid, "M2", "confirm_experiment_design", cv)
    if unconfirmed or confirm is None or confirm.get("resolution") != "APPROVED":
        asked = _ask(core, rid, "M2", "confirm_experiment_design", cv, module_task_id,
                     _C["title"],
                     [_c_card("confirm", "进入 M3 数值建模", "实验设计（13 项参数字段）",
                              "未确认字段：%s" % (", ".join(unconfirmed) or "无"))])
        decisions = [{"decision_id": asked["decision_id"]}]
        return _interview_envelope(
            module_task_id, request, ModuleID.M2,
            {"stage": "confirm", "experiment_type": "三轴压缩",
             "parameter_schema": schema, "unconfirmed_fields": unconfirmed,
             "confirmation_state": "UNCONFIRMED"},
            [], decisions,
            ModuleState.WAITING_FOR_USER.value if not unconfirmed else ModuleState.BLOCKED.value,
            ["字段未确认：%s" % ", ".join(unconfirmed)] if unconfirmed else
            ["实验方案未经用户确认；不得进入 M3"],
        )

    design = {
        "experiment_type": "三轴压缩",
        "parameter_schema": schema,
        "cases": [],  # cases are built only after confinement values are user-given
        "confirmation_state": "CONFIRMED",
    }
    ref = core.store.write_json("m2_parameter_schema", "parameter_schema.json", design)
    return _interview_envelope(
        module_task_id, request, ModuleID.M2,
        dict(design, stage="done"), [ref.to_dict()],
        [{"decision_id": confirm["decision_id"], "resolution": "APPROVED"}],
        ModuleState.COMPLETED.value,
    )


__all__ = [
    "ROUND1_QUESTIONS", "ROUND2_QUESTIONS", "TRIAXIAL_FIELDS", "M2_ROUNDS",
    "m1_run", "m2_run", "_latest_answers", "_split",
]
