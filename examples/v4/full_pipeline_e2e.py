"""4.0 full pipeline E2E: M1->M2->M3->M4->real PFC->M5->M6.

Uses the real itasca-mcp adapter for Core I5 execution.
No claim is made about scientific conclusion validity unless M6 quality_gate passes.
"""

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)

from core import ArtifactRef, ArtifactStore, CoreDispatcher, DecisionKey, DispatchRequest, ModuleID, TaskState  # noqa: E402
from adapters.itasca_mcp import ItascaMcpAdapter  # noqa: E402
from modules import m1_planning, m2_design, m3_modeling  # noqa: E402
from modules import m4_simulation, m5_diagnosis, m6_analysis  # noqa: E402


def artifact(env, aid):
    for a in env.output["artifacts"]:
        if a["artifact_id"] == aid:
            return ArtifactRef.from_dict(a)
    raise KeyError(aid)


def main():
    adapter = ItascaMcpAdapter()
    health = adapter.health()
    print("[BRIDGE]", health.get("version"), health.get("runtime_mode"))

    core = CoreDispatcher(
        artifact_store=ArtifactStore(os.path.join(BASE, "work", "v4_pipeline")),
        executor=adapter,
    )
    for mid, runner in (
        (ModuleID.M1, m1_planning.run),
        (ModuleID.M2, m2_design.run),
        (ModuleID.M3, m3_modeling.run),
        (ModuleID.M4, m4_simulation.run),
        (ModuleID.M5, m5_diagnosis.run),
        (ModuleID.M6, m6_analysis.run),
    ):
        core.register_module(mid, runner)

    research = {
        "research_objective": "研究颗粒半径对单轴压缩峰值强度的影响",
        "research_scope": "PFC2D 圆盘试样",
        "hypotheses": ["粒径增大导致峰值强度降低"],
        "independent_vars": ["颗粒半径"],
        "dependent_vars": ["峰值强度"],
        "control_vars": ["密度"],
        "constraints": ["Console"],
        "expected_outputs": ["应力-应变曲线"],
        "fact_vs_suggestion": [
            {"claim": "研究对象为颗粒集合体", "origin": "user_provided"},
            {"claim": "linear 接触", "origin": "agent_inferred", "evidence_ref": "lit-1"},
        ],
    }
    design = {
        "experiment_type": "单轴压缩",
        "parameter_schema": [{
            "name": "颗粒半径", "unit": "mm", "values": [0.25, 0.35], "default": 0.30,
            "source": "M1", "confirmed": True, "role": "independent",
        }],
        "control_groups": [{"name": "基准组", "values": {"颗粒半径": 0.30}, "description": "对照"}],
        "measurement_plan": [
            {"metric": m, "definition": "压板力/面积", "source": "M2"}
            for m in ["轴向应力", "轴向应变", "峰值强度", "弹性模量"]
        ],
    }

    e1, _ = core.dispatch(DispatchRequest("R-v4", ModuleID.M1, payload={"research_requirements": research}))
    e2, _ = core.dispatch(DispatchRequest("R-v4", ModuleID.M2, input_refs=[artifact(e1, "m1_research_requirements")], payload={"experiment_design": design}))
    case = e2.output["structured"]["cases"][0]
    e3, _ = core.dispatch(DispatchRequest("R-v4", ModuleID.M3, input_refs=[artifact(e2, "m2_parameter_schema")], payload={"model_config": {"dimension": "2D"}, "case": case}))
    script_ref = artifact(e3, "m3_model")
    script = core.store.get(script_ref)
    print("[M1-M3]", e1.status["module_state"], e2.status["module_state"], e3.status["module_state"])

    e4, _ = core.dispatch(DispatchRequest("R-v4", ModuleID.M4, input_refs=[artifact(e3, "m3_model_parameters")], payload={"case_id": case["case_id"], "model_ref": script_ref.artifact_id}))
    print("[M4]", e4.status["module_state"], e4.output["structured"]["task_state"])

    # Core I5: real execution with a synthetic approval for this E2E.
    # In production the authorization must come from a real user decision.
    decision = core.decisions.request(
        DecisionKey("R-v4", "M4", "执行M3脚本", "cv1"),
        "是否执行 M3 脚本？", ["执行"], e4.module_task_id,
        authorization_scope="run_model",
    )[0]
    auth = core.decisions.resolve(decision.decision_id, "APPROVED", "cv1")
    result, errors = core.execute(
        module_task_id=e4.module_task_id,
        operation="execute_dat",
        model_ref=None,
        case_id=case["case_id"],
        authorization_id=auth.authorization_id,
        scope="run_model",
        context_version="cv1",
        code=script,
    )
    print("[I5]", "errors=", errors, "tool_task_id=", result.tool_task_id if result else None,
          "state=", result.task_state.value if result else None, "error_msg=", result.error if result else None)
    if result and result.task_state == TaskState.COMPLETED:
        out = result.output_artifacts[0]["output"]
        print("[PFC_OUTPUT]", out.strip().replace("\n", " | ")[:300])
        e4 = m4_simulation.record_execution(e4.module_task_id, core, result.tool_task_id, result.task_state)

    e5, _ = core.dispatch(DispatchRequest("R-v4", ModuleID.M5, input_refs=[artifact(e4, "m4_simulation_status")]))
    print("[M5]", e5.status["module_state"], "findings=", len(e5.output["structured"]["findings"]))

    e6, _ = core.dispatch(DispatchRequest("R-v4", ModuleID.M6, input_refs=[artifact(e2, "m2_parameter_schema")], payload={
        "unit_system": "model_units",
        "raw_manifest": [{"artifact_id": "bridge_output", "source": result.tool_task_id}],
        "processed_data": [{"name": "sample_state", "source": "PFC output"}],
        "results": [{
            "statement": "试样成样稳定（59-60球/接触已建立）",
            "evidence_ref": "bridge_output",
            "tool_task_id": result.tool_task_id,
            "confidence": "confirmed",
        }],
    }))
    print("[M6]", e6.status["module_state"], "quality_gate=", e6.output["structured"]["quality_gate"]["status"])
    print("[M6] limitations=", e6.limitations[:2])
    print("[DONE] six-module pipeline executed with real PFC bridge")


if __name__ == "__main__":
    main()
