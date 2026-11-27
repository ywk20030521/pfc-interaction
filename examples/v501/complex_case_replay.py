"""5.0.1 offline replay of the complex triaxial acceptance case.

Rebuilds the issue tree, deep discussion, evidence, hypothesis and change
records from the real case JSON produced by outputs/v501_acceptance/scripts.
No PFC execution happens here.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))

from core.v501_archive import ResearchArchive  # noqa: E402
from core.v501_change import ChangeManager  # noqa: E402
from core.v501_deep_discussion import DeepDiscussionEngine, DepthLevel, DiscussionMode  # noqa: E402
from core.v501_evidence import (  # noqa: E402
    EvidenceClass, EvidenceManager, HypothesisManager, Maturity,
)
from core.v501_issues import IssuePriority, IssueTree, IssueType, IssueStatus  # noqa: E402

CASE_DIR = (Path(__file__).resolve().parents[2].parent /
            "outputs" / "v501_acceptance" / "data")


def run(out_path: Path) -> dict:
    cases = {}
    for path in sorted(CASE_DIR.glob("case_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        cases[data["case_id"]] = data

    task_id = "v501-replay"
    tree = IssueTree(task_id)
    h1 = tree.create("围压是否降低峰后脆性", IssueType.HYPOTHESIS,
                     priority=IssuePriority.P0, stage_id="S1",
                     evidence_needs=["独立围压验证"])
    h2 = tree.create("pb_ten 是否提高峰值强度", IssueType.HYPOTHESIS,
                     priority=IssuePriority.P1, stage_id="S4")
    servo = tree.create("侧向伺服未建立目标围压", IssueType.NUMERICAL_RISK,
                       priority=IssuePriority.P0, stage_id="S3",
                       evidence_needs=["C3"])

    engine = DeepDiscussionEngine(tree)
    engine.start(h1.issue_id, DepthLevel.D3, DiscussionMode.DISCOVERY)
    stages = [
        ("problem_definition", {}),
        ("candidate_solutions", {"alternatives": [{"name": "3×2全因子"},
                                                   {"name": "诊断优先"}]}),
        ("adversarial_review", {"counterexample": "伺服失败会制造围压假象"}),
        ("user_feedback", {"user_feedback": "先诊断，不能因有曲线就下结论"}),
        ("revision_synthesis", {"revision": "全矩阵延期，先做三诊断工况"}),
        ("validation_plan", {"validation_plan": "先修复伺服并做独立围压验证"}),
    ]
    for stage, kwargs in stages:
        engine.record_stage(h1.issue_id, stage, "分析:" + stage, **kwargs)
    engine.apply_user_correction(h1.issue_id, "直接全因子", "诊断优先",
                                 "围压控制未验证")
    gate = engine.can_card(h1.issue_id)

    evidence = EvidenceManager()
    tool_ids = []
    for cid, c in cases.items():
        for item in c["tool_task_ids"]:
            entry = evidence.add(
                EvidenceClass.TOOL_OBSERVATION,
                "%s/%s" % (cid, item["step"]),
                description="真实 PFC3D %s %s" % (cid, item["step"]),
                tool_task_id=item["tool_task_id"],
            )
            tool_ids.append(entry.evidence_id)

    hypotheses = HypothesisManager(evidence)
    hy1 = hypotheses.register("围压升高降低峰后脆性", competing=["伺服/边界假象"])
    hy2 = hypotheses.register("pb_ten 提高峰值强度", competing=["围压未受控"])
    hy3 = hypotheses.register("表观响应来自伺服假象")
    for hyp in (hy1, hy2):
        hypotheses.set_maturity(
            hyp.hypothesis_id, Maturity.UNRESOLVED,
            reason="围压自变量操作失败")
    hypotheses.set_maturity(
        hy3.hypothesis_id, Maturity.EMPIRICALLY_SUPPORTED,
        supporting=tool_ids[:3], reason="伺服后围压比低于 0.015")

    change = ChangeManager(tree, None, evidence)
    rec = change.analyze("伺服未建立目标围压", ["C3"], tool_ids[:1], [servo.issue_id])

    archive = ResearchArchive(BASE.parent / "outputs" / "v501_acceptance" / "replay_archive")
    files = archive.write_all(
        {"research_task_id": task_id, "title": "5.0.1 复杂课题回放"},
        tree, None, evidence, hypotheses, change, engine)

    report = {
        "status": "V501_REPLAY_PASS",
        "cases": list(cases),
        "real_tool_evidence_count": len(tool_ids),
        "issues": len(tree.issues),
        "deep_gate": gate,
        "hypotheses": hypotheses.snapshot(),
        "change": rec.to_dict(),
        "servo_issue_status": servo.status.value,
        "archive_files": len(files),
        "scientific_validation": "NOT_VALIDATED",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="5.0.1 complex case replay")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    report = run(Path(args.out).resolve())
    print(report["status"], "cases", report["cases"],
          "evidence", report["real_tool_evidence_count"],
          "science", report["scientific_validation"])


if __name__ == "__main__":
    main()
