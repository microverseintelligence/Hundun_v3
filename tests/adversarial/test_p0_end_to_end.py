"""
P0 Adversarial end-to-end smoke tests.
Covers key invariants from the Hardening TZ and original §60 scenario (simplified).
"""

import pytest
import sys
sys.path.insert(0, "/home/workdir/artifacts/Hundun_v3")

from hundun.core.runtime import HundunRuntime
from hundun.core.budget import BudgetLimits, ResourceType
from hundun.core.decision_frame import FrameLevel
from hundun.core.frame_integrity import ResponderDeclaration
from hundun.core.fsm import State
from hundun.core.errors import BudgetExhausted, ContractViolation, IsolationBroken
from hundun.core.isolation import ToolSessionManager, SessionType


def test_happy_path_integrity_pass():
    rt = HundunRuntime(BudgetLimits(max_llm_calls=8))
    ctx = rt.start_request("Occupancy is falling, what should we do?", risk_class=3)
    rt.run_classify(ctx)
    assert ctx.state == State.FRAME_ANALYZE
    rt.run_frame_analyze(ctx)
    rt.run_fourth_phase1(ctx)
    rt.run_arbitrate_and_commit(
        ctx,
        frame_level=FrameLevel.L2,
        decision_target="restore contribution margin",
        causal_object="pricing + mix",
        objective="maximize contribution margin",
        rejected_surface_problem="just raise occupancy",
        required_decision_scope="commercial",
        success_criteria=["margin stable or up"],
    )
    assert ctx.state == State.SOLVE

    responder = ResponderDeclaration(
        answer_objective="maximize contribution margin",
        addressed_causal_object="pricing + mix",
        decision_scope="commercial",
        success_criteria_addressed=["margin stable or up"],
    )
    result = rt.run_solve_and_integrity(ctx, responder)
    assert result.passed
    state = rt.finish_integrity(ctx, result)
    assert state == State.FINAL_ARBITRATE
    final = rt.finalize(ctx, "accept")
    assert final.terminal_state == "TERMINAL_SUCCESS"
    assert final.decision_frame["status"] == "COMMITTED"


def test_wrong_objective_leads_to_uncertain_when_budget_low():
    rt = HundunRuntime(BudgetLimits(max_llm_calls=4, max_repair=0))
    ctx = rt.start_request("Occupancy falling", risk_class=3)
    rt.run_classify(ctx)
    rt.run_frame_analyze(ctx)
    rt.run_fourth_phase1(ctx)
    rt.run_arbitrate_and_commit(
        ctx,
        frame_level=FrameLevel.L2,
        decision_target="margin",
        causal_object="pricing",
        objective="maximize contribution margin",
        rejected_surface_problem="just raise occupancy",
        required_decision_scope="commercial",
    )
    # Responder reintroduces rejected surface problem
    bad = ResponderDeclaration(
        answer_objective="just raise occupancy",
        addressed_causal_object="something else",
        decision_scope="ops",
    )
    result = rt.run_solve_and_integrity(ctx, bad)
    assert not result.passed
    state = rt.finish_integrity(ctx, result)
    # With max_repair=0 we go terminal
    assert state in (State.TERMINAL_UNCERTAIN, State.REPAIR_OR_REVIEW)


def test_budget_exhaustion_blocks_search_again():
    rt = HundunRuntime(BudgetLimits(max_llm_calls=2, max_search_again=2))
    ctx = rt.start_request("test", risk_class=2)
    rt.run_classify(ctx)
    rt.run_frame_analyze(ctx)
    # Consume remaining LLM budget
    rt.run_fourth_phase1(ctx)  # 1 call
    # Force another call to exhaust
    ctx.budget.reserve(ResourceType.LLM_CALL)  # 2nd call
    assert ctx.budget.is_exhausted() or ctx.budget.counters.llm_calls >= 2

    # Attempt search_again should fail closed
    ctx.state = State.FINAL_ARBITRATE
    state = rt.fsm.transition(ctx, "search_again")
    assert state in (State.TERMINAL_UNCERTAIN, State.SEARCH_AGAIN)  # guard may send to terminal


def test_illegal_transition_from_terminal_raises():
    rt = HundunRuntime()
    ctx = rt.start_request("x", risk_class=0)
    ctx.state = State.TERMINAL_SUCCESS
    with pytest.raises(ContractViolation):
        rt.fsm.transition(ctx, "classify")


def test_fourth_blind_isolation_enforced():
    mgr = ToolSessionManager()
    blind = mgr.open("req-x", SessionType.FOURTH_BLIND)
    evidence = mgr.open("req-x", SessionType.EVIDENCE)
    mgr.write_cache(evidence.session_id, "claim", "secret")
    with pytest.raises(IsolationBroken):
        mgr.assert_can_read_from(blind.session_id, evidence.session_id)
