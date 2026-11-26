"""4.0 full implementation: M5 Diagnosis + M6 Analysis (report 4.5/4.6).

M5: five-layer diagnosis (model/numerical/physical/data/result), 10 functions,
5 standard outputs. Auto-reads real evidence; distinguishes confirmed /
possible / hypothesis; inference alone cannot be confirmed.

M6: 13 functions across data identification, reading, unit check, stress-strain,
mechanical parameters, crack statistics, particle motion, contact network,
multi-case comparison, sensitivity, statistics, quality gate, interpretation.
Emits 6 standard outputs including processed_data/. Computes from real CSV;
never accepts predigested results as evidence.
"""

from __future__ import annotations

import csv
import io
import json
import statistics
from typing import Any, Dict, List, Optional

from core import (
    DispatchRequest, Envelope, Evidence, EvidenceSource, ModuleID,
    ModuleState, CoreDispatcher,
)
from modules.v41_analysis import (
    _read_json_artifacts, _read_csv_artifacts, _fmt_tool_ids, _analyze_rows,
)

MODULE_VERSION = "4.0.0"
LAYERS = ("model", "numerical", "physical", "data", "result")
CONFIDENCE = ("confirmed", "possible", "hypothesis")


# ---------- M5: five-layer diagnosis --------------------------------------

def diagnose_model(stage_states: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """M5.1 模型设置诊断."""
    out = []
    for s in stage_states or []:
        if s.get("status") == "FAIL":
            out.append({"layer": "model", "confidence": "confirmed",
                        "description": "阶段 %s 检查失败" % s.get("stage"),
                        "basis": "; ".join(s.get("findings", [])),
                        "evidence_refs": ["m3_staged_model"],
                        "target_module": "M3", "needs_user_confirmation": True})
    return out


def diagnose_initial(stage_states: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """M5.2 初始状态诊断."""
    out = []
    for s in stage_states or []:
        if s.get("stage") == "sample_preparation" and s.get("status") == "FAIL":
            out.append({"layer": "model", "confidence": "confirmed",
                        "description": "成样阶段初始状态异常",
                        "basis": "; ".join(s.get("findings", [])),
                        "evidence_refs": ["m3_staged_model"],
                        "target_module": "M3", "needs_user_confirmation": True})
    return out


def diagnose_numerical(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """M5.3 数值稳定性诊断."""
    out = []
    ts = [r.get("timestep_s") for r in rows if isinstance(r.get("timestep_s"), (int, float))]
    if ts and (max(ts) / max(min(ts), 1e-30) > 100):
        out.append({"layer": "numerical", "confidence": "possible",
                    "description": "时步变化超过 100 倍，疑似数值不稳定",
                    "basis": "timestep min=%.3g max=%.3g" % (min(ts), max(ts)),
                    "evidence_refs": ["csv"], "target_module": "M4",
                    "needs_user_confirmation": True})
    return out


def diagnose_convergence(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """M5.4 计算收敛性诊断."""
    out = []
    if rows and len(rows) < 10:
        out.append({"layer": "data", "confidence": "possible",
                    "description": "采样点不足 10，难以判断收敛",
                    "basis": "samples=%d" % len(rows),
                    "evidence_refs": ["csv"], "target_module": "M4",
                    "needs_user_confirmation": False})
    return out


def diagnose_physical(summaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """M5.5 物理行为诊断."""
    out = []
    for s in summaries:
        tid = str(s.get("tool_task_id") or "replay")
        target = float(s.get("confining_target_Pa") or 0)
        measured = float(s.get("confining_pressure_initial_Pa") or 0)
        if target > 0 and (measured / target < 0.95 or measured / target > 1.05):
            out.append({"layer": "physical", "confidence": "confirmed",
                        "description": "围压未达标 %.3g/%.3g=%.4f" % (measured, target, measured / target),
                        "basis": "真实 PFC summary 加载前读数",
                        "evidence_refs": [tid], "target_module": "M3",
                        "needs_user_confirmation": True})
        bonded = s.get("bonded_at_load") or s.get("bonded")
        if isinstance(bonded, (int, float)) and bonded < 1000:
            out.append({"layer": "physical", "confidence": "possible",
                        "description": "加载起点成键数偏低 %d" % int(bonded),
                        "basis": "需与成键后计数对比", "evidence_refs": [tid],
                        "target_module": "M3", "needs_user_confirmation": True})
    return out


def diagnose_data(csvs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """M5.6 数据质量诊断."""
    out = []
    for c in csvs:
        if not c.get("rows"):
            out.append({"layer": "data", "confidence": "confirmed",
                        "description": "CSV 无有效数据行",
                        "basis": c.get("artifact_id", "csv"),
                        "evidence_refs": [c.get("artifact_id", "csv")],
                        "target_module": "M4", "needs_user_confirmation": True})
    return out


def diagnose_result(metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """M5.7 实验结果合理性诊断."""
    out = []
    for m in metrics:
        if m.get("peak_is_last"):
            out.append({"layer": "result", "confidence": "confirmed",
                        "description": "峰值在最后采样点，未捕获峰后段",
                        "basis": "CSV 自动计算",
                        "evidence_refs": [m.get("artifact_id", "csv")],
                        "target_module": "M6", "needs_user_confirmation": True})
    return out


def locate_cause(findings: List[Dict[str, Any]]) -> List[str]:
    """M5.8 异常原因定位."""
    return [f["description"] for f in findings if f["confidence"] == "confirmed"]


def correction_proposals(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """M5.9 修正建议生成."""
    proposals = {"model": "修正模型设置后重跑 M3→M4",
                 "numerical": "检查时步/接触后决定是否重算",
                 "physical": "核对围压伺服与胶结保留率后再加载",
                 "data": "补充数据后重跑 M4",
                 "result": "延长加载捕获峰后段，否则禁止峰值结论"}
    return [{"layer": f["layer"], "action": proposals.get(f["layer"], "人工复核"),
             "target_module": f.get("target_module", "M3")} for f in findings]


def revalidation_needed(findings: List[Dict[str, Any]]) -> bool:
    """M5.10 重新计算条件判断."""
    return any(f["confidence"] == "confirmed" for f in findings)


def validate_finding(f: Dict[str, Any]) -> List[str]:
    errors = []
    if f.get("layer") not in LAYERS:
        errors.append("invalid layer")
    if f.get("confidence") not in CONFIDENCE:
        errors.append("invalid confidence")
    if not f.get("evidence_refs"):
        errors.append("missing evidence_refs")
    if f.get("confidence") == "confirmed" and all(
            str(r).startswith("agent_") for r in f.get("evidence_refs", [])):
        errors.append("inference-only evidence cannot be confirmed")
    return errors


def m5_full_run(module_task_id: str, request: DispatchRequest,
                core: CoreDispatcher) -> Envelope:
    payload = request.payload or {}
    stage_states: List[Dict[str, Any]] = []
    for s in _read_json_artifacts(request, core, "m3_staged_model"):
        stage_states += s.get("stages", [])
    csvs = _read_csv_artifacts(request, core)
    summaries = _read_json_artifacts(request, core, "pfc_summary")
    metrics = [_analyze_rows(c["rows"]) for c in csvs]

    findings: List[Dict[str, Any]] = []
    findings += diagnose_model(stage_states)
    findings += diagnose_initial(stage_states)
    rows = [r for c in csvs for r in c["rows"]]
    findings += diagnose_numerical(rows)
    findings += diagnose_convergence(rows)
    findings += diagnose_physical(summaries)
    findings += diagnose_data(csvs)
    findings += diagnose_result(metrics)
    for f in findings:
        f["possible_causes"] = [f.get("basis", "")]
        f.setdefault("correction", "")
    errors = []
    for f in findings:
        errors += ["%s: %s" % (f["description"], e) for e in validate_finding(f)]

    structured = {
        "findings": findings, "layers": LAYERS,
        "confirmed_causes": locate_cause(findings),
        "correction_proposals": correction_proposals(findings),
        "requires_user_confirmation": any(f.get("needs_user_confirmation") for f in findings),
        "suggests_recompute": revalidation_needed(findings),
        "diagnosis_layer": findings[0]["layer"] if findings else "result",
        "confidence": findings[0]["confidence"] if findings else "hypothesis",
        "auto_read_evidence": True, "payload_findings_ignored": bool(payload.get("findings")),
    }
    artifacts = []
    artifacts.append(core.store.write_json("m5_diagnostic_evidence", "diagnostic_evidence.json", structured).to_dict())
    artifacts.append(core.store.write_json("m5_anomaly_records", "anomaly_records.json", findings).to_dict())
    md = "# 诊断报告\n\n%s\n" % "\n".join(
        "- [%s/%s] %s — %s" % (f["layer"], f["confidence"], f["description"], f["basis"])
        for f in findings)
    artifacts.append(core.store.write("m5_diagnosis_report", "diagnosis_report.md", md).to_dict())
    artifacts.append(core.store.write("m5_correction_proposals", "correction_proposals.md",
        "\n".join("- %s: %s" % (p["layer"], p["action"]) for p in structured["correction_proposals"])).to_dict())
    artifacts.append(core.store.write("m5_revalidation_plan", "revalidation_plan.md",
        "# 重新验证计划\n\n%s\n" % ("修正后须重走 M3→M4→M5" if revalidation_needed(findings) else "无需重算")).to_dict())

    return Envelope(
        module_id=ModuleID.M5, module_version=MODULE_VERSION,
        research_task_id=request.research_task_id, module_task_id=module_task_id,
        parent_task_id=request.parent_task_id, input_refs=request.input_refs,
        status={"module_state": ModuleState.COMPLETED.value if findings else ModuleState.BLOCKED.value},
        output={"structured": structured, "artifacts": artifacts, "verified_by_execution": False},
        evidence=[Evidence(EvidenceSource.DERIVED_COMPUTED, "M5.auto", "自动分层诊断")],
        decisions=[], limitations=errors + ["诊断不接受 payload 预整理结论"])


# ---------- M6: 13 functions ----------------------------------------------

def identify_data(csvs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """M6.1 数据文件识别."""
    return [{"artifact_id": c["artifact_id"], "rows": len(c["rows"]),
             "header": c["header"]} for c in csvs]


def read_and_organize(csvs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """M6.2 数据读取和整理."""
    return [{"artifact_id": c["artifact_id"], "rows": c["rows"]} for c in csvs]


def check_units(rows: List[Dict[str, Any]], declared: str) -> List[str]:
    """M6.3 单位与数据口径检查."""
    issues = []
    if not declared:
        issues.append("unit_system 未声明")
    if rows and not any("strain" in k.lower() for k in rows[0]):
        issues.append("缺少应变列")
    return issues


def compute_stress_strain(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """M6.4 应力—应变计算."""
    return _analyze_rows(rows)


def compute_mechanical(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """M6.5 力学参数计算."""
    return {"peak_stress": metrics.get("peak_stress"),
            "peak_strain": metrics.get("peak_strain"),
            "E50": metrics.get("E50"),
            "residual_stress": metrics.get("residual_stress")}


def crack_statistics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """M6.6 裂纹和破坏特征统计."""
    keys = [k for k in (rows[0] if rows else {}) if "crack" in k.lower()]
    if not keys:
        return {"available": False, "reason": "无裂纹列"}
    return {"available": True, "total": rows[-1].get(keys[0]) if rows else None}


def particle_motion(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """M6.7 颗粒运动与位移分析."""
    keys = [k for k in (rows[0] if rows else {}) if "displ" in k.lower() or "velocity" in k.lower()]
    return {"available": bool(keys), "columns": keys}


def contact_network(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """M6.8 接触网络分析."""
    keys = [k for k in (rows[0] if rows else {}) if "contact" in k.lower() or "bond" in k.lower()]
    return {"available": bool(keys), "columns": keys,
            "last": {k: rows[-1].get(k) for k in keys} if rows else {}}


def compare_cases(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """M6.9 多工况结果比较（统一口径）."""
    out = []
    for c in cases:
        out.append({"artifact_id": c.get("artifact_id"),
                    "peak_stress": c.get("peak_stress"),
                    "E50": c.get("E50"),
                    "peak_is_last": c.get("peak_is_last"),
                    "tool_task_id": c.get("tool_task_id")})
    return out


def sensitivity(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """M6.10 参数敏感性分析."""
    peaks = [c.get("peak_stress") for c in cases if isinstance(c.get("peak_stress"), (int, float))]
    if len(peaks) < 2:
        return {"available": False, "reason": "工况不足"}
    return {"available": True, "mean": statistics.mean(peaks),
            "range": max(peaks) - min(peaks),
            "relative_range": (max(peaks) - min(peaks)) / max(abs(statistics.mean(peaks)), 1e-30)}


def statistics_summary(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """M6.11 统计分析."""
    peaks = [c.get("peak_stress") for c in cases if isinstance(c.get("peak_stress"), (int, float))]
    if not peaks:
        return {"count": 0}
    return {"count": len(peaks), "mean": statistics.mean(peaks),
            "stdev": statistics.stdev(peaks) if len(peaks) > 1 else 0.0}


def quality_gate(cases: List[Dict[str, Any]], tool_ids: List[str],
                 predigested: bool) -> Dict[str, Any]:
    """M6.12 结果质量检查（FAIL 阻止结论）."""
    reasons = []
    if not cases:
        reasons.append("无数据文件")
    for c in cases:
        if c.get("error"):
            reasons.append("%s: %s" % (c.get("artifact_id"), c["error"]))
        if c.get("peak_is_last") or (c.get("samples_after_peak", 0) < 3):
            reasons.append("%s: 未捕获峰后段" % c.get("artifact_id"))
        if not c.get("tool_task_id"):
            reasons.append("%s: 无真实 tool_task_id" % c.get("artifact_id"))
    if predigested:
        reasons.append("禁止 payload 传入 results/结论替代自动计算")
    return {"status": "FAIL" if reasons else "PASS", "reasons": reasons,
            "peak_strength_allowed": not reasons}


def interpret(gate: Dict[str, Any], comparison: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """M6.13 结果解释（必须关联证据）."""
    if gate["status"] == "FAIL":
        return []
    return [{"statement": "工况 %s 峰值 %.4g" % (c["artifact_id"], c["peak_stress"] or 0),
             "evidence_ref": c["artifact_id"], "tool_task_id": c.get("tool_task_id"),
             "confidence": "confirmed"} for c in comparison]


def m6_full_run(module_task_id: str, request: DispatchRequest,
                core: CoreDispatcher) -> Envelope:
    payload = request.payload or {}
    csvs = _read_csv_artifacts(request, core)
    tool_ids = _fmt_tool_ids(core, request)
    unit_system = str(payload.get("unit_system", "SI"))
    data_manifest = identify_data(csvs)

    cases: List[Dict[str, Any]] = []
    metrics_list: List[Dict[str, Any]] = []
    unit_issues: List[str] = []
    for c in csvs:
        m = compute_stress_strain(c["rows"])
        metrics_list.append(m)
        tid = tool_ids[0] if tool_ids else None
        cases.append({"artifact_id": c["artifact_id"], **m,
                      "mechanical": compute_mechanical(m),
                      "cracks": crack_statistics(c["rows"]),
                      "motion": particle_motion(c["rows"]),
                      "network": contact_network(c["rows"]),
                      "tool_task_id": tid})
        unit_issues += check_units(c["rows"], unit_system)

    predigested = bool(payload.get("results") or payload.get("interpretation"))
    gate = quality_gate(cases, tool_ids, predigested)
    if unit_issues and gate["status"] == "PASS":
        gate["status"] = "FAIL"
        gate["reasons"] += unit_issues
        gate["peak_strength_allowed"] = False

    processed = [{"artifact_id": c["artifact_id"], "rows": len(c["rows"]),
                  "columns": c["header"]} for c in csvs]
    comparison = compare_cases(cases)
    structured = {
        "raw_data_manifest": data_manifest, "unit_system": unit_system,
        "processed_data": processed,
        "analysis_config": {"unit_system": unit_system, "metric_definitions":
                            [{"name": m, "definition": "自动计算"} for m in
                             ("peak_stress", "peak_strain", "E50", "residual_stress")]},
        "cases": cases, "comparison": comparison,
        "sensitivity": sensitivity(cases), "statistics": statistics_summary(cases),
        "quality_gate": gate, "interpretation": interpret(gate, comparison),
        "auto_computed": True, "accepts_predigested_results": False,
    }
    artifacts = []
    artifacts.append(core.store.write_json("m6_raw_data_manifest", "raw_data_manifest.json", data_manifest).to_dict())
    artifacts.append(core.store.write_json("m6_processed_data", "processed_data", processed).to_dict())
    artifacts.append(core.store.write_json("m6_analysis_config", "analysis_config.json", structured["analysis_config"]).to_dict())
    artifacts.append(core.store.write_json("m6_analysis_results", "analysis_results.json", structured).to_dict())
    artifacts.append(core.store.write("m6_comparison_report", "comparison_report.md",
        "# 工况比较\n\n%s\n" % "\n".join(
            "- %s: peak=%s E50=%s" % (c["artifact_id"], c["peak_stress"], c["E50"])
            for c in comparison)).to_dict())
    artifacts.append(core.store.write("m6_analysis_report", "analysis_report.md",
        "# 分析报告\n\n质量闸门: %s\n\n%s\n" % (gate["status"],
        "; ".join(gate["reasons"]) if gate["reasons"] else "结论须关联证据")).to_dict())

    evidence = [Evidence(EvidenceSource.DERIVED_COMPUTED, "M6.auto", "自动读取 CSV 计算")]
    for tid in tool_ids:
        evidence.append(Evidence(EvidenceSource.PFC_EXECUTED, tid,
                        "真实 PFC 导出", tool_task_id=tid))
    return Envelope(
        module_id=ModuleID.M6, module_version=MODULE_VERSION,
        research_task_id=request.research_task_id, module_task_id=module_task_id,
        parent_task_id=request.parent_task_id, input_refs=request.input_refs,
        status={"module_state": ModuleState.COMPLETED.value if gate["status"] == "PASS"
                else ModuleState.BLOCKED.value, "quality_gate": gate["status"]},
        output={"structured": structured, "artifacts": artifacts, "verified_by_execution": False},
        evidence=evidence, decisions=[],
        limitations=gate["reasons"] + ["M6 不接受人工整理结论"])


__all__ = ["m5_full_run", "m6_full_run", "LAYERS", "CONFIDENCE",
           "diagnose_model", "diagnose_initial", "diagnose_numerical",
           "diagnose_convergence", "diagnose_physical", "diagnose_data",
           "diagnose_result", "locate_cause", "correction_proposals",
           "revalidation_needed", "identify_data", "read_and_organize",
           "check_units", "compute_stress_strain", "compute_mechanical",
           "crack_statistics", "particle_motion", "contact_network",
           "compare_cases", "sensitivity", "statistics_summary",
           "quality_gate", "interpret"]
