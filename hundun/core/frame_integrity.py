"""
Hard Frame Integrity Gate.
See specs/FRAME_INTEGRITY.md
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from .decision_frame import DecisionFrame, FrameStatus
from .errors import FrameMismatch, SchemaViolation, ContractViolation


@dataclass
class ResponderDeclaration:
    answer_objective: str
    addressed_causal_object: str
    decision_scope: str
    assumptions_used: List[str] = field(default_factory=list)
    success_criteria_addressed: List[str] = field(default_factory=list)

    def validate(self) -> None:
        required = ["answer_objective", "addressed_causal_object", "decision_scope"]
        for r in required:
            val = getattr(self, r, None)
            if not val or not str(val).strip():
                raise SchemaViolation(f"ResponderDeclaration missing required field: {r}")


@dataclass
class IntegrityResult:
    passed: bool
    failures: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def raise_if_failed(self, request_id: str) -> None:
        if not self.passed:
            raise FrameMismatch(
                f"Frame integrity failed: {'; '.join(self.failures)}",
                request_id=request_id,
            )


class FrameIntegrityGate:
    def check(self, decision_frame: DecisionFrame, responder: ResponderDeclaration) -> IntegrityResult:
        if decision_frame.status != FrameStatus.COMMITTED:
            raise ContractViolation(
                f"Frame Integrity can only run on COMMITTED DecisionFrame, got {decision_frame.status.value}",
                request_id=decision_frame.request_id,
            )

        responder.validate()
        failures: List[str] = []
        details: Dict[str, Any] = {}

        obj_match = self._normalize(responder.answer_objective) == self._normalize(decision_frame.objective or "")
        obj_contains = (
            self._normalize(decision_frame.objective or "") in self._normalize(responder.answer_objective)
            or self._normalize(responder.answer_objective) in self._normalize(decision_frame.objective or "")
        )
        if not (obj_match or obj_contains):
            failures.append("objective_mismatch")
            details["expected_objective"] = decision_frame.objective
            details["declared_objective"] = responder.answer_objective

        causal_match = self._normalize(responder.addressed_causal_object) == self._normalize(decision_frame.causal_object or "")
        causal_contains = (
            self._normalize(decision_frame.causal_object or "") in self._normalize(responder.addressed_causal_object)
            or self._normalize(responder.addressed_causal_object) in self._normalize(decision_frame.causal_object or "")
        )
        if not (causal_match or causal_contains):
            failures.append("causal_object_mismatch")
            details["expected_causal"] = decision_frame.causal_object
            details["declared_causal"] = responder.addressed_causal_object

        if decision_frame.required_decision_scope:
            if self._normalize(decision_frame.required_decision_scope) not in self._normalize(responder.decision_scope):
                if self._normalize(responder.decision_scope) != self._normalize(decision_frame.required_decision_scope):
                    failures.append("decision_scope_mismatch")
                    details["required_scope"] = decision_frame.required_decision_scope
                    details["declared_scope"] = responder.decision_scope

        if decision_frame.rejected_surface_problem:
            rejected = self._normalize(decision_frame.rejected_surface_problem)
            if rejected and rejected == self._normalize(responder.answer_objective):
                failures.append("reintroduced_rejected_surface_problem")
                details["rejected"] = decision_frame.rejected_surface_problem

        if decision_frame.success_criteria:
            addressed = {self._normalize(c) for c in responder.success_criteria_addressed}
            expected = {self._normalize(c) for c in decision_frame.success_criteria}
            if expected and not (addressed & expected):
                failures.append("success_criteria_not_addressed")
                details["expected_criteria"] = decision_frame.success_criteria
                details["addressed_criteria"] = responder.success_criteria_addressed

        return IntegrityResult(passed=len(failures) == 0, failures=failures, details=details)

    @staticmethod
    def _normalize(s: str) -> str:
        return " ".join(s.lower().strip().split())
