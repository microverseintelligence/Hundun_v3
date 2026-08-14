"""P0: Transactional DecisionFrame tests."""

import pytest
import sys
sys.path.insert(0, "/home/workdir/artifacts/Hundun_v3")

from hundun.core.decision_frame import DecisionFrameStore, FrameStatus, FrameLevel
from hundun.core.errors import SchemaViolation, ContractViolation


def test_only_committed_is_visible():
    store = DecisionFrameStore()
    frame = store.begin("req-1", "snap-1")
    assert frame.status == FrameStatus.DRAFT

    with pytest.raises(ContractViolation):
        frame.public_view()

    # incomplete → cannot commit
    with pytest.raises(SchemaViolation):
        store.validate(frame.frame_id)

    frame.frame_level = FrameLevel.L2
    frame.decision_target = "improve contribution margin"
    frame.causal_object = "pricing + mix"
    frame.objective = "maximize contribution margin"
    frame.rejected_surface_problem = "just increase occupancy"
    frame.required_decision_scope = "commercial"
    frame.snapshot_id = "snap-1"

    store.validate(frame.frame_id)
    committed = store.commit(frame.frame_id)
    assert committed.status == FrameStatus.COMMITTED

    public = store.get_public("req-1")
    assert public["status"] == "COMMITTED"
    assert public["objective"] == "maximize contribution margin"


def test_draft_never_reaches_downstream():
    store = DecisionFrameStore()
    frame = store.begin("req-2", "snap-2")
    with pytest.raises(ContractViolation):
        store.get_committed("req-2")
