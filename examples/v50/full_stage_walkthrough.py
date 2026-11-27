"""5.0 offline stage walkthrough: S1-S6 + calibration loop + evidence rollback.

This is an OFFLINE REPLAY. Historical tool_task_ids are reused only to test the
protocol; this script does not connect to Itasca MCP and does not validate any
physics. Run from the skill root:

    python examples/v50/full_stage_walkthrough.py --out <report.json>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)

from core.v50_context import (
    EvidenceItem, EvidenceKind, ResearchTask, STAGE_ARTIFACTS, STAGE_COMPLETION,
    StageID,
)
from core.v50_decisions import DecisionManager, InteractionRouter
from core.v50_discussion import DiscussionManager, ProposalOption, make_proposal
from core.v50_workflow import WorkflowOrchestrator
from modules.v50_calibration import ParameterCalibrationLoop
from modules.v50_interaction import InteractionCoordinator

# Historical IDs from earlier 4.0 tooling acceptance, used only as replay labels.
REPLAY_TASK_IDS = {
    "build": "pfc-99de70f8",
    "load": "pfc-0016abcd",
    "anomaly": "pfc-85a05d05",
}


def evidence(kind: EvidenceKind, ref: str, tool_task_id: str = "",
             description: str = "", input_refs=None) -> EvidenceItem:
    return EvidenceItem(kind=kind, ref=ref, description=description,
                        tool_task_id=tool_task_id, input_refs=list(input_refs or []))


def complete_stage(task: ResearchTask, workflow: WorkflowOrchestrator,
                   name: str, artifacts: Dict[str, str], ev: EvidenceItem,
                   notes: list) -> None:
    workflow.submit_for_review(artifacts, [ev])
    staging = {c: True for c in STAGE_COMPLETION[task.current_stage]}
    transition = workflow.complete(staging, user_confirmed=True)
    notes.append({
        "stage": name, "status": task.stage_status[name],
        "transition": transition.kind,
    })


def run(out_path: Path) -> Dict[str, Any]:
    task = ResearchTask("v50-walkthrough", "颗粒材料峰值强度研究")
    decisions = DecisionManager(task)
    discussion = DiscussionManager(task)
    workflow = WorkflowOrchestrator(task, decisions)
    loop = ParameterCalibrationLoop(task, decisions)
    router = InteractionRouter(task, decisions)
    coordinator = InteractionCoordinator(task, decisions, router)
    notes: list = []

    # S1: discuss objective, compare routes, confirm research question.
    discussion.add_turn(
        "研究目标", understanding="用户关注围压对峰值强度的影响",
        analysis="PFC 适合观察颗粒胶结破坏过程，但细观参数需标定",
        alternatives=[{"name": "单轴压缩", "reason": "少一个变量，无法回答围压问题"}],
        impact=["结论边界受限于颗粒尺度假设"], next_step="确认研究问题与边界",
    )
    proposal = make_proposal(
        observation="用户给出三组围压目标",
        rationale="三轴压缩可直接比较围压效应",
        options=[
            ProposalOption("三轴压缩", "围压1/5/10MPa", "强度对比",
                           ["可比较围压"], ["成本高"], ["历史数据"], True),
            ProposalOption("巴西劈裂", "拉伸破坏", "拉伸问题",
                           ["制样简单"], ["不回答围压问题"]),
        ],
        risks=["细观参数未标定"], needs_evidence=["目标材料力学参数"],
        user_viewpoint="优先三轴", understanding="用户希望回答围压影响",
    )
    discussion.add_proposal(proposal)
    research_decision = decisions.propose(
        "研究问题", "围压如何影响胶结颗粒材料峰值强度?", "来自用户目标与PFC适用性",
        affected_assets=["research_question", "research_scope"])
    decisions.confirm(research_decision.decision_id, "用户确认研究问题")
    complete_stage(task, workflow, "S1",
                   {n: "replay://%s" % n for n in STAGE_ARTIFACTS[StageID.S1]},
                   evidence(EvidenceKind.USER_INPUT, "user:intent",
                            description="用户研究意图"), notes)

    # S2: experiment design with control strategy.
    workflow.enter(StageID.S2)
    decisions.propose("对照策略", "以1MPa为基准组，5/10MPa为试验组",
                      "单因素比较围压影响", affected_assets=["experiment_matrix"])
    design = decisions.propose("实验设计", "三工况单因素矩阵", "变量关系清晰",
                               affected_assets=["experiment_matrix"])
    decisions.confirm(design.decision_id, "用户确认工况矩阵")
    complete_stage(task, workflow, "S2",
                   {n: "replay://%s" % n for n in STAGE_ARTIFACTS[StageID.S2]},
                   evidence(EvidenceKind.AGENT_PROPOSAL, "design:matrix",
                            description="用户确认的设计方案"), notes)

    # S3: technical route and model validation plan.
    workflow.enter(StageID.S3)
    workflow.submit_for_review(
        {n: "replay://%s" % n for n in STAGE_ARTIFACTS[StageID.S3]},
        [evidence(EvidenceKind.TOOL_EVIDENCE, "model:build", REPLAY_TASK_IDS["build"],
                  "历史成样工具证据（回放）")])
    workflow.complete({c: True for c in STAGE_COMPLETION[StageID.S3]},
                      user_confirmed=True)
    notes.append({"stage": "S3", "status": task.stage_status["S3"],
                  "module_plan": workflow.plan_modules(StageID.S3)})

    # S4: M2 target -> M3 parameter version -> M4 evidence -> M5 trust -> M6 error.
    workflow.enter(StageID.S4)
    param = loop.register_parameter("pb_ten", 2.0, "MPa", "胶结抗拉强度")
    loop.define_target(
        param.parameter_id, "peak_strength", 10.0, "MPa", 0.10,
        evidence(EvidenceKind.USER_INPUT, "target:peak:10MPa", description="用户给定目标"))
    loop.design_matrix(param.parameter_id, [
        {"case_id": "C1", "role": "baseline", "value": 2.0},
        {"case_id": "C2", "role": "test", "value": 3.0},
    ])
    initial = loop.add_run(param.parameter_id, "C1", REPLAY_TASK_IDS["build"],
                           "C1.csv", {"peak_strength": 8.6}, "m1")
    loop.diagnose_trust("C1", True, "回放数据完整", ["C1.csv"])
    first_error = loop.compute_error("C1")
    first_eval = loop.evaluate(param.parameter_id)
    adjustment = loop.propose_adjustment(
        param.parameter_id, 3.0, "首轮误差 %.3f 超容差" % first_error["peak_strength"],
        ["error:C1"])
    decisions.confirm(adjustment.decision_id, "用户同意调整胶结强度")
    loop.apply_parameter(param.parameter_id, 3.0, "标定迭代", adjustment.decision_id, "m2")
    loop.add_run(param.parameter_id, "C2", REPLAY_TASK_IDS["load"],
                 "C2.csv", {"peak_strength": 9.5}, "m2")
    loop.diagnose_trust("C2", True, "回放数据完整", ["C2.csv"])
    second_error = loop.compute_error("C2")
    sensitivity = loop.sensitivity(param.parameter_id)
    final_eval = loop.evaluate(param.parameter_id)
    loop.confirm_calibrated(param.parameter_id, "用户确认本轮参数")
    workflow.submit_for_review(
        {n: "replay://%s" % n for n in STAGE_ARTIFACTS[StageID.S4]},
        [evidence(EvidenceKind.COMPUTED_RESULT, "calibration:errors",
                  input_refs=["C1.csv", "C2.csv"])])
    workflow.complete({c: True for c in STAGE_COMPLETION[StageID.S4]}, user_confirmed=True)
    notes.append({"stage": "S4", "status": task.stage_status["S4"],
                  "first_error": first_error, "first_evaluation": first_eval["status"],
                  "second_error": second_error, "final_evaluation": final_eval["status"],
                  "sensitivity_warning": sensitivity["non_uniqueness_warning"],
                  "parameter_status": param.calibration_status.value})

    # S5: execution management with real-tool evidence replay.
    workflow.enter(StageID.S5)
    workflow.submit_for_review(
        {n: "replay://%s" % n for n in STAGE_ARTIFACTS[StageID.S5]},
        [evidence(EvidenceKind.TOOL_EVIDENCE, "run:C2", REPLAY_TASK_IDS["load"],
                  "历史加载工具证据（回放）")])
    workflow.complete({c: True for c in STAGE_COMPLETION[StageID.S5]}, user_confirmed=True)
    notes.append({"stage": "S5", "status": task.stage_status["S5"],
                  "runs": [c.to_dict() for c in loop.cases.values()]})

    # S6: analysis and bounded conclusion.
    workflow.enter(StageID.S6)
    workflow.submit_for_review(
        {n: "replay://%s" % n for n in STAGE_ARTIFACTS[StageID.S6]},
        [evidence(EvidenceKind.COMPUTED_RESULT, "analysis:peak",
                  input_refs=["C1.csv", "C2.csv"])])
    workflow.complete({c: True for c in STAGE_COMPLETION[StageID.S6]}, user_confirmed=True)
    notes.append({"stage": "S6", "status": task.stage_status["S6"]})

    # Evidence-driven rollback: an anomaly reopens S4 and invalidates its decision.
    rollback = workflow.rollback(
        StageID.S4, "历史数据显示加载中围压失控",
        [evidence(EvidenceKind.TOOL_EVIDENCE, "anomaly:confinement",
                  REPLAY_TASK_IDS["anomaly"], "回放异常证据")],
        ["calibration_plan", "research_question"])

    report = {
        "status": "OFFLINE_REPLAY_PASS",
        "research_task_id": task.research_task_id,
        "context_version": task.context_version,
        "current_stage": task.current_stage.value,
        "stage_notes": notes,
        "decisions": decisions.snapshot(),
        "calibration": loop.snapshot(),
        "rollback": rollback.to_dict(),
        "cards": coordinator.snapshot(),
        "counts": {
            "evidence_items": len(task.evidence),
            "decisions": len(task.decisions),
            "authorizations": len(decisions.authorizations),
            "transitions": len(workflow.transitions),
        },
        "acceptance_scope": {
            "protocol_and_offline_logic": "PASS",
            "real_pfc_tool_execution": "NOT_EXECUTED_IN_THIS_SCRIPT",
            "scientific_validation": "NOT_VALIDATED",
            "note": "历史 tool_task_id 仅作回放标识，不能视为本次真实执行证据",
        },
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="PFC Interaction 5.0 offline walkthrough")
    parser.add_argument("--out", required=True, help="absolute path of the JSON report")
    args = parser.parse_args()
    report = run(Path(args.out).resolve())
    print("status=%s stages=%d evidence=%d rollback=%s" % (
        report["status"], len(report["stage_notes"]),
        report["counts"]["evidence_items"], report["rollback"]["kind"]))


if __name__ == "__main__":
    main()
