# Transactional Semantics — Hundun v3.2

Critical objects must never be visible downstream in a partial state.

## 1. Transaction boundary

Every critical operation follows:

```text
BEGIN
  construct
  validate schema
  validate contract
  validate provenance
  validate budget / counters
COMMIT  → object becomes visible
or
ROLLBACK → object is discarded, no side effects remain
```

## 2. Objects under transaction control

| Object | Lifecycle | Visible only after |
|--------|-----------|--------------------|
| DecisionFrame | DRAFT → VALIDATING → COMMITTED → SUPERSEDED | COMMITTED |
| VetoRecord | DRAFT → COMMITTED | COMMITTED |
| VetoOverrideRecord | DRAFT → COMMITTED | COMMITTED |
| BudgetReservation | RESERVED → COMMITTED / RELEASED | after reserve() success |
| SnapshotPin | PINNED | at request start |
| LessonActivation | CANDIDATE → SHADOW → VALIDATED → ACTIVE | ACTIVE (after external eval) |
| PolicyPromotion | CANDIDATE → TRIAL → PROMOTED | PROMOTED (atomic pointer switch) |
| TerminalDecision | DRAFT → COMMITTED | COMMITTED |

## 3. DecisionFrame

```text
status ∈ {DRAFT, VALIDATING, COMMITTED, SUPERSEDED}
```

- Responder and Fourth Phase 2 may receive **only** a DecisionFrame whose status == `COMMITTED`.
- A DRAFT or VALIDATING frame must never appear in any message visibility scope that reaches those actors.
- Commit is atomic: either the full validated frame is published under the request’s snapshot, or nothing is published.

Required fields for COMMITTED (hard schema):

```json
{
  "frame_id": "...",
  "request_id": "...",
  "status": "COMMITTED",
  "frame_level": "L0|L1|L2|L3|L4|L5",
  "decision_target": "...",
  "causal_object": "...",
  "objective": "...",
  "constraints": [],
  "rejected_surface_problem": "...",
  "success_criteria": [],
  "required_decision_scope": "...",
  "strongest_counterargument": "...",
  "frame_transition": { ... },
  "snapshot_id": "...",
  "provenance": { ... }
}
```

## 4. Budget operations

```text
reserve(resource, amount) → ReservationToken | BudgetExhausted
execute(...)
commit(token, actual_consumption)
  or
release(token)   // on timeout / failure
```

- `reserve` is atomic and decreases the remaining budget immediately.
- If the call fails or times out, `release` returns the reserved amount.
- No component may call an LLM or tool without a valid ReservationToken obtained from BudgetGuard.
- BudgetGuard is the only component allowed to mutate the budget counters.

## 5. Snapshot pin

At `REQUEST_CREATED`:

```text
BEGIN
  compute current snapshot_id (content-addressed)
  record (request_id, snapshot_id, policy_version, lesson_manifest_hash, ...)
  mark pin immutable for this request
COMMIT
```

The request continues under that exact snapshot for its entire lifetime.  
A concurrent promotion creates a new snapshot; it does **not** affect already-pinned requests.

## 6. Policy promotion

```text
BEGIN
  external evaluation result must be present
  create new snapshot (parent → candidate)
  atomically switch production pointer
  write ImprovementEvent
COMMIT
```

Partial promotion is forbidden. Either the new snapshot becomes the production head, or the previous one remains.

## 7. Lesson activation

Framing lessons and all other lessons follow:

```text
candidate → validation → shadow → external_evaluation → ACTIVE
```

Activation is a transactional write that also updates the lesson_manifest_hash of the new snapshot.  
Blind Fourth Phase 1 never sees a lesson whose `visibility.blind_fourth_phase_1 == false` (default).

## 8. Failure semantics

Any exception, schema violation, contract violation, or budget denial inside a transaction causes **ROLLBACK**.  
Downstream actors never observe intermediate state.

## 9. Idempotency

Events that may be redelivered (network retries, etc.) must be handled idempotently:

- Same `message_id` / `event_id` processed twice produces the same final state.
- Counter increments are protected by request-scoped atomic operations.
