# Hundun v3 — Hardened Adaptive Deliberation & Self-Improvement Layer (ADSIL)

**Status:** MACHINE-ENFORCEABLE EXPERIMENTAL SYSTEM (P0 closed)  
**Previous:** Unified Personal Agent Architecture v3-1 (STRONG CONCEPTUAL DESIGN)  
**Date:** 2026-08-14  
**Repository:** microverseintelligence/Hundun_v3

## Goal of this repository

This repository contains the hardened specification of the Unified Personal Agent Architecture after the adversarial audit of 14.08.2026 and the subsequent Hardening TZ.

Critical properties have been moved from natural-language descriptions and example JSON into:

- Formal Finite State Machine (single source of truth for orchestration)
- Transactional semantics for all critical objects
- Tool/session isolation per epistemic branch
- Lesson visibility isolation for Blind Fourth Phase 1
- Hard BudgetGuard with physical denial
- Hard Frame Integrity Gate (beyond label equality)
- Capability Matrix (deny-by-default)
- Explicit contracts, error taxonomy, and adversarial test suite outlines

## Definition of Done (from Hardening TZ)

After this work the system is intended to satisfy:

- Formal FSM is the only allowed orchestration path
- No implicit transitions
- All critical objects (DecisionFrame, Veto, Budget, Snapshot, Lesson activation, Promotion) are transactional
- Blind Fourth Phase 1 cannot see selected frames, Responder output, or frame-leaking lessons
- Tool state is isolated per branch
- Budget exhaustion makes further LLM/tool calls physically impossible
- Frame Integrity failure cannot be silently ignored
- Capability matrix is deny-by-default
- Active requests are snapshot-pinned and never migrate mid-execution

## Artifacts

| Path | Description |
|------|-------------|
| `ARCHITECTURE_v3.2_Hardened.md` | Main architecture document (updated) |
| `specs/FSM.md` | Formal FSM + complete transition table |
| `specs/TRANSACTIONS.md` | Transactional semantics for critical operations |
| `specs/CAPABILITY_MATRIX.md` | Actor × Tool/Data matrix (deny-by-default) |
| `specs/TOOL_ISOLATION.md` | Tool session isolation specification |
| `specs/LESSON_VISIBILITY.md` | Lesson visibility & Blind Fourth isolation |
| `specs/ERROR_TAXONOMY.md` | Error types → terminal mapping |
| `specs/FRAME_INTEGRITY.md` | Hard Frame Integrity Gate contract |
| `tests/ADVERSARIAL_TEST_SUITE.md` | Required adversarial tests |
| `schemas/` | Machine-validatable schemas (JSON Schema sketches) |

## Next steps

1. Implement runtime against these contracts.
2. Run the adversarial test suite.
3. Independent re-audit.
4. Target verdict: **PASS WITH CONDITIONS**.

## Principles (unchanged)

1. Change is not improvement until independent observable gain is demonstrated.
2. Internal self-score is never proof of external quality.
3. Fourth Phase 1 must remain context-independent.
4. BudgetGuard is the sole authority on resource consumption.
5. Fail closed. Never “answer anyway” on critical failures.
