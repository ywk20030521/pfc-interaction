"""5.0 real-bridge calibration loop (protocol validation, NOT physics).

Runs a tiny PFC2D script through the Core-bound V50ExecutionGateway, feeds the
real tool_task_id into the S4 calibration loop, and verifies target/error/
acceptance/user-confirmation with genuine tool evidence.

    python examples/v50/real_bridge_execution.py --out <report.json>

The calibration target is a ball count, used only to validate the protocol and
tool chain. It is NOT a mechanical parameter calibration.
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

from adapters.itasca_mcp import BridgeUnavailable, ItascaMcpAdapter  # noqa: E402
from core.v50_context import EvidenceItem, EvidenceKind, ResearchTask  # noqa: E402
from core.v50_decisions import DecisionManager  # noqa: E402
from modules.v50_calibration import ParameterCalibrationLoop  # noqa: E402
from modules.v50_execution import V50ExecutionGateway, parse_metric  # noqa: E402

def detect_dimension(adapter: ItascaMcpAdapter) -> str:
    """Ask the live engine which domain form it accepts (2D or 3D)."""
    result = adapter.execute_code(
        "import itasca\n"
        "itasca.command('model new')\n"
        "itasca.command('model domain extent -2 2 -2 2 -2 2')\n"
        "print('DIM3D_OK')\n"
    )
    output = str(result.output_artifacts[0].get("output", "")) if result.output_artifacts else ""
    return "3D" if "DIM3D_OK" in output else "2D"


def pfc_script(dimension: str) -> str:
    extent = "-2 2 -2 2 -2 2" if dimension == "3D" else "-2 2 -2 2"
    position = "(%f,0,0)" if dimension == "3D" else "(%f,0)"
    return (
        "import itasca\n"
        "itasca.command('model new')\n"
        "itasca.command('model domain extent %s')\n" % extent +
        "for i in range(1,11):\n"
        "    itasca.command('ball create id=%%d position=%s radius=0.05' %% (i, i*0.1))\n" % position +
        "print('BALL_COUNT=%d' % itasca.ball.count())\n"
    )


def run(out_path: Path) -> Dict[str, Any]:
    adapter = ItascaMcpAdapter()
    try:
        health = adapter.health()
    except BridgeUnavailable as exc:
        report = {"status": "BRIDGE_OFFLINE", "reason": str(exc),
                  "real_tool_execution": False, "scientific_validation": False}
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    dimension = detect_dimension(adapter)
    task = ResearchTask("v50-real", "5.0 真实桥接协议验收")
    decisions = DecisionManager(task)
    loop = ParameterCalibrationLoop(task, decisions)
    gateway = V50ExecutionGateway(task, decisions, adapter)

    param = loop.register_parameter("ball_seed_count", 10, "个", "协议测试用颗粒数",
                                    source_type="user_provided", rationale="仅验证工具链")
    loop.define_target(
        param.parameter_id, "ball_count", 10.0, "个", 0.05,
        EvidenceItem(EvidenceKind.USER_INPUT, "target:ball_count:10", description="协议目标"),
        description="协议验收目标，不是物理标定目标")
    loop.design_matrix(param.parameter_id, [
        {"case_id": "REAL-C1", "role": "baseline", "value": 10},
        {"case_id": "REAL-C2", "role": "test", "value": 10},
    ])

    decision = decisions.propose("启动协议验证", "执行 PFC%s 颗粒计数脚本" % dimension,
                                 "验证 5.0 网关与真实工具证据链",
                                 affected_assets=["model_v1"])
    decisions.confirm(decision.decision_id, "用户确认执行协议验证")
    auth = decisions.authorize(decision.decision_id, "start_formal_simulation",
                               "model_v1", "run_model", "model_v1", "p1", "mx1")
    executed = gateway.execute_code(
        pfc_script(dimension), auth.authorization_id, "start_formal_simulation", "model_v1",
        "model_v1", "p1", "mx1", description="V50 真实 bridge 标定证据")
    if executed["status"] != "EXECUTED":
        report = {"status": "GATEWAY_BLOCKED", "gateway": executed,
                  "real_tool_execution": False, "scientific_validation": False}
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    measured = parse_metric(executed["output"], "BALL_COUNT")
    if measured is None:
        raise ValueError("真实输出中未找到 BALL_COUNT 指标")
    case = loop.add_run(param.parameter_id, "REAL-C1", executed["tool_task_id"],
                        executed["evidence_ref"], {"ball_count": measured}, "model_v1")
    loop.diagnose_trust("REAL-C1", True, "真实 bridge 执行且输出含目标指标",
                        [executed["evidence_ref"]])
    errors = loop.compute_error("REAL-C1")
    evaluation = loop.evaluate(param.parameter_id)
    if not evaluation["acceptance_met"]:
        raise AssertionError("协议验收未达标: %s" % evaluation["reasons"])
    loop.confirm_calibrated(param.parameter_id, "用户确认协议验收结果")

    report = {
        "status": "REAL_BRIDGE_PASS",
        "bridge": health, "dimension": dimension,
        "gateway": {k: executed[k] for k in
                    ("status", "tool_task_id", "task_state", "evidence_ref", "execution_verified")},
        "calibration": {
            "parameter_id": param.parameter_id,
            "parameter_status": param.calibration_status.value,
            "tool_task_id": case.tool_task_id,
            "measured": measured, "errors": errors,
            "evaluation": evaluation,
        },
        "counts": {"evidence_items": len(task.evidence),
                   "decisions": len(task.decisions),
                   "authorizations": len(decisions.authorizations)},
        "acceptance_scope": {
            "real_pfc_tool_execution": "PASS",
            "protocol_and_evidence_chain": "PASS",
            "scientific_calibration": "NOT_VALIDATED",
            "note": "ball_count 仅用于验证协议与真实工具链，不构成物理参数标定",
        },
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="PFC Interaction 5.0 real bridge validation")
    parser.add_argument("--out", required=True, help="absolute path of the JSON report")
    args = parser.parse_args()
    report = run(Path(args.out).resolve())
    print("status=%s tool_task_id=%s" % (
        report["status"], report.get("gateway", {}).get("tool_task_id")))


if __name__ == "__main__":
    main()
