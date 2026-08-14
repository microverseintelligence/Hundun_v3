# Formal Finite State Machine — Hundun v3.2

**Single source of truth for runtime orchestration.**  
No agent may transition the system by itself. Only the FSM engine, driven by validated events and guards, may change state.

## 1. States

```text
REQUEST_CREATED
CLASSIFY
FRAME_ANALYZE
FRAME_PROPOSED
FRAME_ARBITRATE
DECISION_FRAME_COMMITTED
SOLVE
EVIDENCE
DISSENT
FOURTH_PHASE_1
FOURTH_PHASE_2
FINAL_COMPARE
FRAME_INTEGRITY_CHECK
FINAL_ARBITRATE
SEARCH_AGAIN
REPAIR_OR_REVIEW
TERMINAL_SUCCESS
TERMINAL_UNCERTAIN
TERMINAL_REFUSE
TERMINAL_ASK_USER
TERMINAL_ERROR
```

All `TERMINAL_*` states are absorbing. No transitions out of them are permitted.

## 2. Request-scoped counters (atomic)

Every request maintains:

```json
{
  "search_again_count": 0,
  "frame_revision_count": 0,
  "repair_count": 0,
  "veto_override_count": 0,
  "total_transitions": 0,
  "llm_calls": 0,
  "tool_calls": 0,
  "cost_units": 0.0,
  "wall_clock_ms": 0
}
```

Hard limits (defaults, tunable by benchmark):

```json
{
  "max_search_again": 2,
  "max_frame_revision": 1,
  "max_repair": 1,
  "max_veto_override": 1,
  "max_total_transitions": 40,
  "max_llm_calls": 12,
  "max_tool_calls": 16,
  "max_cost_units": 10,
  "max_wall_clock_ms": 120000
}
```

Counters are incremented **atomically** inside the transition that uses the resource.  
Any attempt to exceed a limit produces `BudgetExhausted` / `ContractViolation` → `TERMINAL_ERROR` or `TERMINAL_UNCERTAIN`.

## 3. Transition Table (excerpt of critical paths)

Format:  
`Current | Event | Guard | Next | Side Effect | Timeout | Failure Action`

| Current | Event | Guard | Next | Side Effect | Timeout | Failure |
|---------|-------|-------|------|-------------|---------|---------|
| REQUEST_CREATED | classify | budget.ok && snapshot.pinned | CLASSIFY | pin_snapshot, init_counters | 5s | TERMINAL_ERROR |
| CLASSIFY | risk_low (R0/R1) | risk ∈ {R0,R1} | SOLVE (direct) | — | 10s | TERMINAL_ERROR |
| CLASSIFY | risk_high | risk ≥ R2 | FRAME_ANALYZE | — | 10s | TERMINAL_ERROR |
| FRAME_ANALYZE | frames_ready | surface+causal+candidates produced | FRAME_PROPOSED | emit CandidateFrames | 30s | TERMINAL_UNCERTAIN |
| FRAME_PROPOSED | start_blind | budget.remaining_llm ≥ 1 | FOURTH_PHASE_1 | open FourthBlindToolSession | 30s | TERMINAL_UNCERTAIN |
| FOURTH_PHASE_1 | blind_proposal | isolation_status == strict && schema_valid | FRAME_ARBITRATE | close BlindToolSession, record BlindFrameProposal | 45s | ISOLATION_FAILURE → TERMINAL_ERROR |
| FRAME_ARBITRATE | frame_selected | DecisionFrame constructable | DECISION_FRAME_COMMITTED | **atomic DecisionFrame.commit()** | 20s | TERMINAL_UNCERTAIN |
| FRAME_ARBITRATE | unresolved | max_frame_revision reached | TERMINAL_UNCERTAIN | — | — | — |
| DECISION_FRAME_COMMITTED | start_solve | DecisionFrame.status == COMMITTED | SOLVE | open ResponderToolSession | 10s | TERMINAL_ERROR |
| SOLVE | answer_ready | schema_valid | EVIDENCE or FOURTH_PHASE_2 | close Responder session | 60s | FRAME_MISMATCH later |
| EVIDENCE | evidence_ready | — | DISSENT or FINAL_COMPARE | — | 40s | — |
| DISSENT | dissent_ready | — | FINAL_COMPARE | — | 30s | — |
| FINAL_COMPARE | proceed | — | FRAME_INTEGRITY_CHECK | — | 15s | — |
| FRAME_INTEGRITY_CHECK | pass | all integrity checks true | FINAL_ARBITRATE | record integrity_pass | 10s | — |
| FRAME_INTEGRITY_CHECK | mismatch | budget.remaining allows repair | REPAIR_OR_REVIEW | increment repair_count | 10s | — |
| FRAME_INTEGRITY_CHECK | mismatch | budget.exhausted || repair_count ≥ max | TERMINAL_UNCERTAIN or TERMINAL_REFUSE | record FRAME_MISMATCH | — | — |
| FINAL_ARBITRATE | accept | integrity_pass && (no veto or override recorded) | TERMINAL_SUCCESS | emit final Decision | 15s | — |
| FINAL_ARBITRATE | search_again | search_again_count < max && budget.ok | SEARCH_AGAIN | increment search_again_count | 5s | BudgetExhausted → TERMINAL_UNCERTAIN |
| FINAL_ARBITRATE | veto | Fourth veto && override_count < max | (override path) | record VetoOverrideRecord | 10s | — |
| FINAL_ARBITRATE | refuse | Midwife decides | TERMINAL_REFUSE | — | — | — |
| SEARCH_AGAIN | research_done | — | FRAME_INTEGRITY_CHECK or FINAL_ARBITRATE | close research session | 40s | — |
| REPAIR_OR_REVIEW | repaired | integrity now pass | FINAL_ARBITRATE | — | 30s | — |
| REPAIR_OR_REVIEW | still_mismatch | repair_count ≥ max | TERMINAL_UNCERTAIN | — | — | — |
| *any* | budget_exhausted | remaining == 0 | TERMINAL_UNCERTAIN / TERMINAL_REFUSE / TERMINAL_ASK_USER | **no further calls allowed** | — | — |
| *any* | timeout | wall_clock exceeded | TERMINAL_ERROR | — | — | — |
| *any* | contract_violation | illegal transition attempted | TERMINAL_ERROR | log ContractViolation | — | — |
| TERMINAL_* | * | — | DENY | — | — | ContractViolation |

## 4. Illegal transitions (hard deny)

- Any `TERMINAL_*` → non-terminal
- `DECISION_FRAME_COMMITTED` → `FRAME_ANALYZE` / `FRAME_PROPOSED`
- `FOURTH_PHASE_1` → any state that consumes selected frame without Phase-1 result
- `SEARCH_AGAIN` when `search_again_count ≥ max` or budget exhausted
- Any transition that would increment a counter past its hard limit
- Any attempt to open a tool session after BudgetGuard denial

Violation → `ContractViolation` → `TERMINAL_ERROR` (or `TERMINAL_REFUSE` for high-risk).

## 5. Recovery rules

On recoverable errors (EvidenceConflict, temporary ToolFailure) the FSM may move to `REPAIR_OR_REVIEW` or `SEARCH_AGAIN` **only if** the corresponding counter and budget allow it.

On non-recoverable errors (IsolationBroken, SnapshotConflict, BudgetExhausted after reservation failure, ContractViolation) the only legal destinations are terminal states that do **not** issue new LLM/tool calls.

## 6. Implementation requirement

The FSM engine must be the only component that:

1. Holds the current state.
2. Validates event + guard.
3. Performs the atomic side effects (counter++, DecisionFrame.commit, session open/close, etc.).
4. Emits the next state.

No agent code is allowed to mutate the global request state directly.
