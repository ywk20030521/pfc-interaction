"""4.0 full implementation: M1 Research Planning + M2 Experiment Design.

Technical report sections 4.1 and 4.2. Both modules use Core decision rounds
(never payload confirmation) and emit ALL standard output files:

  M1: research_question.md / research_plan.md / research_hypotheses.md /
      research_workflow.md / research_requirements.json
  M2: experiment_design.md / parameter_schema.json / experiment_matrix.csv /
      control_groups.md / measurement_plan.md

The 9 functions of each module are implemented as pure helpers so they can be
verified independently (functional acceptance).
"""

from __future__ import annotations

import csv
import io
import itertools
from typing import Any, Dict, List, Optional

from core import (
    ArtifactRef, DecisionKey, DispatchRequest, Envelope, Evidence, EvidenceSource,
    ModuleID, ModuleState, CoreDispatcher,
)
from modules.v41_interview import (
    _ask, _latest_answers, _decision_for, _interview_envelope, _split,
)
from modules.experiment_knowledge import get_experiment, supported_types
from modules.nature_experiment_design import (
    nature_questions, sample_preparation_question, design_review,
)
from core import to_decision_questions, meta_for, apply_answers, validate_card

MODULE_VERSION = "4.0.0"

# ---------- M1: nine functions -------------------------------------------

M1_ROUND1: List[Dict[str, Any]] = [
    {"id": "research_object", "question": "研究对象是什么？（岩石/颗粒体/煤体/其他）",
     "options": ["岩石", "胶结颗粒集合体", "煤体", "其他"]},
    {"id": "research_goal", "question": "研究目标是什么？",
     "options": ["强度规律", "参数敏感性", "破坏模式", "细观参数标定"]},
    {"id": "research_scope", "question": "研究范围与边界条件？",
     "options": ["PFC2D", "PFC3D", "2D+3D对比"]},
]
M1_ROUND2: List[Dict[str, Any]] = [
    {"id": "hypotheses", "question": "待验证的科学假设（可多条，逗号分隔）", "options": ["文字作答"]},
    {"id": "independent_vars", "question": "自变量有哪些？", "options": ["文字作答"]},
    {"id": "dependent_vars", "question": "因变量/响应指标有哪些？", "options": ["文字作答"]},
    {"id": "control_vars", "question": "控制变量有哪些？", "options": ["文字作答"]},
]
M1_ROUND3: List[Dict[str, Any]] = [
    {"id": "work_packages", "question": "研究内容拆分（工作包，逗号分隔）", "options": ["文字作答"]},
    {"id": "deliverables", "question": "预期交付物（逗号分隔）", "options": ["文字作答"]},
]


def identify_question(raw: str, answers: Dict[str, Any]) -> str:
    """M1.1 科研问题识别."""
    return str(answers.get("research_goal") or raw or "未明确").strip()


def extract_object_goal(answers: Dict[str, Any]) -> Dict[str, str]:
    """M1.2 研究目标与研究对象提取."""
    return {
        "object": str(answers.get("research_object") or "未回答"),
        "goal": str(answers.get("research_goal") or "未回答"),
    }


def identify_scope(answers: Dict[str, Any]) -> Dict[str, Any]:
    """M1.3 研究范围与边界条件识别."""
    return {
        "scope": str(answers.get("research_scope") or "未回答"),
        "boundary_conditions": _split(answers.get("boundary")),
    }


def organize_hypotheses(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    """M1.4 科学假设整理（假设不得写成结论）."""
    return [{"id": "H%d" % (i + 1), "statement": h, "status": "待验证"}
            for i, h in enumerate(_split(answers.get("hypotheses")))]


def identify_variables(answers: Dict[str, Any]) -> Dict[str, List[str]]:
    """M1.5 研究变量与响应指标识别."""
    return {
        "independent": _split(answers.get("independent_vars")),
        "dependent": _split(answers.get("dependent_vars")),
        "control": _split(answers.get("control_vars")),
    }


def split_work_packages(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    """M1.6 研究内容拆分."""
    return [{"id": "WP%d" % (i + 1), "name": w, "module": "M%d" % min(i + 1, 6)}
            for i, w in enumerate(_split(answers.get("work_packages")))]


def build_workflow(packages: List[Dict[str, Any]]) -> List[str]:
    """M1.7 研究路线制定."""
    return [p["name"] for p in packages] or [
        "研究规划", "实验设计", "数值建模", "仿真管理", "科学诊断", "科学分析"
    ]


def define_deliverables(answers: Dict[str, Any]) -> List[str]:
    """M1.8 研究任务与交付物定义."""
    return _split(answers.get("deliverables"))


def completeness_check(question: str, obj: Dict[str, str],
                       variables: Dict[str, List[str]],
                       hypotheses: List[Dict[str, Any]]) -> List[str]:
    """M1.9 研究计划完整性检查."""
    errors: List[str] = []
    if not question or question == "未明确":
        errors.append("研究问题未明确")
    if obj["object"] == "未回答":
        errors.append("研究对象未确认")
    if obj["goal"] == "未回答":
        errors.append("研究目标未确认")
    if not variables["independent"]:
        errors.append("缺少自变量")
    if not variables["dependent"]:
        errors.append("缺少因变量/响应指标")
    if not hypotheses:
        errors.append("缺少科学假设")
    return errors


def render_m1_docs(question: str, obj: Dict[str, str], scope: Dict[str, Any],
                   hypotheses: List[Dict[str, Any]], variables: Dict[str, List[str]],
                   packages: List[Dict[str, Any]], workflow: List[str],
                   deliverables: List[str], errors: List[str]) -> Dict[str, str]:
    def bullets(items: List[str]) -> str:
        return "\n".join("- %s" % i for i in items) if items else "- （未明确）"
    return {
        "research_question.md": "# 研究问题\n\n%s\n\n## 研究对象\n%s\n\n## 研究目标\n%s\n\n## 边界\n%s\n" % (
            question, obj["object"], obj["goal"], scope["scope"]),
        "research_plan.md": "# 研究计划\n\n## 自变量\n%s\n\n## 因变量\n%s\n\n## 控制变量\n%s\n\n## 工作包\n%s\n\n## 完整性检查\n%s\n" % (
            bullets(variables["independent"]), bullets(variables["dependent"]),
            bullets(variables["control"]),
            bullets(["%s %s" % (p["id"], p["name"]) for p in packages]),
            bullets(errors) if errors else "- 通过"),
        "research_hypotheses.md": "# 研究假设\n\n%s\n" % "\n".join(
            "- [%s] %s" % (h["status"], h["statement"]) for h in hypotheses),
        "research_workflow.md": "# 研究路线\n\n%s\n" % "\n".join(
            "%d. %s" % (i + 1, w) for i, w in enumerate(workflow)),
        "_deliverables": bullets(deliverables),
    }


def m1_full_run(module_task_id: str, request: DispatchRequest,
                core: CoreDispatcher) -> Envelope:
    rid, cv = request.research_task_id, request.context_version
    raw = str((request.payload or {}).get("user_request", ""))
    r1 = _latest_answers(core, rid, "M1", "interview_round1", cv)
    if r1 is None:
        asked = _ask(core, rid, "M1", "interview_round1", cv, module_task_id,
                     "M1 第一轮：研究对象/目标/边界", M1_ROUND1)
        return _interview_envelope(module_task_id, request, ModuleID.M1,
            {"stage": "round1", "pending_questions": M1_ROUND1, "confirmation_state": "UNCONFIRMED"},
            [], [{"decision_id": asked["decision_id"]}], ModuleState.WAITING_FOR_USER.value)

    r2 = _latest_answers(core, rid, "M1", "interview_round2", cv)
    if r2 is None:
        asked = _ask(core, rid, "M1", "interview_round2", cv, module_task_id,
                     "M1 第二轮：假设与变量", M1_ROUND2)
        return _interview_envelope(module_task_id, request, ModuleID.M1,
            {"stage": "round2", "pending_questions": M1_ROUND2, "confirmation_state": "UNCONFIRMED"},
            [], [{"decision_id": asked["decision_id"]}], ModuleState.WAITING_FOR_USER.value)

    r3 = _latest_answers(core, rid, "M1", "interview_round3", cv)
    if r3 is None:
        asked = _ask(core, rid, "M1", "interview_round3", cv, module_task_id,
                     "M1 第三轮：研究内容拆分与交付物", M1_ROUND3)
        return _interview_envelope(module_task_id, request, ModuleID.M1,
            {"stage": "round3", "pending_questions": M1_ROUND3, "confirmation_state": "UNCONFIRMED"},
            [], [{"decision_id": asked["decision_id"]}], ModuleState.WAITING_FOR_USER.value)

    merged = dict(r1); merged.update(r2); merged.update(r3)
    question = identify_question(raw, merged)
    obj = extract_object_goal(merged)
    scope = identify_scope(merged)
    hypotheses = organize_hypotheses(merged)
    variables = identify_variables(merged)
    packages = split_work_packages(merged)
    workflow = build_workflow(packages)
    deliverables = define_deliverables(merged)
    errors = completeness_check(question, obj, variables, hypotheses)

    requirements = {
        "research_task_id": rid, "experiment_type_hint": merged.get("experiment_type", ""),
        "research_question": question, "research_object": obj["object"],
        "research_goal": obj["goal"], "research_scope": scope,
        "hypotheses": hypotheses, "variables": variables,
        "work_packages": packages, "workflow": workflow,
        "deliverables": deliverables, "completeness_errors": errors,
        "fact_vs_suggestion": [
            {"claim": "研究对象=%s" % obj["object"], "origin": "user_provided"},
            {"claim": "研究目标=%s" % obj["goal"], "origin": "user_provided"},
            {"claim": "研究路线由 Agent 编排", "origin": "agent_inferred", "evidence_ref": "M1.workflow"},
        ],
        "confirmation_state": "UNCONFIRMED",
    }
    confirm = _decision_for(core, rid, "M1", "confirm_research_plan", cv)
    if confirm is None or confirm.get("resolution") != "APPROVED":
        asked = _ask(core, rid, "M1", "confirm_research_plan", cv, module_task_id,
                     "是否确认研究计划？完整性检查：%s" % (errors or "通过"),
                     [{"id": "confirm", "question": "确认研究计划", "options": ["确认", "修改", "暂缓"]}])
        return _interview_envelope(module_task_id, request, ModuleID.M1,
            {"stage": "confirm", "research_requirements": requirements,
             "confirmation_state": "UNCONFIRMED"}, [],
            [{"decision_id": asked["decision_id"]}], ModuleState.WAITING_FOR_USER.value,
            errors or ["研究计划未经用户确认"])

    requirements["confirmation_state"] = "CONFIRMED"
    docs = render_m1_docs(question, obj, scope, hypotheses, variables,
                          packages, workflow, deliverables, errors)
    artifacts = []
    for name, text in docs.items():
        if name.startswith("_"):
            continue
        artifacts.append(core.store.write("m1_" + name.replace(".", "_"), name, text).to_dict())
    artifacts.append(core.store.write_json(
        "m1_research_requirements", "research_requirements.json", requirements).to_dict())
    return _interview_envelope(module_task_id, request, ModuleID.M1,
        {"stage": "done", "research_requirements": requirements,
         "nine_functions": ["identify_question", "extract_object_goal", "identify_scope",
             "organize_hypotheses", "identify_variables", "split_work_packages",
             "build_workflow", "define_deliverables", "completeness_check"],
         "confirmation_state": "CONFIRMED"},
        artifacts, [{"decision_id": confirm["decision_id"], "resolution": "APPROVED"}],
        ModuleState.COMPLETED.value)


# ---------- M2: nine functions -------------------------------------------

def _field_q(qid: str, prompt: str, options: List[str],
             unit: str = "-", why: str = ""):
    """Build a structured Question from a legacy short option list."""
    from core import Question, Option
    return Question(
        id=qid, prompt=prompt, unit=unit, why=why,
        options=[Option(o, o, unit=unit, source="agent_proposal") for o in options],
        allow_free_text=True, free_text_hint="自定义输入（数值+单位）",
    )


M2_ROUND1_Q: List[Any] = [
    _field_q("experiment_type", "实验类型？", supported_types(),
             why="决定参数体系、测量指标与阶段流程（8 类实验知识库）"),
    _field_q("independent_spec", "自变量及其取值范围（如 围压=1,5,10 MPa）", ["文字作答"],
             unit="由自变量决定", why="自变量决定实验矩阵；请写数值+单位"),
    _field_q("controlled_spec", "控制变量及固定值", ["文字作答"],
             why="控制量必须保持不变，否则无法归因"),
    _field_q("repeat_count", "每个工况重复次数", ["1", "3", "5"],
             why="独立实验单元与技术重复须区分（Nature 报告规范）"),
]
M2_ROUND2: List[Dict[str, Any]] = [
    {"id": "specimen", "question": "试样几何与尺寸", "options": ["用户给定", "Agent建议后确认"]},
    {"id": "particle", "question": "粒径级配与密度", "options": ["用户给定", "Agent建议后确认"]},
    {"id": "contact", "question": "接触模型与细观参数", "options": ["linearpbond", "linear", "用户给定"]},
    {"id": "loading", "question": "加载方式与速率", "options": ["用户给定", "Agent建议后确认"]},
]
M2_ROUND3_Q: List[Any] = [
    _field_q("measurement_spec", "测量口径与指标定义", ["工程应力应变", "用户给定"],
             why="不同口径得到的峰值/E50 不可直接比较"),
    _field_q("sensitivity", "是否做敏感性分析", ["是", "否"],
             why="须与 M1 研究目标一致；参数敏感性目标应选是"),
    _field_q("control_group", "基准组设置", ["默认值基准", "用户给定"],
             why="基准组是自变量的反事实基准（Nature 报告规范）"),
]


def recognize_type(answers: Dict[str, Any]) -> str:
    """M2.1 实验类型识别."""
    t = str(answers.get("experiment_type", ""))
    return t if t in supported_types() else ""


def design_scheme(answers: Dict[str, Any]) -> Dict[str, Any]:
    """M2.2 实验方案设计."""
    return {"summary": str(answers.get("scheme", "")),
            "type": recognize_type(answers), "repeat": answers.get("repeat_count", "1")}


def build_parameter_system(exp_type: str, answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    """M2.3 变量与参数体系设计 (from knowledge base)."""
    if not exp_type:
        return []
    knowledge = get_experiment(exp_type)
    fields = []
    for i, p in enumerate(knowledge["typical_parameters"], 1):
        fields.append({"name": p, "unit": "-", "source": "knowledge", "confirmed": False,
                       "key": "field_%02d" % i})
    return fields


def design_ranges(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    """M2.4 参数范围和取值设计 (parse 'var=1,5,10 MPa')."""
    spec = str(answers.get("independent_spec", ""))
    out: List[Dict[str, Any]] = []
    for part in spec.replace("，", ",").split(";"):
        if "=" not in part:
            continue
        name, rest = part.split("=", 1)
        tokens = [t.strip() for t in rest.replace("，", ",").split(",") if t.strip()]
        values: List[Any] = []
        unit = ""
        for tok in tokens:
            try:
                values.append(float(tok))
            except ValueError:
                import re
                m = re.match(r"([-\d.]+)\s*([A-Za-z%]+)", tok)
                if m:
                    values.append(float(m.group(1)))
                    unit = m.group(2)
                else:
                    values.append(tok)
        out.append({"name": name.strip(), "values": values, "unit": unit,
                    "source": "user", "confirmed": True})
    return out


def design_matrix(ranges: List[Dict[str, Any]], repeat: int = 1,
                  multi_factor: bool = True) -> List[Dict[str, Any]]:
    """M2.5/7 单/多因素设计与工况矩阵生成."""
    cases: List[Dict[str, Any]] = []
    if not ranges:
        return cases
    if len(ranges) == 1 or not multi_factor:
        base = ranges[0]
        for v in base["values"]:
            cases.append({"values": {base["name"]: v}})
    else:
        names = [r["name"] for r in ranges]
        for combo in itertools.product(*[r["values"] for r in ranges]):
            cases.append({"values": dict(zip(names, combo))})
    final = []
    for c in cases:
        for k in range(max(1, int(repeat))):
            final.append({"case_id": "C%02d" % (len(final) + 1),
                          "repeat": k + 1, "values": dict(c["values"])})
    return final


def design_control_groups(ranges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """M2.6 对照组与基准组设计."""
    if not ranges:
        return []
    baseline = {r["name"]: r["values"][0] for r in ranges if r["values"]}
    return [{"name": "基准组", "values": baseline, "description": "各因素第一水平"}]

def design_repeat_sensitivity(answers: Dict[str, Any], cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """M2.8 重复试验和敏感性分析设计."""
    return {"repeat_count": answers.get("repeat_count", "1"),
            "sensitivity": answers.get("sensitivity", "否"),
            "total_cases": len(cases)}


def feasibility_check(exp_type: str, ranges: List[Dict[str, Any]],
                      measurements: List[Dict[str, Any]]) -> List[str]:
    """M2.9 实验方案可执行性检查."""
    errors: List[str] = []
    if not exp_type:
        errors.append("实验类型未确认")
    if not ranges:
        errors.append("无自变量取值范围")
    knowledge = get_experiment(exp_type) if exp_type else {"required_measurements": []}
    measured = {m.get("metric") for m in measurements}
    for metric in knowledge["required_measurements"]:
        if metric not in measured:
            errors.append("测量计划缺少: %s" % metric)
    return errors


def render_m2_docs(exp_type: str, fields: List[Dict[str, Any]],
                   cases: List[Dict[str, Any]], groups: List[Dict[str, Any]],
                   measurements: List[Dict[str, Any]],
                   repeat_sens: Dict[str, Any], errors: List[str]) -> Dict[str, str]:
    buf = io.StringIO()
    names = sorted({k for c in cases for k in c.get("values", {})})
    writer = csv.DictWriter(buf, fieldnames=["case_id", "repeat"] + names)
    writer.writeheader()
    for c in cases:
        row = {"case_id": c["case_id"], "repeat": c.get("repeat", 1)}
        row.update(c.get("values", {}))
        writer.writerow({k: row.get(k, "") for k in writer.fieldnames})
    return {
        "experiment_design.md": "# 实验设计\n\n## 类型\n%s\n\n## 参数体系\n%s\n\n## 可执行性\n%s\n" % (
            exp_type, "\n".join("- %s" % f["name"] for f in fields),
            "; ".join(errors) if errors else "通过"),
        "experiment_matrix.csv": buf.getvalue(),
        "control_groups.md": "# 对照组\n\n%s\n" % "\n".join(
            "- %s: %s" % (g["name"], g["values"]) for g in groups),
        "measurement_plan.md": "# 测量计划\n\n%s\n" % "\n".join(
            "- %s（口径：%s）" % (m.get("metric"), m.get("definition", "")) for m in measurements),
        "repeat_sensitivity": str(repeat_sens),
    }


def m2_full_run(module_task_id: str, request: DispatchRequest,
                core: CoreDispatcher) -> Envelope:
    rid, cv = request.research_task_id, request.context_version
    collected: Dict[str, Any] = {}
    pending: List[Dict[str, Any]] = []
    # Structured question sets: M2 round 2's sample-prep uses PFC manual basis;
    # round 4 is the Nature-style design review (controls / replication / stats).
    qsets = [
        to_decision_questions(M2_ROUND1_Q),
        to_decision_questions([
            _field_q("specimen", "试样几何与尺寸", ["用户给定", "Agent 建议后确认"]),
            sample_preparation_question(2, 5),
            _field_q("contact", "接触模型与细观参数", ["linearpbond", "linear", "用户给定"]),
            _field_q("loading", "加载方式与速率", ["用户给定", "Agent 建议后确认"]),
        ]),
        to_decision_questions(M2_ROUND3_Q),
        to_decision_questions(nature_questions("三轴压缩", 1, 5)),
    ]
    question_meta_all: List[Dict[str, Any]] = []
    for idx, questions in enumerate(qsets, 1):
        topic = "negotiate_round%d" % idx
        answers = _latest_answers(core, rid, "M2", topic, cv)
        if answers is None:
            asked = _ask(core, rid, "M2", topic, cv, module_task_id,
                         "M2 第%d轮参数协商（共%d轮）" % (idx, len(qsets)), questions)
            pending.append({"decision_id": asked["decision_id"]})
            break
        collected.update(answers)
    if pending:
        return _interview_envelope(module_task_id, request, ModuleID.M2,
            {"stage": "negotiating", "answers": collected,
             "progress": {"current": len(collected) and len(qsets) or 1, "total": len(qsets)},
             "confirmation_state": "UNCONFIRMED"},
            [], pending, ModuleState.WAITING_FOR_USER.value)

    exp_type = recognize_type(collected)
    fields = build_parameter_system(exp_type, collected)
    ranges = design_ranges(collected)
    repeat = collected.get("repeat_count", "1")
    cases = design_matrix(ranges, repeat)
    groups = design_control_groups(ranges)
    repeat_sens = design_repeat_sensitivity(collected, cases)
    measurements = [{"metric": m, "definition": str(collected.get("measurement_spec", "待确认"))}
                    for m in get_experiment(exp_type)["required_measurements"]] if exp_type else []
    errors = feasibility_check(exp_type, ranges, measurements)

    # BUG-W01: M1 -> M2 consistency. The operator may change direction between
    # modules (legitimate), but the Skill must SURFACE the inconsistency rather
    # than silently accept it (report 4.2.5: variables must match the question).
    m1_req = {}
    m1_ref = None
    for ref in request.input_refs:
        if ref.artifact_id.startswith("m1_research_requirements"):
            m1_ref = ref
            break
    if m1_ref is None:
        # Fallback: a caller may omit input_refs on a later negotiation round.
        # Find the M1 requirements artifact from Core's own envelope history.
        for env in core._envelopes.values():
            if env.module_id == ModuleID.M1:
                for art in env.output.get("artifacts", []):
                    if str(art.get("artifact_id", "")).startswith("m1_research_requirements"):
                        m1_ref = ArtifactRef.from_dict(art)
                        break
            if m1_ref is not None:
                break
    if m1_ref is not None:
        try:
            m1_req = core.store.get_json(m1_ref)
        except (KeyError, ValueError, OSError):
            m1_req = {}
    consistency: List[str] = []
    if m1_req:
        m1_vars = (m1_req.get("variables") or {}).get("independent", [])
        m2_vars = [r["name"] for r in ranges]
        if m1_vars and m2_vars and not any(v in str(m2_vars) for v in m1_vars):
            consistency.append(
                "M1 自变量 %s 与 M2 自变量 %s 不一致；请确认是有意调整研究问题"
                % (m1_vars, m2_vars))
        m1_goal = str(m1_req.get("research_goal", ""))
        if m1_goal == "参数敏感性" and str(collected.get("sensitivity", "是")) == "否":
            consistency.append("M1 目标为参数敏感性，但 M2 未启用敏感性分析")

    schema = {
        "experiment_type": exp_type, "parameter_schema": fields,
        "ranges": ranges, "cases": cases, "control_groups": groups,
        "measurement_plan": measurements, "repeat_sensitivity": repeat_sens,
        "feasibility_errors": errors, "consistency_warnings": consistency,
        "nature_design_review": design_review(collected),
        "question_meta": meta_for(nature_questions(exp_type or "三轴压缩", 1, 5))
                         + [sample_preparation_question(2, 5).to_dict()],
        "card_validation": {
            q.id: validate_card(q)
            for q in nature_questions(exp_type or "三轴压缩", 1, 5)
                     + [sample_preparation_question(2, 5)]
        },
        "confirmation_state": "UNCONFIRMED",
        "nine_functions": ["recognize_type", "design_scheme", "build_parameter_system",
            "design_ranges", "design_matrix", "design_control_groups",
            "design_matrix", "design_repeat_sensitivity", "feasibility_check"],
    }
    confirm = _decision_for(core, rid, "M2", "confirm_experiment_design", cv)
    if errors or confirm is None or confirm.get("resolution") != "APPROVED":
        q = "确认实验设计？类型=%s 工况=%d 问题=%s" % (exp_type, len(cases), errors or "无")
        if consistency:
            q += "；注意：" + "；".join(consistency)
        asked = _ask(core, rid, "M2", "confirm_experiment_design", cv, module_task_id,
                     q,
                     [{"id": "confirm", "question": "确认实验设计", "options": ["确认", "修改", "暂缓"]}])
        return _interview_envelope(module_task_id, request, ModuleID.M2,
            {"stage": "confirm", "experiment_design": schema, "confirmation_state": "UNCONFIRMED"},
            [], [{"decision_id": asked["decision_id"]}],
            ModuleState.BLOCKED.value if errors else ModuleState.WAITING_FOR_USER.value,
            errors + consistency)

    schema["confirmation_state"] = "CONFIRMED"
    docs = render_m2_docs(exp_type, fields, cases, groups, measurements, repeat_sens, errors)
    artifacts = []
    for name, text in docs.items():
        if name == "repeat_sensitivity":
            continue
        aid = "m2_" + name.replace(".", "_")
        artifacts.append(core.store.write(aid, name, text).to_dict())
    artifacts.append(core.store.write_json(
        "m2_parameter_schema", "parameter_schema.json", schema).to_dict())
    return _interview_envelope(module_task_id, request, ModuleID.M2,
        {"stage": "done", "experiment_design": schema, "confirmation_state": "CONFIRMED"},
        artifacts, [{"decision_id": confirm["decision_id"], "resolution": "APPROVED"}],
        ModuleState.COMPLETED.value, consistency)


__all__ = [
    "m1_full_run", "m2_full_run", "identify_question", "extract_object_goal",
    "identify_scope", "organize_hypotheses", "identify_variables",
    "split_work_packages", "build_workflow", "define_deliverables", "completeness_check",
    "recognize_type", "design_scheme", "build_parameter_system", "design_ranges",
    "design_matrix", "design_control_groups", "design_repeat_sensitivity",
    "feasibility_check", "render_m1_docs", "render_m2_docs",
]
