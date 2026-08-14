# Hard Frame Integrity Gate — Hundun v3.2

## 1. Problem with label-only checks

```text
answer.frame_level == decision_frame.frame_level
```

is insufficient. A Responder can keep the old objective while emitting the new label.

## 2. Required DecisionFrame fields (COMMITTED)

```json
{
  "frame_level": "...",
  "decision_target": "...",
  "causal_object": "...",
  "objective": "...",
  "constraints": [],
  "rejected_surface_problem": "...",
  "success_criteria": [],
  "required_decision_scope": "..."
}
```

## 3. Required Responder declaration

Responder output must contain structured fields:

```json
{
  "answer_objective": "...",
  "addressed_causal_object": "...",
  "decision_scope": "...",
  "assumptions_used": [],
  "success_criteria_addressed": []
}
```

## 4. Integrity checks (all must pass)

1. `answer_objective` matches `decision_frame.objective` (semantic + structural).
2. `addressed_causal_object` addresses `decision_frame.causal_object`.
3. `decision_scope` respects `required_decision_scope`.
4. Answer does **not** reintroduce `rejected_surface_problem` as the primary target.
5. Selected constraints are not ignored.
6. Solution is evaluated against `success_criteria`.

## 5. Failure policy

```text
FRAME_MISMATCH
```

- If remaining budget and `repair_count < max_repair` → transition to `REPAIR_OR_REVIEW` (or re-invoke Fourth Phase 2 under controlled conditions).
- If budget exhausted or repair limit reached → **only** `TERMINAL_UNCERTAIN` or `TERMINAL_REFUSE`.

**Forbidden:** automatically “fixing” the answer with an unconstrained LLM call when budget is low.

## 6. Visibility of failure

Frame Integrity failure **must** be recorded in provenance.  
Midwife cannot hide it. The failure is part of the final Decision record.

## 7. Machine check vs semantic check

Exact string equality is used for IDs and enums.  
Semantic equivalence of objective/causal_object is assisted by structured fields + optional lightweight verifier, but the presence of the required structured fields is hard-enforced by schema. Missing fields → schema validation failure → cannot reach FINAL_ARBITRATE.
