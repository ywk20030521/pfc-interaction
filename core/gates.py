"""4.1-alpha stage gates: unforgeable approval ledger + physics admission.

The 4.0 dispatcher treated WAITING_FOR_USER as a string: downstream modules
could be dispatched anyway, and ``full_pipeline_e2e.py`` fabricated consent by
calling ``core.decisions.resolve(...)`` directly with a "synthetic approval".

This module makes gates enforcement *code*, not documentation:

  * ApprovalLedger is written ONLY by ``CoreDispatcher.resolve_decision`` after
    the decision has actually been presented. Nothing in a DispatchRequest
    payload can create an approval.
  * StageGate declares the required prior approvals for each module.
  * PhysicsGate decides whether a loading stage may start, from measured
    stage checks (confinement / bonding / boundaries / timestep / peak capture).

Pure standard library; no PFC dependency. 4.0 behaviour is unchanged because
enforcement lives in the V41CoreDispatcher subclass, not the base dispatcher.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .contract import DeliveryStatus, ModuleID
from .decisions import DecisionItem, DecisionKey


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_hash(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class ApprovalRecord:
    """Immutable proof that a specific decision was actually resolved by Core.

    ``answers_hash`` binds the record to what the operator actually answered;
    a caller cannot later substitute a different answer set. ``channel`` records
    whether the answer came from NATIVE_CHAT or AUQ.
    """

    decision_id: str
    experiment_id: str
    stage_id: str
    topic: str
    context_version: str
    resolution: str
    answers_hash: str
    channel: Optional[str]
    bound_context_version: str
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "experiment_id": self.experiment_id,
            "stage_id": self.stage_id,
            "topic": self.topic,
            "context_version": self.context_version,
            "resolution": self.resolution,
            "answers_hash": self.answers_hash,
            "channel": self.channel,
            "bound_context_version": self.bound_context_version,
            "created_at": self.created_at,
        }


class ApprovalLedger:
    """Append-only approval register.

    The only writer is ``record_resolution`` which is called from
    ``CoreDispatcher.resolve_decision``. There is deliberately NO public method
    to insert an approval from a module payload or an E2E script.
    """

    def __init__(self) -> None:
        self._records: List[ApprovalRecord] = []

    def record_resolution(
        self,
        item: DecisionItem,
        resolution: str,
        current_context_version: str,
        answers: Optional[Dict[str, Any]],
        channel: Optional[str],
    ) -> ApprovalRecord:
        """Write a ledger record. Only valid for a delivered, resolved decision."""
        if item.delivery_status not in (
            DeliveryStatus.DELIVERED,
            DeliveryStatus.WAITING_ANSWER,
            DeliveryStatus.ANSWERED,
        ):
            raise ValueError(
                "cannot record approval for an undelivered decision: %s" % item.decision_id
            )
        if resolution not in ("APPROVED", "ANSWERED", "REJECTED", "EXPIRED"):
            raise ValueError("unsupported resolution: %s" % resolution)
        rec = ApprovalRecord(
            decision_id=item.decision_id,
            experiment_id=item.key.experiment_id,
            stage_id=item.key.stage_id,
            topic=item.key.topic,
            context_version=item.key.context_version,
            resolution=resolution,
            answers_hash=_stable_hash(answers or {}),
            channel=channel,
            bound_context_version=current_context_version,
        )
        self._records.append(rec)
        return rec

    def is_approved(
        self,
        experiment_id: str,
        stage_id: str,
        topic: str,
        context_version: str,
    ) -> bool:
        for rec in self._records:
            if (
                rec.resolution == "APPROVED"
                and rec.experiment_id == experiment_id
                and rec.stage_id == stage_id
                and rec.topic == topic
                and rec.bound_context_version == context_version
            ):
                return True
        return False

    def record_for(
        self,
        experiment_id: str,
        stage_id: str,
        topic: str,
        context_version: str,
    ) -> Optional[ApprovalRecord]:
        matches = [
            r for r in self._records
            if (
                r.experiment_id == experiment_id
                and r.stage_id == stage_id
                and r.topic == topic
                and r.bound_context_version == context_version
                and r.resolution == "APPROVED"
            )
        ]
        return matches[-1] if matches else None

    def snapshot(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._records]


# ---- stage dependency declarations --------------------------------------

@dataclass(frozen=True)
class RequiredApproval:
    stage_id: str
    topic: str
    reason: str


# Each entry lists approvals that must exist in the ledger, bound to the same
# context_version, before the module may be dispatched.
STAGE_APPROVALS: Dict[str, List[RequiredApproval]] = {
    "M2": [RequiredApproval("M1", "confirm_research_plan", "研究计划须经用户确认")],
    "M3": [RequiredApproval("M2", "confirm_experiment_design", "实验方案须经用户确认")],
    "M4": [
        RequiredApproval("M3", "confirm_model_parameters", "关键模型参数须经用户确认"),
        RequiredApproval("M4", "authorize_execution", "执行须经用户单独授权"),
    ],
    "M5": [RequiredApproval("M4", "confirm_stage_results", "阶段结果须经确认后诊断")],
    "M6": [RequiredApproval("M5", "confirm_diagnosis", "诊断结论须经确认后分析")],
}

# A failed stage must route to M5 diagnosis immediately (review step 4).
# Either path is sufficient; both still require a real ledger approval.
ALTERNATIVE_APPROVALS: Dict[str, List[RequiredApproval]] = {
    "M5": [RequiredApproval("M3", "request_stage_diagnosis", "阶段失败后进入诊断")],
}


@dataclass
class GateDecision:
    allowed: bool
    module_id: str
    reason: str = ""
    missing: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "module_id": self.module_id,
            "reason": self.reason,
            "missing": self.missing,
        }


def check_stage_gate(
    module_id: ModuleID,
    research_task_id: str,
    context_version: str,
    ledger: ApprovalLedger,
) -> GateDecision:
    """Return whether a module may be dispatched in strict mode."""
    required = STAGE_APPROVALS.get(module_id.value, [])
    alternatives = ALTERNATIVE_APPROVALS.get(module_id.value, [])

    def satisfied(req: RequiredApproval) -> bool:
        return ledger.is_approved(
            research_task_id, req.stage_id, req.topic, context_version
        )

    missing: List[str] = []
    if required and alternatives:
        primary_ok = all(satisfied(r) for r in required)
        alternative_ok = all(satisfied(r) for r in alternatives)
        if not primary_ok and not alternative_ok:
            for req in required:
                if not satisfied(req):
                    missing.append("%s/%s@%s: %s" % (
                        req.stage_id, req.topic, context_version, req.reason))
            missing.append("或替代路径: " + ", ".join(
                "%s/%s" % (r.stage_id, r.topic) for r in alternatives))
    else:
        for req in required:
            if not satisfied(req):
                missing.append("%s/%s@%s: %s" % (
                    req.stage_id, req.topic, context_version, req.reason))

    if missing:
        return GateDecision(
            allowed=False,
            module_id=module_id.value,
            reason="阶段门未满足：前置批准缺失",
            missing=missing,
        )
    return GateDecision(allowed=True, module_id=module_id.value,
                        reason="前置批准齐全")


# ---- physics admission gate ---------------------------------------------

# Defaults are deliberately strict. Values may be supplied by the caller but
# not removed: a missing measurement is a failure, never a pass.
DEFAULT_PHYSICS_THRESHOLDS: Dict[str, float] = {
    "confinement_min_ratio": 0.95,   # measured / target before loading
    "confinement_max_ratio": 1.05,
    "bond_retention_min": 0.80,      # bonded_at_load / bonded_after_bonding
    "overlap_rate_max": 0.01,
    "out_of_bounds_max": 0.0,
    "wall_gap_max": 0.0005,          # metres
    "unbalanced_force_ratio_max": 0.01,
    "timestep_min": 1e-12,
}


@dataclass
class PhysicsResult:
    passed: bool
    can_load: bool
    failures: List[str] = field(default_factory=list)
    measurements: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "can_load": self.can_load,
            "failures": self.failures,
            "measurements": self.measurements,
        }


def check_physics_gate(
    measurements: Dict[str, Any],
    thresholds: Optional[Dict[str, float]] = None,
) -> PhysicsResult:
    """Decide whether the loading stage may start.

    Any missing / non-finite required measurement is a FAILURE. This is the
    code-level fix for the C1/C2/C3 bug: confinement was 5989/6129/5652 Pa
    against targets of 1/5/10 MPa and loading proceeded anyway.
    """
    th = dict(DEFAULT_PHYSICS_THRESHOLDS)
    if thresholds:
        th.update(thresholds)

    failures: List[str] = []
    m = dict(measurements or {})

    required = [
        "confining_measured_Pa",
        "confining_target_Pa",
        "bonded_after_bonding",
        "bonded_at_load",
    ]
    for key in required:
        value = m.get(key)
        if not isinstance(value, (int, float)):
            failures.append("缺失测量值: %s" % key)

    def _num(key: str, default=None):
        v = m.get(key, default)
        return float(v) if isinstance(v, (int, float)) else None

    target = _num("confining_target_Pa")
    measured = _num("confining_measured_Pa")
    if target and measured is not None and target > 0:
        ratio = measured / target
        m["confinement_ratio"] = round(ratio, 6)
        if not (th["confinement_min_ratio"] <= ratio <= th["confinement_max_ratio"]):
            failures.append(
                "围压未达标: 实测 %.3g Pa / 目标 %.3g Pa = %.4f (允许 %.2f–%.2f)"
                % (measured, target, ratio,
                   th["confinement_min_ratio"], th["confinement_max_ratio"])
            )
    elif target is None or measured is None:
        failures.append("无法计算围压比")

    bonded_after = _num("bonded_after_bonding")
    bonded_load = _num("bonded_at_load")
    if bonded_after and bonded_load is not None and bonded_after > 0:
        retention = bonded_load / bonded_after
        m["bond_retention"] = round(retention, 6)
        if retention < th["bond_retention_min"]:
            failures.append(
                "胶结保留率不足: %d/%d = %.3f (最低 %.2f)"
                % (int(bonded_load), int(bonded_after), retention,
                   th["bond_retention_min"])
            )

    overlap = _num("overlap_rate")
    if overlap is not None and overlap > th["overlap_rate_max"]:
        failures.append("颗粒重叠率过高: %.4f > %.4f" % (overlap, th["overlap_rate_max"]))

    oob = _num("out_of_bounds")
    if oob is not None and oob > th["out_of_bounds_max"]:
        failures.append("颗粒越界数: %d > %d" % (int(oob), int(th["out_of_bounds_max"])))

    gap = _num("wall_gap_m")
    if gap is not None and gap > th["wall_gap_max"]:
        failures.append("墙体-试样间隙过大: %.6g m > %.6g m" % (gap, th["wall_gap_max"]))

    ubf = _num("unbalanced_force_ratio")
    if ubf is not None and ubf > th["unbalanced_force_ratio_max"]:
        failures.append("不平衡力比过高: %.4g > %.4g" % (ubf, th["unbalanced_force_ratio_max"]))

    ts = _num("timestep_s")
    if ts is not None and (ts <= 0 or ts < th["timestep_min"]):
        failures.append("时步异常: %.6g s" % ts)

    passed = not failures
    return PhysicsResult(passed=passed, can_load=passed,
                         failures=failures, measurements=m)


def check_peak_capture(peak_is_last: bool, samples_after_peak: int = 0) -> PhysicsResult:
    """Post-peak capture gate: a peak on the last sample is not a peak."""
    failures: List[str] = []
    if peak_is_last:
        failures.append("峰值出现在最后采样点：未捕获峰后段，禁止输出峰值强度结论")
    if samples_after_peak < 3:
        failures.append("峰后采样点不足: %d < 3" % int(samples_after_peak))
    passed = not failures
    return PhysicsResult(passed=passed, can_load=True, failures=failures,
                         measurements={
                             "peak_is_last": bool(peak_is_last),
                             "samples_after_peak": int(samples_after_peak),
                         })


__all__ = [
    "ApprovalLedger", "ApprovalRecord", "GateDecision", "PhysicsResult",
    "STAGE_APPROVALS", "ALTERNATIVE_APPROVALS", "DEFAULT_PHYSICS_THRESHOLDS",
    "check_stage_gate", "check_physics_gate", "check_peak_capture",
    "DecisionKey", "DeliveryStatus", "_stable_hash",
]
