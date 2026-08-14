# Lesson Visibility & Blind Fourth Isolation — Hundun v3.2

## 1. Separation of concerns

Persistent Fourth identity/state is allowed.  
Persistent **blind epistemic context** is not.

Fourth Phase 1 must not be able to reconstruct, even indirectly:

- which frame was previously selected
- what answer was previously given
- which dissent was accepted
- which decisions Midwife approved

## 2. Allowed context for Fourth Phase 1

```text
original_request
risk_class
contract
global_constraints
allowed_tools (capability matrix)
budget_view
request_snapshot_id
```

## 3. Explicitly forbidden for Phase 1

```text
selected_problem_frame
DecisionFrame (any status)
Responder output / reasoning
Camera B output
Camera C output
Speaker output
previous branch conclusions
any lesson with visibility.blind_fourth_phase_1 == false
```

## 4. Lesson visibility schema

Every lesson carries:

```json
{
  "id": "lesson-...",
  "visibility": {
    "blind_fourth_phase_1": false,
    "fourth_phase_2": true,
    "responder": true,
    "midwife": true,
    "problem_frame_engine": true
  },
  "status": "candidate|shadow|validated|active|deprecated|quarantined|superseded",
  ...
}
```

**Default:** `"blind_fourth_phase_1": false` (deny-by-default).

Only lessons that have been explicitly marked and have passed external evaluation may be set to `true` for Phase 1 (rare; most framing lessons stay false).

## 5. Filtering at retrieval time

When Fourth Phase 1 requests lessons, the memory layer **must** filter:

```text
lessons.filter(l => l.visibility.blind_fourth_phase_1 === true && l.status === "active")
```

This filter is enforced by the runtime, not by the prompt.

## 6. Framing lessons special rule

All framing-related lessons (level-shift, objective, steelman, Fourth dissent patterns) follow the full pipeline:

```text
candidate → validation → shadow → external evaluation → activation
```

They are never auto-activated from internal runtime success alone.

## 7. Quarantine

Contradictory or repeatedly harmful lessons move to `quarantined` and are invisible to all production actors until human/external review.
