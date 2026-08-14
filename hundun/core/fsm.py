"""
Formal Finite State Machine — single source of truth for orchestration.
See specs/FSM.md
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Set
import time

from .errors import ContractViolation, BudgetExhausted, HundunError, TerminalState
from .budget import BudgetGuard, ResourceType


class State(str, Enum):
    REQUEST_CREATED = "REQUEST_CREATED"
    CLASSIFY = "CLASSIFY"
    FRAME_ANALYZE = "FRAME_ANALYZE"
    FRAME_PROPOSED = "FRAME_PROPOSED"
    FRAME_ARBITRATE = "FRAME_ARBITRATE"
    DECISION_FRAME_COMMITTED = "DECISION_FRAME_COMMITTED"
    SOLVE = "SOLVE"
    EVIDENCE = "EVIDENCE"
    DISSENT = "DISSENT"
    FOURTH_PHASE_1 = "FOURTH_PHASE_1"
    FOURTH_PHASE_2 = "FOURTH_PHASE_2"
    FINAL_COMPARE = "FINAL_COMPARE"
    FRAME_INTEGRITY_CHECK = "FRAME_INTEGRITY_CHECK"
    FINAL_ARBITRATE = "FINAL_ARBITRATE"
    SEARCH_AGAIN = "SEARCH_AGAIN"
    REPAIR_OR_REVIEW = "REPAIR_OR_REVIEW"
    TERMINAL_SUCCESS = "TERMINAL_SUCCESS"
    TERMINAL_UNCERTAIN = "TERMINAL_UNCERTAIN"
    TERMINAL_REFUSE = "TERMINAL_REFUSE"
    TERMINAL_ASK_USER = "TERMINAL_ASK_USER"
    TERMINAL_ERROR = "TERMINAL_ERROR"


TERMINAL_STATES: Set[State] = {
    State.TERMINAL_SUCCESS,
    State.TERMINAL_UNCERTAIN,
    State.TERMINAL_REFUSE,
    State.TERMINAL_ASK_USER,
    State.TERMINAL_ERROR,
}


@dataclass
class Transition:
    event: str
    guard: Optional[Callable[["FSMContext"], bool]] = None
    next_state: State = State.TERMINAL_ERROR
    side_effect: Optional[Callable[["FSMContext"], None]] = None
    timeout_ms: int = 30_000
    on_failure: State = State.TERMINAL_ERROR


@dataclass
class FSMContext:
    request_id: str
    state: State
    budget: BudgetGuard
    data: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    def log(self, event: str, **kwargs) -> None:
        self.history.append({
            "state": self.state.value,
            "event": event,
            "ts": time.time(),
            **kwargs,
        })


class FSMEngine:
    """
    The only component allowed to change request state.
    All transitions are explicit. Illegal transitions raise ContractViolation.
    """

    def __init__(self):
        self._transitions: Dict[State, Dict[str, Transition]] = {}
        self._register_default_transitions()

    def _add(self, state: State, transition: Transition) -> None:
        if state not in self._transitions:
            self._transitions[state] = {}
        self._transitions[state][transition.event] = transition

    def _register_default_transitions(self) -> None:
        self._add(State.REQUEST_CREATED, Transition(
            event="classify",
            next_state=State.CLASSIFY,
            side_effect=lambda ctx: ctx.budget.reserve(ResourceType.TOTAL_TRANSITIONS),
        ))

        self._add(State.CLASSIFY, Transition(
            event="risk_low",
            guard=lambda ctx: ctx.data.get("risk_class", 2) <= 1,
            next_state=State.SOLVE,
        ))
        self._add(State.CLASSIFY, Transition(
            event="risk_high",
            guard=lambda ctx: ctx.data.get("risk_class", 2) >= 2,
            next_state=State.FRAME_ANALYZE,
        ))

        self._add(State.FRAME_ANALYZE, Transition(
            event="frames_ready",
            next_state=State.FRAME_PROPOSED,
        ))

        self._add(State.FRAME_PROPOSED, Transition(
            event="start_blind",
            guard=lambda ctx: not ctx.budget.is_exhausted(),
            next_state=State.FOURTH_PHASE_1,
        ))

        self._add(State.FOURTH_PHASE_1, Transition(
            event="blind_proposal",
            guard=lambda ctx: ctx.data.get("isolation_status") == "strict",
            next_state=State.FRAME_ARBITRATE,
            on_failure=State.TERMINAL_ERROR,
        ))

        self._add(State.FRAME_ARBITRATE, Transition(
            event="frame_selected",
            next_state=State.DECISION_FRAME_COMMITTED,
        ))
        self._add(State.FRAME_ARBITRATE, Transition(
            event="unresolved",
            next_state=State.TERMINAL_UNCERTAIN,
        ))

        self._add(State.DECISION_FRAME_COMMITTED, Transition(
            event="start_solve",
            guard=lambda ctx: ctx.data.get("decision_frame_status") == "COMMITTED",
            next_state=State.SOLVE,
            on_failure=State.TERMINAL_ERROR,
        ))

        self._add(State.SOLVE, Transition(
            event="answer_ready",
            next_state=State.EVIDENCE,
        ))

        self._add(State.EVIDENCE, Transition(
            event="evidence_ready",
            next_state=State.DISSENT,
        ))
        self._add(State.DISSENT, Transition(
            event="dissent_ready",
            next_state=State.FINAL_COMPARE,
        ))
        self._add(State.FINAL_COMPARE, Transition(
            event="proceed",
            next_state=State.FRAME_INTEGRITY_CHECK,
        ))

        self._add(State.FRAME_INTEGRITY_CHECK, Transition(
            event="pass",
            next_state=State.FINAL_ARBITRATE,
        ))
        self._add(State.FRAME_INTEGRITY_CHECK, Transition(
            event="mismatch",
            guard=lambda ctx: (
                not ctx.budget.is_exhausted()
                and ctx.budget.counters.repair_count < ctx.budget.limits.max_repair
            ),
            next_state=State.REPAIR_OR_REVIEW,
            side_effect=lambda ctx: ctx.budget.reserve(ResourceType.REPAIR),
        ))
        self._add(State.FRAME_INTEGRITY_CHECK, Transition(
            event="mismatch_terminal",
            next_state=State.TERMINAL_UNCERTAIN,
        ))

        self._add(State.FINAL_ARBITRATE, Transition(
            event="accept",
            next_state=State.TERMINAL_SUCCESS,
        ))
        self._add(State.FINAL_ARBITRATE, Transition(
            event="search_again",
            guard=lambda ctx: (
                ctx.budget.counters.search_again_count < ctx.budget.limits.max_search_again
                and not ctx.budget.is_exhausted()
            ),
            next_state=State.SEARCH_AGAIN,
            side_effect=lambda ctx: ctx.budget.reserve(ResourceType.SEARCH_AGAIN),
            on_failure=State.TERMINAL_UNCERTAIN,
        ))
        self._add(State.FINAL_ARBITRATE, Transition(
            event="refuse",
            next_state=State.TERMINAL_REFUSE,
        ))
        self._add(State.FINAL_ARBITRATE, Transition(
            event="ask_user",
            next_state=State.TERMINAL_ASK_USER,
        ))

        self._add(State.SEARCH_AGAIN, Transition(
            event="research_done",
            next_state=State.FRAME_INTEGRITY_CHECK,
        ))

        self._add(State.REPAIR_OR_REVIEW, Transition(
            event="repaired",
            next_state=State.FINAL_ARBITRATE,
        ))
        self._add(State.REPAIR_OR_REVIEW, Transition(
            event="still_mismatch",
            next_state=State.TERMINAL_UNCERTAIN,
        ))

        for s in State:
            if s not in TERMINAL_STATES:
                self._add(s, Transition(
                    event="budget_exhausted",
                    next_state=State.TERMINAL_UNCERTAIN,
                ))
                self._add(s, Transition(
                    event="contract_violation",
                    next_state=State.TERMINAL_ERROR,
                ))
                self._add(s, Transition(
                    event="isolation_broken",
                    next_state=State.TERMINAL_ERROR,
                ))

    def can_transition(self, ctx: FSMContext, event: str) -> bool:
        if ctx.state in TERMINAL_STATES:
            return False
        transitions = self._transitions.get(ctx.state, {})
        if event not in transitions:
            return False
        t = transitions[event]
        if t.guard is not None and not t.guard(ctx):
            return False
        return True

    def transition(self, ctx: FSMContext, event: str) -> State:
        """Execute a transition. Raises ContractViolation on illegal moves."""
        if ctx.state in TERMINAL_STATES:
            raise ContractViolation(
                f"Cannot transition from terminal state {ctx.state.value}",
                request_id=ctx.request_id,
                state_at_failure=ctx.state.value,
            )

        transitions = self._transitions.get(ctx.state, {})
        if event not in transitions:
            raise ContractViolation(
                f"No transition for event '{event}' from state {ctx.state.value}",
                request_id=ctx.request_id,
                state_at_failure=ctx.state.value,
            )

        t = transitions[event]

        if t.guard is not None and not t.guard(ctx):
            if event in ("search_again", "mismatch", "start_blind"):
                ctx.log(event, result="guard_failed", next=t.on_failure.value)
                ctx.state = t.on_failure
                return ctx.state
            raise ContractViolation(
                f"Guard failed for event '{event}' from {ctx.state.value}",
                request_id=ctx.request_id,
                state_at_failure=ctx.state.value,
            )

        if t.side_effect is not None:
            try:
                t.side_effect(ctx)
            except BudgetExhausted:
                ctx.log(event, result="budget_exhausted")
                ctx.state = State.TERMINAL_UNCERTAIN
                return ctx.state

        prev = ctx.state
        ctx.state = t.next_state
        ctx.log(event, from_state=prev.value, to_state=ctx.state.value)
        return ctx.state

    def force_terminal(self, ctx: FSMContext, terminal: State, reason: str) -> None:
        if terminal not in TERMINAL_STATES:
            raise ContractViolation(f"{terminal} is not a terminal state")
        ctx.log("force_terminal", reason=reason, to_state=terminal.value)
        ctx.state = terminal
