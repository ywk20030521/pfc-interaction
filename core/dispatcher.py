"""IF0 sections 2-3: Core dispatcher implementing I1-I6.

The dispatcher is the ONLY entry point for user interaction and PFC execution.
Modules receive Dispatch, return Result, and may request decisions/execution/iteration.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

from .contract import (
    CONTRACT_VERSION,
    ArtifactRef,
    DecisionRef,
    DeliveryStatus,
    Envelope,
    EvidenceSource,
    ModuleID,
    validate_envelope_dict,
)
from .decisions import Authorization, DecisionKey, DecisionRegistry, evidence_chain
from .state_machine import (
    ExecutionResult,
    InteractionState,
    ModuleState,
    StateStore,
    TaskState,
)
from .storage import ArtifactStore
from .gates import (
    ApprovalLedger,
    GateDecision,
    check_stage_gate,
)


class Executor(Protocol):
    """Injected execution channel. Real adapter wraps itasca-mcp tools."""

    def execute(self, request: Dict[str, Any]) -> ExecutionResult: ...


class RecordingExecutor:
    """Test/default executor: records requests without claiming real execution."""

    def __init__(self) -> None:
        self.requests: List[Dict[str, Any]] = []

    def execute(self, request: Dict[str, Any]) -> ExecutionResult:
        self.requests.append(dict(request))
        return ExecutionResult(
            tool_task_id="recorded-" + uuid.uuid4().hex[:8],
            task_state=TaskState.COMPLETED,
            output_artifacts=[],
            error=None,
        )


@dataclass
class DispatchRequest:
    research_task_id: str
    module_id: ModuleID
    input_refs: List[ArtifactRef] = field(default_factory=list)
    context_version: str = "cv1"
    authorizations: List[Authorization] = field(default_factory=list)
    parent_task_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_version": CONTRACT_VERSION,
            "research_task_id": self.research_task_id,
            "module_task_id": None,
            "module_id": self.module_id.value,
            "input_refs": [r.to_dict() for r in self.input_refs],
            "context_version": self.context_version,
            "authorizations": [a.to_dict() for a in self.authorizations],
            "parent_task_id": self.parent_task_id,
            "payload": self.payload,
        }


class CoreDispatcher:
    def __init__(self, artifact_store: ArtifactStore, executor: Optional[Executor] = None):
        self.store = artifact_store
        self.executor: Executor = executor or RecordingExecutor()
        self.decisions = DecisionRegistry()
        self.states = StateStore()
        self.approvals = ApprovalLedger()
        self._module_tasks: Dict[str, DispatchRequest] = {}
        self._envelopes: Dict[str, Envelope] = {}
        self._chains: Dict[str, Dict[str, Any]] = {}
        self._module_runners: Dict[str, Callable[[DispatchRequest, "CoreDispatcher"], Envelope]] = {}
        # 4.1 strict stage gates are opt-in: the 4.0 regression suite uses the
        # base class unchanged. V41CoreDispatcher flips this on.
        self.strict_gates = False

    def register_module(
        self,
        module_id: ModuleID,
        runner: Callable[[str, DispatchRequest, "CoreDispatcher"], Envelope],
    ) -> None:
        self._module_runners[module_id.value] = runner

    # ---- I1 Dispatch -------------------------------------------------
    def _gate_check(self, request: DispatchRequest) -> Optional[GateDecision]:
        """Hook for strict subclasses. Base dispatcher enforces nothing (4.0)."""
        return None

    def _blocked_envelope(
        self, request: DispatchRequest, gate: GateDecision
    ) -> Envelope:
        """Return a BLOCKED envelope without ever invoking the module runner."""
        return Envelope(
            module_id=request.module_id,
            module_version="4.1.0-alpha",
            research_task_id=request.research_task_id,
            module_task_id="BLOCKED-" + uuid.uuid4().hex[:6],
            parent_task_id=request.parent_task_id,
            input_refs=request.input_refs,
            status={"module_state": "BLOCKED", "gate": gate.to_dict()},
            output={
                "structured": {
                    "module_state": "BLOCKED",
                    "gate": gate.to_dict(),
                },
                "artifacts": [],
                "verified_by_execution": False,
            },
            evidence=[],
            decisions=[],
            limitations=[gate.reason] + list(gate.missing),
        )

    def dispatch(self, request: DispatchRequest) -> Tuple[Optional[Envelope], List[str]]:
        errors: List[str] = []
        for ref in request.input_refs:
            if not self.store.verify(ref):
                errors.append("unresolvable input artifact: %s" % ref.artifact_id)
        if errors:
            return None, errors
        gate = self._gate_check(request)
        if gate is not None and not gate.allowed:
            return self._blocked_envelope(request, gate), [
                "%s: %s" % (gate.reason, "; ".join(gate.missing))
            ]
        module_task_id = "%s-%s" % (request.module_id.value, uuid.uuid4().hex[:6])
        request_dict = request.to_dict()
        request_dict["module_task_id"] = module_task_id
        self._module_tasks[module_task_id] = request
        self.states.dispatch(module_task_id)
        runner = self._module_runners.get(request.module_id.value)
        if runner is None:
            return None, ["no runner registered for %s" % request.module_id.value]
        envelope = runner(module_task_id, request, self)
        self._envelopes[module_task_id] = envelope
        return envelope, envelope.validate()

    # ---- I2 Result ---------------------------------------------------
    def accept_result(self, envelope: Envelope) -> List[str]:
        errors = envelope.validate()
        if errors:
            return errors
        mid = envelope.module_task_id
        if mid not in self._module_tasks:
            return ["module task not dispatched: %s" % mid]
        # Never accept a module claim of execution success.
        if envelope.output.get("verified_by_execution"):
            errors.append("module must not claim verified_by_execution; only I5 may set it")
        for artifact in envelope.output.get("artifacts", []):
            ref = ArtifactRef.from_dict(artifact)
            if not self.store.verify(ref):
                errors.append("output artifact unverifiable: %s" % ref.artifact_id)
        evidence_sources = [e.source.value for e in envelope.evidence]
        if evidence_sources:
            self.states.derive_from_evidence(mid, evidence_sources)
        self._envelopes[mid] = envelope
        return errors

    # ---- I3 DecisionRequest ------------------------------------------
    def request_decision(
        self,
        key: DecisionKey,
        question: str,
        options: List[str],
        blocks_module_task_id: str,
        evidence_refs: Optional[List[str]] = None,
        authorization_scope: Optional[str] = None,
        channel: Optional[str] = None,
        question_set: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[Dict[str, Any], bool, str]:
        item, should_present, reason = self.decisions.request(
            key=key,
            question=question,
            options=options,
            blocks_module_task_id=blocks_module_task_id,
            evidence_refs=evidence_refs,
            authorization_scope=authorization_scope,
            question_set=question_set,
        )
        if should_present:
            self.decisions.present(item.decision_id, channel=channel)
            self.states.present(blocks_module_task_id)
        return item.to_dict(), should_present, reason

    # ---- I4 DecisionResolution ---------------------------------------
    def resolve_decision(
        self,
        decision_id: str,
        resolution: str,
        context_version: Optional[str] = None,
        answers: Optional[Dict[str, Any]] = None,
        channel: Optional[str] = None,
    ) -> Dict[str, Any]:
        item_snapshot = self.decisions.snapshot(decision_id)
        current = context_version or item_snapshot["key"]["context_version"]
        auth = self.decisions.resolve(decision_id, resolution, current, answers=answers)
        # Record every resolution in the approval ledger. Only Core can write
        # it; a module or E2E script cannot manufacture an approval record.
        item = self.decisions._get(decision_id)
        if channel:
            item.channel = channel
        self.approvals.record_resolution(item, resolution, current, answers, channel)
        self.states.resolve(item.blocks_module_task_id, resolution)
        return {
            "decision_id": decision_id,
            "resolution": resolution,
            "authorization_id": auth.authorization_id if auth else None,
            "bound_context_version": current,
            "resolved_at": auth.created_at if auth else None,
            "answers_recorded": answers is not None,
        }

    # ---- I5 Execution ------------------------------------------------
    def execute(
        self,
        module_task_id: str,
        operation: str,
        model_ref: Optional[str],
        case_id: Optional[str],
        authorization_id: str,
        scope: str,
        context_version: str,
        code: Optional[str] = None,
    ) -> Tuple[Optional[ExecutionResult], List[str]]:
        valid, reason = self.decisions.valid_authorization(
            authorization_id, context_version, scope
        )
        if not valid:
            return None, ["execution denied: %s" % reason]
        request = {
            "requester_module_id": self._module_tasks[module_task_id].module_id.value,
            "module_task_id": module_task_id,
            "operation": operation,
            "model_ref": model_ref,
            "case_id": case_id,
            "authorization_id": authorization_id,
            "expected_effect": scope,
            "code": code,
        }
        self.states.start_execution(module_task_id)
        result = self.executor.execute(request)
        errors = self.states.finish_execution(module_task_id, result)
        if not errors:
            self._chains[module_task_id] = evidence_chain(
                decision_id=self.decisions._get(
                    self.decisions._authorizations[authorization_id].decision_id
                ).decision_id,
                authorization_id=authorization_id,
                tool_task_id=result.tool_task_id,
                evidence_id="e-" + result.tool_task_id,
                artifact_id=(
                    result.output_artifacts[0]["artifact_id"]
                    if result.output_artifacts
                    else None
                ),
            )
        return result, errors

    # ---- I6 Iteration ------------------------------------------------
    def iterate(
        self,
        source_module: ModuleID,
        target_module: ModuleID,
        trigger_layer: str,
        evidence_refs: List[str],
        context_version: str,
        changes_research_assumption: bool,
        parent_task_id: str,
    ) -> Dict[str, Any]:
        if not evidence_refs:
            raise ValueError("iteration requires evidence_refs")
        parent = self._module_tasks.get(parent_task_id)
        if parent is None:
            raise KeyError("parent task not found: %s" % parent_task_id)
        child = DispatchRequest(
            research_task_id=parent.research_task_id,
            module_id=target_module,
            input_refs=parent.input_refs,
            context_version=context_version,
            parent_task_id=parent_task_id,
        )
        return {
            "source_module": source_module.value,
            "target_module": target_module.value,
            "trigger_layer": trigger_layer,
            "evidence_refs": evidence_refs,
            "context_version": context_version,
            "changes_research_assumption": changes_research_assumption,
            "parent_task_id": parent_task_id,
            "new_module_task": child.to_dict(),
            "requires_new_user_approval": changes_research_assumption,
        }

    # ---- Inspection --------------------------------------------------
    def snapshot(self, module_task_id: str) -> Dict[str, Any]:
        return self.states.snapshot(module_task_id)

    def envelope(self, module_task_id: str) -> Optional[Envelope]:
        return self._envelopes.get(module_task_id)

    def chain(self, module_task_id: str) -> Optional[Dict[str, Any]]:
        return self._chains.get(module_task_id)

    def decision_items(self) -> List[Dict[str, Any]]:
        return [self.decisions.snapshot(d) for d in self.decisions._items]


class V41CoreDispatcher(CoreDispatcher):
    """4.1-alpha strict dispatcher.

    Stage gates are enforced in ``dispatch()``: a module whose prerequisite
    approvals are absent from the ledger is returned as BLOCKED and its runner
    is never invoked. This closes the C16/synthetic-approval bypass.
    """

    def __init__(self, artifact_store: ArtifactStore, executor: Optional[Executor] = None):
        super().__init__(artifact_store, executor)
        self.strict_gates = True

    def _gate_check(self, request: DispatchRequest) -> Optional[GateDecision]:
        return check_stage_gate(
            request.module_id,
            request.research_task_id,
            request.context_version,
            self.approvals,
        )

    def request_decision(self, key: DecisionKey, question: str, options: List[str],
                         blocks_module_task_id: str, evidence_refs=None,
                         authorization_scope=None, channel=None, question_set=None):
        """BUG-T03b fix: execution authorizations must bind the run_model scope.

        Without this, an `authorize_execution` approval carries an empty scope
        and a later I5 `scope="run_model"` call is rejected. The 4.1 strict
        dispatcher closes that gap automatically instead of relying on every
        caller to remember the scope.
        """
        if key.topic == "authorize_execution" and authorization_scope is None:
            authorization_scope = "run_model"
        return super().request_decision(
            key, question, options, blocks_module_task_id, evidence_refs,
            authorization_scope, channel, question_set,
        )

    def approve(
        self,
        decision_id: str,
        resolution: str = "APPROVED",
        context_version: Optional[str] = None,
        answers: Optional[Dict[str, Any]] = None,
        channel: Optional[str] = "NATIVE_CHAT",
    ) -> Dict[str, Any]:
        """Explicit, audited approval entry point for the orchestrating Agent.

        The Agent must pass the operator's actual ``answers``. There is no
        shortcut that approves without a decision item and a ledger record.
        """
        item = self.decisions._get(decision_id)
        if item.delivery_status.value == "UNDELIVERED":
            # Must be presented before it can be resolved.
            self.decisions.present(decision_id, channel=channel)
            self.states.present(item.blocks_module_task_id)
        return self.resolve_decision(
            decision_id, resolution, context_version, answers, channel
        )

