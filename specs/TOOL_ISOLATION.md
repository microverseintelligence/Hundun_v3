# Tool / Session Isolation Specification — Hundun v3.2

## 1. Principle

Isolation is not only about message context.  
Tool state (browser, search cache, retrieval context, filesystem temp, tool conversation memory) must also be isolated per request and per epistemic branch.

## 2. Required Tool Sessions

For every request the runtime creates distinct sessions:

| Session | Used by | Visibility |
|---------|---------|------------|
| `ResponderToolSession` | Responder | full after DecisionFrame COMMITTED |
| `FourthBlindToolSession` | Fourth Phase 1 | request-only, no prior evidence |
| `FourthReviewToolSession` | Fourth Phase 2 | DecisionFrame + admissible evidence |
| `EvidenceToolSession` | Camera B | evidence research |
| `DissentToolSession` | Camera C | dissent research |
| `ProblemFrameToolSession` | ProblemFrameEngine | early framing research (if any) |

Sessions are opened and closed by the FSM as side effects of transitions.

## 3. Forbidden shared state

The following are **not** allowed to be shared across sessions of the same request (or across requests) without explicit provenance and visibility control:

- browser cookies / storage / tabs
- search history or query cache that is not request-scoped
- retrieval embeddings or vector store context that leaks prior branch results
- filesystem temporary directories
- tool-internal conversation memory
- any implicit session object that retains prior tool results

## 4. Shared cache rules (when caching is necessary)

Any cache that is shared must satisfy **all** of:

1. `request_id` scoped (or explicitly multi-request with audit)
2. `visibility_scope` tagged
3. `provenance` recorded (which branch produced the entry)
4. Access control enforced by the runtime before any read

**Hard rule:** Fourth Phase 1 (`FourthBlindToolSession`) must never be able to read a cache entry that was written by Responder, Camera B, Camera C, or Fourth Phase 2 of the same or previous requests.

## 5. Enforcement

- Tool calls are intercepted by a ToolGateway that receives the current `session_id` and `visibility_scope`.
- The gateway rejects any call that would access a resource outside the allowed scope.
- Violation → `IsolationBroken` → `TERMINAL_ERROR` (fail-closed).

## 6. Cleanup

On terminal state (or request timeout) all sessions belonging to the request are destroyed.  
No residual tool state may survive into the next request.
