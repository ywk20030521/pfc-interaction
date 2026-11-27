"""5.1 reusable physics gates for triaxial mechanism comparisons."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


def evaluate_triaxial_case(conf_measured: float, conf_target: float,
                           conf_during_loading: Iterable[float],
                           tool_task_ids: List[str],
                           samples_after_peak: int = 0,
                           tolerance: float = 0.05) -> Dict[str, Any]:
    """Separate data validity from a peak-strength claim.

    Data are valid when the target confinement is established, stays within
    10% during loading, and every sample has a real tool task id. A peak on the
    last sample does not invalidate the run; it only forbids a peak claim.
    """
    if conf_target <= 0:
        raise ValueError("目标围压必须为正")
    if not tool_task_ids or any(not str(t) for t in tool_task_ids):
        raise ValueError("缺少真实 tool_task_id")
    ratio = conf_measured / conf_target
    during = list(conf_during_loading)
    drift_ok = bool(during) and all(
        abs(c / conf_target - 1.0) <= 0.10 for c in during)
    data_valid = abs(ratio - 1.0) <= tolerance and drift_ok
    peak_claim_allowed = samples_after_peak >= 2
    return {
        "confinement_ratio": round(ratio, 4),
        "confinement_during_loading_ok": drift_ok,
        "data_valid_for_mechanism_comparison": data_valid,
        "peak_strength_claim_allowed": peak_claim_allowed,
        "status": (
            "PASS_FOR_MECHANISM_COMPARISON" if data_valid else "BLOCKED_CONFINEMENT"),
        "note": (
            "可比较曲线形态与键断裂；峰值强度结论仅在 peak_strength_claim_allowed=true 时允许"),
    }


__all__ = ["evaluate_triaxial_case"]
