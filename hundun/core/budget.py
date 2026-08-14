"""
Budget model and BudgetGuard — sole authority on resource consumption.
See specs/TRANSACTIONS.md and Hardening TZ §5.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional, Any
from enum import Enum
import threading
import time
import uuid

from .errors import BudgetExhausted, ContractViolation


class ResourceType(str, Enum):
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    COST_UNITS = "cost_units"
    WALL_CLOCK = "wall_clock"
    SEARCH_AGAIN = "search_again"
    FRAME_REVISION = "frame_revision"
    REPAIR = "repair"
    VETO_OVERRIDE = "veto_override"
    TOTAL_TRANSITIONS = "total_transitions"


@dataclass
class BudgetLimits:
    max_llm_calls: int = 12
    max_tool_calls: int = 16
    max_cost_units: float = 10.0
    max_wall_clock_ms: int = 120_000
    max_search_again: int = 2
    max_frame_revision: int = 1
    max_repair: int = 1
    max_veto_override: int = 1
    max_total_transitions: int = 40


@dataclass
class BudgetCounters:
    llm_calls: int = 0
    tool_calls: int = 0
    cost_units: float = 0.0
    wall_clock_ms: int = 0
    search_again_count: int = 0
    frame_revision_count: int = 0
    repair_count: int = 0
    veto_override_count: int = 0
    total_transitions: int = 0

    def remaining(self, limits: BudgetLimits) -> Dict[str, Any]:
        return {
            "llm_calls": limits.max_llm_calls - self.llm_calls,
            "tool_calls": limits.max_tool_calls - self.tool_calls,
            "cost_units": limits.max_cost_units - self.cost_units,
            "wall_clock_ms": limits.max_wall_clock_ms - self.wall_clock_ms,
            "search_again": limits.max_search_again - self.search_again_count,
            "frame_revision": limits.max_frame_revision - self.frame_revision_count,
            "repair": limits.max_repair - self.repair_count,
            "veto_override": limits.max_veto_override - self.veto_override_count,
            "total_transitions": limits.max_total_transitions - self.total_transitions,
        }


@dataclass
class ReservationToken:
    token_id: str
    request_id: str
    resource: ResourceType
    amount: float
    reserved_at: float = field(default_factory=time.time)
    committed: bool = False
    released: bool = False


class BudgetGuard:
    """
    Sole runtime authority on resource consumption.
    No component may call LLM/tool without a successful reserve().
    """

    def __init__(self, request_id: str, limits: Optional[BudgetLimits] = None):
        self.request_id = request_id
        self.limits = limits or BudgetLimits()
        self.counters = BudgetCounters()
        self._lock = threading.RLock()
        self._reservations: Dict[str, ReservationToken] = {}
        self._start_time = time.time()
        self._exhausted = False

    def _check_wall_clock(self) -> None:
        elapsed = int((time.time() - self._start_time) * 1000)
        self.counters.wall_clock_ms = elapsed
        if elapsed >= self.limits.max_wall_clock_ms:
            self._exhausted = True
            raise BudgetExhausted(
                f"Wall clock exceeded ({elapsed}ms >= {self.limits.max_wall_clock_ms}ms)",
                request_id=self.request_id,
                budget_remaining=self.counters.remaining(self.limits),
                counters=self.counters.__dict__,
            )

    def remaining(self) -> Dict[str, Any]:
        with self._lock:
            self._check_wall_clock()
            return self.counters.remaining(self.limits)

    def is_exhausted(self) -> bool:
        with self._lock:
            try:
                self._check_wall_clock()
            except BudgetExhausted:
                return True
            rem = self.counters.remaining(self.limits)
            return any(v <= 0 for v in [
                rem["llm_calls"], rem["tool_calls"], rem["cost_units"],
                rem["total_transitions"]
            ]) or self._exhausted

    def reserve(self, resource: ResourceType, amount: float = 1.0) -> ReservationToken:
        """
        Atomically reserve resource. Raises BudgetExhausted if not available.
        Physical denial — caller must not proceed without a valid token.
        """
        with self._lock:
            if self._exhausted:
                raise BudgetExhausted(
                    "Budget already exhausted",
                    request_id=self.request_id,
                    budget_remaining=self.counters.remaining(self.limits),
                )

            self._check_wall_clock()

            if resource == ResourceType.LLM_CALL:
                if self.counters.llm_calls + amount > self.limits.max_llm_calls:
                    self._exhausted = True
                    raise BudgetExhausted(
                        f"LLM call limit reached ({self.counters.llm_calls}/{self.limits.max_llm_calls})",
                        request_id=self.request_id,
                        budget_remaining=self.counters.remaining(self.limits),
                        counters=self.counters.__dict__,
                    )
            elif resource == ResourceType.TOOL_CALL:
                if self.counters.tool_calls + amount > self.limits.max_tool_calls:
                    self._exhausted = True
                    raise BudgetExhausted(
                        f"Tool call limit reached ({self.counters.tool_calls}/{self.limits.max_tool_calls})",
                        request_id=self.request_id,
                        budget_remaining=self.counters.remaining(self.limits),
                        counters=self.counters.__dict__,
                    )
            elif resource == ResourceType.COST_UNITS:
                if self.counters.cost_units + amount > self.limits.max_cost_units:
                    self._exhausted = True
                    raise BudgetExhausted(
                        f"Cost units limit reached ({self.counters.cost_units}/{self.limits.max_cost_units})",
                        request_id=self.request_id,
                        budget_remaining=self.counters.remaining(self.limits),
                        counters=self.counters.__dict__,
                    )
            elif resource == ResourceType.SEARCH_AGAIN:
                if self.counters.search_again_count + amount > self.limits.max_search_again:
                    raise BudgetExhausted(
                        f"Search again limit reached ({self.counters.search_again_count}/{self.limits.max_search_again})",
                        request_id=self.request_id,
                        budget_remaining=self.counters.remaining(self.limits),
                    )
            elif resource == ResourceType.FRAME_REVISION:
                if self.counters.frame_revision_count + amount > self.limits.max_frame_revision:
                    raise BudgetExhausted(
                        f"Frame revision limit reached",
                        request_id=self.request_id,
                    )
            elif resource == ResourceType.REPAIR:
                if self.counters.repair_count + amount > self.limits.max_repair:
                    raise BudgetExhausted(
                        f"Repair limit reached",
                        request_id=self.request_id,
                    )
            elif resource == ResourceType.VETO_OVERRIDE:
                if self.counters.veto_override_count + amount > self.limits.max_veto_override:
                    raise BudgetExhausted(
                        f"Veto override limit reached",
                        request_id=self.request_id,
                    )
            elif resource == ResourceType.TOTAL_TRANSITIONS:
                if self.counters.total_transitions + amount > self.limits.max_total_transitions:
                    self._exhausted = True
                    raise BudgetExhausted(
                        f"Total transitions limit reached",
                        request_id=self.request_id,
                    )

            self._apply_increment(resource, amount)

            token = ReservationToken(
                token_id=str(uuid.uuid4()),
                request_id=self.request_id,
                resource=resource,
                amount=amount,
            )
            self._reservations[token.token_id] = token
            return token

    def _apply_increment(self, resource: ResourceType, amount: float) -> None:
        if resource == ResourceType.LLM_CALL:
            self.counters.llm_calls += int(amount)
        elif resource == ResourceType.TOOL_CALL:
            self.counters.tool_calls += int(amount)
        elif resource == ResourceType.COST_UNITS:
            self.counters.cost_units += amount
        elif resource == ResourceType.SEARCH_AGAIN:
            self.counters.search_again_count += int(amount)
        elif resource == ResourceType.FRAME_REVISION:
            self.counters.frame_revision_count += int(amount)
        elif resource == ResourceType.REPAIR:
            self.counters.repair_count += int(amount)
        elif resource == ResourceType.VETO_OVERRIDE:
            self.counters.veto_override_count += int(amount)
        elif resource == ResourceType.TOTAL_TRANSITIONS:
            self.counters.total_transitions += int(amount)

    def commit(self, token: ReservationToken, actual_consumption: Optional[float] = None) -> None:
        with self._lock:
            if token.token_id not in self._reservations:
                raise ContractViolation(
                    f"Unknown reservation token {token.token_id}",
                    request_id=self.request_id,
                )
            if token.committed or token.released:
                return
            token.committed = True
            del self._reservations[token.token_id]

    def release(self, token: ReservationToken) -> None:
        """Return reserved amount on failure/timeout."""
        with self._lock:
            if token.token_id not in self._reservations:
                return
            if token.committed or token.released:
                return
            self._apply_increment(token.resource, -token.amount)
            token.released = True
            del self._reservations[token.token_id]

    def view(self) -> Dict[str, Any]:
        """Read-only view for agents (they cannot mutate)."""
        with self._lock:
            return {
                "request_id": self.request_id,
                "limits": self.limits.__dict__,
                "counters": self.counters.__dict__,
                "remaining": self.remaining(),
                "exhausted": self._exhausted,
            }
