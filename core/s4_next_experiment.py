"""S4 Next-Best Experiment / Simulation engine (S4_SPEC V2.0 chapter 8).

Advanced core capability: decide the single most worthwhile next trial by
information gain, computational cost, parameter uncertainty and scientific
value. When compensation is detected, recommend an independent observation
instead of continuing blind parameter search.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

ACTIONS = (
    "single_perturbation",
    "joint_perturbation",
    "new_observation",
    "new_condition",
    "pause_and_negotiate",
    "stop_and_freeze",
)


class NextExperimentEngine:
    def __init__(self, project) -> None:
        self.project = project
        self.history: List[Dict[str, Any]] = []

    def evaluate(
        self,
        candidates: List[Dict[str, Any]],
        compensation_detected: bool = False,
        equivalent_solutions: bool = False,
    ) -> Dict[str, Any]:
        if not candidates:
            raise ValueError("下一步试算决策必须提供候选动作")
        scored = []
        for cand in candidates:
            action = cand.get("action")
            if action not in ACTIONS:
                raise ValueError("未知候选动作: %s" % action)
            info_gain = float(cand.get("information_gain", 0.0))
            cost = float(cand.get("cost", 1.0))
            if cost <= 0:
                raise ValueError("计算成本必须为正")
            uncertainty = float(cand.get("parameter_uncertainty", 0.0))
            science = float(cand.get("scientific_value", 0.0))
            score = (2.0 * info_gain + science) / cost + 0.5 * uncertainty
            scored.append({
                "action": action, "information_gain": info_gain, "cost": cost,
                "parameter_uncertainty": uncertainty, "scientific_value": science,
                "score": round(score, 4), "rationale": cand.get("rationale", ""),
            })

        # Hard override: compensation / equivalent solutions forbid continued
        # blind parameter search; an independent observation must be chosen.
        search_actions = {"single_perturbation", "joint_perturbation"}
        forced = compensation_detected or equivalent_solutions
        if forced:
            for item in scored:
                if item["action"] in search_actions:
                    item["score"] = -1.0
                    item["excluded_reason"] = (
                        "检测到参数补偿或等效解，继续参数搜索无法区分机制；"
                        "应增加独立观测或试验工况")

        scored.sort(key=lambda x: x["score"], reverse=True)
        chosen = scored[0]
        rejected = [
            {"action": s["action"], "score": s["score"],
             "reason": s.get("excluded_reason", "综合评分低于首选动作")}
            for s in scored[1:]
        ]
        result = {
            "chosen": chosen,
            "rejected": rejected,
            "forced_by_compensation": forced,
            "pause_parameter_search": chosen["action"] in ("new_observation", "new_condition",
                                                            "pause_and_negotiate"),
            "requires_user_authorization": chosen["action"] not in ("pause_and_negotiate",
                                                                      "stop_and_freeze"),
            "note": "代理模型预测不得替代真实 PFC 验证；候选仍需真实运行确认",
        }
        self.history.append(result)
        self.project.record("next_experiment", chosen["action"])
        return result

    def last(self) -> Optional[Dict[str, Any]]:
        return self.history[-1] if self.history else None


__all__ = ["ACTIONS", "NextExperimentEngine"]
