"""
Minimal hardened runtime orchestrator.
Wires FSM + BudgetGuard + DecisionFrame store + Isolation + Frame Integrity.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import uuid
import time
import hashlib

from .fsm import FSMEngine, FSMContext, State, TERMINAL_STATES
from .budget import BudgetGuard, BudgetLimits, ResourceType
from .decision_frame import DecisionFrameStore, DecisionFrame, FrameStatus, FrameLevel
from .isolation import ToolSessionManager, SessionType, LessonVisibilityFilter
from .frame_integrity import FrameIntegrityGate, ResponderDeclaration, IntegrityResult
from .errors import (
    HundunError, BudgetExhausted, ContractViolation, IsolationBroken,
    FrameMismatch, SchemaViolation, TerminalState,
)


@dataclass
class RequestResult:
    request_id: str
    terminal_state: str
    decision_frame: Optional[Dict[str, Any]] = None
    integrity: Optional[Dict[str, Any]] = None
    budget_final: Optional[Dict[str, Any]] = None
    provenance: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[Dict[str, Any]] = None


class HundunRuntime:
    """Entry point for a single request. Enforces all P0 contracts."""

    def __init__(self, limits: Optional[BudgetLimits] = None):
        self.fsm = FSMEngine()
        self.frame_store = DecisionFrameStore()
        self.session_manager = ToolSessionManager()
        self.integrity_gate = FrameIntegrityGate()
        self.default_limits = limits or BudgetLimits()

    def _pin_snapshot(self, request_id: str) -> str:
        raw = f"{request_id}:{time.time()}:v3.2"
        return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()[:16]

    def start_request(self, user_request: str, risk_class: int = 2, limits: Optional[BudgetLimits] = None) -> FSMContext:
        request_id = f"req-{uuid.uuid4().hex[:12]}"
        budget = BudgetGuard(request_id, limits or self.default_limits)
        snapshot_id = self._pin_snapshot(request_id)

        ctx = FSMContext(
            request_id=request_id,
            state=State.REQUEST_CREATED,
            budget=budget,
            data={
                "user_request": user_request,
                "risk_class": risk_class,
                "snapshot_id": snapshot_id,
                "isolation_status": "strict",
            },
        )
        ctx.log("request_created", snapshot_id=snapshot_id)
        return ctx

    def run_classify(self, ctx: FSMContext) -> State:
        self.fsm.transition(ctx, "classify")
        if ctx.data["risk_class"] <= 1:
            return self.fsm.transition(ctx, "risk_low")
        return self.fsm.transition(ctx, "risk_high")

    def run_frame_analyze(self, ctx: FSMContext) -> State:
        ctx.data["candidate_frames"] = ["conservative", "structural"]
        return self.fsm.transition(ctx, "frames_ready")

    def run_fourth_phase1(self, ctx: FSMContext) -> State:
        if ctx.state == State.FRAME_PROPOSED:
            self.fsm.transition(ctx, "start_blind")

        session = self.session_manager.open(ctx.request_id, SessionType.FOURTH_BLIND)
        ctx.data["fourth_blind_session_id"] = session.session_id

        token = ctx.budget.reserve(ResourceType.LLM_CALL)
        try:
            ctx.data["blind_frame_proposal"] = {
                "statement": "alternative frame from blind fourth",
                "level": "L2",
            }
            ctx.data["isolation_status"] = "strict"
            ctx.budget.commit(token)
        except Exception:
            ctx.budget.release(token)
            raise

        return self.fsm.transition(ctx, "blind_proposal")

    def commit_decision_frame(
        self,
        ctx: FSMContext,
        *,
        frame_level: FrameLevel,
        decision_target: str,
        causal_object: str,
        objective: str,
        rejected_surface_problem: str,
        required_decision_scope: str,
        success_criteria: Optional[List[str]] = None,
        constraints: Optional[List[str]] = None,
    ) -> DecisionFrame:
        frame = self.frame_store.begin(ctx.request_id, ctx.data["snapshot_id"])
        frame.frame_level = frame_level
        frame.decision_target = decision_target
        frame.causal_object = causal_object
        frame.objective = objective
        frame.rejected_surface_problem = rejected_surface_problem
        frame.required_decision_scope = required_decision_scope
        frame.success_criteria = success_criteria or []
        frame.constraints = constraints or []
        frame.provenance = {"arbitrated_at": time.time()}

        self.frame_store.validate(frame.frame_id)
        committed = self.frame_store.commit(frame.frame_id)
        ctx.data["decision_frame_status"] = "COMMITTED"
        ctx.data["decision_frame_id"] = committed.frame_id
        return committed

    def run_arbitrate_and_commit(self, ctx: FSMContext, **frame_kwargs) -> State:
        self.fsm.transition(ctx, "frame_selected")
        self.commit_decision_frame(ctx, **frame_kwargs)
        if ctx.state != State.DECISION_FRAME_COMMITTED:
            ctx.state = State.DECISION_FRAME_COMMITTED
            ctx.log("decision_frame_committed")
        return self.fsm.transition(ctx, "start_solve")

    def run_solve_and_integrity(self, ctx: FSMContext, responder: ResponderDeclaration) -> IntegrityResult:
        session = self.session_manager.open(ctx.request_id, SessionType.RESPONDER)
        ctx.data["responder_session_id"] = session.session_id

        token = ctx.budget.reserve(ResourceType.LLM_CALL)
        try:
            ctx.data["responder_declaration"] = responder
            ctx.budget.commit(token)
        except Exception:
            ctx.budget.release(token)
            raise

        self.fsm.transition(ctx, "answer_ready")
        self.fsm.transition(ctx, "evidence_ready")
        self.fsm.transition(ctx, "dissent_ready")
        self.fsm.transition(ctx, "proceed")

        frame = self.frame_store.get_committed(ctx.request_id)
        result = self.integrity_gate.check(frame, responder)
        return result

    def finish_integrity(self, ctx: FSMContext, result: IntegrityResult) -> State:
        if result.passed:
            return self.fsm.transition(ctx, "pass")
        if (
            not ctx.budget.is_exhausted()
            and ctx.budget.counters.repair_count < ctx.budget.limits.max_repair
        ):
            return self.fsm.transition(ctx, "mismatch")
        return self.fsm.transition(ctx, "mismatch_terminal")

    def finalize(self, ctx: FSMContext, event: str = "accept") -> RequestResult:
        try:
            self.fsm.transition(ctx, event)
        except (BudgetExhausted, ContractViolation) as e:
            self.fsm.force_terminal(
                ctx,
                State.TERMINAL_UNCERTAIN if isinstance(e, BudgetExhausted) else State.TERMINAL_ERROR,
                str(e),
            )
            return self._result(ctx, error=e)

        self.session_manager.close_all_for_request(ctx.request_id)
        return self._result(ctx)

    def _result(self, ctx: FSMContext, error: Optional[HundunError] = None) -> RequestResult:
        df = None
        try:
            df = self.frame_store.get_public(ctx.request_id)
        except Exception:
            pass
        return RequestResult(
            request_id=ctx.request_id,
            terminal_state=ctx.state.value,
            decision_frame=df,
            budget_final=ctx.budget.view(),
            provenance=ctx.history,
            error=error.to_provenance() if error else None,
        )
