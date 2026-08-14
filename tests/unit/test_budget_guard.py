"""P0: BudgetGuard hard enforcement tests."""

import pytest
import sys
sys.path.insert(0, "/home/workdir/artifacts/Hundun_v3")

from hundun.core.budget import BudgetGuard, BudgetLimits, ResourceType
from hundun.core.errors import BudgetExhausted


def test_reserve_commit_happy_path():
    bg = BudgetGuard("req-1", BudgetLimits(max_llm_calls=3))
    token = bg.reserve(ResourceType.LLM_CALL)
    assert bg.counters.llm_calls == 1
    bg.commit(token)
    assert token.committed


def test_reserve_when_exhausted_raises():
    bg = BudgetGuard("req-1", BudgetLimits(max_llm_calls=1))
    bg.reserve(ResourceType.LLM_CALL)
    with pytest.raises(BudgetExhausted):
        bg.reserve(ResourceType.LLM_CALL)


def test_release_restores_budget():
    bg = BudgetGuard("req-1", BudgetLimits(max_llm_calls=2))
    token = bg.reserve(ResourceType.LLM_CALL)
    assert bg.counters.llm_calls == 1
    bg.release(token)
    assert bg.counters.llm_calls == 0
    # can reserve again
    token2 = bg.reserve(ResourceType.LLM_CALL)
    assert bg.counters.llm_calls == 1


def test_search_again_limit():
    bg = BudgetGuard("req-1", BudgetLimits(max_search_again=1))
    bg.reserve(ResourceType.SEARCH_AGAIN)
    with pytest.raises(BudgetExhausted):
        bg.reserve(ResourceType.SEARCH_AGAIN)


def test_concurrent_last_unit_only_one_succeeds():
    """Simulate race: only one of two last units can succeed."""
    bg = BudgetGuard("req-1", BudgetLimits(max_llm_calls=1))
    t1 = bg.reserve(ResourceType.LLM_CALL)
    with pytest.raises(BudgetExhausted):
        bg.reserve(ResourceType.LLM_CALL)
    bg.commit(t1)


def test_view_is_read_only_snapshot():
    bg = BudgetGuard("req-1")
    view = bg.view()
    assert "remaining" in view
    assert view["request_id"] == "req-1"
