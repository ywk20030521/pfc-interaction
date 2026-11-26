"""IF0 section 5: three orthogonal state layers with single writers.

Interaction state  -> Core writes
Task state         -> written only from Itasca MCP execution results
Module state       -> Core derives from the two above

No module may write any of these directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .contract import CONTRACT_VERSION, EvidenceSource


class InteractionState(str, Enum):
    PENDING = "PENDING"
    PRESENTED = "PRESENTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"


class TaskState(str, Enum):
    CREATED = "CREATED"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RECOVERING = "RECOVERING"


class ModuleState(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


@dataclass
class ExecutionResult:
    """I5 ExecutionResult. task_state must come from the tool, not inference."""

    tool_task_id: str
    task_state: TaskState
    output_artifacts: List[Dict[str, Any]] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self.tool_task_id:
            errors.append("tool_task_id is required for a valid execution result")
        if not isinstance(self.task_state, TaskState):
            errors.append("task_state must be a TaskState enum")
        return errors


class StateStore:
    """Core-owned state registry. All writes go through Core methods."""

    def __init__(self) -> None:
        self._records: Dict[str, Dict[str, Any]] = {}

    def dispatch(self, module_task_id: str) -> None:
        self._records[module_task_id] = {
            "interaction_state": None,
            "task_state": None,
            "module_state": ModuleState.READY,
            "execution": None,
            "completed_evidence": [],
        }

    def record(self, module_task_id: str) -> Dict[str, Any]:
        if module_task_id not in self._records:
            raise KeyError("module task not dispatched: %s" % module_task_id)
        return self._records[module_task_id]

    def present(self, module_task_id: str) -> None:
        if module_task_id not in self._records:
            self.dispatch(module_task_id)
        self.record(module_task_id)["interaction_state"] = InteractionState.PRESENTED
        self.record(module_task_id)["module_state"] = ModuleState.WAITING_FOR_USER

    def resolve(self, module_task_id: str, resolution: str) -> None:
        if module_task_id not in self._records:
            self.dispatch(module_task_id)
        rec = self.record(module_task_id)
        rec["interaction_state"] = InteractionState(resolution)
        if resolution == InteractionState.APPROVED.value:
            # Approval only grants permission; it never executes anything.
            rec["task_state"] = TaskState.READY
            rec["module_state"] = ModuleState.RUNNING
        elif resolution == InteractionState.REJECTED.value:
            rec["module_state"] = ModuleState.BLOCKED
        elif resolution == InteractionState.EXPIRED.value:
            rec["module_state"] = ModuleState.BLOCKED

    def start_execution(self, module_task_id: str) -> None:
        self.record(module_task_id)["task_state"] = TaskState.RUNNING
        self.record(module_task_id)["module_state"] = ModuleState.RUNNING

    def finish_execution(self, module_task_id: str, result: ExecutionResult) -> List[str]:
        """Write task_state ONLY from a tool result with a real tool_task_id."""
        errors = result.validate()
        if errors:
            self.record(module_task_id)["module_state"] = ModuleState.FAILED
            return errors
        rec = self.record(module_task_id)
        rec["task_state"] = result.task_state
        rec["execution"] = result
        if result.task_state == TaskState.COMPLETED:
            rec["interaction_state"] = InteractionState.EXECUTED
            rec["module_state"] = ModuleState.COMPLETED
        elif result.task_state == TaskState.FAILED:
            rec["interaction_state"] = InteractionState.FAILED
            rec["module_state"] = ModuleState.FAILED
        elif result.task_state == TaskState.CANCELLED:
            rec["module_state"] = ModuleState.CANCELLED
        elif result.task_state == TaskState.RECOVERING:
            rec["module_state"] = ModuleState.RUNNING
        else:
            rec["module_state"] = ModuleState.RUNNING
        return []

    def set_module_state(self, module_task_id: str, state: ModuleState) -> None:
        """Core-only write for non-execution module progress."""
        self.record(module_task_id)["module_state"] = state

    def derive_from_evidence(
        self, module_task_id: str, evidence_sources: List[str]
    ) -> None:
        """Block completion when evidence is only inference / assumption."""
        rec = self.record(module_task_id)
        sources = {EvidenceSource(s) for s in evidence_sources}
        if sources and sources.issubset(EvidenceSource.non_conclusive()):
            rec["module_state"] = ModuleState.BLOCKED
            rec.setdefault("limitations", []).append(
                "completion blocked: evidence is only inference or pending assumption"
            )

    def snapshot(self, module_task_id: str) -> Dict[str, Any]:
        rec = dict(self.record(module_task_id))
        exec_result = rec.get("execution")
        if exec_result is not None:
            rec["execution"] = {
                "tool_task_id": exec_result.tool_task_id,
                "task_state": exec_result.task_state.value,
                "error": exec_result.error,
            }
        return rec


def state_mapping_check() -> Dict[str, bool]:
    """Self-check of the IF0 section 5.2 mapping table."""
    s = StateStore()
    s.dispatch("m")
    s.present("m")
    a = s.snapshot("m")
    s.resolve("m", "APPROVED")
    b = s.snapshot("m")
    s.finish_execution("m", ExecutionResult("task-1", TaskState.COMPLETED))
    c = s.snapshot("m")
    return {
        "presented_maps_to_waiting": (
            a["interaction_state"] == InteractionState.PRESENTED
            and a["module_state"] == ModuleState.WAITING_FOR_USER
        ),
        "approved_is_not_executed": (
            b["interaction_state"] == InteractionState.APPROVED
            and b["task_state"] == TaskState.READY
        ),
        "execution_completes": (
            c["interaction_state"] == InteractionState.EXECUTED
            and c["task_state"] == TaskState.COMPLETED
            and c["module_state"] == ModuleState.COMPLETED
        ),
    }
