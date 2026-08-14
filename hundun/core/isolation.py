"""
Tool / Session Isolation.
See specs/TOOL_ISOLATION.md and specs/LESSON_VISIBILITY.md
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Set, Optional, Any, List
from enum import Enum
import uuid
import time

from .errors import IsolationBroken, ContractViolation


class SessionType(str, Enum):
    RESPONDER = "ResponderToolSession"
    FOURTH_BLIND = "FourthBlindToolSession"
    FOURTH_REVIEW = "FourthReviewToolSession"
    EVIDENCE = "EvidenceToolSession"
    DISSENT = "DissentToolSession"
    PROBLEM_FRAME = "ProblemFrameToolSession"


SESSION_VISIBILITY: Dict[SessionType, Set[str]] = {
    SessionType.FOURTH_BLIND: {"request_only"},
    SessionType.RESPONDER: {"request_only", "decision_frame", "full_comparison"},
    SessionType.FOURTH_REVIEW: {"request_only", "decision_frame", "full_comparison"},
    SessionType.EVIDENCE: {"request_only", "decision_frame"},
    SessionType.DISSENT: {"request_only", "decision_frame"},
    SessionType.PROBLEM_FRAME: {"request_only"},
}


@dataclass
class ToolSession:
    session_id: str
    request_id: str
    session_type: SessionType
    visibility_scope: Set[str]
    created_at: float = field(default_factory=time.time)
    closed: bool = False
    local_cache: Dict[str, Any] = field(default_factory=dict)
    tool_call_log: List[Dict[str, Any]] = field(default_factory=list)


class ToolSessionManager:
    """Creates and enforces per-branch tool sessions. Cross-session reads are IsolationBroken."""

    def __init__(self):
        self._sessions: Dict[str, ToolSession] = {}
        self._by_request: Dict[str, Dict[SessionType, str]] = {}

    def open(self, request_id: str, session_type: SessionType) -> ToolSession:
        if request_id not in self._by_request:
            self._by_request[request_id] = {}
        if session_type in self._by_request[request_id]:
            sid = self._by_request[request_id][session_type]
            return self._sessions[sid]

        session = ToolSession(
            session_id=str(uuid.uuid4()),
            request_id=request_id,
            session_type=session_type,
            visibility_scope=set(SESSION_VISIBILITY.get(session_type, {"request_only"})),
        )
        self._sessions[session.session_id] = session
        self._by_request[request_id][session_type] = session.session_id
        return session

    def close(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].closed = True
            self._sessions[session_id].local_cache.clear()

    def close_all_for_request(self, request_id: str) -> None:
        if request_id not in self._by_request:
            return
        for sid in self._by_request[request_id].values():
            self.close(sid)
        del self._by_request[request_id]

    def get(self, session_id: str) -> ToolSession:
        if session_id not in self._sessions:
            raise IsolationBroken(f"Unknown tool session {session_id}")
        session = self._sessions[session_id]
        if session.closed:
            raise IsolationBroken(f"Tool session {session_id} is closed")
        return session

    def write_cache(self, session_id: str, key: str, value: Any) -> None:
        session = self.get(session_id)
        session.local_cache[key] = value

    def read_cache(self, session_id: str, key: str) -> Any:
        session = self.get(session_id)
        if key not in session.local_cache:
            return None
        return session.local_cache[key]

    def assert_can_read_from(self, reader_session_id: str, writer_session_id: str) -> None:
        reader = self.get(reader_session_id)
        writer = self.get(writer_session_id)
        if reader.request_id != writer.request_id:
            raise IsolationBroken("Cross-request tool session access forbidden")
        if reader.session_type == SessionType.FOURTH_BLIND:
            if writer.session_type != SessionType.FOURTH_BLIND:
                raise IsolationBroken(
                    f"FourthBlindToolSession cannot read from {writer.session_type.value}"
                )


class LessonVisibilityFilter:
    """Enforces deny-by-default visibility for Blind Fourth Phase 1."""

    @staticmethod
    def filter_for_phase1(lessons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = []
        for lesson in lessons:
            vis = lesson.get("visibility", {})
            if vis.get("blind_fourth_phase_1", False) is True and lesson.get("status") == "active":
                result.append(lesson)
        return result

    @staticmethod
    def default_visibility() -> Dict[str, bool]:
        return {
            "blind_fourth_phase_1": False,
            "fourth_phase_2": True,
            "responder": True,
            "midwife": True,
            "problem_frame_engine": True,
        }
