"""P0: Tool session isolation + lesson visibility tests."""

import pytest
import sys
sys.path.insert(0, "/home/workdir/artifacts/Hundun_v3")

from hundun.core.isolation import ToolSessionManager, SessionType, LessonVisibilityFilter
from hundun.core.errors import IsolationBroken


def test_fourth_blind_cannot_read_responder_cache():
    mgr = ToolSessionManager()
    blind = mgr.open("req-1", SessionType.FOURTH_BLIND)
    responder = mgr.open("req-1", SessionType.RESPONDER)

    mgr.write_cache(responder.session_id, "secret_evidence", "leaked_value")

    with pytest.raises(IsolationBroken):
        mgr.assert_can_read_from(blind.session_id, responder.session_id)


def test_lesson_visibility_deny_by_default():
    lessons = [
        {"id": "l1", "status": "active", "visibility": {"blind_fourth_phase_1": False}},
        {"id": "l2", "status": "active", "visibility": {"blind_fourth_phase_1": True}},
        {"id": "l3", "status": "active"},  # missing visibility → default False
        {"id": "l4", "status": "candidate", "visibility": {"blind_fourth_phase_1": True}},
    ]
    filtered = LessonVisibilityFilter.filter_for_phase1(lessons)
    assert len(filtered) == 1
    assert filtered[0]["id"] == "l2"


def test_sessions_closed_on_cleanup():
    mgr = ToolSessionManager()
    s = mgr.open("req-1", SessionType.FOURTH_BLIND)
    mgr.close_all_for_request("req-1")
    with pytest.raises(IsolationBroken):
        mgr.get(s.session_id)
