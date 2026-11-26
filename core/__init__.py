"""PFC Interaction 4.0 Core runtime - IF0-1.0.0 contract implementation."""

from .contract import (
    CONTRACT_VERSION,
    ArtifactRef,
    DecisionRef,
    DeliveryStatus,
    Envelope,
    Evidence,
    EvidenceSource,
    ModuleID,
    validate_envelope_dict,
)
from .decisions import Authorization, DecisionKey, DecisionRegistry, evidence_chain
from .dispatcher import CoreDispatcher, DispatchRequest, ExecutionResult, RecordingExecutor, V41CoreDispatcher
from .gates import (
    ApprovalLedger, ApprovalRecord, GateDecision, PhysicsResult,
    STAGE_APPROVALS, ALTERNATIVE_APPROVALS, DEFAULT_PHYSICS_THRESHOLDS,
    check_stage_gate, check_physics_gate, check_peak_capture,
)
from .state_machine import (
    InteractionState,
    ModuleState,
    StateStore,
    TaskState,
    state_mapping_check,
)
from .storage import ArtifactStore, hash_bytes, hash_file
from .workflow import (
    InteractionEventType, FEEDBACK_ROUTES, IterationRequest, WorkflowOrchestrator,
)
from .question import (
    Option, Question, Decision, CardType, CardStatus, QuestionPriority,
    AUTHOR_INPUT_NEEDED, DEFER_LABEL, dedup_key, validate_card,
    to_decision_questions, meta_for, apply_answers,
)

__all__ = [
    "CONTRACT_VERSION",
    "ArtifactRef",
    "DecisionRef",
    "DeliveryStatus",
    "Envelope",
    "Evidence",
    "EvidenceSource",
    "ModuleID",
    "validate_envelope_dict",
    "Authorization",
    "DecisionKey",
    "DecisionRegistry",
    "evidence_chain",
    "CoreDispatcher",
    "V41CoreDispatcher",
    "ApprovalLedger",
    "ApprovalRecord",
    "GateDecision",
    "PhysicsResult",
    "STAGE_APPROVALS",
    "ALTERNATIVE_APPROVALS",
    "DEFAULT_PHYSICS_THRESHOLDS",
    "check_stage_gate",
    "check_physics_gate",
    "check_peak_capture",
    "DispatchRequest",
    "ExecutionResult",
    "RecordingExecutor",
    "InteractionState",
    "ModuleState",
    "StateStore",
    "TaskState",
    "state_mapping_check",
    "ArtifactStore",
    "hash_bytes",
    "hash_file",
    "InteractionEventType",
    "FEEDBACK_ROUTES",
    "IterationRequest",
    "WorkflowOrchestrator",
    "Option",
    "Question",
    "Decision",
    "CardType",
    "CardStatus",
    "QuestionPriority",
    "AUTHOR_INPUT_NEEDED",
    "DEFER_LABEL",
    "dedup_key",
    "validate_card",
    "to_decision_questions",
    "meta_for",
    "apply_answers",
]
