"""M6 Scientific Analysis - second batch module.

IF0 contract fields (report 4.6.4):
  raw_data_manifest, processed_data/, analysis_config, analysis_results,
  comparison_report, analysis_report

IF0 section 4.2 structured fields:
  raw_manifest[], unit_system, metric_definitions[], results[],
  quality_gate (pass/fail + reason), interpretation[] (evidence-linked)

Rules (report 4.6.3, IF0 6.3):
  - distinguish raw data / processed data / analysis results
  - units and calculation definitions must be explicit
  - quality_gate=fail must block conclusions, not just warn
  - interpretation must link to evidence; inference cannot be a confirmed result
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core import (
    DecisionKey,
    DispatchRequest,
    Envelope,
    Evidence,
    EvidenceSource,
    ModuleID,
    ModuleState,
    CoreDispatcher,
)

MODULE_VERSION = "0.1.0"
MODULE_ID = ModuleID.M6


@dataclass
class AnalysisConfig:
    unit_system: str
    metric_definitions: List[Dict[str, Any]] = field(default_factory=list)
    data_source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "unit_system": self.unit_system,
            "metric_definitions": self.metric_definitions,
            "data_source": self.data_source,
        }

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self.unit_system:
            errors.append("unit_system is required")
        for m in self.metric_definitions:
            if not m.get("name") or not m.get("definition"):
                errors.append("each metric needs name and definition")
        return errors


def quality_gate(
    raw_count: int, processed_count: int, definitions: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """C12: data-quality gate that can block conclusions."""
    reasons: List[str] = []
    if raw_count == 0:
        reasons.append("no raw data files")
    if processed_count == 0:
        reasons.append("no processed data")
    if not definitions:
        reasons.append("no metric definitions - calculation口径 undefined")
    incomplete = [m.get("name") for m in definitions if not m.get("definition")]
    if incomplete:
        reasons.append("metrics without definition: %s" % ", ".join(incomplete))
    return {"status": "PASS" if not reasons else "FAIL", "reasons": reasons}


def _load_measurement_plan(request: DispatchRequest, core: CoreDispatcher) -> List[Dict[str, Any]]:
    for ref in request.input_refs:
        if ref.artifact_id.startswith("m2_parameter_schema"):
            design = core.store.get_json(ref)
            return design.get("measurement_plan", [])
    return list((request.payload or {}).get("measurement_plan", []))


def run(module_task_id: str, request: DispatchRequest, core: CoreDispatcher) -> Envelope:
    payload = request.payload or {}
    plan = _load_measurement_plan(request, core)
    definitions = [
        {
            "name": m.get("metric"),
            "definition": m.get("definition", ""),
            "source": m.get("source", "M2.measurement_plan"),
        }
        for m in plan
    ]
    cfg = AnalysisConfig(
        unit_system=str(payload.get("unit_system", "model_units")),
        metric_definitions=definitions,
        data_source=str(payload.get("data_source", "M4.simulation_artifacts")),
    )
    errors = cfg.validate()

    raw_manifest = list(payload.get("raw_manifest", []))
    processed = list(payload.get("processed_data", []))
    results = list(payload.get("results", []))
    gate = quality_gate(len(raw_manifest), len(processed), definitions)

    interpretations: List[Dict[str, Any]] = []
    for item in results:
        interpretations.append(
            {
                "statement": item.get("statement", ""),
                "evidence_ref": item.get("evidence_ref", ""),
                "tool_task_id": item.get("tool_task_id"),
                "confidence": item.get("confidence", "hypothesis"),
            }
        )

    # Validate evidence BEFORE building structured / artifacts so that a
    # malformed PFC evidence claim fails the gate and is reflected in outputs.
    invalid_refs: List[str] = []
    evidence: List[Evidence] = [
        Evidence(EvidenceSource.DERIVED_COMPUTED, "M6.quality_gate", "数据质量检查")
    ]
    for i in interpretations:
        if not i.get("evidence_ref"):
            continue
        ref = str(i["evidence_ref"])
        if ref.startswith("pfc-") and not i.get("tool_task_id"):
            # An execution claim without a real tool id is INVALID, never a
            # downgrade to inference (IF0 6.3 / reporting_policy).
            invalid_refs.append(ref)
            evidence.append(
                Evidence(
                    EvidenceSource.INVALID_EVIDENCE,
                    ref,
                    "PFC evidence without tool_task_id: %s" % i.get("statement", ""),
                )
            )
            i["confidence"] = "hypothesis"
        elif ref.startswith("pfc-"):
            evidence.append(
                Evidence(EvidenceSource.PFC_EXECUTED, ref, i.get("statement", ""),
                         tool_task_id=str(i["tool_task_id"]))
            )
        else:
            evidence.append(
                Evidence(EvidenceSource.AGENT_INFERRED, ref, i.get("statement", ""))
            )
    if invalid_refs:
        gate["status"] = "FAIL"
        gate["reasons"].append(
            "invalid PFC evidence (no tool_task_id): %s" % ", ".join(invalid_refs)
        )

    structured = {
        "raw_manifest": raw_manifest,
        "unit_system": cfg.unit_system,
        "metric_definitions": definitions,
        "results": results,
        "quality_gate": gate,
        "interpretation": interpretations,
    }

    artifacts: List[Dict[str, Any]] = []
    artifacts.append(
        core.store.write_json("m6_raw_data_manifest", "raw_data_manifest.json", raw_manifest).to_dict()
    )
    artifacts.append(
        core.store.write_json("m6_analysis_config", "analysis_config.json", cfg.to_dict()).to_dict()
    )
    artifacts.append(
        core.store.write_json("m6_analysis_results", "analysis_results.json", structured).to_dict()
    )
    artifacts.append(
        core.store.write("m6_comparison_report", "comparison_report.md",
                         "# 工况比较报告\n\n" + (
                             "\n".join("- %s" % i.get("statement") for i in interpretations)
                             or "- 无可比较结果"
                         )).to_dict()
    )
    block_note = (
        "质量闸门未通过，禁止输出确定性科研结论。"
        if gate["status"] == "FAIL"
        else "质量闸门通过，结论仍需关联证据。"
    )
    artifacts.append(
        core.store.write("m6_analysis_report", "analysis_report.md",
                         "# 科研分析报告\n\n%s\n" % block_note).to_dict()
    )

    if gate["status"] == "FAIL":
        core.request_decision(
            key=DecisionKey(
                experiment_id=request.research_task_id,
                stage_id="M6",
                topic="数据质量不足如何处理",
                context_version=request.context_version,
            ),
            question="数据质量闸门未通过：%s。如何继续？" % "; ".join(gate["reasons"]),
            options=["补充数据后重跑", "降低结论强度为待验证", "仅记录不解释"],
            blocks_module_task_id=module_task_id,
            evidence_refs=["m6_quality_gate"],
            authorization_scope=None,
        )

    state = ModuleState.BLOCKED.value if gate["status"] == "FAIL" else ModuleState.COMPLETED.value

    limitations = errors + gate["reasons"]
    if gate["status"] == "PASS":
        limitations.append("指标计算口径需独立复核，禁止机械套用模板")

    return Envelope(
        module_id=MODULE_ID,
        module_version=MODULE_VERSION,
        research_task_id=request.research_task_id,
        module_task_id=module_task_id,
        parent_task_id=request.parent_task_id,
        input_refs=request.input_refs,
        status={"module_state": state},
        output={"structured": structured, "artifacts": artifacts, "verified_by_execution": False},
        evidence=evidence,
        decisions=[],
        limitations=limitations,
    )
