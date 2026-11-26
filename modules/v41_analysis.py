"""4.1-alpha M5/M6: automatic diagnosis and analysis from real evidence files.

4.0 M5 just wrapped caller-supplied ``findings``; M6 only checked that input
lists were non-empty and echoed caller-supplied ``results``. This module reads
real CSV / summary artifacts and computes findings and metrics itself. It does
not accept pre-digested conclusions as evidence.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional

from core import (
    DispatchRequest,
    Envelope,
    Evidence,
    EvidenceSource,
    ModuleID,
    ModuleState,
    CoreDispatcher,
    check_peak_capture,
)

MODULE_VERSION = "4.1.0-alpha"


def _read_json_artifacts(request: DispatchRequest, core: CoreDispatcher,
                         prefix: str) -> List[Dict[str, Any]]:
    out = []
    for ref in request.input_refs:
        if ref.artifact_id.startswith(prefix):
            obj = core.store.get_json(ref)
            if isinstance(obj, dict):
                out.append(obj)
    return out


def _read_csv_artifacts(request: DispatchRequest, core: CoreDispatcher) -> List[Dict[str, Any]]:
    out = []
    for ref in request.input_refs:
        if ref.artifact_id.startswith("pfc_csv") or ref.artifact_id.startswith("raw_tcsv"):
            text = core.store.get(ref)
            reader = csv.DictReader(io.StringIO(text))
            rows = []
            for row in reader:
                try:
                    rows.append({k: (float(v) if v not in (None, "") else None)
                                 for k, v in row.items()})
                except ValueError:
                    rows.append(row)
            out.append({"artifact_id": ref.artifact_id, "rows": rows,
                        "header": reader.fieldnames or []})
    return out


def _fmt_tool_ids(core: CoreDispatcher, request: DispatchRequest) -> List[str]:
    ids = []
    for ref in request.input_refs:
        if ref.artifact_id.startswith("m4_run"):
            obj = core.store.get_json(ref)
            tid = obj.get("tool_task_id")
            if tid:
                ids.append(str(tid))
    return ids


# ---- M5 automatic diagnosis ----------------------------------------------

def m5_run(module_task_id: str, request: DispatchRequest,
           core: CoreDispatcher) -> Envelope:
    """Derive layered findings from real measurements; ignore payload findings."""
    payload = request.payload or {}
    findings: List[Dict[str, Any]] = []
    tool_ids = _fmt_tool_ids(core, request)

    def add(layer: str, confidence: str, description: str, basis: str,
            refs: List[str], correction: str, target_module: str) -> None:
        findings.append({
            "layer": layer, "confidence": confidence, "description": description,
            "basis": basis, "evidence_refs": refs or ["m4_status"],
            "correction": correction, "target_module": target_module,
            "needs_user_confirmation": True,
        })

    for summary in _read_json_artifacts(request, core, "pfc_summary"):
        tid = str(summary.get("tool_task_id") or "replay")
        refs = [tid] if tid else tool_ids
        target = float(summary.get("confining_target_Pa") or 0)
        initial = float(summary.get("confining_pressure_initial_Pa") or 0)
        bonded = summary.get("bonded_at_load") or summary.get("bonded")
        if target > 0 and (initial / target < 0.95 or initial / target > 1.05):
            add("physical", "confirmed",
                "围压未达标: %.3g Pa / %.3g Pa = %.4f" % (initial, target, initial / target),
                "真实 PFC summary 加载前读数", refs,
                "在围压达到目标 ±5% 前禁止加载；检查墙贴靠与伺服增益", "M3")
        if isinstance(bonded, (int, float)) and bonded < 1000:
            add("model", "possible",
                "加载起点成键数偏低: %d（胶结保留率疑似不足）" % int(bonded),
                "真实 PFC summary bonded 字段（需与成键后计数对比）", refs,
                "核对成样→胶结→预压路径的胶结保留率", "M3")
        peak_last = summary.get("peak_is_last")
        if peak_last is True:
            add("result", "confirmed",
                "峰值出现在最后采样点，未捕获峰后段",
                "真实 PFC summary peak_is_last=true", refs,
                "延长加载至峰后 3 个以上采样点，否则禁止输出峰值强度", "M6")

    for stage in _read_json_artifacts(request, core, "m3_staged_model"):
        for state in stage.get("stages", []):
            if state.get("status") == "FAIL":
                add("model", "confirmed",
                    "M3 阶段 %s 检查失败: %s" % (
                        state.get("stage"), "; ".join(state.get("findings", []))),
                    "M3 阶段化检查报告", [],
                    "修正对应阶段后重新执行 M3→M4→M5", "M3")
        admit = stage.get("physics_gate", {}).get("admission", {})
        for f in admit.get("failures", []):
            add("physical", "confirmed", f, "物理准入闸门 check_physics_gate", [],
                "按失败项修正模型/伺服后再申请加载", "M3")

    structured = {
        "findings": findings,
        "correction_proposals": [f["correction"] for f in findings],
        "requires_user_confirmation": any(f["needs_user_confirmation"] for f in findings),
        "suggests_recompute": any(f["confidence"] == "confirmed" for f in findings),
        "diagnosis_layer": findings[0]["layer"] if findings else "result",
        "confidence": findings[0]["confidence"] if findings else "hypothesis",
        "auto_read_evidence": True,
        "payload_findings_ignored": bool(payload.get("findings")),
    }
    ref = core.store.write_json("m5_auto_diagnosis", "diagnosis.json", structured)
    state = ModuleState.COMPLETED.value if findings else ModuleState.BLOCKED.value
    return Envelope(
        module_id=ModuleID.M5,
        module_version=MODULE_VERSION,
        research_task_id=request.research_task_id,
        module_task_id=module_task_id,
        parent_task_id=request.parent_task_id,
        input_refs=request.input_refs,
        status={"module_state": state},
        output={"structured": structured, "artifacts": [ref.to_dict()],
                "verified_by_execution": False},
        evidence=[Evidence(EvidenceSource.DERIVED_COMPUTED, "M5.auto",
                           "自动读取证据并诊断")],
        decisions=[],
        limitations=["诊断来自真实数据自动计算；不接受 payload 预整理结论"],
    )


# ---- M6 automatic analysis ------------------------------------------------

def _analyze_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute peak / peak strain / E50 / post-peak from real CSV rows."""
    stress_key = None
    strain_key = None
    if rows:
        for k in rows[0]:
            kl = k.lower()
            if "stress" in kl and stress_key is None:
                stress_key = k
            if "strain" in kl and strain_key is None:
                strain_key = k
    if not stress_key or not strain_key:
        return {"error": "CSV 缺少应力/应变列", "header": list(rows[0]) if rows else []}

    series = []
    for r in rows:
        s, e = r.get(stress_key), r.get(strain_key)
        if isinstance(s, (int, float)) and isinstance(e, (int, float)):
            series.append((float(e), float(s)))
    if not series:
        return {"error": "无有效数据点"}

    peak_idx = max(range(len(series)), key=lambda i: series[i][1])
    peak_strain, peak_stress = series[peak_idx]
    samples_after = len(series) - 1 - peak_idx
    peak_is_last = peak_idx == len(series) - 1

    e50 = None
    target = 0.5 * peak_stress
    for i in range(1, len(series)):
        s0, s1 = series[i - 1][1], series[i][1]
        if s0 <= target <= s1:
            e0, e1 = series[i - 1][0], series[i][0]
            if s1 != s0:
                e50 = e0 + (target - s0) * (e1 - e0) / (s1 - s0)
            break

    residual = series[-1][1] if samples_after >= 3 else None
    return {
        "samples": len(series),
        "peak_stress": peak_stress,
        "peak_strain": peak_strain,
        "peak_is_last": peak_is_last,
        "samples_after_peak": samples_after,
        "E50": e50,
        "residual_stress": residual,
        "stress_column": stress_key,
        "strain_column": strain_key,
    }


def m6_run(module_task_id: str, request: DispatchRequest,
           core: CoreDispatcher) -> Envelope:
    """Read CSVs, compute metrics, gate conclusions on post-peak capture."""
    payload = request.payload or {}
    tool_ids = _fmt_tool_ids(core, request)
    csvs = _read_csv_artifacts(request, core)
    cases: List[Dict[str, Any]] = []
    gate_failures: List[str] = []
    evidence: List[Evidence] = [Evidence(
        EvidenceSource.DERIVED_COMPUTED, "M6.auto", "自动读取 CSV 计算")]

    if not csvs:
        gate_failures.append("未提供可读取的 PFC CSV 数据文件")

    for entry in csvs:
        metrics = _analyze_rows(entry["rows"])
        case = {"artifact_id": entry["artifact_id"], **metrics}
        tid = tool_ids[0] if tool_ids else None
        case["tool_task_id"] = tid
        if "error" in metrics:
            gate_failures.append("%s: %s" % (entry["artifact_id"], metrics["error"]))
        else:
            if metrics["peak_is_last"] or metrics["samples_after_peak"] < 3:
                gate_failures.append(
                    "%s: 未捕获峰后段（peak_is_last=%s, after=%d）" % (
                        entry["artifact_id"], metrics["peak_is_last"],
                        metrics["samples_after_peak"])
                )
                case["peak_conclusion_blocked"] = True
            if tid:
                evidence.append(Evidence(
                    EvidenceSource.PFC_EXECUTED, entry["artifact_id"],
                    "M6 直接读取的真实 PFC 导出", tool_task_id=tid,
                ))
            else:
                evidence.append(Evidence(
                    EvidenceSource.INVALID_EVIDENCE, entry["artifact_id"],
                    "PFC CSV 无关联 tool_task_id",
                ))
                gate_failures.append("%s: 无真实 tool_task_id" % entry["artifact_id"])
        cases.append(case)

    if payload.get("results") or payload.get("interpretation"):
        gate_failures.append("禁止以 payload 传入的 results/结论替代自动计算")

    gate = {
        "status": "FAIL" if gate_failures else "PASS",
        "reasons": gate_failures,
        "peak_strength_allowed": not gate_failures,
    }
    structured = {
        "unit_system": str(payload.get("unit_system", "SI")),
        "cases": cases,
        "quality_gate": gate,
        "interpretation": [],
        "auto_computed": True,
        "accepts_predigested_results": False,
    }
    ref = core.store.write_json("m6_auto_analysis", "analysis_results.json", structured)
    state = ModuleState.COMPLETED.value if gate["status"] == "PASS" else ModuleState.BLOCKED.value
    return Envelope(
        module_id=ModuleID.M6,
        module_version=MODULE_VERSION,
        research_task_id=request.research_task_id,
        module_task_id=module_task_id,
        parent_task_id=request.parent_task_id,
        input_refs=request.input_refs,
        status={"module_state": state, "quality_gate": gate["status"]},
        output={"structured": structured, "artifacts": [ref.to_dict()],
                "verified_by_execution": False},
        evidence=evidence, decisions=[],
        limitations=gate_failures + ["M6 自动读取文件计算，不接受人工整理结论"],
    )


__all__ = ["m5_run", "m6_run", "_analyze_rows"]
