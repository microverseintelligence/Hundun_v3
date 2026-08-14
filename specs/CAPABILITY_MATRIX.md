# Capability Matrix — Hundun v3.2

**Default policy: deny unless explicitly allowed.**

## Actors

- ProblemFrameEngine
- Responder
- CameraB (Evidence)
- CameraC (Dissent)
- FourthPhase1
- FourthPhase2
- Speaker
- Midwife
- Evaluator (external)
- ImprovementEngine

## Matrix (high-level)

| Actor | LLM calls | Tool calls | Read DecisionFrame | Write DecisionFrame | Read Sealed Eval | Write Policy | Side effects |
|-------|-----------|------------|--------------------|---------------------|------------------|--------------|--------------|
| ProblemFrameEngine | yes (budgeted) | limited research | no | draft only | no | no | none irreversible |
| Responder | yes | ResponderToolSession | COMMITTED only | no | no | no | none irreversible |
| CameraB | yes | EvidenceToolSession | COMMITTED | no | no | no | none |
| CameraC | yes | DissentToolSession | COMMITTED | no | no | no | none |
| FourthPhase1 | yes | FourthBlindToolSession | **no** | no | no | no | none |
| FourthPhase2 | yes | FourthReviewToolSession | COMMITTED | no | no | no | veto only |
| Speaker | yes (optional) | restricted | COMMITTED | no | no | no | none |
| Midwife | orchestration only | none (or read-only) | yes | commit via FSM | no | no | terminal decisions |
| Evaluator | external process | sealed only | no | no | yes | no | scores only |
| ImprovementEngine | via external eval | none on production | no | no | results only | promote via transaction | policy pointer |

## Hard prohibitions (must be enforced by runtime)

1. **Agent runtime → Evaluator / Sealed data** — no read access.
2. **FourthPhase1 → any selected frame, Responder state, or frame-leaking lesson**.
3. **External content → Policy store / Contract / FSM / BudgetGuard**.
4. **Any actor → increase its own budget**.
5. **Midwife → silent veto override** (must produce VetoOverrideRecord).
6. **ImprovementEngine → change evaluator scoring or sealed probes**.

## Enforcement

Capability checks occur in the ToolGateway and in the message router before any content is delivered to an actor.  
Violation → `ContractViolation` or `IsolationBroken` → fail-closed terminal state.
