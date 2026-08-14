# Hundun v3 — Hardened Adaptive Deliberation & Self-Improvement Layer (ADSIL)

**Status:** MACHINE-ENFORCEABLE EXPERIMENTAL SYSTEM — Runtime P0 implemented + tests green  
**Previous:** Unified Personal Agent Architecture v3-1 (STRONG CONCEPTUAL DESIGN)  
**Date:** 2026-08-14  
**Repository:** microverseintelligence/Hundun_v3  
**Test status:** 19/19 passed (unit + adversarial P0)

## Goal

This repository contains:

1. Hardened architecture contracts (after adversarial audit 14.08.2026)
2. **Executable runtime** that enforces the critical P0 invariants
3. Unit and adversarial tests that are currently green

## What is machine-enforced (P0)

- Formal FSM is the only allowed orchestration path
- No implicit transitions; illegal transitions raise `ContractViolation`
- DecisionFrame is transactional (only `COMMITTED` visible downstream)
- BudgetGuard is the sole authority — `reserve()` physically denies when exhausted
- Tool sessions are isolated per epistemic branch; cross-reads raise `IsolationBroken`
- Lesson visibility for Blind Fourth Phase 1 is deny-by-default
- Frame Integrity Gate checks structured objective/causal/scope, not just labels
- Fail-closed error taxonomy

## Layout

```
ARCHITECTURE_v3.2_Hardened.md
specs/                  # Formal contracts
hundun/                 # Runtime package
  core/
    fsm.py
    budget.py
    decision_frame.py
    isolation.py
    frame_integrity.py
    runtime.py
    errors.py
tests/
  unit/
  adversarial/
schemas/
```

## Running tests

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

Expected: 19 passed.

## Next steps

1. Expand adversarial coverage (full §60 scenario with more branches)
2. Wire real LLM / tool adapters behind BudgetGuard + ToolGateway
3. Capability matrix enforcement in message router
4. Independent re-audit → target **PASS WITH CONDITIONS**

## Principles

1. Change is not improvement until independent observable gain is demonstrated.
2. Internal self-score is never proof of external quality.
3. Fourth Phase 1 must remain context-independent.
4. BudgetGuard is the sole authority on resource consumption.
5. Fail closed. Never “answer anyway” on critical failures.
