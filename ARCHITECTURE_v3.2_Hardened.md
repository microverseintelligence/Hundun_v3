# Unified Personal Agent Architecture v3.2 — Hardened Runtime

**Status:** MACHINE-ENFORCEABLE EXPERIMENTAL SYSTEM  
**Previous:** v3-1 (STRONG CONCEPTUAL DESIGN)  
**Hardening date:** 2026-08-14  
**Repository:** microverseintelligence/Hundun_v3

---

## 0. Change summary from v3-1

This version closes the P0 gaps identified by the adversarial audit of 14.08.2026 and implements the Hardening Technical Specification.

| Area | v3-1 | v3.2 Hardened |
|------|------|---------------|
| FSM | Textual diagram + examples | Formal single source of truth + complete transition rules (see `specs/FSM.md`) |
| DecisionFrame | Described | Transactional lifecycle DRAFT→COMMITTED; only COMMITTED visible downstream |
| BudgetGuard | Middleware described | Physical denial; no recovery path may issue calls after exhaustion |
| Fourth Phase 1 | Context isolation claimed | Tool session isolation + lesson visibility filter (deny-by-default) |
| Frame Integrity | Label + causal checks | Required structured fields on both DecisionFrame and Responder; mismatch cannot be silently ignored |
| Tool state | Message context only | Per-branch ToolSessions; shared cache rules; ToolGateway enforcement |
| Capability | Implicit | Explicit deny-by-default matrix |
| Errors | Partial mapping | Full taxonomy → deterministic terminal states |
| Tests | Mentioned | Explicit adversarial test suite required for Definition of Done |

All critical invariants now have:

**Contract + Runtime enforcement point + Adversarial test + Observable evidence**

---

## 1. Core invariants (machine-enforceable)

1. The FSM is the only component allowed to change request state.
2. No LLM/tool call occurs without a successful `BudgetGuard.reserve()`.
3. DecisionFrame is visible to Responder / Fourth Phase 2 only after `COMMITTED`.
4. Fourth Phase 1 receives only the explicitly allowed context and a filtered lesson set.
5. Tool sessions are branch-isolated; cross-session reads are IsolationBroken.
6. Frame Integrity failure is recorded in provenance and cannot be hidden by Midwife.
7. After any hard limit, only terminal states that issue no new calls are legal.
8. Active requests remain on their pinned snapshot for their entire lifetime.
9. Policy promotion and lesson activation are transactional and externally gated.
10. Capability matrix is deny-by-default; Agent cannot reach Evaluator/Sealed data.

---

## 2. Runtime overview

```text
USER REQUEST
    │
    ▼
REQUEST_CREATED  ──pin snapshot, init counters──► CLASSIFY
    │
    ├── R0/R1 ──► SOLVE (direct) ──► LIGHT_VALIDATE ──► TERMINAL_*
    │
    └── R2+ ──► FRAME_ANALYZE ──► FRAME_PROPOSED
                    │
                    ▼
              FOURTH_PHASE_1 (BlindToolSession)
                    │
                    ▼
              FRAME_ARBITRATE
                    │
                    ▼
         DECISION_FRAME_COMMITTED  (atomic)
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
        SOLVE          (parallel possible later)
   (ResponderSession)
          │
          ▼
     EVIDENCE / DISSENT / FOURTH_PHASE_2
          │
          ▼
  FRAME_INTEGRITY_CHECK
          │
          ├── pass ──► FINAL_ARBITRATE ──► TERMINAL_SUCCESS / UNCERTAIN / REFUSE / ASK_USER
          │
          └── mismatch ──► REPAIR (budget permitting) or TERMINAL_UNCERTAIN/REFUSE
```

Full transition table, guards, counters and illegal transitions: **`specs/FSM.md`**.

---

## 3. Key hardened components

### 3.1 Formal FSM
See `specs/FSM.md`.  
Every state has defined events, guards, side effects, timeouts and failure actions.  
Implicit transitions do not exist.

### 3.2 Transactional DecisionFrame
See `specs/TRANSACTIONS.md`.  
Lifecycle: `DRAFT → VALIDATING → COMMITTED → SUPERSEDED`.  
Only `COMMITTED` is delivered to downstream actors.

### 3.3 BudgetGuard
Sole authority.  
`reserve → execute → commit | release`.  
Physical interceptor; remaining == 0 makes the next call impossible.  
No recovery path after exhaustion may start a new LLM/tool call.

### 3.4 Tool / Session Isolation
See `specs/TOOL_ISOLATION.md`.  
Distinct sessions per branch.  
Shared caches, if used, are request-scoped, visibility-scoped and provenance-tagged.  
FourthBlindToolSession cannot read other branches’ cache.

### 3.5 Blind Fourth + Lesson Isolation
See `specs/LESSON_VISIBILITY.md`.  
Phase 1 context is strictly limited.  
Lessons carry explicit visibility; default for Phase 1 is `false`.  
Persistent Fourth identity ≠ persistent access to past selected frames.

### 3.6 Hard Frame Integrity Gate
See `specs/FRAME_INTEGRITY.md`.  
Required structured fields on DecisionFrame and on Responder output.  
Mismatch → repair only if budget/counter allow; otherwise terminal UNCERTAIN/REFUSE.  
Failure is always recorded in provenance.

### 3.7 Capability Matrix
See `specs/CAPABILITY_MATRIX.md`.  
Deny-by-default.  
Hard prohibitions on Agent→Evaluator, FourthPhase1→selected frame, external content→policy/contract, etc.

### 3.8 Error Taxonomy
See `specs/ERROR_TAXONOMY.md`.  
Every error type maps deterministically to a terminal or limited recovery path.  
No silent “answer anyway”.

---

## 4. Self-improvement (unchanged principle, hardened gates)

```text
failure / opportunity
    → hypothesis
    → candidate policy
    → shadow / trial
    → external evaluation
    → promote | reject | hold
```

- Internal score never triggers promotion.
- Framing lessons follow the same external-evaluation path.
- Promotion is a transactional snapshot switch.
- Active requests never see the new snapshot mid-flight.

---

## 5. Observability & provenance

Every request produces a complete, replayable provenance chain:

```text
request → snapshot_id → policy_version → risk → frames → BlindFrameProposal
→ DecisionFrame (COMMITTED) → Responder → Evidence/Dissent → Fourth Phase 2
→ FrameIntegrity result → Midwife decision → budget events → terminal state
```

Missing mandatory provenance fields → fail-closed.

---

## 6. Implementation roadmap (updated)

**Phase 0 (P0) — completed at specification level in this repository**

- Formal FSM
- Transactional DecisionFrame / Veto / Budget / Snapshot / Promotion
- Tool session isolation
- Lesson visibility for Blind Fourth
- Hard BudgetGuard
- Hard Frame Integrity Gate
- Capability matrix
- Error taxonomy
- Adversarial test suite definition

**Phase 1 — implementation**

- Runtime engine that enforces the above contracts
- Runnable adversarial tests
- Correlation / ablation / negative benchmarks

**Phase 2 — optimization (only after tests pass)**

- Adaptive depth
- Controlled early exit (optional stages only)
- Cost-per-useful-dissent tuning
- Inference diversity measures

---

## 7. Definition of Done (from Hardening TZ)

The architecture is considered ready for independent re-audit when:

- Formal FSM is the sole orchestration path
- All P0 isolation, transactional and budget properties are machine-enforced
- Adversarial test suite (including §60 end-to-end scenario) can be executed
- No critical invariant relies solely on “the prompt tells the agent not to do X”

**Target verdict after re-audit:** PASS WITH CONDITIONS

---

## 8. References

- Original Unified_Personal_Agent_Architecture_v3-1.md
- Adversarial Audit Report 14.08.2026
- Hardening Technical Specification (Новый документ (3).pdf)
- This repository’s `specs/` and `tests/` directories
