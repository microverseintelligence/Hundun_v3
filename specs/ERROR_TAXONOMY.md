# Error Taxonomy & Fail-Closed Mapping — Hundun v3.2

Every error type has a deterministic mapping.  
There is no generic “something went wrong → answer anyway”.

| Error | Recoverable? | Retryable? | Max retries | Terminal mapping | User-visible? | Provenance event? |
|-------|--------------|------------|-------------|------------------|---------------|-------------------|
| BudgetExhausted | no (for new calls) | no | 0 | TERMINAL_UNCERTAIN / TERMINAL_REFUSE / TERMINAL_ASK_USER | yes | yes |
| Timeout | no | no | 0 | TERMINAL_ERROR | yes | yes |
| ContractViolation | no | no | 0 | TERMINAL_ERROR / TERMINAL_REFUSE | yes | yes |
| IsolationBroken | no | no | 0 | TERMINAL_ERROR | yes | yes |
| SnapshotConflict | no | no | 0 | TERMINAL_ERROR | yes | yes |
| FrameMismatch | conditional | via REPAIR | ≤ max_repair | TERMINAL_UNCERTAIN / TERMINAL_REFUSE if limit reached | yes | yes |
| EvidenceConflict | yes | SEARCH_AGAIN if budget | ≤ max_search_again | TERMINAL_UNCERTAIN if unresolved | yes | yes |
| ToolFailure | conditional | limited | 1–2 | TOOL_FAILURE → ASK_USER or UNCERTAIN | yes | yes |
| ArbitrationFailure | no | no | 0 | TERMINAL_UNCERTAIN | yes | yes |
| SchemaViolation | no | no | 0 | TERMINAL_ERROR | yes | yes |

## Recovery constraints

- After BudgetExhausted, **no** recovery path may issue a new LLM or tool call.
- After IsolationBroken or ContractViolation the only legal action is terminal.
- FrameMismatch repair is itself budget- and counter-limited.

## Observability

Every error produces a provenance event with:

```json
{
  "error_type": "...",
  "request_id": "...",
  "state_at_failure": "...",
  "budget_remaining": {},
  "counters": {},
  "timestamp": "..."
}
```
