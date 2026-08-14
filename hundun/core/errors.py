"""
Error Taxonomy — deterministic fail-closed mapping.
See specs/ERROR_TAXONOMY.md
"""

from __future__ import annotations
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
import time


class ErrorType(str, Enum):
    BUDGET_EXHAUSTED = "BudgetExhausted"
    TIMEOUT = "Timeout"
    CONTRACT_VIOLATION = "ContractViolation"
    ISOLATION_BROKEN = "IsolationBroken"
    SNAPSHOT_CONFLICT = "SnapshotConflict"
    FRAME_MISMATCH = "FrameMismatch"
    EVIDENCE_CONFLICT = "EvidenceConflict"
    TOOL_FAILURE = "ToolFailure"
    ARBITRATION_FAILURE = "ArbitrationFailure"
    SCHEMA_VIOLATION = "SchemaViolation"


class TerminalState(str, Enum):
    SUCCESS = "TERMINAL_SUCCESS"
    UNCERTAIN = "TERMINAL_UNCERTAIN"
    REFUSE = "TERMINAL_REFUSE"
    ASK_USER = "TERMINAL_ASK_USER"
    ERROR = "TERMINAL_ERROR"


ERROR_TO_TERMINAL: Dict[ErrorType, TerminalState] = {
    ErrorType.BUDGET_EXHAUSTED: TerminalState.UNCERTAIN,
    ErrorType.TIMEOUT: TerminalState.ERROR,
    ErrorType.CONTRACT_VIOLATION: TerminalState.ERROR,
    ErrorType.ISOLATION_BROKEN: TerminalState.ERROR,
    ErrorType.SNAPSHOT_CONFLICT: TerminalState.ERROR,
    ErrorType.FRAME_MISMATCH: TerminalState.UNCERTAIN,
    ErrorType.EVIDENCE_CONFLICT: TerminalState.UNCERTAIN,
    ErrorType.TOOL_FAILURE: TerminalState.ASK_USER,
    ErrorType.ARBITRATION_FAILURE: TerminalState.UNCERTAIN,
    ErrorType.SCHEMA_VIOLATION: TerminalState.ERROR,
}


@dataclass
class HundunError(Exception):
    error_type: ErrorType
    message: str
    request_id: Optional[str] = None
    state_at_failure: Optional[str] = None
    budget_remaining: Optional[Dict[str, Any]] = None
    counters: Optional[Dict[str, Any]] = None
    recoverable: bool = False
    timestamp: float = field(default_factory=time.time)

    def __str__(self) -> str:
        return f"[{self.error_type.value}] {self.message}"

    def to_provenance(self) -> Dict[str, Any]:
        return {
            "error_type": self.error_type.value,
            "message": self.message,
            "request_id": self.request_id,
            "state_at_failure": self.state_at_failure,
            "budget_remaining": self.budget_remaining,
            "counters": self.counters,
            "recoverable": self.recoverable,
            "timestamp": self.timestamp,
        }

    def preferred_terminal(self) -> TerminalState:
        return ERROR_TO_TERMINAL.get(self.error_type, TerminalState.ERROR)


class BudgetExhausted(HundunError):
    def __init__(self, message: str = "Budget exhausted", **kwargs):
        super().__init__(ErrorType.BUDGET_EXHAUSTED, message, recoverable=False, **kwargs)


class ContractViolation(HundunError):
    def __init__(self, message: str = "Contract violation", **kwargs):
        super().__init__(ErrorType.CONTRACT_VIOLATION, message, recoverable=False, **kwargs)


class IsolationBroken(HundunError):
    def __init__(self, message: str = "Isolation broken", **kwargs):
        super().__init__(ErrorType.ISOLATION_BROKEN, message, recoverable=False, **kwargs)


class FrameMismatch(HundunError):
    def __init__(self, message: str = "Frame integrity mismatch", **kwargs):
        super().__init__(ErrorType.FRAME_MISMATCH, message, recoverable=True, **kwargs)


class SchemaViolation(HundunError):
    def __init__(self, message: str = "Schema violation", **kwargs):
        super().__init__(ErrorType.SCHEMA_VIOLATION, message, recoverable=False, **kwargs)
