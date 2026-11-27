"""5.1: replay physics gates over the real PFC3D case data (no execution)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
from core.v510_physics import evaluate_triaxial_case  # noqa: E402

DATA = Path(__file__).resolve().parents[2].parent / "outputs" / "v510_acceptance" / "data"


def main() -> None:
    parser = argparse.ArgumentParser(description="5.1 scientific gate replay")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    results = {}
    for path in sorted(DATA.glob("case_*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        results[case["case_id"]] = evaluate_triaxial_case(
            case["conf_after_servo_MPa"], case["conf_target_MPa"],
            case["conf_during_loading_MPa"],
            [t["tool_task_id"] for t in case["tool_task_ids"]],
            samples_after_peak=case["samples_after_peak"])
    report = {
        "status": "V510_SCIENCE_REPLAY_PASS"
        if all(r["status"] == "PASS_FOR_MECHANISM_COMPARISON"
               for r in results.values()) else "BLOCKED",
        "cases": results,
        "note": "峰值强度仅在 peak_strength_claim_allowed=true 时可声明",
    }
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report["status"], "cases", len(results))


if __name__ == "__main__":
    main()
