"""M5 Scientific Diagnosis - second batch module.

IF0 contract fields (report 4.5.5):
  diagnosis_report, diagnostic_evidence, anomaly_records,
  correction_proposals, revalidation_plan

IF0 section 4.2 structured fields:
  diagnosis_layer (model/numerical/physical/data/result),
  confidence (confirmed/possible/hypothesis), findings[],
  correction_proposals[], requires_user_confirmation,
  suggests_recompute, target_module

Rules (report 4.5.4, IF0 6.3):
  - diagnosis must be layered; never rely on a single threshold
  - distinguish confirmed / possible / hypothesis
  - inference alone cannot be a confirmed finding
  - model/physics changes require user confirmation via Core
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
MODULE_ID = ModuleID.M5

VALID_LAYERS = ("model", "numerical", "physical", "data", "result")
VALID_CONFIDENCE = ("confirmed", "possible", "hypothesis")


@dataclass
class Finding:
    layer: str
    description: str
    basis: str
    evidence_refs: List[str]
    confidence: str
    possible_causes: List[str] = field(default_factory=list)
    correction: Optional[str] = None
    target_module: Optional[str] = None
    needs_user_confirmation: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer": self.layer,
            "description": self.description,
            "basis": self.basis,
            "evidence_refs": self.evidence_refs,
            "confidence": self.confidence,
            "possible_causes": self.possible_causes,
            "correction": self.correction,
            "target_module": self.target_module,
            "needs_user_confirmation": self.needs_user_confirmation,
        }

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.layer not in VALID_LAYERS:
            errors.append("invalid diagnosis layer: %s" % self.layer)
        if self.confidence not in VALID_CONFIDENCE:
            errors.append("invalid confidence: %s" % self.confidence)
        if not self.evidence_refs:
            errors.append("finding requires evidence_refs")
        if self.confidence == "confirmed" and all(
            ref.startswith("agent_") for ref in self.evidence_refs
        ):
            errors.append("inference-only evidence cannot be confirmed")
        return errors


def _load_simulation(request: DispatchRequest, core: CoreDispatcher) -> Dict[str, Any]:
    for ref in request.input_refs:
        if ref.artifact_id.startswith("m4_simulation_status"):
            return core.store.get_json(ref)
    return (request.payload or {}).get("simulation", {})


def run(module_task_id: str, request: DispatchRequest, core: CoreDispatcher) -> Envelope:
    payload = request.payload or {}
    sim = _load_simulation(request, core)
    findings_data = list(payload.get("findings", []))
    findings: List[Finding] = [Finding(**f) for f in findings_data]
    errors: List[str] = []
    for f in findings:
        errors.extend(f.validate())

    # Auto-derive a finding from a real tool status if present.
    task_state = sim.get("task_state", "CREATED")
    if task_state in ("FAILED", "CANCELLED"):
        findings.append(
            Finding(
                layer="numerical",
                description="仿真任务状态为 %s" % task_state,
                basis="M4 simulation_status.json 的 task_state（来自工具结果）",
                evidence_refs=[sim.get("tool_task_id", "m4_status")],
                confidence="confirmed",
                possible_causes=["数值发散", "模型设置问题", "人为中断"],
                correction="检查 timestep、接触数与边界设置后再决定恢复或重跑",
                target_module="M3",
                needs_user_confirmation=True,
            )
        )

    correction_proposals = [f.correction for f in findings if f.correction]
    target_modules = sorted({f.target_module for f in findings if f.target_module})
    requires_user = any(f.needs_user_confirmation for f in findings)
    suggests_recompute = any(f.confidence == "confirmed" for f in findings)

    structured = {
        "findings": [f.to_dict() for f in findings],
        "correction_proposals": correction_proposals,
        "requires_user_confirmation": requires_user,
        "suggests_recompute": suggests_recompute,
        "target_module": target_modules[0] if target_modules else None,
        "diagnosis_layer": findings[0].layer if findings else "result",
        "confidence": findings[0].confidence if findings else "hypothesis",
    }

    artifacts: List[Dict[str, Any]] = []
    artifacts.append(
        core.store.write_json("m5_diagnostic_evidence", "diagnostic_evidence.json", structured).to_dict()
    )
    artifacts.append(
        core.store.write_json("m5_anomaly_records", "anomaly_records.json", [
            f.to_dict() for f in findings
        ]).to_dict()
    )
    report_md = "# 诊断报告\n\n" + "\n".join(
        "- [%s/%s] %s — 依据：%s" % (f.layer, f.confidence, f.description, f.basis)
        for f in findings
    ) + "\n\n> 推断不得写成确定事实；涉及模型假设改变须用户确认。\n"
    artifacts.append(core.store.write("m5_diagnosis_report", "diagnosis_report.md", report_md).to_dict())
    artifacts.append(
        core.store.write("m5_correction_proposals", "correction_proposals.md",
                         "\n".join("- %s" % c for c in correction_proposals) or "- 无").to_dict()
    )
    artifacts.append(
        core.store.write("m5_revalidation_plan", "revalidation_plan.md",
                         "# 重新验证计划\n\n修正后须重新走 M3→M4→M5，不得只替换文件。\n").to_dict()
    )

    if requires_user and target_modules:
        core.request_decision(
            key=DecisionKey(
                experiment_id=request.research_task_id,
                stage_id="M5",
                topic="确认诊断修正方案",
                context_version=request.context_version,
            ),
            question="诊断发现需要修正，是否授权回退到 %s？" % target_modules[0],
            options=["授权修正并重跑", "仅记录不修改", "需要更多证据"],
            blocks_module_task_id=module_task_id,
            evidence_refs=[sim.get("tool_task_id", "m4_status")],
            authorization_scope=None,
        )

    evidence = []
    if task_state in ("FAILED", "CANCELLED"):
        evidence.append(
            Evidence(EvidenceSource.PFC_EXECUTED, sim.get("tool_task_id", "m4_status"),
                     "M4 工具状态", tool_task_id=sim.get("tool_task_id"))
        )
    else:
        evidence.append(
            Evidence(EvidenceSource.DERIVED_COMPUTED, "M4.simulation_status", "诊断输入")
        )

    return Envelope(
        module_id=MODULE_ID,
        module_version=MODULE_VERSION,
        research_task_id=request.research_task_id,
        module_task_id=module_task_id,
        parent_task_id=request.parent_task_id,
        input_refs=request.input_refs,
        status={"module_state": ModuleState.COMPLETED.value},
        output={"structured": structured, "artifacts": artifacts, "verified_by_execution": False},
        evidence=evidence,
        decisions=[],
        limitations=errors + ["诊断结论不自动改变模型；须经用户确认后由 Core 组织回退"],
    )
