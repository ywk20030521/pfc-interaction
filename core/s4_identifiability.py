"""S4 identifiability and coupling analysis (S4_SPEC V2.0 chapters 4, 6).

Implements the five identifiability questions, equivalent-solution detection,
the four coupling questions, and the hard rule: an unidentifiable parameter
must NOT be hidden by larger automatic optimisation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.s4_contracts import CalibrationProject, ParameterGroup, RelationStatus, _uid


class IdentifiabilityEngine:
    def __init__(self, project: CalibrationProject) -> None:
        self.project = project

    def assess(self, parameter_id: str, target_ids: List[str],
               sensitivities: Dict[str, Dict[str, float]],
               pairwise_correlations: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """sensitivities: {target_id: {param_id: S_ij}}."""
        if parameter_id not in self.project.parameters:
            raise KeyError("参数不存在: %s" % parameter_id)
        missing = [t for t in target_ids if not any(
            r.target_id == t and r.parameter_id == parameter_id
            and r.status != RelationStatus.NEGATED
            for r in self.project.relations.values())]
        questions = {
            "has_effect": self._has_effect(parameter_id, target_ids, sensitivities),
            "effect_significant": self._significant(parameter_id, target_ids, sensitivities),
            "effects_distinguishable": self._distinguishable(
                parameter_id, target_ids, sensitivities, pairwise_correlations or {}),
            "data_can_constrain": bool(target_ids) and not missing,
            "need_more_observations": bool(missing),
        }
        identifiable = (questions["has_effect"] and questions["effect_significant"]
                        and questions["effects_distinguishable"]
                        and questions["data_can_constrain"])
        verdict = "identifiable" if identifiable else "NOT_IDENTIFIABLE"
        result = {
            "parameter_id": parameter_id, "questions": questions,
            "verdict": verdict, "missing_observation_targets": missing,
            "equivalent_solution_risk": not questions["effects_distinguishable"],
            "action": ("proceed_to_calibration" if identifiable
                       else "add_observations_or_condition; DO_NOT_expand_blind_search"),
            "note": "不可辨识不得通过更大规模自动优化掩盖；应增加区分力强的指标/工况",
        }
        self.project.record("assess_identifiability", "%s:%s" % (parameter_id, verdict))
        return result

    def coupling_check(self, group: ParameterGroup) -> Dict[str, Any]:
        """Four coupling questions for each parameter pair in a group."""
        if len(group.parameter_ids) < 2:
            raise ValueError("耦合分析至少需要两个参数")
        for pid in group.parameter_ids:
            if pid not in self.project.parameters:
                raise KeyError("参数组引用了不存在的参数: %s" % pid)
        pairs = []
        for i, a in enumerate(group.parameter_ids):
            for b in group.parameter_ids[i + 1:]:
                shared = sorted({r.target_id for r in self.project.relations.values()
                                 if r.parameter_id == a} &
                                {r.target_id for r in self.project.relations.values()
                                 if r.parameter_id == b})
                pairs.append({
                    "parameters": [a, b],
                    "shared_targets": shared,
                    "q1_same_macro_target": bool(shared),
                    "q2_same_direction": group.coupling_questions.get(
                        "%s|%s|direction" % (a, b), None),
                    "q3_compensation": group.coupling_questions.get(
                        "%s|%s|compensation" % (a, b), None),
                    "q4_distinguishable_by_condition": group.coupling_questions.get(
                        "%s|%s|distinguishable" % (a, b), None),
                })
        result = {"group_id": group.group_id, "pairs": pairs,
                  "note": "四问任一为是/未定时必须登记补偿或不可辨识风险"}
        self.project.record("coupling_check", group.group_id)
        return result

    def equivalent_solutions(self, target_id: str,
                             candidate_sets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect distinct parameter sets with near-identical macro response."""
        if len(candidate_sets) < 2:
            raise ValueError("等效解检测至少需要两组候选参数")
        tol = 0.02
        clusters: List[List[int]] = []
        for idx, cand in enumerate(candidate_sets):
            value = float(cand.get("response", cand.get(target_id, 0.0)))
            placed = False
            for cluster in clusters:
                ref = float(candidate_sets[cluster[0]].get(
                    "response", candidate_sets[cluster[0]].get(target_id, 0.0)))
                if ref and abs(value - ref) / abs(ref) <= tol:
                    cluster.append(idx)
                    placed = True
                    break
            if not placed:
                clusters.append([idx])
        ambiguous = [c for c in clusters if len(c) > 1]
        return {
            "target_id": target_id,
            "has_equivalent_solutions": bool(ambiguous),
            "ambiguous_clusters": ambiguous,
            "conclusion": ("多组近似解，参数不可唯一识别；应增加独立观测"
                           if ambiguous else "当前候选未发现等效解"),
        }

    def _has_effect(self, pid: str, targets: List[str],
                    sensitivities: Dict[str, Dict[str, float]]) -> bool:
        return any(abs(sensitivities.get(t, {}).get(pid, 0.0)) > 0 for t in targets)

    def _significant(self, pid: str, targets: List[str],
                     sensitivities: Dict[str, Dict[str, float]]) -> bool:
        return any(abs(sensitivities.get(t, {}).get(pid, 0.0)) >= 0.05 for t in targets)

    def _distinguishable(self, pid: str, targets: List[str],
                         sensitivities: Dict[str, Dict[str, float]],
                         corr: Dict[str, float]) -> bool:
        if any(abs(v) >= 0.9 for v in corr.values()):
            return False
        # Column comparison needs at least two targets; with a single target
        # cosine similarity is trivially 1 and would falsely flag all params.
        if len(targets) < 2:
            return True
        param_ids = list(sensitivities.get(targets[0], {}))
        cols = [[sensitivities.get(t, {}).get(p, 0.0) for t in targets]
                for p in param_ids]
        # Near-identical sensitivity columns across parameters -> not distinguishable.
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                a, b = cols[i], cols[j]
                if a and b:
                    num = sum(x * y for x, y in zip(a, b))
                    den = (sum(x * x for x in a) ** 0.5) * (sum(y * y for y in b) ** 0.5)
                    if den and num / den >= 0.98:
                        return False
        return True


__all__ = ["IdentifiabilityEngine"]
