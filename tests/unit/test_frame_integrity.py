"""P0: Hard Frame Integrity Gate tests."""

import pytest
import sys
sys.path.insert(0, "/home/workdir/artifacts/Hundun_v3")

from hundun.core.decision_frame import DecisionFrameStore, FrameLevel
from hundun.core.frame_integrity import FrameIntegrityGate, ResponderDeclaration
from hundun.core.errors import FrameMismatch, SchemaViolation


def _committed_frame():
    store = DecisionFrameStore()
    f = store.begin("req-1", "snap-1")
    f.frame_level = FrameLevel.L2
    f.decision_target = "fix contribution margin"
    f.causal_object = "pricing and customer mix"
    f.objective = "maximize contribution margin"
    f.rejected_surface_problem = "increase occupancy at any cost"
    f.required_decision_scope = "commercial"
    f.success_criteria = ["margin up", "no ADR collapse"]
    store.validate(f.frame_id)
    return store.commit(f.frame_id)


def test_correct_answer_passes():
    gate = FrameIntegrityGate()
    frame = _committed_frame()
    responder = ResponderDeclaration(
        answer_objective="maximize contribution margin",
        addressed_causal_object="pricing and customer mix",
        decision_scope="commercial",
        success_criteria_addressed=["margin up", "no ADR collapse"],
    )
    result = gate.check(frame, responder)
    assert result.passed


def test_wrong_objective_detected():
    gate = FrameIntegrityGate()
    frame = _committed_frame()
    responder = ResponderDeclaration(
        answer_objective="increase occupancy at any cost",  # rejected surface!
        addressed_causal_object="pricing and customer mix",
        decision_scope="commercial",
        success_criteria_addressed=["margin up"],
    )
    result = gate.check(frame, responder)
    assert not result.passed
    assert "objective_mismatch" in result.failures or "reintroduced_rejected_surface_problem" in result.failures


def test_missing_responder_fields_raise():
    with pytest.raises(SchemaViolation):
        ResponderDeclaration(
            answer_objective="",
            addressed_causal_object="x",
            decision_scope="y",
        ).validate()
