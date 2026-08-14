# Audit Report vNext — Post-Hardening

**Date:** 2026-08-14  
**Subject:** Unified Personal Agent Architecture after Hardening to v3.2  
**Previous verdict (v3-1):** REQUIRES REVISIONS  

## Executive summary

P0 items from the adversarial audit and the subsequent Hardening TZ have been closed at the **specification and contract level**:

- Formal FSM with explicit states, transition table, counters, illegal transitions and recovery rules.
- Transactional semantics for DecisionFrame, Budget, Snapshot pin, Veto/Override, Lesson activation and Policy promotion.
- Tool/session isolation per epistemic branch.
- Lesson visibility isolation for Blind Fourth Phase 1 (deny-by-default).
- Hard BudgetGuard with physical denial and no recovery-call bypass.
- Hard Frame Integrity Gate requiring structured fields beyond label equality.
- Capability matrix (deny-by-default).
- Complete error taxonomy with fail-closed mapping.
- Adversarial test suite definition covering the original §60 scenario and isolation/budget/integrity cases.

The architecture has moved from **STRONG CONCEPTUAL DESIGN** to **MACHINE-ENFORCEABLE EXPERIMENTAL SYSTEM** (specification stage).

## Remaining work before PASS WITH CONDITIONS

1. Implement the runtime that actually enforces the contracts (FSM engine, ToolGateway, BudgetGuard interceptor, schema validators).
2. Make the adversarial test suite executable and obtain green results.
3. Independent re-audit against the new contracts.

## Residual risks (unchanged in nature)

- Epistemic quality of steelman / discriminating evidence remains LLM-dependent; runtime gates reduce but do not eliminate the possibility of a formally correct yet substantively wrong decision.
- Persistent Fourth long-term correlation risk is mitigated by visibility rules but requires ongoing monitoring.
- Evaluation cost and latency of the external evaluator remain practical constraints.

## Recommendation

Proceed to implementation of the P0 contracts and the adversarial test harness.  
After green tests, request independent re-audit targeting **PASS WITH CONDITIONS**.
