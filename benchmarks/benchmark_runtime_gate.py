#!/usr/bin/env python3
"""Reproducible performance benchmark for the pfc-interaction runtime gate.

Covers the key usage paths introduced by the runtime gate:
host capability probing (L0/L1/L2), missing-parameter stop protocol,
Native Chat ask, structured ask, duplicate suppression, authorization
grant/block, version-change invalidation and Native Chat turn validation.

Metrics: per-call latency (mean/p50/p95/p99/min/max), CPU time, process RSS,
Python allocation peak (tracemalloc), and stability (expected exception rate,
output determinism, RSS growth across repeated rounds). No PFC execution and
no real host UI are involved.
"""
from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover - optional
    psutil = None  # type: ignore

from core.host_interaction import (  # noqa: E402
    HostInteractionAdapter,
    attach_host_ask,
    probe_host_capability,
)
from core.stop_protocol import (  # noqa: E402
    FormalRunAuthorization,
    gate_formal_execution,
    minimum_native_chat_requirements,
    require_user_decision,
)
from core.v50_context import ResearchTask  # noqa: E402
from core.v50_decisions import DecisionManager, InteractionRouter  # noqa: E402
from modules.question_cards import execution_card  # noqa: E402
from modules.v50_interaction import InteractionCoordinator  # noqa: E402

CONTEXT = {
    "experiment_purpose": "真实岩样标定",
    "boundary_type": "圆柱柔性膜",
    "specimen_size": "直径 50 mm / 高 100 mm",
    "confining_pressure": "10 MPa",
    "loading_endpoint": "峰值后 1% 应变",
    "parameter_source": "室内试验反演",
}
GOOD_TURN = {
    "understanding": "三轴压缩，参数未定",
    "alternatives": [{"label": "方形刚壁"}, {"label": "圆柱柔性膜"}],
    "unresolved_parameters": ["围压", "加载终点"],
    "questions": ["目的是什么?", "用哪种边界?"],
    "stopped": True,
}


def _setup() -> tuple[ResearchTask, DecisionManager, InteractionRouter,
                      InteractionCoordinator]:
    task = ResearchTask("task-bench", "运行时闸门性能基准")
    decisions = DecisionManager(task)
    router = InteractionRouter(task, decisions)
    return task, decisions, router, InteractionCoordinator(task, decisions, router)


def _exec_card(qid: str = "exec-bench"):
    return execution_card(
        qid, "是否确认执行正式三轴 Run?",
        "操作：启动正式三轴压缩仿真。",
        "start_formal_simulation", "pfc3d_console", "生成正式科研数据",
    )


def scenario_probe_l0() -> dict[str, Any]:
    return probe_host_capability().to_dict()


def scenario_probe_l2() -> dict[str, Any]:
    return probe_host_capability(
        structured_ask=lambda payload: {"answer": "柔性膜"},
        auq_available=True, card_ui_available=True,
    ).to_dict()


def scenario_missing_parameters_stop() -> dict[str, Any]:
    task, decisions, _, _ = _setup()
    result = require_user_decision(task, decisions, {"experiment_purpose": "教学演示"})
    payload = result.to_dict()
    # Normalize generated IDs: determinism compares behavior, not UUIDs.
    payload["pending_decision_id"] = bool(payload["pending_decision_id"])
    payload["decision_status"] = task.decisions[result.pending_decision_id].status.value
    return payload


def scenario_ask_native_chat() -> dict[str, Any]:
    task, decisions, router, _ = _setup()
    adapter = HostInteractionAdapter(task, decisions, router, probe_host_capability())
    outcome = adapter.ask(
        {"question": "使用哪种边界?", "understanding": "三轴压缩建模"},
        topic="边界选择", context_version="v1",
    )
    return {
        "status": outcome.status, "delivered": outcome.delivered,
        "pending_decision_id": bool(outcome.pending_decision_id),
    }


def scenario_ask_structured() -> dict[str, Any]:
    task, decisions, router, _ = _setup()
    capability = probe_host_capability(
        structured_ask=lambda payload: {"answer": "柔性膜"},
        auq_available=True, card_ui_available=True,
    )
    adapter = HostInteractionAdapter(task, decisions, router, capability)
    attach_host_ask(adapter, lambda payload: {"answer": "柔性膜"})
    outcome = adapter.ask({"question": "边界?"}, topic="边界", context_version="v1")
    return {"status": outcome.status, "delivered": outcome.delivered,
            "answer": outcome.answer}


def scenario_duplicate_suppression() -> dict[str, Any]:
    task, decisions, router, _ = _setup()
    capability = probe_host_capability(
        structured_ask=lambda payload: {"answer": "柔性膜"},
        auq_available=True, card_ui_available=True,
    )
    adapter = HostInteractionAdapter(task, decisions, router, capability)
    attach_host_ask(adapter, lambda payload: {"answer": "柔性膜"})
    first = adapter.ask({"question": "边界?"}, topic="边界", context_version="v1")
    second = adapter.ask({"question": "边界?"}, topic="边界", context_version="v1")
    return {"first": first.status, "second": second.status,
            "interactions": len(task.interactions)}


def scenario_authorize_and_gate() -> dict[str, Any]:
    task, decisions, router, coordinator = _setup()
    prepared = coordinator.prepare(_exec_card())
    coordinator.submit(prepared.interaction_id, "确认执行")
    auth = coordinator.authorize_execution(
        prepared.interaction_id, operation="start_formal_simulation",
        target="pfc3d_console", model_version="model-v1",
        parameter_version="param-v1", matrix_version="matrix-v1",
    )
    gate = gate_formal_execution(decisions, FormalRunAuthorization(
        authorization_id=auth.authorization_id,
        research_task_id=task.research_task_id,
        decision_id=prepared.decision_id,
        model_version="model-v1", parameter_version="param-v1",
        matrix_version="matrix-v1", scope="execute:exec",
    ))
    return {"status": gate.status, "next_action": gate.allowed_next_action,
            "has_auth_arg": bool(gate.authorization_metadata.get("--authorization-id"))}


def scenario_gate_unauthorized() -> dict[str, Any]:
    task, decisions, _, _ = _setup()
    gate = gate_formal_execution(decisions, FormalRunAuthorization(
        authorization_id="auth-missing", research_task_id=task.research_task_id,
        decision_id="dec-none", model_version="v1",
        parameter_version="v1", matrix_version="v1",
    ))
    return {"status": gate.status, "issue_count": len(gate.issues)}


def scenario_version_invalidation() -> dict[str, Any]:
    task, decisions, router, coordinator = _setup()
    prepared = coordinator.prepare(_exec_card())
    coordinator.submit(prepared.interaction_id, "确认执行")
    auth = coordinator.authorize_execution(
        prepared.interaction_id, operation="start_formal_simulation",
        target="pfc3d_console", model_version="model-v1",
        parameter_version="param-v1", matrix_version="matrix-v1",
    )
    task.bump_version("model:edited")
    gate = gate_formal_execution(decisions, FormalRunAuthorization(
        authorization_id=auth.authorization_id,
        research_task_id=task.research_task_id,
        decision_id=prepared.decision_id,
        model_version="model-v1", parameter_version="param-v1",
        matrix_version="matrix-v1", scope="execute:exec",
    ))
    return {"status": gate.status, "issue_count": len(gate.issues)}


def scenario_validate_native_turn() -> dict[str, Any]:
    issues = minimum_native_chat_requirements(GOOD_TURN)
    poor = dict(GOOD_TURN, alternatives=[{"label": "单一方案"}], stopped=False)
    return {"good_issues": len(issues), "poor_issues": len(minimum_native_chat_requirements(poor))}


SCENARIOS: list[tuple[str, Callable[[], dict[str, Any]], int]] = [
    ("probe_host_capability_l0", scenario_probe_l0, 500),
    ("probe_host_capability_l2", scenario_probe_l2, 500),
    ("missing_parameters_stop", scenario_missing_parameters_stop, 300),
    ("ask_native_chat_pending", scenario_ask_native_chat, 300),
    ("ask_structured_delivered", scenario_ask_structured, 300),
    ("duplicate_suppression", scenario_duplicate_suppression, 200),
    ("authorize_and_gate", scenario_authorize_and_gate, 200),
    ("gate_unauthorized", scenario_gate_unauthorized, 300),
    ("version_change_invalidates", scenario_version_invalidation, 200),
    ("validate_native_chat_turn", scenario_validate_native_turn, 500),
]


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - pos) + ordered[hi] * (pos - lo)


def measure(name: str, fn: Callable[[], dict[str, Any]],
            iterations: int, warmup: int, rounds: int) -> dict[str, Any]:
    for _ in range(warmup):
        fn()

    proc = psutil.Process() if psutil else None
    round_stats: list[dict[str, Any]] = []
    signatures: set[str] = set()
    failures = 0

    for _ in range(rounds):
        samples: list[float] = []
        rss_before = proc.memory_info().rss if proc else 0
        cpu_before = time.process_time()
        wall_before = time.perf_counter()
        for _ in range(iterations):
            start = time.perf_counter()
            try:
                result = fn()
            except Exception:  # noqa: BLE001 - recorded as instability signal
                failures += 1
                continue
            samples.append((time.perf_counter() - start) * 1000.0)
            signatures.add(json.dumps(result, sort_keys=True, default=str))
        wall_ms = (time.perf_counter() - wall_before) * 1000.0
        cpu_ms = (time.process_time() - cpu_before) * 1000.0
        rss_after = proc.memory_info().rss if proc else 0
        round_stats.append({
            "samples_ms": samples, "wall_ms": wall_ms, "cpu_ms": cpu_ms,
            "rss_before_bytes": rss_before, "rss_after_bytes": rss_after,
        })

    tracemalloc.start()
    for _ in range(iterations):
        fn()
    _, allocation_peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    all_samples = [s for r in round_stats for s in r["samples_ms"]]
    rss_growth = round_stats[-1]["rss_after_bytes"] - round_stats[0]["rss_before_bytes"]
    return {
        "name": name,
        "iterations_per_round": iterations,
        "rounds": rounds,
        "total_calls": sum(len(r["samples_ms"]) for r in round_stats),
        "latency_ms": {
            "mean": round(statistics.fmean(all_samples), 6),
            "median": round(_percentile(all_samples, 0.5), 6),
            "p95": round(_percentile(all_samples, 0.95), 6),
            "p99": round(_percentile(all_samples, 0.99), 6),
            "min": round(min(all_samples), 6),
            "max": round(max(all_samples), 6),
            "stdev": round(statistics.pstdev(all_samples), 6),
        },
        "resource": {
            "cpu_ms_per_round_mean": round(
                statistics.fmean(r["cpu_ms"] for r in round_stats), 3),
            "wall_ms_per_round_mean": round(
                statistics.fmean(r["wall_ms"] for r in round_stats), 3),
            "rss_start_bytes": round_stats[0]["rss_before_bytes"],
            "rss_end_bytes": round_stats[-1]["rss_after_bytes"],
            "rss_growth_bytes": rss_growth,
            "tracemalloc_peak_bytes": allocation_peak_bytes,
            "psutil_available": psutil is not None,
        },
        "stability": {
            "unexpected_exceptions": failures,
            "distinct_outputs": len(signatures),
            "deterministic": len(signatures) == 1 and failures == 0,
            "rss_growth_bytes": rss_growth,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "benchmarks" / "results.json")
    args = parser.parse_args()

    results = {
        "benchmark": "pfc-interaction-runtime-gate",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "psutil": getattr(psutil, "__version__", None),
            "real_pfc_execution": False,
            "real_host_ui": False,
        },
        "scenarios": [
            measure(name, fn, iterations, max(5, iterations // 20), args.rounds)
            for name, fn, iterations in SCENARIOS
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False),
                           encoding="utf-8")
    for scenario in results["scenarios"]:
        latency = scenario["latency_ms"]
        print(f"{scenario['name']:34s} mean={latency['mean']:.4f}ms "
              f"p95={latency['p95']:.4f}ms p99={latency['p99']:.4f}ms "
              f"deterministic={scenario['stability']['deterministic']}")
    print(f"Results written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
