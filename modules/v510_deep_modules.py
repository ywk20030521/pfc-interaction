"""5.1 generic deep-module wrapper for M1-M6.

Every professional module now exposes a depth-checked module_result: it cannot
run before its research issue passes the D0-D3 gate, and it must report
candidates, evidence, confidence, unresolved items and user decisions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional

from core.v501_deep_discussion import DeepDiscussionEngine
from core.v501_issues import IssueTree


MODULE_DEPTH_REQUIREMENTS: Dict[str, List[str]] = {
    "M1": ["research_question", "competing_explanations", "scope"],
    "M2": ["control_strategy", "variable_map", "measurement_plan"],
    "M3": ["model_assumptions", "validation_plan", "data_spec"],
    "M4": ["execution_plan", "version_binding", "checkpoint_plan"],
    "M5": ["phenomenon", "evidence_layers", "cause_hypotheses"],
    "M6": ["metric_definitions", "hypothesis_assessment", "limitations"],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class V510DeepModuleRunner:
    """Runs M1-M6 only after substantive discussion, then returns a deep result."""

    def __init__(self, legacy_bus: Optional[Any] = None) -> None:
        # legacy_bus is the 4.0/5.0 module dispatcher adapter (optional).
        self.legacy_bus = legacy_bus

    def run(self, module_id: str, issue_id: str, payload: Dict[str, Any],
            issues: IssueTree, engine: DeepDiscussionEngine,
            evidence: Optional[Iterable[str]] = None,
            research_task_id: str = "") -> Dict[str, Any]:
        mid = str(module_id).upper()
        if mid not in MODULE_DEPTH_REQUIREMENTS:
            raise ValueError("未知专业模块: %s" % module_id)
        issue = issues.get(issue_id)
        gate = engine.gate(issue_id)
        requirements = MODULE_DEPTH_REQUIREMENTS[mid]
        provided = set(payload.keys())
        missing = [r for r in requirements if r not in provided]
        if not gate["ready"] or missing:
            return {
                "module_id": mid, "module_version": "5.1.0",
                "research_task_id": research_task_id or issues.research_task_id,
                "stage_id": issue.stage_id, "current_issue": issue_id,
                "status": "blocked", "method": "depth_check",
                "candidates": payload.get("candidates", []),
                "key_evidence": list(evidence or []),
                "conclusion": "模块未运行", "confidence": "none",
                "unresolved_items": [f"讨论门槛未完成: {m}" for m in gate["missing"]] +
                                    [f"缺少模块输入: {m}" for m in missing],
                "decisions_required": [], "affected_assets": [],
                "next_recommendation": "补齐实质讨论与模块输入后重跑",
                "input_refs": [], "created_at": _now(),
            }

        legacy_result = None
        if self.legacy_bus is not None:
            legacy_result = self.legacy_bus.run(mid, payload)

        return {
            "module_id": mid, "module_version": "5.1.0",
            "module_task_id": "%s-%s" % (mid, uuid.uuid4().hex[:8]),
            "research_task_id": research_task_id or issues.research_task_id,
            "stage_id": issue.stage_id, "current_issue": issue_id,
            "input_refs": list(payload.get("input_refs", [])),
            "preconditions": [f"D{gate['depth']}: {mid} 深度门槛通过"],
            "status": "completed", "method": payload.get("method", "deep_review"),
            "candidates": list(payload.get("candidates", [])),
            "key_evidence": list(evidence or []),
            "conclusion": payload.get("conclusion", "形成阶段判断"),
            "confidence": payload.get("confidence", "provisional"),
            "unresolved_items": list(payload.get("unresolved_items", [])),
            "decisions_required": list(payload.get("decisions_required", [])),
            "affected_assets": list(payload.get("affected_assets", [])),
            "next_recommendation": payload.get(
                "next_recommendation", "回写科研档案并进入下一议题"),
            "legacy_module_result": (
                legacy_result.to_dict() if hasattr(legacy_result, "to_dict")
                else legacy_result),
            "created_at": _now(),
        }


__all__ = ["MODULE_DEPTH_REQUIREMENTS", "V510DeepModuleRunner"]
