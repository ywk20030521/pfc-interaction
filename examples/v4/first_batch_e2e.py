"""First batch end-to-end case: research question -> plan -> design -> model.

This script drives M1 -> M2 -> M3 through CoreDispatcher using real IF0 contracts.
It does NOT claim PFC execution: the generated model must be executed through
Core I5 (see separate PFC execution step in the acceptance report).
"""

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "modules"))

from core import ArtifactStore, CoreDispatcher, DispatchRequest, ModuleID  # noqa: E402
from m1_planning import run as m1_run  # noqa: E402
from m2_design import run as m2_run  # noqa: E402
from m3_modeling import run as m3_run  # noqa: E402


def main():
    core = CoreDispatcher(ArtifactStore(os.path.join(BASE, "work", "first_batch")))
    for mid, runner in (
        (ModuleID.M1, m1_run),
        (ModuleID.M2, m2_run),
        (ModuleID.M3, m3_run),
    ):
        core.register_module(mid, runner)

    research = {
        "research_objective": "研究颗粒半径对单轴压缩峰值强度的影响",
        "research_scope": "PFC2D 圆盘试样，线性接触模型",
        "hypotheses": ["颗粒半径增大导致峰值强度降低"],
        "independent_vars": ["颗粒半径"],
        "dependent_vars": ["峰值强度", "弹性模量"],
        "control_vars": ["颗粒密度"],
        "constraints": ["PFC2D Console 可用", "计算时间可控"],
        "expected_outputs": ["应力-应变曲线", "峰值强度对比"],
        "fact_vs_suggestion": [
            {"claim": "研究对象为颗粒集合体单轴压缩", "origin": "user_provided"},
            {
                "claim": "采用 linear 接触模型",
                "origin": "agent_inferred",
                "evidence_ref": "PFC 常规做法/已实测可用",
            },
        ],
    }
    design = {
        "experiment_type": "单轴压缩",
        "parameter_schema": [
            {
                "name": "颗粒半径",
                "unit": "mm",
                "values": [0.25, 0.35],
                "default": 0.30,
                "source": "M1.independent_vars",
                "confirmed": True,
                "role": "independent",
            }
        ],
        "control_groups": [
            {"name": "基准组", "values": {"颗粒半径": 0.30}, "description": "中等粒径对照"}
        ],
        "measurement_plan": [
            {"metric": m, "definition": "压板接触力/截面积; 位移/初始高度", "source": "M2 建议"}
            for m in ["轴向应力", "轴向应变", "峰值强度", "弹性模量"]
        ],
    }

    e1, err1 = core.dispatch(
        DispatchRequest(
            "R-first-batch",
            ModuleID.M1,
            context_version="cv1",
            payload={"research_requirements": research},
        )
    )
    print("[M1] state=%s errors=%s" % (e1.status["module_state"], err1))

    m1_json = [a for a in e1.output["artifacts"] if a["artifact_id"] == "m1_research_requirements"][0]
    from core import ArtifactRef

    e2, err2 = core.dispatch(
        DispatchRequest(
            "R-first-batch",
            ModuleID.M2,
            input_refs=[ArtifactRef.from_dict(m1_json)],
            context_version="cv1",
            payload={"experiment_design": design},
        )
    )
    print("[M2] state=%s errors=%s cases=%d" % (
        e2.status["module_state"], err2, len(e2.output["structured"]["cases"])
    ))

    m2_json = [a for a in e2.output["artifacts"] if a["artifact_id"] == "m2_parameter_schema"][0]
    e3, err3 = core.dispatch(
        DispatchRequest(
            "R-first-batch",
            ModuleID.M3,
            input_refs=[ArtifactRef.from_dict(m2_json)],
            context_version="cv1",
            payload={"model_config": {"dimension": "2D"}, "case": e2.output["structured"]["cases"][0]},
        )
    )
    print("[M3] state=%s errors=%s" % (e3.status["module_state"], err3))
    print("[M3] case=%s dimension=%s" % (
        e3.output["structured"]["case_id"], e3.output["structured"]["dimension"]
    ))
    print("[M3] validation=%s" % {
        k: v["status"] for k, v in e3.output["structured"]["validation"].items()
        if isinstance(v, dict)
    })
    print("[M3] verified_by_execution=%s" % e3.output["verified_by_execution"])
    print("[M3] limitations=%s" % e3.limitations)

    script_ref = [a for a in e3.output["artifacts"] if a["artifact_id"] == "m3_model"][0]
    script = core.store.get(ArtifactRef.from_dict(script_ref))
    script_path = os.path.join(BASE, "work", "first_batch_generated.dat")
    with open(script_path, "w", encoding="utf-8") as fh:
        fh.write(script)
    print("[OUTPUT] script=%s" % script_path)

    print("[DECISIONS] %d" % len(core.decision_items()))
    for item in core.decision_items():
        print("  - %s state=%s topic=%s" % (
            item["decision_id"], item["delivery_status"], item["key"]["topic"]
        ))


if __name__ == "__main__":
    main()
