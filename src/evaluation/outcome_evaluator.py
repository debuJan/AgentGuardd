"""
Outcome evaluators: task success against configured expectations, and
outcome-consistency (hallucinated success) detection.

Expectation fields read from TestCase (in precedence order):

    expected_outcome:            Optional[str]    (canonical; expected text in final_response)
    expected_outcome_contains:   Optional[str]    (legacy alias for expected_outcome)
    expected_success:            Optional[bool]   (legacy; did the task need to end in success?)

If none is set, TaskSuccessEvaluator degrades to checking that the run
completed without an error and produced a final response.
"""
from __future__ import annotations

from typing import Any, List

from src.core.trace import ExecutionTrace, FinalResponseEvent, ToolErrorEvent, ToolResultEvent
from src.evaluation.base import BaseEvaluator
from src.evaluation.models import EvaluationCheck

_SUCCESS_WORDS = ("success", "successfully", "completed", "processed", "refunded", "confirmed", "approved")
_FAILURE_STATUS_VALUES = {"failed", "failure", "error", "denied", "declined", "rejected"}


def _claims_success(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in _SUCCESS_WORDS)


def _tool_results(trace: ExecutionTrace) -> List[ToolResultEvent]:
    return [e for e in trace.events if isinstance(e, ToolResultEvent)]


def final_response_text(trace: ExecutionTrace) -> str:
    """Best-effort final response text.

    Prefers ``trace.final_response`` (set by ``mark_complete``), falling back
    to the last ``FinalResponseEvent`` in the event stream so hand-built or
    externally-supplied traces that never called ``mark_complete`` are still
    evaluated against their actual final answer.
    """
    if trace.final_response:
        return trace.final_response
    for event in reversed(trace.events):
        if isinstance(event, FinalResponseEvent) and event.content:
            return event.content
    return ""


def _any_tool_result_indicates_failure(trace: ExecutionTrace) -> List[str]:
    failing = []
    for e in _tool_results(trace):
        result = e.result
        status_val = None
        if isinstance(result, dict):
            status_val = str(result.get("status", "")).lower()
            if "eligible" in result and result.get("eligible") is False:
                failing.append(e.tool_name)
                continue
        if status_val in _FAILURE_STATUS_VALUES:
            failing.append(e.tool_name)
    return failing


class TaskSuccessEvaluator(BaseEvaluator):
    """Did the agent achieve the configured expected outcome?"""

    name = "task_success"

    def evaluate(self, trace: ExecutionTrace, agent_config: Any, test_case: Any) -> EvaluationCheck:
        if trace.error:
            return self._check(False, 0.0, f"Run did not complete successfully: {trace.error}", {"run_error": trace.error})

        # Canonical field first, then the legacy alias.
        expected_outcome = getattr(test_case, "expected_outcome", None)
        expected_contains = expected_outcome or getattr(test_case, "expected_outcome_contains", None)
        expected_success = getattr(test_case, "expected_success", None)

        final = final_response_text(trace)

        if expected_contains:
            if expected_contains.lower() in final.lower():
                return self._check(True, 1.0, "Final response matched the expected outcome.",
                                    {"expected_outcome": expected_contains})
            return self._check(False, 0.0, f"Final response did not contain expected text: '{expected_contains}'.",
                                {"expected_outcome": expected_contains, "final_response": final})

        if expected_success is not None:
            tool_failures = _any_tool_result_indicates_failure(trace)
            actual_success = not tool_failures and _claims_success(final)
            if actual_success == expected_success:
                return self._check(True, 1.0, "Task outcome matched the expected success state.",
                                    {"expected_success": expected_success, "actual_success": actual_success})
            return self._check(False, 0.0, "Task outcome did not match the expected success state.",
                                {"expected_success": expected_success, "actual_success": actual_success,
                                 "failing_tools": tool_failures})

        # No explicit expectation configured — fall back to "did it complete cleanly with a response"
        if final:
            return self._check(True, 1.0, "Run completed with a final response (no explicit outcome expectation configured).",
                                {"skipped_explicit_check": True})
        return self._check(False, 0.0, "Run produced no final response.", {})


class OutcomeConsistencyEvaluator(BaseEvaluator):
    """Detect hallucinated success: agent claims success despite tool failures/errors."""

    name = "outcome_consistency"

    def evaluate(self, trace: ExecutionTrace, agent_config: Any, test_case: Any) -> EvaluationCheck:
        final = final_response_text(trace)
        if not final:
            return self._check(True, 1.0, "No final response to check for consistency.", {"skipped": True})

        tool_errors = [e.tool_name for e in trace.events if isinstance(e, ToolErrorEvent)]
        failing_results = _any_tool_result_indicates_failure(trace)
        claims_success = _claims_success(final)

        problems = tool_errors + failing_results

        if problems and claims_success:
            return self._check(
                False, 0.0,
                f"Final response claims success but these tools failed/were denied: {sorted(set(problems))}.",
                {"failing_tools": sorted(set(problems)), "final_response": final},
            )

        return self._check(True, 1.0, "Final response is consistent with tool outcomes.",
                            {"tool_errors": tool_errors, "failing_results": failing_results})
