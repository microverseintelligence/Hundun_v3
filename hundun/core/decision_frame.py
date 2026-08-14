"""
Transactional DecisionFrame lifecycle.
Only COMMITTED frames are visible downstream.
See specs/TRANSACTIONS.md and specs/FRAME_INTEGRITY.md
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid
import time

from .errors import SchemaViolation, ContractViolation


class FrameStatus(str, Enum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    COMMITTED = "COMMITTED"
    SUPERSEDED = "SUPERSEDED"


class FrameLevel(str, Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    L5 = "L5"


@dataclass
class FrameTransition:
    from_level: Optional[str] = None
    to_level: Optional[str] = None
    why_previous_frame_failed: Optional[str] = None
    decisive_evidence: List[str] = field(default_factory=list)


@dataclass
class DecisionFrame:
    request_id: str
    frame_id: str = field(default_factory=lambda: f"frame-{uuid.uuid4().hex[:12]}")
    status: FrameStatus = FrameStatus.DRAFT
    frame_level: Optional[FrameLevel] = None
    decision_target: Optional[str] = None
    causal_object: Optional[str] = None
    objective: Optional[str] = None
    constraints: List[str] = field(default_factory=list)
    rejected_surface_problem: Optional[str] = None
    success_criteria: List[str] = field(default_factory=list)
    required_decision_scope: Optional[str] = None
    strongest_counterargument: Optional[str] = None
    frame_transition: Optional[FrameTransition] = None
    remaining_uncertainty: List[str] = field(default_factory=list)
    snapshot_id: Optional[str] = None
    provenance: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    committed_at: Optional[float] = None

    _REQUIRED_FOR_COMMIT = [
        "frame_level",
        "decision_target",
        "causal_object",
        "objective",
        "rejected_surface_problem",
        "required_decision_scope",
        "snapshot_id",
    ]

    def validate_for_commit(self) -> None:
        missing = []
        for field_name in self._REQUIRED_FOR_COMMIT:
            val = getattr(self, field_name, None)
            if val is None or (isinstance(val, str) and not val.strip()):
                missing.append(field_name)
        if missing:
            raise SchemaViolation(
                f"DecisionFrame missing required fields for COMMIT: {missing}",
                request_id=self.request_id,
            )
        if self.frame_level is None:
            raise SchemaViolation("frame_level is required", request_id=self.request_id)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        if self.frame_level:
            d["frame_level"] = self.frame_level.value
        return d

    def public_view(self) -> Dict[str, Any]:
        if self.status != FrameStatus.COMMITTED:
            raise ContractViolation(
                f"Attempt to expose DecisionFrame in status={self.status.value}. "
                "Only COMMITTED is allowed downstream.",
                request_id=self.request_id,
            )
        return self.to_dict()


class DecisionFrameStore:
    """Transactional store. Downstream actors can only obtain COMMITTED frames."""

    def __init__(self):
        self._frames: Dict[str, DecisionFrame] = {}
        self._by_request: Dict[str, str] = {}

    def begin(self, request_id: str, snapshot_id: str) -> DecisionFrame:
        frame = DecisionFrame(request_id=request_id, snapshot_id=snapshot_id, status=FrameStatus.DRAFT)
        self._frames[frame.frame_id] = frame
        return frame

    def validate(self, frame_id: str) -> DecisionFrame:
        frame = self._get(frame_id)
        if frame.status not in (FrameStatus.DRAFT, FrameStatus.VALIDATING):
            raise ContractViolation(
                f"Cannot validate frame in status {frame.status.value}",
                request_id=frame.request_id,
            )
        frame.status = FrameStatus.VALIDATING
        frame.validate_for_commit()
        return frame

    def commit(self, frame_id: str) -> DecisionFrame:
        frame = self._get(frame_id)
        if frame.status not in (FrameStatus.DRAFT, FrameStatus.VALIDATING):
            raise ContractViolation(
                f"Cannot commit frame in status {frame.status.value}",
                request_id=frame.request_id,
            )
        frame.validate_for_commit()
        old_id = self._by_request.get(frame.request_id)
        if old_id and old_id in self._frames:
            self._frames[old_id].status = FrameStatus.SUPERSEDED
        frame.status = FrameStatus.COMMITTED
        frame.committed_at = time.time()
        self._by_request[frame.request_id] = frame.frame_id
        return frame

    def get_committed(self, request_id: str) -> DecisionFrame:
        frame_id = self._by_request.get(request_id)
        if not frame_id:
            raise ContractViolation(
                f"No COMMITTED DecisionFrame for request {request_id}",
                request_id=request_id,
            )
        frame = self._frames[frame_id]
        if frame.status != FrameStatus.COMMITTED:
            raise ContractViolation(
                f"Frame {frame_id} is not COMMITTED (status={frame.status.value})",
                request_id=request_id,
            )
        return frame

    def get_public(self, request_id: str) -> Dict[str, Any]:
        return self.get_committed(request_id).public_view()

    def _get(self, frame_id: str) -> DecisionFrame:
        if frame_id not in self._frames:
            raise ContractViolation(f"Unknown DecisionFrame {frame_id}")
        return self._frames[frame_id]
